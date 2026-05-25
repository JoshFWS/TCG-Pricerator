"""SQLite persistence layer via stdlib sqlite3."""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Generator

from pricerator import config

_DB_PATH = config.data_dir() / "pricerator.db"

# Re-evaluate db path lazily so tests can override PRICERATOR_DATA before import.
def _db_path():
    return config.data_dir() / "pricerator.db"


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(_db_path())
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS card (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                name             TEXT    NOT NULL,
                set_code         TEXT    NOT NULL,
                collector_number TEXT    NOT NULL,
                foil_type        TEXT    NOT NULL DEFAULT 'nonfoil',
                language         TEXT    NOT NULL DEFAULT 'English',
                condition        TEXT    NOT NULL DEFAULT 'Near Mint',
                quantity         INTEGER NOT NULL DEFAULT 1,
                scryfall_id      TEXT,
                image_url        TEXT,
                imported_at      REAL    NOT NULL,
                UNIQUE(set_code, collector_number, foil_type, language, condition)
            );

            CREATE TABLE IF NOT EXISTS price_snapshot (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id         INTEGER NOT NULL REFERENCES card(id) ON DELETE CASCADE,
                price_usd_cents INTEGER,
                fetched_at      REAL    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshot_card ON price_snapshot(card_id, fetched_at DESC);
        """)


# ---------------------------------------------------------------------------
# Card operations
# ---------------------------------------------------------------------------

def upsert_cards(cards: list[dict]) -> int:
    """Insert or update cards. Returns count of new rows inserted."""
    now = time.time()
    inserted = 0
    with _conn() as con:
        for c in cards:
            cur = con.execute("""
                INSERT INTO card(name, set_code, collector_number, foil_type, language, condition, quantity, imported_at)
                VALUES (:name, :set_code, :collector_number, :foil_type, :language, :condition, :quantity, :now)
                ON CONFLICT(set_code, collector_number, foil_type, language, condition)
                DO UPDATE SET quantity=excluded.quantity, name=excluded.name, imported_at=excluded.imported_at
            """, {**c, "now": now})
            if cur.lastrowid and cur.rowcount == 1:
                inserted += 1
    return inserted


def all_cards() -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute("SELECT * FROM card ORDER BY name").fetchall()


def card_by_id(card_id: int) -> sqlite3.Row | None:
    with _conn() as con:
        return con.execute("SELECT * FROM card WHERE id=?", (card_id,)).fetchone()


def set_scryfall_match(card_id: int, scryfall_id: str, image_url: str | None) -> None:
    with _conn() as con:
        con.execute(
            "UPDATE card SET scryfall_id=?, image_url=? WHERE id=?",
            (scryfall_id, image_url, card_id),
        )


def cards_with_latest_price() -> list[sqlite3.Row]:
    """Returns all cards joined with their most recent price snapshot."""
    with _conn() as con:
        return con.execute("""
            SELECT c.*,
                   s.price_usd_cents AS latest_price_cents,
                   s.fetched_at      AS latest_fetched_at
            FROM card c
            LEFT JOIN price_snapshot s ON s.id = (
                SELECT id FROM price_snapshot WHERE card_id = c.id ORDER BY fetched_at DESC LIMIT 1
            )
            ORDER BY c.name
        """).fetchall()


def delete_all_cards() -> None:
    with _conn() as con:
        con.execute("DELETE FROM card")


# ---------------------------------------------------------------------------
# Price snapshot operations
# ---------------------------------------------------------------------------

def insert_snapshots(snapshots: list[dict]) -> None:
    with _conn() as con:
        con.executemany(
            "INSERT INTO price_snapshot(card_id, price_usd_cents, fetched_at) VALUES(:card_id, :price_usd_cents, :fetched_at)",
            snapshots,
        )


def recent_snapshots(card_id: int, limit: int = 30) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM price_snapshot WHERE card_id=? ORDER BY fetched_at DESC LIMIT ?",
            (card_id, limit),
        ).fetchall()


def previous_latest_prices() -> dict[int, int | None]:
    """Snapshot of card_id → latest price BEFORE inserting new snapshots."""
    with _conn() as con:
        rows = con.execute("""
            SELECT card_id, price_usd_cents
            FROM price_snapshot
            WHERE id IN (
                SELECT MAX(id) FROM price_snapshot GROUP BY card_id
            )
        """).fetchall()
    return {r["card_id"]: r["price_usd_cents"] for r in rows}


def prune_snapshots(keep: int = 30) -> None:
    """Delete all but the most recent `keep` snapshots per card."""
    with _conn() as con:
        con.execute("""
            DELETE FROM price_snapshot
            WHERE id NOT IN (
                SELECT id FROM price_snapshot p2
                WHERE p2.card_id = price_snapshot.card_id
                ORDER BY fetched_at DESC LIMIT ?
            )
        """, (keep,))
