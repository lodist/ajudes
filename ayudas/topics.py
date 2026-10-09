"""Everyday topics for announcements, found with keyword rules (no AI)."""
import re
from typing import NamedTuple

from .text import normalize


class Topic(NamedTuple):
    slug: str
    label: str
    family: str  # "personas" or "empresas": where the topic is offered
    pattern: re.Pattern


def _topic(slug: str, label: str, family: str, pattern: str) -> Topic:
    return Topic(slug, label, family, re.compile(pattern))


# Order matters: the first match is the announcement's main topic.
# Patterns run on accent-free lowercase text and cover Spanish plus common Catalan/Valencian words.
TOPICS = (
    _topic("premios", "Premios y concursos", "personas",
           r"\bpremios?\b|\bpremis?\b|\bconcurso(?! (general|publico) de (becas|ayudas))|\bcertamen"),
    _topic("bebes", "Familia y crianza", "personas",
           r"nacimiento|natalidad|naixement|natalitat|nacemento|\bbebes?\b|ben rebuda|crianza|criansa|primera infancia"
           r"|0 a 3 anos|conciliacion|familias? numerosas?|monoparental"),
    _topic("colegio", "Colegio y material escolar", "personas",
           r"material escolar|material didactic|libros de texto|\bllibres\b|comedor(?! social)|menjador|guarderi"
           r"|escoleta|escuela infantil|escola infantil|educacion infantil|transporte escolar|\bescolar\b"
           r"|(materia|promocion|ayudas|ajudes|tasques|tareas) educativ|cheque escolar|xec escolar"),
    _topic("estudios", "Estudios y becas", "personas",
           r"estudiant|universitari|\bbecas?\b[^.]*\bestudi|\bestudios?\b[^.]*\bbecas?\b|\bmaster\b|bachiller"
           r"|batxiller|formacion profesional|ciclos? formativ|matricula|erasmus|doctorand|idiomas|\bidiomes\b"
           r"|ayudas? al estudio|ajudes a l'estudi|olimpiada|\bcursos? de\b|\bbeques?\b|alumnado"),
    _topic("facturas", "Suministros del hogar", "personas",
           r"suministro|subministrament|electricidad|electricitat|\bagua\b|\baigua\b|\bgas\b|pobreza energetica"
           r"|\bfacturas?\b|bono social"),
    _topic("vivienda", "Vivienda y alquiler", "personas",
           r"vivienda|habitatge|alquiler|lloguer|rehabilitaci|fachada|facana|accesibilidad|accessibilitat"
           r"|ascensor|edificio|edificis|informe de evaluacion|\bibi\b"),
    _topic("emergencias", "Emergencias y catástrofes", "personas",
           r"\bdana\b|inundaci|riada|incendio|catastrof|volcan|erupcion|borrasca|granizo|29/10/2024"
           r"|temporal (de|del) (lluvia|viento|nieve|mar)"
           r"|29 de octubre de 2024|danos? (causados|ocasionados|sufridos)"),
    _topic("social", "Ayudas sociales", "personas",
           r"prestaciones? economicas? individualizadas|\bpeis+\b|emergencia social|vulnerab|inclusion social"
           r"|inclusio social|exclusion social|garantia alimentaria|necesidades basicas|violencia de genero"
           r"|violencia contra la mujer|juguete|joguet|ingreso minimo|renta (minima|garantizada|social)"),
    _topic("salud", "Salud, discapacidad y dependencia", "personas",
           r"discapacidad|diversidad funcional|diversitat funcional|dependencia|celiaq|enfermedad|malaltia"
           r"|salud mental|salut mental|asperger|\btea\b|personas sordas|sanitari"),
    _topic("mayores", "Personas mayores", "personas",
           r"personas mayores|gent gran|\bmajors\b|jubilad|tercera edad|envejecimiento|pensionista"),
    _topic("bonos", "Bonos de consumo", "personas",
           r"\bbonos?[\s-]?consum|\bbons\b|bonos? (al |de |del )?(comerc|consum|hosteleria)|tarjetas? regalo"
           r"|dinamizacion comercial|fomento del consumo|campana de navidad|gastaors|compra express"),
    _topic("contratacion", "Contratación de personal", "empresas",
           r"contratacion|contratar|fomento del empleo|contratos? (indefinidos?|de trabajo)|incentivos? al empleo"
           r"|empleo estable|creacion de empleo|insercion laboral|mantenimiento del empleo"),
    _topic("empleo", "Empleo y formación", "personas",
           r"\bempleo\b|ocupacio|desemplead|aturad|\bpracticas\b|formacion (para el empleo|profesional para)"
           r"|cualificacion|busqueda de empleo|garantia juvenil"),
    _topic("emprender", "Emprendimiento y autónomos", "empresas",
           r"emprend|creacion de empresas|nuevas empresas|autoemple|\bautonom|inicio de (la )?actividad|start-?up"
           r"|relevo generacional|traspaso de negocios"),
    _topic("digital", "Digitalización", "empresas",
           r"digitaliz|transformacion digital|kit digital|comercio electronico|e-commerce|ciberseguridad|\btic\b"
           r"|inteligencia artificial|software|tecnologias de la informacion"),
    _topic("energia", "Energía y sostenibilidad", "empresas",
           r"eficiencia energetica|energias? renovables?|autoconsumo|fotovoltaic|placas solares|descarboniz"
           r"|hidrogeno|movilidad (electrica|sostenible)|vehiculos? electricos?|puntos de recarga|economia circular"
           r"|residuos|sostenibilidad|medio ambiente|biodiversidad"),
    _topic("idi", "I+D+i e innovación", "empresas",
           r"\bi\+d|\bid\+i|innovacion|investigacion|transferencia de (conocimiento|tecnologia)|tecnologic"
           r"|proyectos de i"),
    _topic("internacional", "Internacionalización", "empresas",
           r"internacionaliz|exportaci|ferias? internacional|mercados exteriores|comercio exterior"),
    _topic("agro", "Agricultura, ganadería y pesca", "empresas",
           r"agricol|agrari|agricultur|ganader|pesca|pesquer|acuicultura|forestal|regadio|apicultur|vinedo"
           r"|vitivinicol|\bpac\b|desarrollo rural|leader|jovenes agricultores|explotaciones|cosecha|sequia"),
    _topic("comercio", "Comercio, hostelería y turismo", "empresas",
           r"\bcomercios?\b|comerciant|hosteleria|hostelera|turism|alojamientos? turisticos?|artesan"
           r"|establecimientos"),
    _topic("industria", "Industria e inversión", "empresas",
           r"industri|inversion(es)? productiva|maquinaria|equipamiento productivo|modernizacion|competitividad"
           r"|manufactur|poligono|\bnaves?\b|activos? fijos"),
    _topic("transporte", "Transporte y movilidad", "personas",
           r"transporte|\btransport\b|movilidad|mobilitat|bicicleta|vehiculo|\btaxi\b|\babono\b"
           r"|permiso de conducir|carnet de conducir|permis de conduir"),
    _topic("deporte", "Deporte", "personas", r"deportist|deportiv|\besport"),
    _topic("jovenes", "Jóvenes", "personas", r"\bjovenes\b|\bjoven\b|\bjoves\b|\bjove\b|juventud|joventut"),
    _topic("cultura", "Cultura y ocio", "personas",
           r"cultur|festiv|musica|teatro|\bfallas?\b|\bfalles\b|moros y cristianos|filaes|comparsas|patrimonio"
           r"|bono viaje|vacaciones|audiovisual|cine|libro|lectura"),
)
OTHER = Topic("otras", "Otras ayudas", "personas", re.compile(r"(?!x)x"))
BY_SLUG = {topic.slug: topic for topic in (*TOPICS, OTHER)}

