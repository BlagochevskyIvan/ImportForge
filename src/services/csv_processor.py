import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation
from typing import BinaryIO, TextIO

from src.schemas.import_config import CsvColumn, CsvConfig


class CsvFileError(ValueError):
    """The whole file cannot be processed with the saved configuration."""


def validate_headers(headers: list[str] | None, config: CsvConfig) -> None:
    if not headers:
        raise CsvFileError("В CSV отсутствует строка заголовков.")
    if any(not header.strip() or "\x00" in header for header in headers):
        raise CsvFileError("Названия колонок не должны быть пустыми или содержать NULL")
    if len(headers) != len(set(headers)):
        raise CsvFileError("В CSV повторяются названия колонок")
    missing = sorted({column.source for column in config.columns} - set(headers))
    if missing:
        raise CsvFileError("В CSV отсутствуют колонки: " + ", ".join(missing))


def normalize_value(value: str, column: CsvColumn) -> str:
    if "\x00" in value:
        raise ValueError("значение не должно содержать NUL")
    value = value.strip() if column.trim else value
    if not value:
        if column.required:
            raise ValueError("значение не должно быть пустым")
        return ""
    if column.type == "text":
        return value
    if column.type == "integer":
        if not re.fullmatch(r"[+-]?[0-9]+", value):
            raise ValueError("ожидается целое число")
    elif not re.fullmatch(r"[+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)", value):
        raise ValueError("ожидается десятичное число")
    try:
        number = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("некорректное число") from exc
    if not number.is_finite():
        raise ValueError("число должно быть конечным")
    if column.min_value is not None and number < column.min_value:
        raise ValueError(f"значение меньше {column.min_value}")
    if column.max_value is not None and number > column.max_value:
        raise ValueError(f"значение больше {column.max_value}")
    return format(number, "f") if column.type == "decimal" else format(number, ".0f")


def map_and_validate_row(row: dict[str, str], config: CsvConfig) -> tuple[dict, list[str]]:
    mapped, errors = {}, []
    for column in config.columns:
        try:
            mapped[column.target] = normalize_value(row[column.source], column)
        except ValueError as exc:
            errors.append(f"{column.target}: {exc}")
    return mapped, errors


def process_csv(
    source: BinaryIO, config: CsvConfig, result_file: TextIO, errors_file: TextIO
) -> dict[str, int]:
    """Write valid records and a row error report; file errors invalidate both outputs."""
    encoding = "utf-8-sig" if config.encoding == "utf-8" else config.encoding
    text_file = io.TextIOWrapper(source, encoding=encoding, newline="")
    stats = {"total_rows": 0, "successful_rows": 0, "failed_rows": 0}
    try:
        reader = csv.DictReader(text_file, delimiter=config.delimiter, strict=True)
        validate_headers(reader.fieldnames, config)
        writer = csv.DictWriter(
            result_file, fieldnames=[column.target for column in config.columns]
        )
        error_writer = csv.DictWriter(
            errors_file, fieldnames=["record_number", "line_number", "error", "source_data"]
        )
        writer.writeheader()
        error_writer.writeheader()
        for row in reader:
            stats["total_rows"] += 1
            if None in row or any(value is None for value in row.values()):
                errors = ["Число значений в записи не совпадает с числом колонок."]
            else:
                mapped, errors = map_and_validate_row(row, config)
            if errors:
                stats["failed_rows"] += 1
                error_writer.writerow(
                    {
                        "record_number": stats["total_rows"],
                        "line_number": reader.line_num,
                        "error": "; ".join(errors),
                        "source_data": json.dumps(row, ensure_ascii=False),
                    }
                )
            else:
                stats["successful_rows"] += 1
                writer.writerow(mapped)
        if stats["total_rows"] == 0:
            raise CsvFileError("CSV содержит заголовки, но не содержит записей.")
        return stats
    except UnicodeError as exc:
        raise CsvFileError(f"Файл не удалось прочитать в кодировке {config.encoding}.") from exc
    except csv.Error as exc:
        raise CsvFileError(f"Некорректная структура CSV: {exc}") from exc
    finally:
        text_file.detach()
