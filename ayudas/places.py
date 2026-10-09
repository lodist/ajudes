"""Who publishes an announcement and where it applies.

A regional, provincial or local body can only fund within its own territory, even when the
BDNS record says "ES" (all of Spain): its scope is cut down to that territory.
"""
import re
from dataclasses import dataclass

from . import geo
from .text import nice_place, normalize, slugify

_PROVINCIAL = re.compile(r"^(diputacio|cabildo|consell insular|consejo insular|consell de)")
_SUPRA_MUNICIPAL = re.compile(r"^(mancomun|comarca|consorci|area metropolitana|entidad metropolitana|agrupacion)")


@dataclass(frozen=True)
class Place:
    kind: str  # "estado", "comunidad", "provincia", "comarca", "municipio" or "otros"
    organ: str  # who publishes it: "Ayuntamiento de Llíria", "Junta de Andalucía"...
    scope: tuple[str, ...]  # NUTS codes where it applies, e.g. ("ES523",); ("ES",) is all of Spain
    region: str | None  # NUTS 2 code, when the announcement belongs to one region
    province: str | None  # NUTS 3 code, when known
    town: str | None = None  # municipality name, for town halls
    town_slug: str | None = None


def _most_specific(codes: list[str], length: int) -> str | None:
    return next((code for code in codes if len(code) == length), None)


def _within(codes: list[str], area: str) -> tuple[str, ...]:
    """The record's codes that fall inside `area`, or the area itself."""
    return tuple(code for code in codes if code.startswith(area)) or (area,)


def place_of(call: dict) -> Place:
    organ = call.get("organo") or {}
    level = (organ.get("nivel1") or "").upper()
    second = (organ.get("nivel2") or "").strip()
    third = (organ.get("nivel3") or "").strip()
    codes = geo.codes_from(call.get("regiones"))
    province = _most_specific(codes, 5)
    region = geo.region_of(province) or _most_specific(codes, 4)
    key = normalize(second)

    if level in ("ESTADO", "ESTATAL"):  # the BDNS says "ESTADO"
        scope = tuple(codes) or (geo.SPAIN,)
        return Place("estado", nice_place(second) or "Administración General del Estado", scope,
                     None if geo.SPAIN in scope else region, province)
    if level == "AUTONOMICA":
        region = geo.region_in_text(second) or region
        if province and not province.startswith(region or "-"):
            province = None
        scope = _within(codes, region) if region else (tuple(codes) or (geo.SPAIN,))
        return Place("comunidad", geo.GOVERNMENTS.get(region) or nice_place(second), scope, region,
                     _most_specific(list(scope), 5))
    if level == "LOCAL" and _PROVINCIAL.search(key):
        province = geo.province_in_text(second) or geo.province_in_text(third) or province
        region = geo.region_of(province) or region
        name = re.sub(r"\bProv\.\s*", "", nice_place(second))
        return Place("provincia", name, _within(codes, province) if province else tuple(codes), region, province)
    # A town's grant is never national: when the record only says "ES", the bulletin it was published in
    # ("B.O.P. DE ZARAGOZA") or a town named like its province ("Murcia") tell where it is.
    local_codes = tuple(code for code in codes if code != geo.SPAIN)
    town = nice_place(second)
    if level == "LOCAL" and not province:
        found = geo.bulletin_area((call.get("boletin") or {}).get("diario"))
        if not found and not _SUPRA_MUNICIPAL.search(key):
            found = geo.province_named(town)
        if found and found.startswith(region or ""):
            province = found if len(found) == 5 else None
            region = found[:4]
        province = province or geo.sole_province(region)
    if level == "LOCAL" and _SUPRA_MUNICIPAL.search(key):
        area = province or region
        return Place("comarca", nice_place(second), _within(codes, area) if area else local_codes, region, province)
    if level == "LOCAL" and town:
        area = province or region
        return Place("municipio", f"Ayuntamiento de {town}", _within(codes, area) if area else local_codes, region,
                     province, town, slugify(town))
    name = nice_place(second) or nice_place(third) or "Otros organismos"
    province = province or geo.province_in_text(second)
    region = geo.region_of(province) or region or geo.region_in_text(second)
    area = province or region
    return Place("otros", name, _within(codes, area) if area else (tuple(codes) or (geo.SPAIN,)), region, province)
