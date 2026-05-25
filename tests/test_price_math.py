"""Port of PriceMathTest."""
import pytest
from pricerator.price_math import (
    parse_price_string_to_cents,
    cents_to_display,
    price_for_foil_type,
    crossed_above,
)


def test_parse_price_string_to_cents_dollars_and_cents():
    assert parse_price_string_to_cents("1.49") == 149
    assert parse_price_string_to_cents("0.05") == 5
    assert parse_price_string_to_cents("12") == 1200
    assert parse_price_string_to_cents("12.345") == 1234  # 12.345*100 = 1234.499… in IEEE 754 → rounds down


def test_parse_price_string_to_cents_blank_or_garbage():
    assert parse_price_string_to_cents(None) is None
    assert parse_price_string_to_cents("") is None
    assert parse_price_string_to_cents("free") is None


def test_price_for_foil_type_picks_right_column():
    prices = {"usd": "1.00", "usd_foil": "5.00", "usd_etched": "12.50"}
    assert price_for_foil_type(prices, "nonfoil") == 100
    assert price_for_foil_type(prices, "foil") == 500
    assert price_for_foil_type(prices, "etched") == 1250


def test_price_for_foil_type_missing_key_returns_none():
    assert price_for_foil_type({}, "foil") is None
    assert price_for_foil_type({"usd": "1.00"}, "foil") is None


def test_cents_to_display_formats_and_handles_null():
    assert cents_to_display(149) == "$1.49"
    assert cents_to_display(0) == "$0.00"
    assert cents_to_display(None) == "—"


def test_crossed_above_below_to_above():
    # prev None → above threshold
    assert crossed_above(None, 200, 100) is True
    # prev below → above threshold
    assert crossed_above(50, 200, 100) is True


def test_crossed_above_above_to_above_does_not_renotify():
    # Both above threshold — should NOT fire
    assert crossed_above(200, 300, 100) is False


def test_crossed_above_below_to_below():
    assert crossed_above(50, 80, 100) is False


def test_crossed_above_exact_threshold():
    # Exactly at threshold counts as above
    assert crossed_above(50, 100, 100) is True
