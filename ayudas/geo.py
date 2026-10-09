"""Spain's regions (comunidades autónomas) and provinces or islands, by NUTS code.

The BDNS tags every announcement with NUTS codes such as "ES523 - Valencia / València". The
codes nest by prefix (ES -> ES5 -> ES52 -> ES523), so an announcement tagged "ES52" applies
to every province whose code starts with "ES52".
"""
import re

from .text import normalize, slugify

SPAIN = "ES"
REGIONS = {  # NUTS 2
    "ES11": "Galicia", "ES12": "Principado de Asturias", "ES13": "Cantabria", "ES21": "País Vasco",
    "ES22": "Comunidad Foral de Navarra", "ES23": "La Rioja", "ES24": "Aragón", "ES30": "Comunidad de Madrid",
    "ES41": "Castilla y León", "ES42": "Castilla-La Mancha", "ES43": "Extremadura", "ES51": "Cataluña",
    "ES52": "Comunitat Valenciana", "ES53": "Illes Balears", "ES61": "Andalucía", "ES62": "Región de Murcia",
    "ES63": "Ceuta", "ES64": "Melilla", "ES70": "Canarias",
}
GOVERNMENTS = {  # who signs the regional announcements
    "ES11": "Xunta de Galicia", "ES12": "Principado de Asturias", "ES13": "Gobierno de Cantabria",
    "ES21": "Gobierno Vasco", "ES22": "Gobierno de Navarra", "ES23": "Gobierno de La Rioja",
    "ES24": "Gobierno de Aragón", "ES30": "Comunidad de Madrid", "ES41": "Junta de Castilla y León",
    "ES42": "Junta de Castilla-La Mancha", "ES43": "Junta de Extremadura", "ES51": "Generalitat de Catalunya",
    "ES52": "Generalitat Valenciana", "ES53": "Govern de les Illes Balears", "ES61": "Junta de Andalucía",
    "ES62": "Región de Murcia", "ES63": "Ciudad Autónoma de Ceuta", "ES64": "Ciudad Autónoma de Melilla",
    "ES70": "Gobierno de Canarias",
}
PROVINCES = {  # NUTS 3: provinces, and islands in the Balearic and Canary Islands
    "ES111": "A Coruña", "ES112": "Lugo", "ES113": "Ourense", "ES114": "Pontevedra", "ES120": "Asturias",
    "ES130": "Cantabria", "ES211": "Araba/Álava", "ES212": "Gipuzkoa", "ES213": "Bizkaia", "ES220": "Navarra",
    "ES230": "La Rioja", "ES241": "Huesca", "ES242": "Teruel", "ES243": "Zaragoza", "ES300": "Madrid",
    "ES411": "Ávila", "ES412": "Burgos", "ES413": "León", "ES414": "Palencia", "ES415": "Salamanca",
    "ES416": "Segovia", "ES417": "Soria", "ES418": "Valladolid", "ES419": "Zamora", "ES421": "Albacete",
    "ES422": "Ciudad Real", "ES423": "Cuenca", "ES424": "Guadalajara", "ES425": "Toledo", "ES431": "Badajoz",
    "ES432": "Cáceres", "ES511": "Barcelona", "ES512": "Girona", "ES513": "Lleida", "ES514": "Tarragona",
    "ES521": "Alicante/Alacant", "ES522": "Castellón/Castelló", "ES523": "Valencia/València",
    "ES531": "Eivissa y Formentera", "ES532": "Mallorca", "ES533": "Menorca", "ES611": "Almería",
    "ES612": "Cádiz", "ES613": "Córdoba", "ES614": "Granada", "ES615": "Huelva", "ES616": "Jaén",
    "ES617": "Málaga", "ES618": "Sevilla", "ES620": "Murcia", "ES630": "Ceuta", "ES640": "Melilla",
    "ES703": "El Hierro", "ES704": "Fuerteventura", "ES705": "Gran Canaria", "ES706": "La Gomera",
    "ES707": "La Palma", "ES708": "Lanzarote", "ES709": "Tenerife",
}
# Other spellings of province and island names, as they appear in "Diputación de ..." or "Cabildo de ...".
_ALIASES = {
    "alacant": "ES521", "castello": "ES522", "alava": "ES211", "guipuzcoa": "ES212", "vizcaya": "ES213",
    "la coruna": "ES111", "coruna": "ES111", "orense": "ES113", "gerona": "ES512", "lerida": "ES513",
    "ibiza": "ES531", "eivissa": "ES531", "formentera": "ES531", "palmas": "ES705",
}


