"""Text helpers: accent-free matching, URL slugs, readable titles and place names."""
import re
import unicodedata

MAX_TITLE = 170

_SMALL_WORDS = {"de", "del", "la", "las", "les", "el", "els", "los", "y", "i", "en", "a"}
_ARTICLE = re.compile(r"^(.*?),\s*(la|el|els|les|los|las|l')$", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(el|la|els|les|los|las)\s+|^l'", re.IGNORECASE)

# Bureaucratic openings that tell a citizen nothing; removed from the start of titles.
_PREAMBLES = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"^(expediente|expte\.?)\s*(n[.º°o]*\s*)?[\w./-]+\s*[:.\-–]?\s*",
    r"^(?:(?:extracto|resoluci[oó]n|decreto|acuerdo|anuncio|orden|providencia)\b|resol\.).*?\bpor (la|el|lo) "
    r"(que|cual) se (convocan?|aprueban?|tramitan?|regulan?|establecen?|efect[uú]an?)\s+",
    r"^resoluci[oó]n\s+(de\s+(la\s+)?alcald[ií]a\s+)?n[.º°o]*\s*\d[\w/.-]*[^:–-]*[:–-]\s*(decreto\s+)?",
    r"^anuncio d(el|e la)\b.*?\bsobre\s+",
    r"^(el\s+)?ayuntamiento de [^:,]+? (para|sobre)\s+(la\s+)?",
    r"^extracto\s+(de\s+)?(las\s+)?",
    r"^(aprobaci[oó]n\s+(de\s+)?(las\s+)?)?bases(\s+reguladoras)?"
    r"(\s+(y|de la|de)\s+(la\s+)?convocatoria(\s+p[uú]blica)?)?\s+((de|para)\s+(la\s+|las\s+|los\s+|el\s+)?|del\s+)?",
    r"^(la\s+)?convocatoria(\s+p[uú]blica)?(\s+anual)?(\s+(de|del|para)(\s+(la|las|el|los))?)?\s+",
    r"^(la\s+)?concesi[oó]n(\s+directa)?\s+(de\s+(las\s+|los\s+)?|del\s+)",
)]
_FILLER = re.compile(
    r",?\s*(?:en r[eé]gimen de|por el procedimiento de|por|mediante|en)\s+concurrencia competitiva\b,?"
    r"|\s*\((?:decreto|resoluci[oó]n|expediente|expte?\.?)[^)]*\)",
    re.IGNORECASE)
_ACRONYMS = ("dana", "bop", "boe", "dogv", "iprem", "irpf", "iva", "upv", "crue", "peiss", "ong", "uji", "umh",
             "ue", "fp", "ieev.cv", "tea")
_ACRONYM = re.compile(r"\b(" + "|".join(re.escape(a) for a in _ACRONYMS) + r")\b")
_ROMAN = re.compile(r"\b(?=[ivxlc]{2,}\b)c{0,3}(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})\b")


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str | None) -> str:
    """Lowercase, accent-free, single-spaced text for keyword matching."""
    text = strip_accents((text or "").replace("’", "'")).lower()
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize(text)).strip("-")


def _capitalize(word: str, first: bool) -> str:
    low = word.lower()
    if not first and low in _SMALL_WORDS:
        return low
    elided = re.match(r"^([dl]')(.+)$", low)  # l'eliana -> L'Eliana, d'alcoi -> d'Alcoi
    if elided:
        head = elided.group(1).capitalize() if first else elided.group(1)
        return head + _capitalize(elided.group(2), True)
    # Upper-case the first letter, also after "(" or a hyphen: (estudi -> (Estudi
    return re.sub(r"(^|[(\-])(\w)", lambda m: m.group(1) + m.group(2).upper(), low)


def _one_name(name: str) -> str:
    name = name.strip()
    match = _ARTICLE.match(name)
    if match:
        article = match.group(2)
        name = f"{article}{match.group(1)}" if article.endswith("'") else f"{article} {match.group(1)}"
    words = name.split()
    return " ".join(_capitalize(word, i == 0) for i, word in enumerate(words))


def nice_place(raw: str | None) -> str:
    """'POBLA DE VALLBONA, LA' -> 'La Pobla de Vallbona'. Bilingual names stay bilingual: 'Alcoy/Alcoi'."""
    name = re.sub(r",?\s*entidad local menor\s*$", "", (raw or "").strip(), flags=re.IGNORECASE)
    return "/".join(_one_name(part) for part in name.split("/") if part.strip())


def _is_shouting(text: str) -> bool:
    letters = [ch for ch in text if ch.isalpha()]
    return len(letters) >= 4 and sum(ch.isupper() for ch in letters) / len(letters) > 0.7


def _calm(text: str, names: tuple[str, ...]) -> str:
    """Lower-case an ALL-CAPS title but keep acronyms, roman numerals and place names."""
    text = _ACRONYM.sub(lambda m: m.group(1).upper(), text.lower())
    text = _ROMAN.sub(lambda m: m.group(0).upper(), text)
    for name in names:
        for variant in filter(None, (v.strip() for v in name.split("/"))):
            for form in {variant, _LEADING_ARTICLE.sub("", variant)}:
                text = re.sub(rf"\b{re.escape(form.lower())}\b", lambda _m, form=form: form, text)
    return text


def clean_title(raw: str | None, names: tuple[str, ...] = ()) -> str:
    """Turn a bureaucratic announcement title into something a person can read.

    `names` are place names to restore when an ALL-CAPS title gets lower-cased.
    """
    original = re.sub(r"\s+", " ", (raw or "").replace("*", "")).strip()
    text = original
    for _ in range(4):
        before = text
        for pattern in _PREAMBLES:
            text = pattern.sub("", text, count=1).strip()
        if text == before:
            break
    text = _FILLER.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,;:-–")
    if len(text) < 8:  # the clean-up ate everything useful
        text = original.strip(" .")
    parts = re.split(r"(\s[-–]\s|:\s)", text)
    text = "".join(_calm(part, names) if _is_shouting(part) else part for part in parts)
    text = text[:1].upper() + text[1:]
    if len(text) > MAX_TITLE:
        text = text[:MAX_TITLE].rsplit(" ", 1)[0].rstrip(" ,;:-–") + "…"
    return text
