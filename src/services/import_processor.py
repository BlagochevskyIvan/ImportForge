import logging
from datetime import UTC, datetime
from tempfile import TemporaryFile
from uuid import UUID

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from src.db import config_crud, file_crud, run_crud
from src.db.models import ImportRun
from src.schemas.import_config import CsvConfig
from src.schemas.imports import ImportRunRead, SourceFileRead
from src.services.csv_processor import CsvFileError, process_csv
from src.services.s3_storage import S3Storage

logger = logging.getLogger(__name__)


class SourceFileNotFoundError(ValueError):
    pass


class ProcessingInProgressError(ValueError):
    pass


class ImportConfigurationError(ValueError):
    pass


class ConfigurationNotFoundError(ValueError):
    pass


def cleanup_artifacts(storage: S3Storage, keys: list[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except (ClientError, BotoCoreError):
            logger.exception("Failed to clean processing artifact: key=%s", key)


def build_artifacts(storage, source_key, config, result_key, errors_key):
    with (
        TemporaryFile(mode="w+b") as source,
        TemporaryFile(mode="w+", encoding="utf-8-sig", newline="") as result_file,
        TemporaryFile(mode="w+", encoding="utf-8-sig", newline="") as errors_file,
    ):
        storage.download(source_key, source)
        source.seek(0)
        stats = process_csv(source, config, result_file, errors_file)
        for key, stream in [(result_key, result_file), (errors_key, errors_file)]:
            stream.flush()
            stream.buffer.seek(0)
            storage.upload(stream.buffer, key)
        return {**stats, "result_key": result_key, "errors_key": errors_key}


async def create_import_run(
    file_id: UUID,
    *,
    user_id: int,
    session_factory,
    config_id: int | None = None,
    new_run: bool = True,
):
    """Snapshot settings and serialize start requests on the source file row."""
    async with session_factory() as session, session.begin():
        source = await file_crud.get_file_by_id(session, file_id, user_id=user_id, for_update=True)
        if source is None:
            raise SourceFileNotFoundError("File not found")
        active = await session.scalar(
            select(ImportRun.id).where(
                ImportRun.source_file_id == file_id, ImportRun.status.in_(run_crud.ACTIVE_STATUSES)
            )
        )
        if active is not None:
            raise ProcessingInProgressError("File processing is already in progress")
        latest = (await run_crud.latest_runs(session, [file_id], user_id=user_id)).get(file_id)
        # Preserve the old endpoint's completed-file response when no explicit new run is requested.
        if (
            not new_run
            and config_id is None
            and latest is not None
            and latest.status == "completed"
        ):
            return source, latest, False
        config_name, config_data = "Снимок файла", source.config_data
        if config_id is not None:
            selected = await config_crud.get_config(
                session, source.supplier_id, user_id=user_id, config_id=config_id
            )
            if selected is None:
                raise ConfigurationNotFoundError("Configuration not found")
            config_name, config_data = selected.name, selected.config_data
        if config_data is None:
            raise ImportConfigurationError("Choose a configuration before processing")
        try:
            snapshot = CsvConfig.model_validate(config_data).model_dump(mode="json")
        except ValidationError as exc:
            raise ImportConfigurationError("The saved configuration is invalid") from exc
        run = ImportRun(
            source_file_id=file_id,
            config_id=config_id,
            config_name=config_name,
            config_data=snapshot,
            # Record acceptance after acquiring the lock, not the transaction's start time.
            created_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        return source, run, True


async def execute_import_run(
    run_id: UUID, *, file_id: UUID, user_id: int, storage: S3Storage, session_factory
) -> ImportRunRead:
    """Execute one recorded run synchronously; no transaction spans file processing."""
    async with session_factory() as session, session.begin():
        run = await session.scalar(
            run_crud.owned_runs(user_id)
            .where(ImportRun.id == run_id, ImportRun.source_file_id == file_id)
            .with_for_update(of=ImportRun)
        )
        if run is None:
            raise SourceFileNotFoundError("File not found")
        if run.status in ("completed", "failed"):
            return ImportRunRead.model_validate(run)
        if run.status != "queued":
            raise ProcessingInProgressError("File processing is already in progress")
        source = await file_crud.get_file_by_id(session, file_id, user_id=user_id)
        source_key = source.object_key
        snapshot = run.config_data
        run.status = "processing"
        run.started_at = datetime.now(UTC)
        run.attempt_count += 1

    prefix = f"processed/{file_id}/{run_id}"
    keys = [f"{prefix}/result.csv", f"{prefix}/errors.csv"]
    metadata, error_code, error = None, None, None
    try:
        config = CsvConfig.model_validate(snapshot)
        metadata = await run_in_threadpool(
            build_artifacts, storage, source_key, config, keys[0], keys[1]
        )
    except (CsvFileError, ValidationError) as exc:
        error_code, error = "invalid_csv", str(exc)
    except (ClientError, BotoCoreError, S3UploadFailedError):
        logger.exception("Storage failed during processing: run_id=%s", run_id)
        error_code, error = (
            "storage_error",
            "Хранилище файлов недоступно. Повторите обработку позже.",
        )
    except Exception:
        logger.exception("CSV processing failed: run_id=%s", run_id)
        error_code, error = "processing_error", "Не удалось завершить обработку. Повторите попытку."

    if error is not None:
        await run_in_threadpool(cleanup_artifacts, storage, keys)
    # Keep database commit failures outside the artifact-error handler: commit may have succeeded.
    async with session_factory() as session, session.begin():
        run = await run_crud.get_run(session, run_id, file_id=file_id, user_id=user_id)
        run.status = "completed" if error is None else "failed"
        run.processing_result = metadata if error is None else {"error": error}
        run.error_code, run.error_message = error_code, error
        run.finished_at = datetime.now(UTC)
        result = ImportRunRead.model_validate(run)
    return result


async def process_import(
    file_id: UUID,
    *,
    user_id: int,
    storage: S3Storage,
    session_factory,
    config_id: int | None = None,
    new_run: bool = False,
) -> SourceFileRead:
    source, run, created = await create_import_run(
        file_id,
        user_id=user_id,
        session_factory=session_factory,
        config_id=config_id,
        new_run=new_run,
    )
    result = (
        await execute_import_run(
            run.id,
            file_id=file_id,
            user_id=user_id,
            storage=storage,
            session_factory=session_factory,
        )
        if created
        else ImportRunRead.model_validate(run)
    )
    return SourceFileRead.from_file(source, result)
