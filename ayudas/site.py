"""Builds the static website: data files for the in-browser app, and readable pages for search engines.

Everything personal (the profile, saved aid) happens in the visitor's browser; this module only
writes public files: public/data/*.json for the app, plus one page per region, province, town and
topic so search engines can find them.
"""
import dataclasses
import datetime as dt
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from email.utils import format_datetime
from pathlib import Path

from . import bdns, deadlines, extract, geo, places, store, topics
from .text import clean_title, looks_abbreviated, normalize

STATIC = Path(__file__).parent / "static"
SITE_NAME = "Ajudes"
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre")
MONTHS_SHORT = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
LISTED = ("abierta", "proxima", "revisar", "sin_fecha")
STALE_DAYS = 90  # an announcement with no known deadline is dropped after three months
PAGE_LIMIT = 60  # cards on a static page; the search page shows the rest
SECTION_LIMIT = 12  # cards in the secondary sections of a page
_ORDER = {"abierta": 0, "proxima": 1, "revisar": 2, "sin_fecha": 3, "cerrada": 4}
_PRECISION = {"exact": "x", "computed": "c", "earliest": "l"}
_KIND_LETTERS = {"estado": "e", "comunidad": "c", "provincia": "p", "comarca": "a", "municipio": "m", "otros": "o"}
# Order of the topic tiles on the home page: everyday needs first, prizes and contests last.
_TILE_ORDER = ("bebes", "colegio", "estudios", "vivienda", "facturas", "social", "salud", "mayores", "jovenes",
               "empleo", "emergencias", "bonos", "transporte", "deporte", "cultura", "premios")
# Empty templates some bodies leave in the deadline field: "abierto desde  hasta .", "cerrado el dia ."
_EMPTY_NOTE = re.compile(r"(desde|hasta|el dia)\s*\.?\s*$|desde\s+hasta")
# Titles that say the money goes to organisations, even when the BDNS also lists individuals.
_FOR_ORGANISATIONS = re.compile(
    r"\b(a|para|de) (las |los )?(entidades|asociaciones|ayuntamientos|entidades locales|municipios|clubes"
    r"|federaciones|fundaciones|centros (docentes|educativos|de formacion)|cofradias|comunidades de regantes"
    r"|organizaciones|ong|corporaciones locales)\b|entidades (de formacion|sin animo|sin fines|del tercer sector)")
# ...or when the "who can apply" paragraph starts with organisations: "Entidades de formación y agrupaciones..."
_ORGANISATIONS_APPLY = re.compile(
    r"^(podran (ser beneficiari\w+|solicitar\w*)[^.:]{0,80}?:?\s*)?(las |los )?(entidades|asociaciones|ayuntamientos"
    r"|municipios|clubes|federaciones|fundaciones|centros (docentes|educativos|de formacion)|cofradias|organizaciones"
    r"|corporaciones|comunidades de regantes)\b")
ME_KINDS = (1, 3, 4)  # beneficiary types the site serves

esc = html.escape


@dataclass
class Item:
    code: str
    title: str
    place: places.Place
    topics: list[str]
    beneficiaries: list[int]
    sectors: list[str]
    window: deadlines.Window
    status: str
    note: str | None
    budget: float | None
    who: str | None
    document: dict | None
    bulletin: dict | None
    office_url: str | None
    received: dt.date | None
    first_seen: dt.date
    for_organisations: bool = False

    @property
    def official_url(self) -> str:
        return bdns.call_url(self.code)

    @property
    def placed(self) -> bool:
        """Town and district grants need a known place: without one they would show up all over Spain."""
        return bool(self.place.scope) or self.place.kind not in ("municipio", "comarca")

    @property
    def listed(self) -> bool:
        return self.status in LISTED and self.placed


# ---------------------------------------------------------------------------------------------- items

def items_from(db: dict, today: dt.date) -> list[Item]:
    """One Item per announcement open to the public, best first."""
    items = []
    for code, call in db["calls"].items():
        raw_title = call.get("titulo") or call.get("titulo_boletin") or ""
        if looks_abbreviated(raw_title) and call.get("titulo_boletin"):
            raw_title = call["titulo_boletin"]
        if not store.is_public(raw_title) or "instrumental" in normalize(call.get("tipo")):
            continue
        win = deadlines.window(call)
        status = deadlines.status(win, today)
        received = deadlines.iso_date(call.get("fechaRecepcion"))
        first_seen = dt.date.fromisoformat(call["first_seen"])
        if status == "sin_fecha" and (today - (received or first_seen)).days > STALE_DAYS:
            continue
        place = places.place_of(call)
        kinds = call.get("beneficiarios") or [5]
        found = topics.classify(raw_title, call.get("titulo_cooficial"), call.get("titulo_boletin"),
                                purpose=call.get("finalidad"), for_businesses=1 not in kinds)
        note = (call.get("textFin") or "").strip()
        usable_note = (win.end is None and 3 <= len(note) <= 60 and normalize(note) != "no procede"
                       and not _EMPTY_NOTE.search(normalize(note)))
        items.append(Item(
            code=code, title=clean_title(raw_title, names=tuple(filter(None, (place.town,)))), place=place,
            topics=found, beneficiaries=kinds, sectors=call.get("sectores") or [], window=win, status=status,
            note=note if usable_note else None, budget=call.get("presupuesto") or None, who=call.get("quien"),
            document=call.get("documento"), bulletin=call.get("boletin"), office_url=call.get("sede"),
            received=received, first_seen=first_seen,
            for_organisations=bool(_FOR_ORGANISATIONS.search(normalize(raw_title))
                                   or _ORGANISATIONS_APPLY.search(normalize(call.get("quien"))))))
    _fill_town_provinces(items)
    return sorted(items, key=_sort_key)


