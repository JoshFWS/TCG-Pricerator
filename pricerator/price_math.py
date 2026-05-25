"""Price math utilities — port of PriceMath.kt."""
from __future__ import annotations


def parse_price_string_to_cents(raw: str | None) -> int | None:
    """'1.49' -> 149. Returns None when blank or unparseable."""
    if not raw or not raw.strip():
        return None
    try:
        return round(float(raw.strip()) * 100)
    except ValueError:
        return None


def cents_to_display(cents: int | None) -> str:
    if cents is None:
        return "—"
    return f"${cents / 100:.2f}"


def price_for_foil_type(prices: dict, foil_type: str) -> int | None:
    """Pick the right price column from a Scryfall prices dict."""
    if foil_type == "foil":
        return parse_price_string_to_cents(prices.get("usd_foil"))
    if foil_type == "etched":
        return parse_price_string_to_cents(prices.get("usd_etched"))
    return parse_price_string_to_cents(prices.get("usd"))


def crossed_above(prev_cents: int | None, current_cents: int, threshold_cents: int) -> bool:
    """True only on a below→above transition. Above→above never re-notifies."""
    was_below = prev_cents is None or prev_cents < threshold_cents
    now_above = current_cents >= threshold_cents
    return was_below and now_above
