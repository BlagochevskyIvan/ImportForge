import logging
from tempfile import TemporaryFile
from uuid import UUID, uuid4

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from src.db import file_crud
from src.schemas.import_config import CsvConfig
from src.schemas.imports import SourceFileRead
from src.services.csv_processor import CsvFileError, process_csv
from src.services.s3_storage import S3Storage

logger = logging.getLogger(__name__)


class SourceFileNotFoundError(ValueError):
    pass


class ProcessingInProgressError(ValueError):
    pass


def cleanup_artifacts(storage: S3Storage, keys: list[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except (ClientError, BotoCoreError):
            logger.exception("Failed to clean processing artifact: key=%s", key)


# скакчивание исходника
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


async def process_import(
    file_id: UUID, *, user_id: int, storage: S3Storage, session_factory
) -> SourceFileRead:
    async with session_factory() as session, session.begin():
        source_file = await file_crud.get_file_by_id(
            session, file_id, user_id=user_id, for_update=True
        )
        if source_file is None:
            raise SourceFileNotFoundError("File not found")
        if source_file.status == "processing":
            raise ProcessingInProgressError("File processing is already in progress")
        if source_file.status == "completed":
            return SourceFileRead.model_validate(source_file)
        source_key = source_file.object_key
        config_data = source_file.config_data
        source_file.status = "processing"
        source_file.processing_result = None

    prefix = f"processed/{file_id}/{uuid4()}"
    keys = [f"{prefix}/result.csv", f"{prefix}/errors.csv"]
    try:
        if config_data is None:
            raise CsvFileError("У файла отсутствует сохранённый снимок конфига.")
        try:
            config = CsvConfig.model_validate(config_data)
        except ValidationError as exc:
            raise CsvFileError("Снимок конфига файла содержит недопустимые настройки.") from exc
        metadata = await run_in_threadpool(
            build_artifacts, storage, source_key, config, keys[0], keys[1]
        )
        async with session_factory() as session, session.begin():
            source_file = await file_crud.get_file_by_id(session, file_id, user_id=user_id)
            source_file.status = "completed"
            source_file.processing_result = metadata
            result = SourceFileRead.model_validate(source_file)
        return result
    except CsvFileError as exc:
        error = str(exc)
    except (ClientError, BotoCoreError, S3UploadFailedError):
        logger.exception("Storage failed during processing: file_id=%s", file_id)
        error = "Хранилище файлов недоступно. Повторите обработку позже."
    except Exception:
        logger.exception("CSV processing failed: file_id=%s", file_id)
        error = "Не удалось завершить обработку. Повторите попытку."

    await run_in_threadpool(cleanup_artifacts, storage, keys)
    async with session_factory() as session, session.begin():
        source_file = await file_crud.get_file_by_id(session, file_id, user_id=user_id)
        source_file.status = "failed"
        source_file.processing_result = {"error": error}
        result = SourceFileRead.model_validate(source_file)
    return result
