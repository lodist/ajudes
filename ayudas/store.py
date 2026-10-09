"""Local copy of the announcements, kept up to date by the daily job.

Stored as data/convocatorias.jsonl (one announcement per line, sorted by code, so daily
changes make small git diffs) plus data/estado.json (when it was updated and how far back
the download has reached).
"""
import datetime as dt
import json
import re
import time
from pathlib import Path
from typing import Callable

from . import deadlines, extract, geo
from .text import normalize

HORIZON_DAYS = 180  # how far back announcements are collected
RECENT_DAYS = 10  # each run re-reads what was registered in the last 10 days (catches corrections)
RECHECK_RECENT_DAYS = 3  # ...re-reading each of those at most every 3 days
RECHECK_OPEN_DAYS = 14  # still-open announcements are re-read every two weeks (deadline extensions)
BACKFILL_STEP_DAYS = 10
FORGET_AFTER_DAYS = 400
FORGET_CLOSED_AFTER_DAYS = 60
SAVE_EVERY = 200
# Grants named for one association, agreements with one, and calls for a university's own staff
# are not open to the public.
NOT_PUBLIC = re.compile(r"\bnom+inativa\b|\bnom\.|^convenio|^conveni\b|\bpdi\b|\bpas\b|\bptgas\b|personal docente"
                        r"|personal investigador|personal de administracion|personal tecnico de gestion")
PEOPLE_AND_BUSINESSES = "1,3,4"  # BDNS beneficiary types: individuals, SMEs/self-employed, large companies


def empty() -> dict:
    return {"estado": {}, "calls": {}}


def load(folder: Path) -> dict:
    db = empty()
    lines = folder / "convocatorias.jsonl"
    if lines.exists():
        for line in lines.read_text(encoding="utf-8").splitlines():
            if line.strip():
                call = json.loads(line)
                db["calls"][call["codigo"]] = call
    state = folder / "estado.json"
    if state.exists():
        db["estado"] = json.loads(state.read_text(encoding="utf-8"))
    return db


