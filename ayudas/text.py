"""Text helpers: accent-free matching, URL slugs, readable titles and place names."""
import re
import unicodedata

MAX_TITLE = 170

_SMALL_WORDS = {"de", "del", "la", "las", "les", "el", "els", "los", "y", "i", "en", "a"}
_ARTICLE = re.compile(r"^(.*?),\s*(la|el|els|les|los|las|l')$", re.IGNORECASE)
_LEADING_ARTICLE = re.compile(r"^(el|la|els|les|los|las)\s+|^l'", re.IGNORECASE)

# Bureaucratic openings that tell a citizen nothing; removed from the start of titles.
_DOC = r"(?:extracto|resoluci[oó]n|decreto|acuerdo|anuncio|orden|providencia)"
_DATE = r"(?:\d{1,2}\s+de\s+[a-záéíóú]+(?:\s+(?:de\s+)?\d{4})?|\d{1,2}/\d{1,2}/\d{2,4})"
_AID = r"(?=(?:ayudas?|subvenci|becas?|premios?|bonos?|prestaci|l[ií]neas?|programas?|concesi|convocat|resoluci)\w*\b)"
_RULE = r"(deben\s+)?(regir[aá]n|regir|rigen|regulan?)"  # "que deben regir", "que regulan"
_PREAMBLES = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"^(expediente|expte\.?)\s*(n[.º°o]*\s*)?[\w./-]+\s*[:.\-–]?\s*",
    r"^\d{6,}\s*[-–:.]?\s*",  # internal file numbers: "202604907006 subvención..."
    r"^20\d\d\s*[-–:.]?\s+(?=\D)",  # a leading year: "2026 - Convocatoria de ayudas..."
    r"^[«\"“'`]\s*",
    # "Resolución ... por la que se convocan (y hacen públicas) ..." -> what is convened
    rf"^(?:(?:del?\s+|la\s+|el\s+|por\s+)?{_DOC}\b|resol\.).*?\bpor (la|el|lo) (que|cual) se\s+"
    r"((convocan?|aprueban?|tramitan?|regulan?|establecen?|efect[uú]an?|realizan?|abren?|inician?|ordenan?"
    r"|procede\s+a|autoriza\s+el\s+gasto\s+y\s+se\s+aprueban?)"
    r"(\s+y\s+(se\s+)?(hacen?\s+p[uú]blicas?|aprueban?|convocan?))?"
    r"(\s+(para|en)\s+(el\s+)?(a[nñ]o\s+|ejercicio\s+)?\d{4})?\s+((la|el)\s+)?(apertura\s+y\s+)?)?",
    # "Convocatoria de 16 de septiembre de 2026, del Vicerrectorado de X, de ayudas a..." -> "ayudas a..."
    rf"^(convocatoria|resoluci[oó]n|orden|decreto|acuerdo)(\s+[a-z]{{2,}}/\d+/\d{{4}})?,?\s+de\s+{_DATE},\s*"
    r"(del?\s+[^,]+,\s*)*(por\s+delegaci[oó]n,\s*)?(de\s+)?",
    rf"^{_DOC}\s+(del?|de la)\s+[^,]+,\s*(de\s+)?(?=convocat)",  # "Resolución del director general, de convocatoria..."
    rf"^{_DOC}\b[^:]*?\s+de\s+(?=convocatoria\s+de\b)",  # "Resolución de la consejera de X de convocatoria de..."
    r"^resoluci[oó]n\s+(de\s+(la\s+)?alcald[ií]a\s+)?n[.º°o]*\s*\d[\w/.-]*[^:–-]*[:–-]\s*(decreto\s+)?",
    r"^decreto\s+(de\s+(la\s+)?alcald[ií]a\s+)?(n[.º°o]*\s*)?\d[\d/-]*\s+(?=convocat)",
    rf"^(?:{_DOC}|aprobaci[oó]n)(\s+de(\s+la)?)?\s+(?=(convocat|concesi|bases))",  # "Resolución convocatoria para..."
    rf"^{_DOC}\b.*?\b(que|por el que)\s+(se\s+)?(aprueban?|convocan?|regulan?)\s+((la|las|el|los)\s+)?",
    r"^acuerdo\b.*?\brelativo\s+a\s+(la\s+)?",
    r"^acuerdo\s+(de\s+(la\s+)?)?(aprobaci[oó]n\s+de\s+la\s+)?junta\s+(de\s+)?gobierno(\s+local)?\s+"
    r"((de\s+)?aprobaci[oó]n\s+)?(de\s+)?",
    r"^anuncio d(el|e la)\b.*?\bsobre\s+",
    r"^(el\s+)?ayuntamiento de [^:,]+? (para|sobre)\s+(la\s+)?",
    r"^extract[oe]\s+(de\s+)?((la|las|el|los)\s+)?",  # also Catalan "extracte"
    r"^(aprobaci[oó]n\s+(de\s+)?)?(las\s+)?(bases|bbrr)(\s+(reguladoras|espec[ií]ficas|generales))?"
    r"(\s+(y|de la|de)\s+(la\s+)?convocatoria(\s+p[uú]blica)?(\s+\d{4})?)?"
    rf"(\s+que\s+{_RULE}(\s+(la|las|el|los))?)?"
    r"\s+((de|para)\s+(la\s+|las\s+|los\s+|el\s+)?|del\s+)?",
    r"^(la\s+)?convocat[oòó]rias?(\s+(p[uú]blica|anual|anticipada|extraordinaria|ordinaria))*"
    r"(\s+(para\s+el\s+|del?\s+|en\s+|correspondiente\s+al\s+)?(a[nñ]o\s+|ejercicio\s+)?\d{4})?(\s+de\s+participaci[oó]n)?"
    r"(\s+(de|del|para|en)(\s+(la|las|el|los))?)?(\s*[:–-])?\s+",
    rf"^que\s+{_RULE}\s+((la|las|el|los)\s+)?(solicitud\s+y\s+)?",
    r"^(por|para)\s+(el|la)\s+(?=(concesi|otorgamiento))",
    r"^(el\s+)?procedimiento\s+de\s+(?=concesi)",
    r"^(la\s+)?(concesi[oó]n|otorgamiento)(\s+directa)?\s+((de\s+(las\s+|los\s+)?|del\s+)"
    r"|(?=(ayudas?|subvenci|becas?|premios?|prestaci)))",
    rf"^del?\s+((la|las|el|los)\s+)?{_AID}",  # "De subvenciones a deportistas"
    r"^y\s+(se\s+(convocan?|aprueban?)\s+)?",  # left over from "...se aprueban las bases y (se convocan)..."
    rf"^(la|las|el|los)\s+{_AID}",
)]
_FILLER = re.compile(
    r",?\s*(?:en\s+r[eé]g(?:imen|\.)\s+de|por\s+(?:el\s+)?procedimiento\s+de|por|mediante|en)\s+"
    r"conc(?:urrencia\s+|\.\s*)comp(?:etitiva\b|\.)\s*,?"  # "en régimen de concurrencia competitiva", "en rég. de conc. comp."
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


def _balance_quotes(text: str) -> str:
    """Drop quote marks left unpaired once the preamble is gone."""
    text = text.replace("`", "")
    for opening, closing in (("«", "»"), ("“", "”")):
        if text.count(opening) != text.count(closing):
            text = text.replace(opening, "").replace(closing, "")
    return text.replace('"', "") if text.count('"') % 2 else text


def looks_abbreviated(title: str | None) -> bool:
    """Titles squeezed into the BDNS field: 'FEADER.AYUD.MANT.VIÑEDO SECANO...'."""
    return len(re.findall(r"[^\W\d_]{2,}\.[^\W\d_]", title or "")) >= 2


def clean_title(raw: str | None, names: tuple[str, ...] = ()) -> str:
    """Turn a bureaucratic announcement title into something a person can read.

    `names` are place names to restore when an ALL-CAPS title gets lower-cased.
    """
    original = re.sub(r"\s+", " ", (raw or "").replace("*", "")).strip()
    original = re.sub(r"(?<=\w)¿(?=\w)", "'", original)  # a broken apostrophe: "l¿ajuntament"
    text = original
    for _ in range(5):
        before = text
        text = re.sub(r"\s+", " ", _FILLER.sub(" ", text)).strip()  # "concesión, en régimen de..., de ayudas"
        for pattern in _PREAMBLES:
            text = pattern.sub("", text, count=1).strip()
        if text == before:
            break
    text = _balance_quotes(_FILLER.sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip(" .,;:-–")
    if len(text) < 8:  # the clean-up ate everything useful
        text = original.strip(" .")
    parts = re.split(r"(\s[-–]\s|:\s)", text)
    text = "".join(_calm(part, names) if _is_shouting(part) else part for part in parts)
    text = text[:1].upper() + text[1:]
    if len(text) > MAX_TITLE:
        text = text[:MAX_TITLE].rsplit(" ", 1)[0].rstrip(" ,;:-–") + "…"
    return text