def _fill_town_provinces(items: list[Item]) -> None:
    """Town halls tagged only with their region get the province their other announcements use."""
    by_town = defaultdict(Counter)
    for item in items:
        if item.place.kind == "municipio" and item.place.province:
            by_town[(item.place.region, item.place.town_slug)][item.place.province] += 1
            by_town[(None, item.place.town_slug)][item.place.province] += 1
    for item in items:
        place = item.place
        if place.kind == "municipio" and not place.province:
            guesses = by_town.get((place.region, place.town_slug)) or by_town.get((None, place.town_slug))
            if guesses and len(guesses) == 1:
                province = next(iter(guesses))
                item.place = dataclasses.replace(place, province=province, region=geo.region_of(province),
                                                 scope=place.scope or (province,))


def _sort_key(item: Item) -> tuple:
    """Open first, soonest deadline first; everyday aid before prizes and university calls."""
    if item.status == "abierta":
        second = item.window.end.toordinal()
    elif item.status == "proxima":
        second = item.window.start.toordinal()
    else:
        second = -(item.received or item.first_seen).toordinal()
    niche = item.topics[0] == "premios" or item.place.kind == "otros"
    return _ORDER[item.status], niche, second, item.title


def files_for(item: Item) -> list[str]:
    """Which data file(s) the item goes in: "ES" (all of Spain) or the regions it applies to."""
    if not item.placed:
        return []
    scope = item.place.scope or (geo.SPAIN,)
    if geo.SPAIN in scope:
        return [geo.SPAIN]
    return sorted({r for r in geo.REGIONS for code in scope if r.startswith(code) or code.startswith(r)})


def item_json(item: Item) -> dict:
    w, place = item.window, item.place
    document = item.document or {}
    data = {
        "c": item.code, "t": item.title, "o": place.organ, "k": _KIND_LETTERS[place.kind], "sc": list(place.scope),
        "r": place.region, "p": place.province, "tn": place.town, "ts": place.town_slug,
        "b": item.beneficiaries, "g": item.topics, "sec": item.sectors,
        "s": w.start.isoformat() if w.start else None, "e": w.end.isoformat() if w.end else None,
        "x": _PRECISION[w.precision], "pl": w.period, "n": item.note,
        "a": round(item.budget) if item.budget else None, "w": item.who,
        "d": document.get("id"), "dp": 1 if (document.get("nombre") or "").lower().endswith(".pdf") else None,
        "bu": (item.bulletin or {}).get("url"), "se": item.office_url,
        "f": item.first_seen.isoformat(), "rv": item.received.isoformat() if item.received else None,
        "og": 1 if item.for_organisations else None,
    }
    return {key: value for key, value in data.items() if value not in (None, [], "")}


# ----------------------------------------------------------------------------------------- formatting

def fecha(day: dt.date, today: dt.date) -> str:
    text = f"{day.day} de {MONTHS[day.month - 1]}"
    return text if day.year == today.year else f"{text} de {day.year}"


def fecha_larga(day: dt.date) -> str:
    return f"{day.day} de {MONTHS[day.month - 1]} de {day.year}"


def money(amount: float) -> str:
    return f"{round(amount):,}".replace(",", ".") + " €"


def number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def deadline_text(item: Item, today: dt.date) -> tuple[str, str]:
    """(headline, detail) describing the application window, e.g. ('Abierta', 'hasta el 26 de octubre…')."""
    win = item.window
    if item.status == "proxima":
        return "Próximamente", f"se abre el {fecha(win.start, today)}"
    if item.status == "sin_fecha":
        return "Plazo", item.note or "consulta las bases"
    when = fecha(win.end, today)
    if item.status == "cerrada":
        return "Cerrada", f"el {when}"
    if item.status == "revisar":
        return "Puede haber cerrado", f"plazo de {win.period or 'solicitud'} desde su publicación; comprueba las bases"
    if win.precision == "exact":
        left = (win.end - today).days
        tail = "último día" if left == 0 else ("queda 1 día" if left == 1 else f"quedan {left} días")
        return "Abierta", f"hasta el {when} ({tail})"
    if win.precision == "computed":
        return "Abierta", f"plazo de {win.period} desde su publicación: hasta el {when} aprox."
    return "Abierta", f"plazo de {win.period} desde su publicación: al menos hasta el {when}"


