"""Core refresh logic: download Scryfall bulk data, update price snapshots, notify."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from pricerator import config, db, notifier, scryfall
from pricerator.price_math import crossed_above, price_for_foil_type

log = logging.getLogger(__name__)


@dataclass
class RefreshResult:
    priced: int
    unpriced: int
    unmatched: int
    newly_above: list[str]  # card names


def refresh_all_prices(progress_cb=None) -> RefreshResult:
    cards = db.all_cards()
    if not cards:
        return RefreshResult(0, 0, 0, [])

    # Snapshot previous-latest prices BEFORE inserting new ones.
    prev_latest = db.previous_latest_prices()

    # Index by (set_code, collector_number) for O(1) bulk lookup.
    by_key: dict[tuple[str, str], list] = {}
    for card in cards:
        key = (card["set_code"].lower(), card["collector_number"])
        by_key.setdefault(key, []).append(card)

    matched: dict[int, dict] = {}  # card_id -> scryfall card dict

    def on_card(dto: dict) -> None:
        key = (dto.get("set", "").lower(), dto.get("collector_number", ""))
        rows = by_key.get(key)
        if not rows:
            return
        for card in rows:
            cid = card["id"]
            if cid not in matched:
                matched[cid] = dto

    scryfall.stream_default_cards(on_card, progress_cb=progress_cb)

    settings = config.load()
    now = time.time()
    snapshots: list[dict] = []
    newly_above: list[str] = []
    priced = 0
    unpriced = 0

    for card in cards:
        cid = card["id"]
        dto = matched.get(cid)
        prices = dto.get("prices", {}) if dto else {}
        price_cents = price_for_foil_type(prices, card["foil_type"])
        snapshots.append({"card_id": cid, "price_usd_cents": price_cents, "fetched_at": now})

        if price_cents is not None:
            priced += 1
            threshold = settings.threshold_for(card["foil_type"])
            if crossed_above(prev_latest.get(cid), price_cents, threshold):
                newly_above.append(card["name"])
        else:
            unpriced += 1

        if dto and card["scryfall_id"] != dto.get("id"):
            image_url = (
                (dto.get("image_uris") or {}).get("normal")
                or next(
                    (f.get("image_uris", {}).get("normal") for f in dto.get("card_faces", []) if f.get("image_uris")),
                    None,
                )
            )
            db.set_scryfall_match(cid, dto["id"], image_url)

    db.insert_snapshots(snapshots)
    db.prune_snapshots(keep=30)

    settings.last_refreshed_at = now
    config.save(settings)

    if settings.notifications_enabled and newly_above:
        notifier.notify_above_threshold(newly_above)

    unmatched = len(cards) - len(matched)
    log.info("Refresh complete: %d priced, %d unpriced, %d unmatched, %d newly above threshold",
             priced, unpriced, unmatched, len(newly_above))
    return RefreshResult(priced, unpriced, unmatched, newly_above)
