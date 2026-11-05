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


def flexible_process(text, columns):
    output, errors = io.StringIO(), io.StringIO()
    stats = process_csv(
        io.BytesIO(text.encode()), CsvConfig(delimiter=";", columns=columns), output, errors
    )
    return stats, output.getvalue(), list(csv.DictReader(io.StringIO(errors.getvalue())))


def test_arbitrary_columns_types_rules_and_order_without_global_fields():
    stats, output, errors = flexible_process(
        'Компания;Количество;Стоимость;Описание;Лишнее\n ООО Тест ;+002;"-12,50";  текст  ;ignored\n',
        [
            {"source": "Стоимость", "target": "сумма", "type": "decimal"},
            {"source": "Компания", "target": "поставщик", "required": True},
            {"source": "Количество", "target": "остаток", "type": "integer", "min_value": 0},
            {"source": "Описание", "target": "комментарий", "trim": False},
        ],
    )
    assert stats == {"total_rows": 1, "successful_rows": 1, "failed_rows": 0}
    rows = list(csv.DictReader(io.StringIO(output)))
    assert rows == [
        {"сумма": "-12.50", "поставщик": "ООО Тест", "остаток": "2", "комментарий": "  текст  "}
    ]
    assert list(rows[0]) == ["сумма", "поставщик", "остаток", "комментарий"]
    assert errors == []


def test_optional_numeric_cells_bounds_and_required_are_per_column():
    stats, output, errors = flexible_process(
        "A;B;C\n;-3;ok\n4;0;\n5;6;ok\n",
        [
            {"source": "A", "target": "optional", "type": "integer"},
            {"source": "B", "target": "bounded", "type": "decimal", "max_value": 5},
            {"source": "C", "target": "required", "required": True},
        ],
    )
    assert stats == {"total_rows": 3, "successful_rows": 1, "failed_rows": 2}
    assert list(csv.DictReader(io.StringIO(output))) == [
        {"optional": "", "bounded": "-3", "required": "ok"}
    ]
    assert "required" in errors[0]["error"]
    assert "bounded" in errors[1]["error"]


def test_optional_value_still_requires_the_selected_source_header():
    with pytest.raises(CsvFileError, match="отсутствуют колонки"):
        flexible_process("A\nvalue\n", [{"source": "B", "target": "optional"}])
