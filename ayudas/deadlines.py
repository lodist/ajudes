"""Application windows worked out from the official data, without AI.

Spanish administrative law (Ley 39/2015, art. 30) counts a period from the day after
publication, and a period in days means working days unless it says "naturales".
Public holidays are not known here, so computed dates can come a day or two early,
never late.
"""
import calendar
import datetime as dt
import re
from dataclasses import dataclass

from .text import normalize

MONTHS = {
    "enero": 1, "gener": 1, "febrero": 2, "febrer": 2, "marzo": 3, "marc": 3, "abril": 4,
    "mayo": 5, "maig": 5, "junio": 6, "juny": 6, "julio": 7, "juliol": 7, "agosto": 8, "agost": 8,
    "septiembre": 9, "setiembre": 9, "setembre": 9, "octubre": 10, "noviembre": 11, "novembre": 11,
    "diciembre": 12, "desembre": 12,
}
NUMBERS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "quatre": 4, "cinco": 5, "cinc": 5,
    "seis": 6, "sis": 6, "siete": 7, "set": 7, "ocho": 8, "huit": 8, "vuit": 8, "nueve": 9, "nou": 9,
    "diez": 10, "deu": 10, "once": 11, "onze": 11, "doce": 12, "dotze": 12, "quince": 15, "quinze": 15,
    "veinte": 20, "viente": 20, "vint": 20, "veinticinco": 25, "treinta": 30, "trenta": 30,
    "cuarenta": 40, "quaranta": 40, "cuarenta y cinco": 45, "sesenta": 60, "seixanta": 60,
}
_MONTH_NAMES = "|".join(MONTHS)
_TEXT_DATE = re.compile(r"\b(\d{1,2})\s+(?:de\s+|d')?(" + _MONTH_NAMES + r")\s*(?:de\s+|del\s+|,\s*)?(\d{4})\b")
_DAY_MONTH = re.compile(r"\b(\d{1,2})\s+(?:de\s+|d')?(" + _MONTH_NAMES + r")\b")
_NUM_DATE = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_YEAR_END = re.compile(r"ultimo dia del (ano|ejercicio)")
_PERIOD = re.compile(
    r"\b(\d{1,3}|" + "|".join(sorted(NUMBERS, key=len, reverse=True)) + r")[oa]?"  # "16º" is normalised to "16o"
    r"(?:\s*\(\d{1,3}\))?\s+"  # "treinta (30) días"
    r"(dias?|dies|semanas?|setmanes|meses|mes|mesos)\b"
    r"(?:\s+(habiles|habil|naturales|natural|habils|naturals))?")
# How long after the computed end an item is still shown as "may have closed".
_GRACE_DAYS = {"exact": 0, "computed": 3, "earliest": 20}


@dataclass(frozen=True)
class Window:
    start: dt.date | None
    end: dt.date | None
    precision: str  # "exact", "computed" (period + publication date) or "earliest" (lower bound)
    period: str | None = None  # e.g. "20 días naturales", when the end comes from a period


def iso_date(value: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def _safe_date(year: int, month: int, day: int) -> dt.date | None:
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def parse_date(text: str, reference: dt.date | None = None) -> dt.date | None:
    """First date written in accent-free lowercase text: 2026-12-31, 31/12/26 or '31 de diciembre de 2026'.

    With a `reference` date, '27 de julio' (no year) means its next occurrence from then,
    and 'último día del año' means 31 December of that year.
    """
    if match := _ISO_DATE.search(text):
        return _safe_date(int(match[1]), int(match[2]), int(match[3]))
    if match := _NUM_DATE.search(text):
        year = int(match[3])
        return _safe_date(year + 2000 if year < 100 else year, int(match[2]), int(match[1]))
    if match := _TEXT_DATE.search(text):
        return _safe_date(int(match[3]), MONTHS[match[2]], int(match[1]))
    for match in _DAY_MONTH.finditer(text) if reference else ():
        if re.search(r"\bley\b|decreto|\d/\d{4}", text[max(0, match.start() - 30):match.start()]):
            continue  # "Ley 39/2015, de 1 de octubre" names a law, it is not a deadline
        day = _safe_date(reference.year, MONTHS[match[2]], int(match[1]))
        if day and day < reference:
            day = _safe_date(reference.year + 1, MONTHS[match[2]], int(match[1]))
        return day
    if reference and _YEAR_END.search(text):
        return dt.date(reference.year, 12, 31)
    return None


def parse_period(text: str) -> tuple[int, str, str] | None:
    """('10 días hábiles…') -> (10, 'days', 'habiles'); ('un mes') -> (1, 'months', '')."""
    match = _PERIOD.search(text)
    if not match:
        return None
    amount = int(match[1]) if match[1].isdigit() else NUMBERS[match[1]]
    if match[2].startswith("mes"):
        return amount, "months", ""
    if match[2].startswith(("seman", "setman")):
        return amount * 7, "days", "naturales"
    kind = "naturales" if (match[3] or "").startswith("natural") else "habiles"
    return amount, "days", kind


def add_working_days(start: dt.date, days: int) -> dt.date:
    """The `days`-th working day after `start`, skipping weekends."""
    current, left = start, days
    while left > 0:
        current += dt.timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def add_months(start: dt.date, months: int) -> dt.date:
    """Same day number `months` later, or the month's last day if it doesn't exist (art. 30.4)."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return dt.date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def _describe(amount: int, unit: str, kind: str) -> str:
    if unit == "months":
        return "1 mes" if amount == 1 else f"{amount} meses"
    label = "hábiles" if kind == "habiles" else "naturales"
    return f"{amount} {'día' if amount == 1 else 'días'} {label}"


def publication_date(call: dict) -> dt.date | None:
    """When the extract appeared in an official bulletin (BOP/DOGV), if the BDNS knows it."""
    dates = [iso_date(a.get("fecha")) for a in call.get("anuncios") or []]
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def window(call: dict) -> Window:
    received = iso_date(call.get("fechaRecepcion"))
    start = iso_date(call.get("fechaInicioSolicitud")) or parse_date(normalize(call.get("textInicio")), received)
    end = iso_date(call.get("fechaFinSolicitud"))
    if end:
        return Window(start, end, "exact")
    for raw in (call.get("textFin"), call.get("textInicio")):
        text = normalize(raw)
        if not text:
            continue
        if (date := parse_date(text, received)) and date != start:
            return Window(start, date, "exact")
        if period := parse_period(text):
            published = publication_date(call)
            base = published or received
            label = _describe(*period)
            if base is None:
                return Window(start, None, "earliest", label)
            amount, unit, kind = period
            if unit == "months":
                end = add_months(base, amount)
            elif kind == "naturales":
                end = base + dt.timedelta(days=amount)
            else:
                end = add_working_days(base, amount)
            if published:
                return Window(start or published + dt.timedelta(days=1), end, "computed", label)
            return Window(start, end, "earliest", label)
    return Window(start, None, "exact")


def status(win: Window, today: dt.date) -> str:
    """'proxima', 'abierta', 'revisar' (may have closed), 'cerrada' or 'sin_fecha'."""
    if win.start and today < win.start:
        return "proxima"
    if win.end is None:
        return "sin_fecha"
    if today <= win.end:
        return "abierta"
    if (today - win.end).days <= _GRACE_DAYS[win.precision]:
        return "revisar"
    return "cerrada"
