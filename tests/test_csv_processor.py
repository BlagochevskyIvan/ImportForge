import csv
import io

import pytest

from src.schemas.import_config import CsvConfig
from src.services.csv_processor import CsvFileError, process_csv

MAPPING = {"Код": "sku", "Товар": "name", "Цена": "price"}


def process(content, *, encoding="utf-8", delimiter=";", mapping=None):
    source = io.BytesIO(content)
    result, errors = io.StringIO(newline=""), io.StringIO(newline="")
    stats = process_csv(
        source,
        CsvConfig(encoding=encoding, delimiter=delimiter, column_mapping=mapping or MAPPING),
        result,
        errors,
    )
    assert not source.closed
    return (
        stats,
        list(csv.DictReader(io.StringIO(result.getvalue()))),
        list(csv.DictReader(io.StringIO(errors.getvalue()))),
    )


@pytest.mark.parametrize(
    ("encoding", "delimiter"),
    [("utf-8", ";"), ("utf-8-sig", ","), ("cp1251", "|"), ("utf-8", "\t")],
)
def test_config_encoding_delimiter_and_mapping(encoding, delimiter):
    text = f'Цена{delimiter}Код{delimiter}Товар{delimiter}Лишнее\r\n"12,50"{delimiter} A-1 {delimiter}" Чайник{delimiter}чай "{delimiter}ignored\r\n'
    stats, rows, errors = process(text.encode(encoding), encoding=encoding, delimiter=delimiter)
    assert stats == {"total_rows": 1, "successful_rows": 1, "failed_rows": 0}
    assert rows == [{"sku": "A-1", "name": f"Чайник{delimiter}чай", "price": "12.50"}]
    assert list(rows[0]) == ["sku", "name", "price"]
    assert errors == []


def test_utf8_bom_multiline_fields_and_physical_line_numbers():
    text = 'Код;Товар;Цена\n1;"Чайник\nс крышкой";0\n2;Кружка;abc\n'
    stats, rows, errors = process(text.encode("utf-8-sig"))
    assert stats == {"total_rows": 2, "successful_rows": 1, "failed_rows": 1}
    assert rows[0]["name"] == "Чайник\nс крышкой"
    assert errors[0]["record_number"] == "2"
    assert errors[0]["line_number"] == "4"
    assert "price" in errors[0]["error"]
    assert "Кружка" in errors[0]["source_data"]


@pytest.mark.parametrize(
    "record",
    [
        ";Чай;1",
        "1; ;1",
        "1;Чай;-1",
        "1;Чай;NaN",
        "1;Чай;Infinity",
        "1;Чай;1e3",
        "1;Чай",
        "1;Чай;1;extra",
        "1;Ча\x00й;1",
    ],
)
def test_invalid_records_go_to_error_report(record):
    stats, rows, errors = process(f"Код;Товар;Цена\n{record}\n".encode())
    assert stats == {"total_rows": 1, "successful_rows": 0, "failed_rows": 1}
    assert rows == []
    assert len(errors) == 1 and errors[0]["error"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n\n",
        "Код;Товар;Цена\n",
        "Код;Товар\n1;Чай\n",
        "Код;Товар;Цена;Код\n1;Чай;1;2\n",
        "Код;;Цена\n1;Чай;1\n",
        'Код;Товар;Цена\n1;"Незакрытая кавычка;1\n',
    ],
)
def test_file_errors_stop_processing(text):
    with pytest.raises(CsvFileError):
        process(text.encode())


def test_wrong_encoding_fails_the_file():
    with pytest.raises(CsvFileError, match="кодировке"):
        process("Код;Товар;Цена\n1;Чай;1\n".encode("cp1251"))
