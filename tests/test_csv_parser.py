"""Port of MoxfieldCsvParserTest."""
import io
import pytest
from pricerator.csv_parser import parse


def _parse(csv_text: str):
    return parse(io.BytesIO(csv_text.strip().encode()))


HEADER = '"Count","Tradelist Count","Name","Edition","Condition","Language","Foil","Tags","Last Modified","Collector Number","Alter","Proxy","Purchase Price"'


def test_parses_standard_rows():
    csv = f"""{HEADER}
"1","1","A Little Chat","snc","Near Mint","English","","","2023-05-07 21:00:09.060000","47","False","False",""
"4","4","Aarakocra Sneak","clb","Near Mint","English","","","2025-02-22 22:38:53.143000","54","False","False",""
"""
    result = _parse(csv)
    assert len(result.cards) == 2
    assert result.cards[0].name == "A Little Chat"
    assert result.cards[0].set_code == "snc"
    assert result.cards[0].quantity == 1
    assert result.cards[1].quantity == 4


def test_parses_foil_and_etched():
    csv = f"""{HEADER}
"1","1","Abrade","fdn","Near Mint","English","foil","","2024-11-12 01:55:33.730000","327","False","False",""
"1","1","Atla Palani, Nest Tender","2x2","Near Mint","English","etched","","2025-02-08 21:03:39.087000","476","False","False",""
"""
    result = _parse(csv)
    assert [c.foil_type for c in result.cards] == ["foil", "etched"]


def test_parses_the_list_collector_numbers():
    csv = f"""{HEADER}
"1","1","Abrupt Decay","plst","Near Mint","English","","","2023-05-07 21:00:18.353000","GK1-57","False","False",""
"""
    result = _parse(csv)
    assert len(result.cards) == 1
    assert result.cards[0].set_code == "plst"
    assert result.cards[0].collector_number == "GK1-57"


def test_skips_rows_with_invalid_count():
    csv = f"""{HEADER}
"abc","1","Bad Row","snc","Near Mint","English","","","2023-05-07 21:00:09.060000","47","False","False",""
"1","1","Good Row","snc","Near Mint","English","","","2023-05-07 21:00:09.060000","48","False","False",""
"""
    result = _parse(csv)
    assert len(result.cards) == 1
    assert result.cards[0].name == "Good Row"
    assert len(result.skipped) == 1
    assert result.skipped[0].row_number == 2


def test_resilient_to_reordered_columns():
    reordered = '"Name","Count","Tradelist Count","Edition","Condition","Language","Foil","Tags","Last Modified","Collector Number","Alter","Proxy","Purchase Price"'
    csv = f"""{reordered}
"A Little Chat","1","1","snc","Near Mint","English","","","2023-05-07 21:00:09.060000","47","False","False",""
"""
    result = _parse(csv)
    assert len(result.cards) == 1
    assert result.cards[0].name == "A Little Chat"
    assert result.cards[0].quantity == 1


def test_lowercases_set_codes():
    csv = f"""{HEADER}
"1","1","Big Daddy","SNC","Near Mint","English","","","2023-05-07 21:00:09.060000","47","False","False",""
"""
    result = _parse(csv)
    assert result.cards[0].set_code == "snc"


def test_empty_input_returns_empty():
    result = parse(io.BytesIO(b""))
    assert result.cards == []
    assert result.skipped == []


def test_nonfoil_when_foil_column_blank():
    csv = f"""{HEADER}
"1","1","Lightning Bolt","lea","Near Mint","English","","","2023-01-01 00:00:00.000000","61","False","False",""
"""
    result = _parse(csv)
    assert result.cards[0].foil_type == "nonfoil"
