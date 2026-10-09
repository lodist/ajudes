"""Everyday topics for announcements, found with keyword rules (no AI)."""
import re
from typing import NamedTuple

from .text import normalize


class Topic(NamedTuple):
    slug: str
    label: str
    pattern: re.Pattern


def _topic(slug: str, label: str, pattern: str) -> Topic:
    return Topic(slug, label, re.compile(pattern))


# Order matters: the first match is the announcement's main topic.
# Patterns run on accent-free lowercase text and cover Spanish and Valencian.
TOPICS = (
    _topic("premios", "Premios y concursos",
           r"\bpremios?\b|\bpremis?\b|\bconcurso(?! (general|publico) de (becas|ayudas))|\bcertamen"),
    _topic("bebes", "Bebés y crianza",
           r"nacimiento|natalidad|naixement|natalitat|\bbebe\b|ben rebuda|crianza|criansa|primera infancia"
           r"|0 a 3 anos"),
    _topic("colegio", "Colegio y material escolar",
           r"material escolar|material didactic|libros de texto|\bllibres\b|comedor(?! social)|menjador|guarderi"
           r"|escoleta|escuela infantil|escola infantil|educacion infantil|transporte escolar|\bescolar\b"
           r"|(materia|promocion|ayudas|ajudes|tasques|tareas) educativ|cheque escolar|xec escolar"),
    _topic("estudios", "Estudios y becas",
           r"estudiant|universitari|\bbecas?\b[^.]*\bestudi|\bestudios?\b[^.]*\bbecas?\b|\bmaster\b|bachiller"
           r"|batxiller|formacion profesional|ciclos? formativ|matricula|erasmus|doctorand|investigaci"
           r"|idiomas|\bidiomes\b|ayudas? al estudio|ajudes a l'estudi|olimpiada|\bcursos? de\b"),
    _topic("facturas", "Luz, agua y gas",
           r"suministro|subministrament|electricidad|electricitat|\bagua\b|\baigua\b|\bgas\b"
           r"|pobreza energetica|\bfacturas?\b"),
    _topic("vivienda", "Vivienda y alquiler",
           r"vivienda|habitatge|alquiler|lloguer|rehabilitaci|fachada|facana|accesibilidad|accessibilitat"
           r"|ascensor|eficiencia energetica|placas solares|autoconsumo|edificio|edificis|informe de evaluacion"),
    _topic("dana", "Afectados por la DANA", r"\bdana\b|inundaci|riada|29/10/2024|29 de octubre de 2024"),
    _topic("social", "Ayudas sociales y emergencia",
           r"prestaciones? economicas? individualizadas|\bpeis+\b|emergencia social|vulnerab|monoparental"
           r"|inclusion social|inclusio social|exclusion social|garantia alimentaria|necesidades basicas"
           r"|familias? numerosas?|violencia de genero|violencia contra la mujer|juguete|joguet"),
    _topic("salud", "Salud, discapacidad y dependencia",
           r"discapacidad|diversidad funcional|diversitat funcional|dependencia|celiaq|enfermedad|malaltia"
           r"|salud mental|salut mental|asperger|\btea\b|personas sordas"),
    _topic("mayores", "Personas mayores",
           r"personas mayores|gent gran|\bmajors\b|jubilad|tercera edad|envejecimiento|pensionista"),
    _topic("bonos", "Bonos de comercio local",
           r"\bbonos?[\s-]?consum|\bbons\b|bonos? (al |de |del )?(comerc|consum|hosteleria)|tarjetas? regalo"
           r"|dinamizacion comercial|fomento del consumo|campana de navidad|gastaors|compra express"),
    _topic("empleo", "Empleo y emprendimiento",
           r"\bempleo\b|ocupacio|emprend|desemplead|\bautonom|contratacion|\bpracticas\b|insercion laboral"),
    _topic("transporte", "Transporte y movilidad",
           r"transporte|\btransport\b|movilidad|mobilitat|bicicleta|vehiculo|\btaxi\b|\babono\b"
           r"|permiso de conducir|carnet de conducir|permis de conduir"),
    _topic("deporte", "Deporte", r"deportist|deportiv|\besport"),
    _topic("jovenes", "Jóvenes", r"\bjovenes\b|\bjoven\b|\bjoves\b|\bjove\b|juventud|joventut"),
    _topic("cultura", "Cultura, ocio y viajes",
           r"cultur|festiv|musica|teatro|\bfallas?\b|\bfalles\b|moros y cristianos|filaes|comparsas|patrimonio"
           r"|basilica|bono viaje|turism|vacaciones"),
)
OTHER = Topic("otras", "Otras ayudas", re.compile(r"(?!x)x"))
BY_SLUG = {topic.slug: topic for topic in (*TOPICS, OTHER)}


def classify(title: str | None, *other_texts: str | None) -> list[str]:
    """Slugs of the matching topics, main topic first. Never empty.

    The main topic comes from `title` when it matches anything; `other_texts` (the
    Valencian title, the bulletin's title) only add topics.
    """
    def matches(text: str) -> list[str]:
        text = normalize(text)
        return [topic.slug for topic in TOPICS if topic.pattern.search(text)]

    found = matches(title or "")
    found += [slug for slug in matches(" ".join(t for t in other_texts if t)) if slug not in found]
    return found or [OTHER.slug]
