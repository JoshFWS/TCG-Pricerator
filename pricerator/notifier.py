"""Desktop notifications via plyer (Mac + Windows).  Falls back to log on failure."""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_APP_NAME = "TCG Pricerator"


def notify_above_threshold(card_names: list[str]) -> None:
    if not card_names:
        return
    count = len(card_names)
    title = f"TCG Pricerator — {count} card{'s' if count != 1 else ''} worth selling"
    if count <= 3:
        message = "\n".join(card_names)
    else:
        message = "\n".join(card_names[:3]) + f"\n…and {count - 3} more"
    _send(title, message)


def _send(title: str, message: str) -> None:
    try:
        from plyer import notification  # type: ignore
        notification.notify(
            title=title,
            message=message,
            app_name=_APP_NAME,
            timeout=10,
        )
    except Exception as exc:
        log.warning("Desktop notification failed (%s): %s — %s", type(exc).__name__, title, message)
