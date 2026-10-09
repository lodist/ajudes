"""Local copy of the announcements: one JSON file that the daily job keeps up to date."""
import datetime as dt
import json
from pathlib import Path
from typing import Callable

from . import deadlines

DEFAULT_DAYS = 45  # each run re-reads what was registered in the last 45 days (catches corrections)
FORGET_AFTER_DAYS = 400  # drop announcements registered more than ~13 months ago
FORGET_CLOSED_AFTER_DAYS = 60  # ...or closed for more than two months
KEEP = ("codigoBDNS", "organo", "descripcion", "descripcionLeng", "fechaRecepcion", "fechaInicioSolicitud",
        "fechaFinSolicitud", "textInicio", "textFin", "presupuestoTotal", "sedeElectronica",
        "urlBasesReguladoras", "descripcionFinalidad", "tipoConvocatoria", "regiones", "tiposBeneficiarios")


def empty() -> dict:
    return {"updated": None, "calls": {}}


def load(path: Path) -> dict:
    if not path.exists():
        return empty()
    return json.loads(path.read_text(encoding="utf-8"))


def save(db: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(db, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def slim(detail: dict) -> dict:
    """Keep only what the site uses, so the data file stays small."""
    call = {key: detail.get(key) for key in KEEP}
    call["documentos"] = [{"id": d.get("id"), "nombre": d.get("nombreFic") or d.get("descripcion")}
                          for d in detail.get("documentos") or []]
    call["anuncios"] = [{"titulo": a.get("titulo"), "texto": a.get("texto"), "diario": a.get("desDiarioOficial"),
                         "fecha": a.get("datPublicacion"), "url": a.get("url")}
                        for a in detail.get("anuncios") or []]
    return call


def update(db: dict, search: Callable, detail: Callable, today: dt.date, lookback_days: int,
           log: Callable = print) -> list[str]:
    """Add announcements registered in the last `lookback_days` days and refresh the known ones.

    `search(since, until)` and `detail(code)` are the BDNS client functions, passed in so tests
    can fake them. Returns the codes seen for the first time.
    """
    since = today - dt.timedelta(days=lookback_days)
    found = search(since, today)
    log(f"BDNS: {len(found)} convocatorias para personas desde el {since:%d/%m/%Y}")
    new = []
    for number, summary in enumerate(found, 1):
        code = str(summary["numeroConvocatoria"])
        known = db["calls"].get(code)
        if known and known.get("checked") == today.isoformat():
            continue
        try:
            fresh = slim(detail(code))
        except Exception as error:  # one unreadable record shouldn't stop the daily run
            log(f"  aviso: no se pudo leer {code}: {error}")
            continue
        fresh["first_seen"] = known["first_seen"] if known else today.isoformat()
        fresh["notified"] = known.get("notified", False) if known else False
        fresh["checked"] = today.isoformat()
        db["calls"][code] = fresh
        if not known:
            new.append(code)
        if number % 100 == 0:
            log(f"  {number}/{len(found)} leídas")
    forget_old(db, today)
    db["updated"] = today.isoformat()
    log(f"Nuevas: {len(new)} · guardadas en total: {len(db['calls'])}")
    return new


def forget_old(db: dict, today: dt.date) -> None:
    for code, call in list(db["calls"].items()):
        received = dt.date.fromisoformat((call.get("fechaRecepcion") or call["first_seen"])[:10])
        end = deadlines.window(call).end
        closed_long_ago = end is not None and (today - end).days > FORGET_CLOSED_AFTER_DAYS
        if (today - received).days > FORGET_AFTER_DAYS or closed_long_ago:
            del db["calls"][code]
