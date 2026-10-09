"""Who publishes an announcement and where it applies."""
from dataclasses import dataclass

from .text import nice_place, normalize, slugify

PROVINCES = {"alicante": "Alicante", "castellon": "Castellón", "valencia": "Valencia"}
_REGION_CODES = {"ES521": "alicante", "ES522": "castellon", "ES523": "valencia"}


@dataclass(frozen=True)
class Place:
    kind: str  # "municipio", "diputacion", "comunitat", "estado" or "otros"
    name: str  # what we show: "La Pobla de Vallbona", "Diputación de Valencia"...
    slug: str  # URL key, used for town pages
    province: str | None  # "alicante", "castellon" or "valencia" when known


def province_of(call: dict) -> str | None:
    """Province from the announcement's NUTS regions, e.g. 'ES523 - Valencia / València'."""
    for region in call.get("regiones") or []:
        code = (region.get("descripcion") or "").split(" ")[0]
        if code in _REGION_CODES:
            return _REGION_CODES[code]
    return None


def _diputacion_province(name: str) -> str | None:
    words = normalize(name)
    for key in PROVINCES:
        if key in words or (key == "alicante" and "alacant" in words):
            return key
    return None


def place_of(call: dict) -> Place:
    organo = call.get("organo") or {}
    level = (organo.get("nivel1") or "").upper()
    second = (organo.get("nivel2") or "").strip()
    province = province_of(call)
    if level == "AUTONOMICA":
        return Place("comunitat", "Generalitat Valenciana", "generalitat", None)
    if level == "ESTATAL":
        return Place("estado", "Gobierno de España", "estado", None)
    if level == "LOCAL" and normalize(second).startswith("diputacion"):
        key = _diputacion_province(second) or province
        label = PROVINCES.get(key, "la provincia")
        return Place("diputacion", f"Diputación de {label}", f"diputacion-{key or 'provincia'}", key)
    if level == "LOCAL" and (name := nice_place(second)):
        return Place("municipio", name, slugify(name), province)
    name = nice_place(second) or "Otras entidades"
    return Place("otros", name, slugify(name), province)