def _name_index() -> dict[str, str]:
    index = dict(_ALIASES)
    for code, name in PROVINCES.items():
        for part in name.split("/"):
            index[normalize(part)] = code
    return index


_PROVINCE_NAMES = _name_index()


def region_of(code: str | None) -> str | None:
    return code[:4] if code and len(code) >= 4 and code[:4] in REGIONS else None


def province_name(code: str) -> str:
    return PROVINCES.get(code) or REGIONS.get(code) or "España"


def region_slug(code: str) -> str:
    return slugify(REGIONS[code])


def province_slug(code: str) -> str:
    return slugify(PROVINCES[code].split("/")[0])


def codes_from(regions: list[dict | str] | None) -> list[str]:
    """NUTS codes from the BDNS 'regiones' field ({"descripcion": "ES523 - Valencia"} or plain codes).

    'Todo el mundo' counts as all of Spain.
    """
    codes = []
    for region in regions or []:
        text = region.get("descripcion") if isinstance(region, dict) else region
        code = (text or "").split(" ")[0].strip()
        if code == "XXXX":
            code = SPAIN
        if code.startswith(SPAIN) and code not in codes:
            codes.append(code)
    return codes


def province_in_text(text: str | None) -> str | None:
    """Province or island named in an organ, e.g. 'DIPUTACIÓN PROV. DE VALENCIA' -> ES523."""
    words = normalize(text)
    for name in sorted(_PROVINCE_NAMES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", words):
            return _PROVINCE_NAMES[name]
    return None


def region_in_text(text: str | None) -> str | None:
    """Region named in a regional government's organ, e.g. 'COMUNIDAD VALENCIANA' -> ES52."""
    words = normalize(text).replace("-", " ")
    for code, name in REGIONS.items():
        key = normalize(name).replace("-", " ")
        if key in words:
            return code
    aliases = {"comunidad valenciana": "ES52", "baleares": "ES53", "murcia": "ES62", "navarra": "ES22",
               "asturias": "ES12", "madrid": "ES30", "ceuta": "ES63", "melilla": "ES64", "cataluna": "ES51",
               "catalunya": "ES51", "euskadi": "ES21"}
    return next((code for key, code in aliases.items() if key in words), None)


def province_named(name: str | None) -> str | None:
    """The province a town is named after: 'Zaragoza' -> ES243. Only exact names count ('Valencia de Don Juan' isn't)."""
    return next((_PROVINCE_NAMES[part] for part in map(normalize, (name or "").split("/")) if part in _PROVINCE_NAMES),
                None)


def sole_province(region: str | None) -> str | None:
    """The province of a one-province region: ES30 (Comunidad de Madrid) -> ES300."""
    provinces = [code for code in PROVINCES if region and code.startswith(region)]
    return provinces[0] if len(provinces) == 1 else None


def bulletin_area(name: str | None) -> str | None:
    """Where an official bulletin is published: 'B.O.P. DE ZARAGOZA' -> ES243, 'DOCV. D.O. DE LA COMUNITAT...' -> ES52.

    Regional bulletins of one-province regions give the province ('BORM. B.O. DE LA REGIÓN DE MURCIA' -> ES620).
    Island bulletins cover several islands, so they only give the region. The BOE gives nothing.
    """
    text = normalize(name)
    if not text:
        return None
    region = region_in_text(text)
    if region:
        return sole_province(region) or region
    province = province_in_text(text)
    if province and province[:4] in ("ES53", "ES70"):
        return province[:4]
    return province
