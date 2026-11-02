import csv
import io
import json
import re
from decimal import Decimal, InvalidOperation
from typing import BinaryIO, TextIO

from src.schemas.import_config import CsvConfig

TARGET_COLUMNS = ["sku", "name", "price"]


class CsvFileError(ValueError):
    """The whole file cannot be processed with the saved configuration."""


def validate_headers(headers: list[str] | None, mapping: dict[str, str]) -> None:
    if not headers:
        raise CsvFileError("В CSV отсутствует строка заголовков.")
    if any(not header.strip() or "\x00" in header for header in headers):
        raise CsvFileError("Названия колонок не должны быть пустыми или содержать NULL")
    if len(headers) != len(set(headers)):
        raise CsvFileError("В CSV повторяются названия колонок")
    missing = [column for column in mapping if column not in headers]
    if missing:
        raise CsvFileError("В CSV отсутствуют колонки: " + ", ".join(missing))


# преобразуем в типовые поля sku name price
def map_row(row: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    return {target: row[source].strip() for source, target in mapping.items()}


# Проверяем и разбиваем десятичную цену
def _parse_price(value: str) -> Decimal:
    if not re.fullmatch(r"[+-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)", value):
        raise ValueError("price: ожидается десятичное число.")
    try:
        price = Decimal(value.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("price: ожидается десятичное число.") from exc
    if not price.is_finite() or price < 0:
        raise ValueError("price: цена должна быть конечным неотрицательным числом.")
    return price


def validate_row(row: dict[str, str]) -> list[str]:
    errors = []
    for field in ["sku", "name"]:
        if not row[field]:
            errors.append(f"{field}: значение не должно быть пустым.")
    if any("\x00" in value for value in row.values()):
        errors.append("Значения не должны содержать NUL.")
    try:
        _parse_price(row["price"])
    except ValueError as exc:
        errors.append(str(exc))
    return errors


def process_csv(
    # source эт открытый бинарный поток исходника файла
    source: BinaryIO,
    config: CsvConfig,
    result_file: TextIO,
    errors_file: TextIO,
) -> dict[str, int]:
    """Caller owns streams; file errors invalidate partially written output.

    record_number counts data records. line_number is the final physical line
    of the record, since quoted CSV fields can contain newlines.
    """
    encoding = "utf-8-sig" if config.encoding == "utf-8" else config.encoding
    text_file = io.TextIOWrapper(source, encoding=encoding, newline="")
    stats = {"total_rows": 0, "successful_rows": 0, "failed_rows": 0}
    try:
        reader = csv.DictReader(text_file, delimiter=config.delimiter, strict=True)
        validate_headers(reader.fieldnames, config.column_mapping)
        writer = csv.DictWriter(result_file, fieldnames=TARGET_COLUMNS)
        error_writer = csv.DictWriter(
            errors_file, fieldnames=["record_number", "line_number", "error", "source_data"]
        )
        writer.writeheader()
        error_writer.writeheader()
        for row in reader:
            stats["total_rows"] += 1
            errors = []
            if None in row or any(value is None for value in row.values()):
                errors.append("Число значений в записи не совпадает с числом колонок.")
            else:
                mapped = map_row(row, config.column_mapping)
                errors = validate_row(mapped)
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
                mapped["price"] = format(_parse_price(mapped["price"]), "f")
                writer.writerow(mapped)
                stats["successful_rows"] += 1
        if stats["total_rows"] == 0:
            raise CsvFileError("CSV содержит заголовки, но не содержит записей.")
        return stats
    except UnicodeError as exc:
        raise CsvFileError(f"Файл не удалось прочитать в кодировке {config.encoding}.") from exc
    except csv.Error as exc:
        raise CsvFileError(f"Некорректная структура CSV: {exc}") from exc
    finally:
        # Leave the caller's binary stream open when disposing of the text wrapper.
        text_file.detach()
