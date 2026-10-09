"""Optional: announce new aid on a Telegram channel through the free Bot API.

Turned on by setting TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (e.g. "@mi_canal").
"""
import datetime as dt
import html
import json
import os
import time
import urllib.request

from . import topics
from .site import Item, deadline_text, place_line

RECENT_DAYS = 2  # only announce what appeared in the last days, never an old backlog
MAX_PER_RUN = 25


def configured() -> bool:
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def message(item: Item, today: dt.date) -> str:
    head, detail = deadline_text(item, today)
    topic = topics.BY_SLUG[item.topics[0]].label
    return (f"<b>{html.escape(place_line(item))}</b> · {html.escape(topic)}\n"
            f"{html.escape(item.title)}\n{html.escape(head)}: {html.escape(detail)}\n{item.official_url}")


def send(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    payload = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text, "parse_mode": "HTML",
               "disable_web_page_preview": True}
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def notify(db: dict, items: list[Item], today: dt.date, log=print) -> int:
    """Post recent, still-useful announcements once each. Returns how many were sent."""
    if not configured():
        log("Telegram sin configurar: no se envían avisos.")
        return 0
    useful = {i.code: i for i in items if i.status in ("abierta", "proxima", "sin_fecha")}
    pending = [code for code, call in db["calls"].items()
               if code in useful and not call.get("notified")
               and (today - dt.date.fromisoformat(call["first_seen"])).days <= RECENT_DAYS]
    sent = 0
    for code in sorted(pending)[:MAX_PER_RUN]:
        send(message(useful[code], today))
        db["calls"][code]["notified"] = True
        sent += 1
        time.sleep(1.1)  # Telegram allows about one message per second in a channel
    log(f"Telegram: {sent} avisos enviados.")
    return sent