def badge(item: Item, today: dt.date) -> tuple[str, str, str, str]:
    """(tone, top line, big text, bottom line) for the date block at the left of a card."""
    win = item.window
    if item.status == "proxima":
        return "upcoming", "Abre", str(win.start.day), MONTHS_SHORT[win.start.month - 1]
    if item.status == "sin_fecha":
        return "none", "Plazo", "—", "ver bases"
    if item.status == "revisar":
        return "check", "Plazo", "?", "revisar"
    left = (win.end - today).days
    tone = "urgent" if left <= 3 else "soon" if left <= 10 else "open"
    if win.precision == "exact":
        bottom = "hoy" if left == 0 else "mañana" if left == 1 else f"{left} días"
    else:
        bottom = "aprox." if win.precision == "computed" else "al menos"
    return tone, MONTHS_SHORT[win.end.month - 1], str(win.end.day), bottom


def place_line(item: Item) -> str:
    place = item.place
    if place.kind == "estado":
        return f"{place.organ} · Toda España"
    if place.kind in ("municipio", "comarca") and place.province:
        return f"{place.organ} · {geo.province_name(place.province)}"
    if place.kind == "otros" and place.region:
        return f"{place.organ} · {geo.REGIONS[place.region]}"
    return place.organ


# ---------------------------------------------------------------------------------------------- icons

ICONS = {
    "mark": '<svg viewBox="0 0 32 32" aria-hidden="true"><rect width="32" height="32" rx="9" fill="currentColor"/>'
            '<path d="M9.5 16.5l4.5 4.5 8.5-9.5" fill="none" stroke="#fff" stroke-width="3.2" '
            'stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "lock": '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4.5" y="10.5" width="15" height="10" rx="2.5" '
            'fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" fill="none" '
            'stroke="currentColor" stroke-width="1.8"/></svg>',
    "arrow": '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    "user": '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8.5" r="3.8" fill="none" '
            'stroke="currentColor" stroke-width="1.8"/><path d="M4.5 20c1.2-3.6 4.2-5.5 7.5-5.5s6.3 1.9 7.5 5.5" '
            'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
}


# ---------------------------------------------------------------------------------------------- cards

def card(item: Item, root: str, today: dt.date) -> str:
    tone, top, big, bottom = badge(item, today)
    topic = topics.BY_SLUG[item.topics[0]]
    tags = [f'<a class="tag" href="{root}tema/{topic.slug}/">{esc(topic.label)}</a>']
    tags += [f'<span class="tag tag-soft">{esc(extract.BENEFICIARY_TYPES[k])}</span>'
             for k in item.beneficiaries if k in ME_KINDS]
    if item.budget:
        tags.append(f'<span class="tag tag-money">{money(item.budget)}</span>')
    head, detail = deadline_text(item, today)
    rows = [f"<dt>Plazo</dt><dd>{esc(head)}: {esc(detail)}</dd>"]
    if item.who:
        rows.append(f"<dt>Para quién</dt><dd>{esc(item.who)}</dd>")
    if item.sectors and len(item.sectors) < 8:
        rows.append(f"<dt>Sectores</dt><dd>{esc(', '.join(extract.SECTIONS[s] for s in item.sectors))}</dd>")
    if item.received:
        rows.append(f"<dt>Registrada</dt><dd>{fecha(item.received, today)} · código BDNS {item.code}</dd>")
    links = [f'<a href="{esc(item.official_url)}" target="_blank" rel="noopener">Ficha oficial</a>']
    if item.document:
        label = "Bases (PDF)" if (item.document.get("nombre") or "").lower().endswith(".pdf") else "Documento"
        links.append(f'<a href="{esc(bdns.document_url(item.document["id"]))}" target="_blank" rel="noopener">'
                     f'{label}</a>')
    if item.bulletin and item.bulletin.get("url"):
        links.append(f'<a href="{esc(item.bulletin["url"])}" target="_blank" rel="noopener">Boletín oficial</a>')
    if item.office_url:
        links.append(f'<a href="{esc(item.office_url)}" target="_blank" rel="noopener">Sede electrónica</a>')
    end = ""
    if item.window.end and item.status == "abierta":
        end = f' data-end="{item.window.end.isoformat()}"'
        links.append('<button class="link-button" type="button" data-ics hidden>Añadir al calendario</button>')
    return (f'<article class="aid" data-code="{item.code}"{end}>'
            f'<div class="aid-date tone-{tone}"><span class="aid-top">{esc(top)}</span>'
            f'<span class="aid-big">{esc(big)}</span><span class="aid-bottom">{esc(bottom)}</span></div>'
            f'<div class="aid-body"><h3 class="aid-title"><a href="{esc(item.official_url)}" target="_blank" '
            f'rel="noopener">{esc(item.title)}</a></h3>'
            f'<p class="aid-org">{esc(place_line(item))}</p><p class="aid-tags">{"".join(tags)}</p>'
            f'<details class="aid-more"><summary>Detalles</summary><dl>{"".join(rows)}</dl>'
            f'<p class="aid-links">{"".join(links)}</p></details></div></article>\n')


