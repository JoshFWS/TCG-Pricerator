"""Scryfall bulk-data downloader with streaming ijson parser."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Iterator

import ijson
import requests

from pricerator import config

log = logging.getLogger(__name__)

_API_BASE = "https://api.scryfall.com"
_MIN_REQUEST_GAP = 0.11  # 110 ms between API calls (Scryfall rate-limit courtesy)
_last_api_call: float = 0.0

_HEADERS = {
    "User-Agent": "TCGPricerator/1.0 (github.com/user/tcg-pricerator)",
    "Accept": "application/json",
}


def _throttled_get(url: str, stream: bool = False, **kwargs) -> requests.Response:
    global _last_api_call
    if "api.scryfall.com" in url:
        gap = time.monotonic() - _last_api_call
        if gap < _MIN_REQUEST_GAP:
            time.sleep(_MIN_REQUEST_GAP - gap)
        _last_api_call = time.monotonic()
    resp = requests.get(url, headers=_HEADERS, stream=stream, timeout=60, **kwargs)
    resp.raise_for_status()
    return resp


def _bulk_download_url() -> tuple[str, str]:
    """Returns (download_url, updated_at) for the default_cards bulk file."""
    data = _throttled_get(f"{_API_BASE}/bulk-data").json()
    entry = next((e for e in data["data"] if e["type"] == "default_cards"), None)
    if entry is None:
        raise RuntimeError("Scryfall bulk-data has no default_cards entry")
    return entry["download_uri"], entry.get("updated_at", "")


def stream_default_cards(
    on_card: Callable[[dict], None],
    progress_cb: Callable[[int], None] | None = None,
) -> None:
    """Stream the Scryfall bulk default_cards JSON, calling on_card for each object.

    Uses an ETag cache file so repeated runs skip re-downloading an unchanged file.
    progress_cb is called with bytes downloaded so far (if provided).
    """
    cache_dir = config.data_dir() / "cache"
    cache_dir.mkdir(exist_ok=True)
    etag_file = cache_dir / "bulk_etag.txt"
    bulk_file = cache_dir / "default_cards.json"

    download_url, _ = _bulk_download_url()

    stored_etag = etag_file.read_text().strip() if etag_file.exists() else ""
    head = requests.head(download_url, headers=_HEADERS, timeout=30)
    server_etag = head.headers.get("ETag", "").strip('"')

    if stored_etag and server_etag and stored_etag == server_etag and bulk_file.exists():
        log.info("Scryfall bulk data unchanged (ETag match), using cached file")
        _stream_from_file(bulk_file, on_card, progress_cb)
        return

    log.info("Downloading Scryfall bulk data from %s", download_url)
    resp = requests.get(download_url, headers=_HEADERS, stream=True, timeout=300)
    resp.raise_for_status()

    downloaded = 0
    with open(bulk_file, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            fh.write(chunk)
            downloaded += len(chunk)
            if progress_cb:
                progress_cb(downloaded)

    new_etag = resp.headers.get("ETag", "").strip('"')
    if new_etag:
        etag_file.write_text(new_etag)

    _stream_from_file(bulk_file, on_card, progress_cb=None)


def _stream_from_file(
    path: Path,
    on_card: Callable[[dict], None],
    progress_cb: Callable[[int] | None] = None,
) -> None:
    with open(path, "rb") as fh:
        for obj in ijson.items(fh, "item"):
            on_card(obj)


def fetch_single_card(set_code: str, collector_number: str) -> dict:
    """Per-card API call for the detail screen refresh."""
    url = f"{_API_BASE}/cards/{set_code.lower()}/{collector_number}"
    return _throttled_get(url).json()