# The BDNS 'finalidad' (purpose), used when the title says nothing recognisable.
_PURPOSES = {
    "acceso a la vivienda y fomento de la edificacion": "vivienda",
    "agricultura, pesca y alimentacion": "agro",
    "comercio, turismo y pymes": "comercio",
    "cultura": "cultura",
    "desempleo": "empleo",
    "educacion": "estudios",
    "industria y energia": "industria",
    "investigacion, desarrollo e innovacion": "idi",
    "sanidad": "salud",
    "servicios sociales y promocion social": "social",
    "subvenciones al transporte": "transporte",
}


def classify(title: str | None, *other_texts: str | None, purpose: str | None = None,
             for_businesses: bool = False) -> list[str]:
    """Slugs of the matching topics, main topic first. Never empty.

    The main topic comes from `title` when it matches anything; `other_texts` (the
    co-official title, the bulletin's title) only add topics. If nothing matches, the
    BDNS purpose decides; "fomento del empleo" means hiring for businesses, jobs for people.
    """
    def matches(text: str) -> list[str]:
        text = normalize(text)
        return [topic.slug for topic in TOPICS if topic.pattern.search(text)]

    found = matches(title or "")
    found += [slug for slug in matches(" ".join(t for t in other_texts if t)) if slug not in found]
    if not found and purpose:
        key = normalize(purpose)
        if key == "fomento del empleo":
            found = ["contratacion" if for_businesses else "empleo"]
        elif key in _PURPOSES:
            found = [_PURPOSES[key]]
    return found or [OTHER.slug]