def cards(items: list[Item], root: str, today: dt.date, empty: str = "") -> str:
    if not items:
        return f'<p class="empty">{esc(empty)}</p>' if empty else ""
    return f'<div class="aids">\n{"".join(card(i, root, today) for i in items)}</div>'


# ---------------------------------------------------------------------------------------------- pages

def page(*, title: str, description: str, root: str, body: str, today: dt.date, kind: str,
         canonical: str | None = None, feed: str | None = None) -> str:
    head = []
    if canonical:
        head.append(f'<link rel="canonical" href="{esc(canonical)}">')
    if feed:
        head.append(f'<link rel="alternate" type="application/rss+xml" title="{esc(title)}" href="{feed}">')
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#1d4ed8">
{''.join(head)}
<link rel="icon" href="{root}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}style.css">
</head>
<body data-page="{kind}" data-root="{root}">
<a class="skip" href="#main">Saltar al contenido</a>
<header class="topbar"><div class="wrap topbar-inner">
<a class="brand" href="{root}">{ICONS["mark"]}<span>{SITE_NAME}</span></a>
<nav class="nav" aria-label="Principal">
<a href="{root}#para-ti">Para ti</a><a href="{root}buscar.html">Buscar</a><a href="{root}acerca.html">Cómo funciona</a>
</nav>
<button class="profile-button" type="button" data-open-profile>{ICONS["user"]}<span data-profile-label>Mi perfil</span></button>
</div></header>
<main id="main">
{body}
</main>
<footer class="footer"><div class="wrap footer-inner">
<div><a class="brand brand-small" href="{root}">{ICONS["mark"]}<span>{SITE_NAME}</span></a>
<p>Todas las ayudas públicas para particulares, autónomos y empresas de España, actualizadas cada día.</p></div>
<div><p>Datos de la <a href="https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias">Base de Datos Nacional
de Subvenciones</a> (Ministerio de Hacienda), actualizados el {fecha_larga(today)}.</p>
<p>Información orientativa: lee siempre las bases oficiales antes de pedir una ayuda. Esta web no es una
administración pública.</p></div>
<nav aria-label="Pie de página"><a href="{root}acerca.html">Cómo funciona</a><a href="{root}privacidad.html">Privacidad</a>
<a href="{root}feed.xml">RSS</a></nav>
</div></footer>
<script src="{root}app.js" defer></script>
</body>
</html>
"""


def _stats(listed: list[Item], today: dt.date) -> dict:
    week = today + dt.timedelta(days=7)
    return {
        "open": sum(i.status == "abierta" for i in listed),
        "week": sum(i.status == "abierta" and i.window.end <= week for i in listed),
        "new": sum((today - (i.received or i.first_seen)).days < 7 for i in listed),
        "total": len(listed),
    }


def _home(listed: list[Item], stats: dict, region_counts: dict, national: int, today: dt.date) -> str:
    counts = Counter(slug for item in listed for slug in item.topics)
    tiles = {"personas": [], "empresas": []}
    for topic in sorted(topics.TOPICS, key=lambda t: _TILE_ORDER.index(t.slug) if t.slug in _TILE_ORDER else 99):
        if counts[topic.slug]:
            tiles[topic.family].append(
                f'<a class="tile" href="tema/{topic.slug}/"><span class="tile-label">{esc(topic.label)}</span>'
                f'<span class="tile-count">{number(counts[topic.slug])} ayudas</span></a>')
    regions = "".join(
        f'<a class="region" href="comunidad/{geo.region_slug(code)}/"><span>{esc(name)}</span>'
        f'<span class="count">{number(region_counts.get(code, 0))}</span></a>'
        for code, name in sorted(geo.REGIONS.items(), key=lambda pair: normalize(pair[1])))
    return f"""<section class="hero"><div class="wrap hero-inner">
