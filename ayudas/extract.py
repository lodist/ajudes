"""Pieces taken from an announcement's full record: who can apply, the rules document, the bulletin."""
import html
import re

from .text import normalize

BENEFICIARY_TYPES = {
    1: "Particulares",
    2: "Asociaciones y entidades",
    3: "Autónomos y pymes",
    4: "Grandes empresas",
    5: "Sin especificar",
}

# The "Personas beneficiarias" section of the bulletin extract: a heading, then text up to the next heading.
_BENEFICIARIES = re.compile(r"beneficiari(?:[ao]s?|s)?\b", re.IGNORECASE)
_HEADING_BEFORE = re.compile(
    r"(?:\n|\b(?:primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|quint[oa]|sext[oa]|\d+\s*[.)\-–º°]+))"
    r"[\s.:\-–]*(?:las?\s+|los\s+)?(?:personas\s+)?$", re.IGNORECASE)
_NEXT_HEADING = re.compile(
    r"\n\s*(?:\d+\s*[.)\-–º°]|primer|segund|tercer|cuart|quint|sext|objet|finalidad|bases|cuant[ií]a|import|plazo"
    r"|termini|requisit)|\s(?:segund[oa]|tercer[oa]|cuart[oa]|quint[oa]|sext[oa])[.:]\s", re.IGNORECASE)


# Economic sections of the CNAE 2025 (NACE Rev. 2.1), A to V, and the two-digit divisions in each.
SECTIONS = {
    "A": "Agricultura, ganadería, silvicultura y pesca", "B": "Industrias extractivas",
    "C": "Industria manufacturera", "D": "Energía eléctrica y gas", "E": "Agua, saneamiento y residuos",
    "F": "Construcción", "G": "Comercio", "H": "Transporte y almacenamiento", "I": "Hostelería",
    "J": "Edición, radio y contenidos", "K": "Telecomunicaciones e informática", "L": "Finanzas y seguros",
    "M": "Actividades inmobiliarias", "N": "Actividades profesionales, científicas y técnicas",
    "O": "Actividades administrativas", "P": "Administración pública", "Q": "Educación",
    "R": "Sanidad y servicios sociales", "S": "Arte, deporte y ocio", "T": "Otros servicios",
    "U": "Hogares", "V": "Organismos extraterritoriales",
}
_DIVISIONS = ((1, 3, "A"), (5, 9, "B"), (10, 33, "C"), (35, 35, "D"), (36, 39, "E"), (41, 43, "F"), (45, 47, "G"),
              (49, 53, "H"), (55, 56, "I"), (58, 60, "J"), (61, 63, "K"), (64, 66, "L"), (68, 68, "M"), (69, 75, "N"),
              (77, 82, "O"), (84, 84, "P"), (85, 85, "Q"), (86, 88, "R"), (90, 93, "S"), (94, 96, "T"), (97, 98, "U"),
              (99, 99, "V"))


def sections(codes: list[str]) -> list[str]:
    """Economic sections (letters A-V) from BDNS sector codes, which mix letters and CNAE numbers."""
    found = set()
    for code in codes:
        code = str(code).strip().upper()
        if re.fullmatch(r"[A-V]", code):
            found.add(code)
        elif match := re.match(r"(\d{2})", code):
            division = int(match.group(1))
            found.update(letter for low, high, letter in _DIVISIONS if low <= division <= high)
    return sorted(found)


def beneficiary_types(entries: list[dict] | None) -> list[int]:
    """BDNS beneficiary descriptions -> ids 1-5 (see BENEFICIARY_TYPES)."""
    found = []
    for entry in entries or []:
        text = normalize(entry.get("descripcion") if isinstance(entry, dict) else str(entry))
        if "gran empresa" in text:
            kind = 4
        elif "pyme" in text or ("fisicas" in text and "desarrollan actividad" in text and "no desarrollan" not in text):
            kind = 3
        elif "juridicas" in text:
            kind = 2
        elif "fisicas" in text:
            kind = 1
        else:
            kind = 5
        if kind not in found:
            found.append(kind)
    return sorted(found) or [5]


def who_can_apply(notices: list[dict]) -> str | None:
    """Who can apply, quoted from the bulletin extract's 'beneficiarias' section."""
    for notice in notices:
        text = "\n" + html.unescape(re.sub(r"<[^>]+>", "\n", notice.get("texto") or ""))
        for match in _BENEFICIARIES.finditer(text):
            if not _HEADING_BEFORE.search(text[max(0, match.start() - 40):match.start()]):
                continue  # a passing mention, not the section heading
            # skip separators and heading tails such as "o consumidoras:" in "beneficiarias o consumidoras:"
            rest = re.sub(r"^[\s:.\-–]+(?:[oyi]\s+\w+\s*:\s*)?", "", text[match.end():])
            end = _NEXT_HEADING.search(rest)
            who = re.sub(r"\s+", " ", rest[:end.start()] if end else rest[:400]).strip(" .:-–")
            if len(who) >= 15:
                return who if len(who) <= 240 else who[:240].rsplit(" ", 1)[0] + "…"
    return None


def best_document(documents: list[dict]) -> dict | None:
    """The document most likely to be the rules, preferably in Spanish: {"id", "nombre"}."""
    documents = [d for d in documents if d.get("id")]
    if not documents:
        return None

    def score(document: dict) -> int:
        name = normalize(document.get("nombreFic") or document.get("nombre") or document.get("descripcion"))
        good = ("bases" in name) + ("convocatoria" in name or "extracto" in name) + ("cast" in name)
        bad = any(word in name for word in ("valencia", "anex", "model", "solicitud", "instancia"))
        return good - 2 * bad

    best = max(documents, key=score)
    return {"id": best["id"], "nombre": best.get("nombreFic") or best.get("nombre") or best.get("descripcion")}


def fix_url(raw: str | None) -> str | None:
    """Repair the hand-typed office addresses: 'https//x', 'https: x', 'www.x.es'."""
    url = re.sub(r"^(https?)[:/\s]+", r"\1://", (raw or "").strip(), flags=re.IGNORECASE)
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("/")
    return url if re.match(r"^https?://[^\s/]+\.[^\s/]+", url) else None
