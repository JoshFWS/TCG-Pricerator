"""Moxfield 'haves' CSV parser — port of MoxfieldCsvParser.kt."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import IO


@dataclass
class ParsedCard:
    name: str
    set_code: str
    collector_number: str
    foil_type: str          # "nonfoil" | "foil" | "etched"
    language: str
    condition: str
    quantity: int


@dataclass
class SkippedRow:
    row_number: int
    reason: str


@dataclass
class ParsedCollection:
    cards: list[ParsedCard]
    skipped: list[SkippedRow]


def _foil_from_csv(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    if v == "foil":
        return "foil"
    if v == "etched":
        return "etched"
    return "nonfoil"


def parse(stream: IO[bytes] | IO[str]) -> ParsedCollection:
    """Parse a Moxfield haves CSV.  Column order is detected from the header."""
    if isinstance(stream, (bytes, bytearray)):
        stream = io.BytesIO(stream)

    raw_bytes = stream.read()
    if isinstance(raw_bytes, bytes):
        text = raw_bytes.decode("utf-8-sig")  # strips BOM if present
    else:
        text = raw_bytes

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return ParsedCollection([], [])

    header = [h.strip().lower() for h in rows[0]]

    def col(name: str) -> int:
        try:
            return header.index(name.lower())
        except ValueError:
            return -1

    count_col = col("count")
    name_col = col("name")
    edition_col = col("edition")
    condition_col = col("condition")
    language_col = col("language")
    foil_col = col("foil")
    collector_col = col("collector number")

    missing = [n for n, c in [
        ("Count", count_col), ("Name", name_col), ("Edition", edition_col),
        ("Condition", condition_col), ("Language", language_col),
        ("Foil", foil_col), ("Collector Number", collector_col),
    ] if c < 0]
    if missing:
        raise ValueError(f"Missing required CSV columns: {', '.join(missing)}")

    def get(row: list[str], idx: int) -> str:
        return row[idx].strip() if idx < len(row) else ""

    cards: list[ParsedCard] = []
    skipped: list[SkippedRow] = []

    for offset, row in enumerate(rows[1:], start=1):
        row_number = offset + 1  # 1-indexed, +1 for header
        name = get(row, name_col)
        edition = get(row, edition_col).lower()
        collector = get(row, collector_col)

        if not name or not edition or not collector:
            skipped.append(SkippedRow(row_number, "Empty name/edition/collector number"))
            continue

        count_str = get(row, count_col)
        quantity = int(count_str) if count_str.isdigit() else None
        if quantity is None or quantity <= 0:
            skipped.append(SkippedRow(row_number, f"Invalid Count: '{count_str}'"))
            continue

        cards.append(ParsedCard(
            name=name,
            set_code=edition,
            collector_number=collector,
            foil_type=_foil_from_csv(get(row, foil_col)),
            language=get(row, language_col) or "English",
            condition=get(row, condition_col) or "Near Mint",
            quantity=quantity,
        ))

    return ParsedCollection(cards, skipped)