<div class="hero-text">
<p class="eyebrow">Gratis · Sin registro · Toda España</p>
<h1>Las ayudas públicas que te corresponden, en un solo sitio</h1>
<p class="lead">Cada día revisamos el registro oficial de subvenciones y te mostramos las convocatorias abiertas
para particulares, autónomos y empresas de tu zona.</p>
<div class="hero-actions"><button class="btn btn-primary" type="button" data-open-profile>Encontrar mis ayudas
{ICONS["arrow"]}</button><a class="btn btn-ghost" href="buscar.html">Ver todas</a></div>
<p class="hero-note">{ICONS["lock"]}Tus datos se quedan en tu dispositivo: sin cuentas ni servidores.</p>
</div>
<div class="hero-stats" aria-label="Resumen de hoy">
<p class="stats-title">Hoy en toda España</p>
<div class="stat"><strong>{number(stats["open"])}</strong><span>ayudas abiertas hoy</span></div>
<div class="stat stat-warn"><strong>{number(stats["week"])}</strong><span>cierran en los próximos 7 días</span></div>
<div class="stat"><strong>{number(stats["new"])}</strong><span>nuevas esta semana</span></div>
<div class="stat"><strong>{number(national)}</strong><span>para toda España</span></div>
<p class="stat-note">Actualizado el {fecha_larga(today)}</p>
</div>
</div></section>
<section id="para-ti" class="foryou" aria-live="polite"></section>
<section class="section"><div class="wrap">
<div class="section-head"><h2>Explora por tema</h2><a href="buscar.html">Abrir el buscador {ICONS["arrow"]}</a></div>
<h3 class="family">Para personas y familias</h3><div class="tiles">{"".join(tiles["personas"])}</div>
<h3 class="family">Para autónomos y empresas</h3><div class="tiles">{"".join(tiles["empresas"])}</div>
</div></section>
<section class="section section-alt"><div class="wrap">
<div class="section-head"><h2>Por comunidad autónoma</h2></div>
<div class="regions">{regions}</div>
</div></section>
<section class="section"><div class="wrap">
<div class="section-head"><h2>Cómo funciona</h2></div>
<ol class="steps">
<li><strong>Cuéntanos quién eres</strong><span>Particular, autónomo o empresa, dónde vives y qué te interesa. Tarda un
minuto y se guarda solo en tu navegador.</span></li>
<li><strong>Te mostramos lo que encaja</strong><span>Ayudas de tu ayuntamiento, tu diputación, tu comunidad y el
Estado, ordenadas por fecha de cierre.</span></li>
<li><strong>Pídelas a tiempo</strong><span>Cada ficha enlaza a las bases oficiales. Guarda las que te interesan o
añade el plazo a tu calendario.</span></li>
</ol>
</div></section>
"""


def _list_page(*, crumbs: list[tuple[str, str | None]], heading: str, lead: str, stats: dict, search_link: str,
               sections: list[tuple[str, str]], root: str) -> str:
    trail = " <span>›</span> ".join(f'<a href="{href}">{esc(label)}</a>' if href else f"<span>{esc(label)}</span>"
                                    for label, href in crumbs)
    parts = [f'<div class="wrap"><nav class="crumbs" aria-label="Ruta">{trail}</nav>',
             f'<header class="page-head"><h1>{esc(heading)}</h1><p class="lead">{esc(lead)}</p>',
             f'<div class="mini-stats"><span><strong>{number(stats["open"])}</strong> abiertas</span>'
             f'<span><strong>{number(stats["week"])}</strong> cierran en 7 días</span>'
             f'<span><strong>{number(stats["new"])}</strong> nuevas esta semana</span></div>',
             f'<a class="btn btn-primary" href="{root}{search_link}">Filtrar en el buscador {ICONS["arrow"]}</a>'
             f'</header>']
    for title, content in sections:
        if content:
            parts.append(f'<section class="block"><h2>{esc(title)}</h2>{content}</section>')
    parts.append("</div>")
    return "\n".join(parts)


def _links(entries: list[tuple[str, str, int]]) -> str:
    if not entries:
        return ""
    return '<ul class="link-grid">' + "".join(
        f'<li><a href="{href}">{esc(label)}</a> <span>{number(count)}</span></li>' for href, label, count in entries
    ) + "</ul>"


ABOUT = """<div class="wrap prose">
<h1>Cómo funciona Ajudes</h1>
<p class="lead">Ajudes reúne en un solo sitio las ayudas y subvenciones públicas para particulares, autónomos y
empresas de toda España: del Estado, de las comunidades autónomas, de las diputaciones y de los ayuntamientos.</p>
<h2>De dónde salen los datos</h2>
<p>Todas las convocatorias vienen de la <a href="https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias">Base de
Datos Nacional de Subvenciones</a> (BDNS), el registro oficial del Ministerio de Hacienda donde cada administración
publica sus ayudas. Reutilizamos esos datos según sus
<a href="https://www.infosubvenciones.es/bdnstrans/GE/es/avisolegal">condiciones de uso</a>. La web se actualiza una
vez al día y reúne lo publicado en los últimos seis meses.</p>
<h2>Cómo elegimos las ayudas para ti</h2>
<p>Con tu perfil comparamos tres cosas de cada convocatoria: para quién es (particulares, autónomos y pymes o grandes
empresas, según la BDNS), dónde se aplica (todo el país, tu comunidad, tu provincia o tu municipio) y de qué trata. El
tema se deduce del título, así que alguna ayuda puede aparecer en un tema que no le corresponde. Los requisitos
concretos, como la renta o la antigüedad en el padrón, solo están en las bases oficiales.</p>
<h2>Cómo calculamos los plazos</h2>
<p>Si la convocatoria da una fecha, la mostramos tal cual. Si da un plazo («10 días hábiles desde su publicación»), lo
contamos desde la fecha del boletín oficial sin contar fines de semana. No conocemos todos los festivos, así que el
plazo real puede acabar uno o dos días después. Si aún no sabemos cuándo se publicó, damos la fecha más temprana
posible («al menos hasta…»).</p>
<h2>Importante</h2>
<p>Ajudes no es una administración pública ni tramita ayudas. La información es orientativa: antes de pedir una ayuda,
lee siempre las bases oficiales enlazadas en cada ficha.</p>
</div>"""

PRIVACY = """<div class="wrap prose">
<h1>Privacidad</h1>
<p class="lead">Ajudes no tiene cuentas de usuario ni servidores que guarden tus datos.</p>
<h2>Tu perfil se queda en tu dispositivo</h2>
<p>Lo que indicas en tu perfil (si eres particular o empresa, dónde vives, tu edad aproximada y tus intereses) y las
ayudas que guardas se almacenan solo en el almacenamiento local de tu navegador. No se envían a ningún sitio:
la web descarga la lista pública de ayudas y hace la selección en tu propio dispositivo.</p>
<h2>Sin cookies de seguimiento</h2>
<p>No usamos cookies, analítica ni publicidad.</p>
<h2>Borrar tus datos</h2>
<p>Puedes borrarlos cuando quieras con este botón, o borrando los datos del sitio en tu navegador.</p>
<p><button class="btn btn-ghost" type="button" data-clear-data>Borrar mi perfil y mis ayudas guardadas</button></p>
</div>"""

SEARCH = """<div class="wrap search">
<header class="search-head"><h1>Buscar ayudas</h1>
<p class="lead" data-search-summary>Filtra por lugar, por tema y por quién puede pedirlas.</p></header>
<div class="search-layout">
<aside class="filters" data-filters aria-label="Filtros"></aside>
<section class="results" aria-live="polite">
<div class="results-bar" data-results-bar></div>
<div class="aids" data-results><p class="empty">Cargando ayudas…</p></div>
<button class="btn btn-ghost more" type="button" data-more hidden>Mostrar más</button>
</section>
</div>
<noscript><p class="empty">El buscador necesita JavaScript. También puedes navegar por comunidad, provincia o tema
desde la <a href="./">portada</a>.</p></noscript>
</div>"""


def _rss(items: list[Item], title: str, link: str, today: dt.date) -> str:
    entries = sorted((i for i in items if i.listed), key=lambda i: (i.first_seen, i.code), reverse=True)
    rows = []
    for item in entries[:100]:
        head, detail = deadline_text(item, today)
        published = format_datetime(dt.datetime.combine(item.first_seen, dt.time(6, 0), tzinfo=dt.timezone.utc))
        rows.append(f"<item><title>{esc(item.title)}</title><link>{esc(item.official_url)}</link>"
                    f"<guid isPermaLink=\"false\">bdns-{item.code}</guid><pubDate>{published}</pubDate>"
                    f"<description>{esc(place_line(item))}. {esc(head)}: {esc(detail)}</description></item>\n")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0"><channel>\n'
            f"<title>{esc(title)}</title><link>{esc(link)}</link><description>{esc(title)}</description>"
            f"<language>es</language>\n{''.join(rows)}</channel></rss>\n")


FAVICON = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="9" '
           'fill="#1d4ed8"/><path d="M9.5 16.5l4.5 4.5 8.5-9.5" fill="none" stroke="#fff" stroke-width="3.2" '
           'stroke-linecap="round" stroke-linejoin="round"/></svg>\n')


# ---------------------------------------------------------------------------------------------- build

def build(items: list[Item], out: Path, today: dt.date, site_url: str = "", telegram_url: str = "") -> dict:
    """Write the whole site into `out` (replacing what was there). Returns a few counts."""
    site_url = site_url.rstrip("/") + "/" if site_url else ""
    if out.exists():
        shutil.rmtree(out)
    (out / "data" / "r").mkdir(parents=True)
    for asset in ("style.css", "app.js"):
        shutil.copy(STATIC / asset, out / asset)
    (out / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    pages: list[str] = []

    def write(path: str, text: str) -> None:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def publish(path: str, *, title: str, description: str, body: str, kind: str, feed: str | None = None) -> None:
        """Write one page. `path` is its public address: "" (home), "buscar.html" or "tema/bebes/"."""
        filename = path + "index.html" if path == "" or path.endswith("/") else path
        root = "../" * filename.count("/") or "./"
        write(filename, page(title=title, description=description, root=root, body=body.replace("{root}", root),
                             today=today, kind=kind, canonical=(site_url + path) if site_url else None, feed=feed))
        pages.append(path)

    listed = [item for item in items if item.listed]
    stats = _stats(listed, today)

    # Data files for the in-browser app: all of Spain, then one file per region.
    by_file = defaultdict(list)
    for item in listed:
        for name in files_for(item):
            by_file[name].append(item)
    for name in [geo.SPAIN, *geo.REGIONS]:
        rows = [item_json(item) for item in by_file.get(name, [])]
        write(f"data/r/{name}.json", json.dumps(rows, ensure_ascii=False, separators=(",", ":")))

    towns = defaultdict(lambda: defaultdict(list))  # province -> town slug -> items
    for item in listed:
        if item.place.kind == "municipio" and item.place.province:
            towns[item.place.province][item.place.town_slug].append(item)
    region_counts = {code: len(by_file.get(code, [])) for code in geo.REGIONS}
    topic_counts = Counter(slug for item in listed for slug in item.topics)
    meta = {
        "updated": today.isoformat(), "stats": stats, "national": len(by_file.get(geo.SPAIN, [])),
        "regions": [{"code": code, "name": name, "slug": geo.region_slug(code), "count": region_counts[code],
                     "provinces": [{"code": p, "name": geo.PROVINCES[p], "slug": geo.province_slug(p)}
                                   for p in geo.PROVINCES if p.startswith(code)]}
                    for code, name in sorted(geo.REGIONS.items(), key=lambda pair: normalize(pair[1]))],
        "towns": {province: sorted(([slug, its[0].place.town, len(its)] for slug, its in by_town.items()),
                                   key=lambda row: normalize(row[1]))
                  for province, by_town in towns.items()},
        "topics": [{"slug": t.slug, "label": t.label, "family": t.family, "count": topic_counts[t.slug]}
                   for t in (*topics.TOPICS, topics.OTHER)],
        "kinds": {str(k): extract.BENEFICIARY_TYPES[k] for k in (*ME_KINDS, 5)},
        "sections": extract.SECTIONS,
    }
    write("data/meta.json", json.dumps(meta, ensure_ascii=False, separators=(",", ":")))

    # Readable pages.
    year = today.year
    publish("", title=f"Ayudas y subvenciones públicas en España ({year}) · {SITE_NAME}",
            description=f"{number(stats['open'])} ayudas abiertas hoy para particulares, autónomos y empresas. "
                        "Crea tu perfil en un minuto y mira las que encajan contigo. Gratis y sin registro.",
            body=_home(listed, stats, region_counts, meta["national"], today), kind="home", feed="feed.xml")
    publish("buscar.html", title=f"Buscar ayudas · {SITE_NAME}", body=SEARCH, kind="search",
            description="Busca ayudas y subvenciones por comunidad, provincia, municipio, tema y tipo de beneficiario.")
    publish("acerca.html", title=f"Cómo funciona · {SITE_NAME}", body=ABOUT, kind="about",
            description="De dónde salen los datos de Ajudes, cómo elegimos tus ayudas y cómo calculamos los plazos.")
    publish("privacidad.html", title=f"Privacidad · {SITE_NAME}", body=PRIVACY, kind="about",
            description="Ajudes no tiene cuentas ni servidores: tu perfil se queda en tu dispositivo.")
    write("feed.xml", _rss(listed, f"{SITE_NAME}: nuevas ayudas en España", site_url, today))

    for topic in (*topics.TOPICS, topics.OTHER):
        its = [i for i in listed if topic.slug in i.topics]
        nationwide = [i for i in its if files_for(i) == [geo.SPAIN]]
        local = [i for i in its if files_for(i) != [geo.SPAIN]]
        per_region = Counter(code for i in local for code in files_for(i))
        region_links = [(f"{{root}}buscar.html?g={topic.slug}&amp;c={code}", name, per_region[code])
                        for code, name in sorted(geo.REGIONS.items(), key=lambda pair: normalize(pair[1]))
                        if per_region[code]]
        publish(f"tema/{topic.slug}/", kind="list",
                title=f"{topic.label}: ayudas y subvenciones abiertas ({year}) · {SITE_NAME}",
                description=f"{topic.label}: {number(len(its))} ayudas públicas en España, con plazos y enlaces "
                            "a las bases oficiales.",
                body=_list_page(crumbs=[("Inicio", "{root}"), (topic.label, None)], heading=topic.label,
                                lead="Ayudas de este tema en toda España, ordenadas por fecha de cierre.",
                                stats=_stats(its, today), search_link=f"buscar.html?g={topic.slug}",
                                sections=[("Para toda España", cards(nationwide[:SECTION_LIMIT], "{root}", today)),
                                          ("Por comunidad autónoma", _links(region_links)),
                                          ("De comunidades, provincias y ayuntamientos",
                                           cards(local[:PAGE_LIMIT], "{root}", today,
                                                 "Ahora mismo no hay convocatorias abiertas de este tema."))],
                                root="{root}"))

    national = by_file.get(geo.SPAIN, [])
    for code, region_name in geo.REGIONS.items():
        region_items = by_file.get(code, [])
        regional = [i for i in region_items if i.place.kind in ("comunidad", "otros")]
        province_links = [(f"{{root}}provincia/{geo.province_slug(p)}/", geo.PROVINCES[p],
                           sum(1 for i in region_items if i.place.province == p))
                          for p in geo.PROVINCES if p.startswith(code)]
        publish(f"comunidad/{geo.region_slug(code)}/", kind="list", feed="feed.xml",
                title=f"Ayudas y subvenciones en {region_name} ({year}) · {SITE_NAME}",
                description=f"{number(len(region_items))} ayudas abiertas en {region_name}: de la comunidad, las "
                            "diputaciones y los ayuntamientos, con plazos.",
                body=_list_page(crumbs=[("Inicio", "{root}"), (region_name, None)],
                                heading=f"Ayudas en {region_name}",
                                lead=f"Convocatorias de {geo.GOVERNMENTS[code]}, las diputaciones y los "
                                     f"ayuntamientos de {region_name}, más {number(len(national))} para toda España.",
                                stats=_stats(region_items, today), search_link=f"buscar.html?c={code}",
                                sections=[(f"De {geo.GOVERNMENTS[code]} y otros organismos",
                                           cards(regional[:PAGE_LIMIT], "{root}", today,
                                                 "Ahora mismo no hay convocatorias abiertas de la comunidad.")),
                                          ("Por provincia", _links(province_links))],
                                root="{root}"))
        write(f"comunidad/{geo.region_slug(code)}/feed.xml",
              _rss(region_items, f"{SITE_NAME}: ayudas en {region_name}",
                   f"{site_url}comunidad/{geo.region_slug(code)}/", today))

    for province, province_name in geo.PROVINCES.items():
        region = geo.region_of(province)
        region_items = by_file.get(region, [])
        in_province = [i for i in region_items if i.place.province == province]
        provincial = [i for i in in_province if i.place.kind != "municipio"]
        town_links = [(f"{{root}}municipio/{geo.province_slug(province)}/{slug}/", its[0].place.town, len(its))
                      for slug, its in sorted(towns.get(province, {}).items(),
                                              key=lambda pair: normalize(pair[1][0].place.town))]
        regional = [i for i in region_items if i.place.kind in ("comunidad", "otros") and not i.place.province]
        publish(f"provincia/{geo.province_slug(province)}/", kind="list",
                title=f"Ayudas y subvenciones en {province_name} ({year}) · {SITE_NAME}",
                description=f"Ayudas abiertas en {province_name}: de la diputación, {len(town_links)} ayuntamientos "
                            f"y {geo.GOVERNMENTS[region]}, con plazos.",
                body=_list_page(crumbs=[("Inicio", "{root}"),
                                        (geo.REGIONS[region], f"{{root}}comunidad/{geo.region_slug(region)}/"),
                                        (province_name, None)],
                                heading=f"Ayudas en {province_name}",
                                lead=f"Convocatorias de la diputación o el cabildo, los ayuntamientos de la "
                                     f"provincia y {geo.GOVERNMENTS[region]}.",
                                stats=_stats(in_province + regional, today),
                                search_link=f"buscar.html?c={region}&p={province}",
                                sections=[("De la diputación y otros organismos provinciales",
                                           cards(provincial[:PAGE_LIMIT], "{root}", today)),
                                          ("Ayuntamientos con ayudas abiertas", _links(town_links)),
                                          (f"De {geo.GOVERNMENTS[region]}",
                                           cards(regional[:SECTION_LIMIT], "{root}", today))],
                                root="{root}"))

    for province, by_town in towns.items():
        region = geo.region_of(province)
        region_items = by_file.get(region, [])
        provincial = [i for i in region_items if i.place.province == province and i.place.kind != "municipio"]
        regional = [i for i in region_items if i.place.kind in ("comunidad", "otros") and not i.place.province]
        for slug, its in by_town.items():
            town = its[0].place.town
            publish(f"municipio/{geo.province_slug(province)}/{slug}/", kind="list",
                    title=f"Ayudas en {town} ({year}) · {SITE_NAME}",
                    description=f"Ayudas y subvenciones abiertas en {town} ({geo.province_name(province)}): del "
                                "ayuntamiento, la diputación, la comunidad y el Estado, con plazos.",
                    body=_list_page(crumbs=[("Inicio", "{root}"),
                                            (geo.REGIONS[region], f"{{root}}comunidad/{geo.region_slug(region)}/"),
                                            (geo.province_name(province),
                                             f"{{root}}provincia/{geo.province_slug(province)}/"),
                                            (town, None)],
                                    heading=f"Ayudas en {town}",
                                    lead=f"Convocatorias del Ayuntamiento de {town}, y las de la provincia y "
                                         f"la comunidad que también puedes pedir si vives allí.",
                                    stats=_stats(its, today),
                                    search_link=f"buscar.html?c={region}&p={province}&m={slug}",
                                    sections=[(f"Del Ayuntamiento de {town}", cards(its, "{root}", today)),
                                              (f"De la provincia de {geo.province_name(province)}",
                                               cards(provincial[:SECTION_LIMIT], "{root}", today)),
                                              (f"De {geo.GOVERNMENTS[region]}",
                                               cards(regional[:SECTION_LIMIT], "{root}", today))],
                                    root="{root}"))

    if site_url:
        rows = "".join(f"<url><loc>{esc(site_url + p)}</loc><lastmod>{today.isoformat()}</lastmod></url>\n"
                       for p in pages)
        write("sitemap.xml", '<?xml version="1.0" encoding="utf-8"?>\n'
                             f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n')
    write("robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: {site_url}sitemap.xml\n" if site_url else ""))
    return {"listed": len(listed), "open": stats["open"], "pages": len(pages)}