def save(db: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    lines = (json.dumps(db["calls"][code], ensure_ascii=False, sort_keys=True)
             for code in sorted(db["calls"], key=lambda c: (len(c), c)))
    temporary = folder / "convocatorias.jsonl.tmp"
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(folder / "convocatorias.jsonl")
    (folder / "estado.json").write_text(json.dumps(db["estado"], indent=1, sort_keys=True) + "\n", encoding="utf-8")


def slim(detail: dict) -> dict:
    """Keep only what the site uses, already digested, so the data file stays small."""
    notices = detail.get("anuncios") or []
    bulletin = next((n for n in notices if n.get("url")), None)
    published = sorted(n["datPublicacion"] for n in notices if n.get("datPublicacion"))
    return {
        "codigo": str(detail.get("codigoBDNS")),
        "titulo": (detail.get("descripcion") or "").strip(),
        "titulo_cooficial": detail.get("descripcionLeng"),
        "titulo_boletin": next((n["titulo"] for n in notices if n.get("titulo")), None),
        "organo": detail.get("organo"),
        "fechaRecepcion": detail.get("fechaRecepcion"),
        "fechaInicioSolicitud": detail.get("fechaInicioSolicitud"),
        "fechaFinSolicitud": detail.get("fechaFinSolicitud"),
        "textInicio": detail.get("textInicio"),
        "textFin": detail.get("textFin"),
        "publicacion": published[0][:10] if published else None,
        "presupuesto": detail.get("presupuestoTotal"),
        "sede": extract.fix_url(detail.get("sedeElectronica")),
        "tipo": detail.get("tipoConvocatoria"),
        "finalidad": detail.get("descripcionFinalidad"),
        "beneficiarios": extract.beneficiary_types(detail.get("tiposBeneficiarios")),
        "regiones": geo.codes_from(detail.get("regiones")),
        "sectores": extract.sections([s["codigo"] for s in detail.get("sectores") or [] if s.get("codigo")]),
        "documento": extract.best_document(detail.get("documentos") or []),
        "boletin": {"url": bulletin["url"], "diario": bulletin.get("desDiarioOficial")} if bulletin else None,
        "quien": extract.who_can_apply(notices),
    }


def is_public(title: str | None) -> bool:
    return not NOT_PUBLIC.search(normalize(title))


class _Run:
    """One update: fetches details within a time budget and saves progress as it goes."""

    def __init__(self, db: dict, detail: Callable, today: dt.date, budget_seconds: float, save: Callable | None,
                 log: Callable):
        self.db, self.detail, self.today, self.save, self.log = db, detail, today, save, log
        self.deadline = time.monotonic() + budget_seconds
        self.new: list[str] = []
        self.fetched = 0

    def time_left(self) -> bool:
        return time.monotonic() < self.deadline

    def fetch(self, code: str) -> None:
        known = self.db["calls"].get(code)
        try:
            fresh = slim(self.detail(code))
        except Exception as error:  # one unreadable record shouldn't stop the run
            self.log(f"  aviso: no se pudo leer {code}: {error}")
            return
        fresh["codigo"] = code
        fresh["first_seen"] = known["first_seen"] if known else self.today.isoformat()
        fresh["notified"] = known.get("notified", False) if known else False
        fresh["checked"] = self.today.isoformat()
        self.db["calls"][code] = fresh
        if not known:
            self.new.append(code)
        self.fetched += 1
        if self.save and self.fetched % SAVE_EVERY == 0:
            self.save(self.db)
            self.log(f"  {self.fetched} leídas, {len(self.db['calls'])} guardadas")

    def days_since_checked(self, code: str) -> int:
        checked = self.db["calls"][code].get("checked") or "2000-01-01"
        return (self.today - dt.date.fromisoformat(checked)).days


def update(db: dict, search: Callable, detail: Callable, today: dt.date, *, budget_seconds: float = 3000,
           horizon_days: int = HORIZON_DAYS, save: Callable | None = None, log: Callable = print) -> list[str]:
    """Bring the copy up to date with the BDNS. Returns the codes seen for the first time.

    1. Announcements registered in the last days: new ones, and corrections to recent ones.
    2. Backfill: walk further back, ten days at a time, until `horizon_days` are covered.
    3. Re-read still-open announcements every two weeks, in case a deadline changed.
    Everything stops when the time budget runs out; the next run carries on.
    `search(since, until)` and `detail(code)` are the BDNS client functions.
    """
    run = _Run(db, detail, today, budget_seconds, save, log)
    state = db["estado"]

    recent = search(today - dt.timedelta(days=RECENT_DAYS), today)
    log(f"BDNS: {len(recent)} convocatorias registradas en los últimos {RECENT_DAYS} días")
    for summary in recent:
        code = str(summary["numeroConvocatoria"])
        if not run.time_left():
            break
        if code in db["calls"]:
            if run.days_since_checked(code) >= RECHECK_RECENT_DAYS:
                run.fetch(code)
        elif is_public(summary.get("descripcion")):
            run.fetch(code)

    horizon = today - dt.timedelta(days=horizon_days)
    covered = dt.date.fromisoformat(state.get("cubierto_desde") or
                                    (today - dt.timedelta(days=RECENT_DAYS)).isoformat())
    while covered > horizon and run.time_left():
        since = max(horizon, covered - dt.timedelta(days=BACKFILL_STEP_DAYS))
        older = search(since, covered - dt.timedelta(days=1))
        log(f"BDNS: {len(older)} convocatorias del {since:%d/%m} al {covered - dt.timedelta(days=1):%d/%m/%Y}")
        complete = True
        for summary in older:
            code = str(summary["numeroConvocatoria"])
            if code in db["calls"] or not is_public(summary.get("descripcion")):
                continue
            if not run.time_left():
                complete = False
                break
            run.fetch(code)
        if not complete:
            break
        covered = since
        state["cubierto_desde"] = covered.isoformat()

    still_open = [code for code, call in db["calls"].items()
                  if deadlines.status(deadlines.window(call), today) != "cerrada"
                  and run.days_since_checked(code) >= RECHECK_OPEN_DAYS]
    for code in sorted(still_open, key=lambda c: db["calls"][c].get("checked") or ""):
        if not run.time_left():
            break
        run.fetch(code)

    forget_old(db, today)
    state["actualizado"] = today.isoformat()
    log(f"Nuevas: {len(run.new)} · leídas: {run.fetched} · guardadas: {len(db['calls'])} · "
        f"cubierto desde: {state.get('cubierto_desde')}")
    return run.new


def forget_old(db: dict, today: dt.date) -> None:
    for code, call in list(db["calls"].items()):
        received = dt.date.fromisoformat((call.get("fechaRecepcion") or call["first_seen"])[:10])
        end = deadlines.window(call).end
        closed_long_ago = end is not None and (today - end).days > FORGET_CLOSED_AFTER_DAYS
        if (today - received).days > FORGET_AFTER_DAYS or closed_long_ago:
            del db["calls"][code]
