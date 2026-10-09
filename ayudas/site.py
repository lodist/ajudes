"""Builds the static website (HTML pages, RSS feeds and sitemap) from the local data."""
import datetime as dt
import html
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from email.utils import format_datetime
from pathlib import Path

from . import bdns, deadlines, places, topics
from .text import clean_title, normalize

STATIC = Path(__file__).parent / "static"
SITE_NAME = "Ajudes"
MONTH_NAMES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
               "octubre", "noviembre", "diciembre")
LISTED = ("abierta", "proxima", "revisar", "sin_fecha")
STALE_DAYS = 90  # an announcement with no known deadline is dropped after three months
_ORDER = {"abierta": 0, "proxima": 1, "revisar": 2, "sin_fecha": 3, "cerrada": 4}
# Grants named for one association, or agreements with one, are not open to the public.
_NOT_PUBLIC = re.compile(r"\bnom+inativa\b|\bnom\.|^convenio|^conveni\b")
# Empty templates some bodies leave in the deadline field: "abierto desde  hasta .", "cerrado el dia ."
_EMPTY_NOTE = re.compile(r"(desde|hasta|el dia)\s*\.?\s*$|desde\s+hasta")
# The "Personas beneficiarias" section of the official extract: a heading, then text up to the next heading.
_BENEFICIARIES = re.compile(r"beneficiari(?:[ao]s?|s)?\b", re.IGNORECASE)
_HEADING_BEFORE = re.compile(
    r"(?:\n|\b(?:primer[oa]?|segund[oa]|tercer[oa]?|cuart[oa]|quint[oa]|sext[oa]|\d+\s*[.)\-–º°]+))"
    r"[\s.:\-–]*(?:las?\s+|los\s+)?(?:personas\s+)?$", re.IGNORECASE)
_NEXT_HEADING = re.compile(
    r"\n\s*(?:\d+\s*[.)\-–º°]|primer|segund|tercer|cuart|quint|sext|objet|finalidad|bases|cuant[ií]a|import|plazo"
    r"|termini|requisit)|\s(?:segund[oa]|tercer[oa]|cuart[oa]|quint[oa]|sext[oa])[.:]\s", re.IGNORECASE)

esc = html.escape


@dataclass
class Item:
    code: str
    title: str
    place: places.Place
    topics: list[str]
    window: deadlines.Window
    status: str
    note: str | None  # the official deadline wording, when no date could be worked out
    budget: float | None
    who: str | None
    official_url: str
    document: tuple[str, str] | None  # (link label, url)
    bulletin_url: str | None
    office_url: str | None
    received: dt.date | None
    first_seen: dt.date
    search: str


def items_from(db: dict, today: dt.date) -> list[Item]:
    """One Item per announcement open to the public, best first."""
    items = []
    for code, call in db["calls"].items():
        notices = call.get("anuncios") or []
        raw_title = call.get("descripcion") or next((n["titulo"] for n in notices if n.get("titulo")), "")
        if _NOT_PUBLIC.search(normalize(raw_title)) or "instrumental" in normalize(call.get("tipoConvocatoria")):
            continue
        win = deadlines.window(call)
        status = deadlines.status(win, today)
        received = deadlines.iso_date(call.get("fechaRecepcion"))
        first_seen = dt.date.fromisoformat(call["first_seen"])
        if status == "sin_fecha" and (today - (received or first_seen)).days > STALE_DAYS:
            continue
        place = places.place_of(call)
        title = clean_title(raw_title, names=(place.name,))
        found = topics.classify(raw_title, call.get("descripcionLeng"), *(n.get("titulo") for n in notices))
        note = (call.get("textFin") or "").strip()
        usable_note = (win.end is None and 3 <= len(note) <= 60 and normalize(note) != "no procede"
                       and not _EMPTY_NOTE.search(normalize(note)))
        items.append(Item(
            code=code, title=title, place=place, topics=found, window=win, status=status,
            note=note if usable_note else None,
            budget=call.get("presupuestoTotal") or None, who=_who(notices),
            official_url=bdns.call_url(code), document=_document(call.get("documentos") or []),
            bulletin_url=next((n["url"] for n in notices if n.get("url")), None),
            office_url=_fix_url(call.get("sedeElectronica")),
            received=received, first_seen=first_seen,
            search=normalize(" ".join([title, place.name, *(topics.BY_SLUG[t].label for t in found)])),
        ))
    return sorted(items, key=_sort_key)


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


def _who(notices: list[dict]) -> str | None:
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


def _document(documents: list[dict]) -> tuple[str, str] | None:
    """The document most likely to be the rules, in Spanish."""
    documents = [d for d in documents if d.get("id")]
    if not documents:
        return None

    def score(document: dict) -> int:
        name = normalize(document.get("nombre"))
        good = ("bases" in name) + ("convocatoria" in name or "extracto" in name) + ("cast" in name)
        bad = any(word in name for word in ("valencia", "anex", "model", "solicitud", "instancia"))
        return good - 2 * bad

    best = max(documents, key=score)
    label = "Bases (PDF)" if (best.get("nombre") or "").lower().endswith(".pdf") else "Documento"
    return label, bdns.document_url(best["id"])


def _fix_url(raw: str | None) -> str | None:
    """Repair the hand-typed office addresses: 'https//x', 'https: x', 'www.x.es'."""
    url = re.sub(r"^(https?)[:/\s]+", r"\1://", (raw or "").strip(), flags=re.IGNORECASE)
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        url = "https://" + url.lstrip("/")
    return url if re.match(r"^https?://[^\s/]+\.[^\s/]+", url) else None


def fecha(day: dt.date, today: dt.date) -> str:
    text = f"{day.day} de {MONTH_NAMES[day.month - 1]}"
    return text if day.year == today.year else f"{text} de {day.year}"


def money(amount: float) -> str:
    return f"{round(amount):,}".replace(",", ".") + " €"


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


def card(item: Item, root: str, today: dt.date) -> str:
    topic = topics.BY_SLUG[item.topics[0]]
    if item.place.kind == "municipio":
        place = f'<a class="place" href="{root}municipio/{item.place.slug}/">{esc(item.place.name)}</a>'
    else:
        place = f'<span class="place">{esc(item.place.name)}</span>'
    head, detail = deadline_text(item, today)
    who = f'<p class="who"><span>Para quién:</span> {esc(item.who)}</p>' if item.who else ""
    facts = []
    if item.budget:
        facts.append(f"presupuesto total: {money(item.budget)}")
    if item.received:
        facts.append(f"registrada el {fecha(item.received, today)}")
    facts_text = " · ".join(facts)
    facts_html = f'<p class="facts">{esc(facts_text[:1].upper() + facts_text[1:])}</p>' if facts else ""
    links = [f'<a href="{esc(item.official_url)}">Ficha oficial</a>']
    if item.document:
        links.append(f'<a href="{esc(item.document[1])}">{esc(item.document[0])}</a>')
    if item.bulletin_url:
        links.append(f'<a href="{esc(item.bulletin_url)}">Boletín oficial</a>')
    if item.office_url:
        links.append(f'<a href="{esc(item.office_url)}">Sede electrónica</a>')
    return (f'<li class="card" data-topics="{" ".join(item.topics)}" data-search="{esc(item.search)}">'
            f'<div class="meta"><a class="chip" href="{root}tema/{topic.slug}/">{esc(topic.label)}</a>{place}</div>'
            f'<h3><a href="{esc(item.official_url)}">{esc(item.title)}</a></h3>'
            f'<p class="when {item.status}"><strong>{esc(head)}</strong> · {esc(detail)}</p>{who}{facts_html}'
            f'<p class="links">{" · ".join(links)}</p></li>\n')


def _cards(items: list[Item], root: str, today: dt.date, empty: str = "") -> str:
    if not items:
        return f'<p class="empty">{esc(empty)}</p>' if empty else ""
    return f'<ul class="cards">\n{"".join(card(i, root, today) for i in items)}</ul>'


def page(*, title: str, description: str, root: str, body: str, today: dt.date,
         feed: str | None = None, canonical: str | None = None) -> str:
    head = []
    if canonical:
        head.append(f'<link rel="canonical" href="{esc(canonical)}">')
    if feed:
        head.append(f'<link rel="alternate" type="application/rss+xml" title="{esc(title)}" href="{feed}">')
    updated = f"{today.day} de {MONTH_NAMES[today.month - 1]} de {today.year}"
    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{''.join(head)}
<link rel="stylesheet" href="{root}style.css">
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="{root}">{SITE_NAME}</a>
<span class="region">Comunitat Valenciana</span>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">
<p>Datos de la <a href="https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias">Base de Datos Nacional de
Subvenciones</a> (Ministerio de Hacienda), actualizados el {updated}. Información orientativa: lee siempre las bases
oficiales antes de pedir una ayuda.</p>
<p><a href="{root}acerca.html">Acerca de esta web</a> · <a href="{root}feed.xml">RSS</a></p>
</div></footer>
<script src="{root}app.js" defer></script>
</body>
</html>
"""


def _home(listed: list[Item], towns: list[tuple[str, str, int]], today: dt.date, telegram_url: str) -> str:
    root = "./"
    open_now = sum(i.status == "abierta" for i in listed)
    counts = Counter(slug for item in listed for slug in set(item.topics))
    everyday_first = sorted((*topics.TOPICS, topics.OTHER), key=lambda t: t.slug in ("premios", "otras"))
    chips = ['<button type="button" data-filter="" aria-pressed="true">Todas</button>']
    chips += [f'<button type="button" data-filter="{t.slug}" aria-pressed="false">{esc(t.label)} '
              f'<span>{counts[t.slug]}</span></button>'
              for t in everyday_first if counts[t.slug]]
    town_links = "".join(f'<li><a href="{root}municipio/{slug}/">{esc(name)}</a> <span>{n}</span></li>'
                         for slug, name, n in towns)
    alerts = f'<a href="{root}feed.xml">RSS</a>'
    if telegram_url:
        alerts += f' o en nuestro <a href="{esc(telegram_url)}">canal de Telegram</a>'
    return f"""<h1>Ayudas públicas para personas en la Comunitat Valenciana</h1>
<p class="lead">Cada día revisamos las convocatorias de ayuntamientos, diputaciones, la Generalitat y las
universidades. Ahora mismo hay <strong>{open_now} abiertas</strong>.</p>
<div class="filters">
<input id="q" type="search" placeholder="Busca tu municipio o una palabra: bebé, alquiler, beca…" aria-label="Buscar ayudas">
<div class="chips" role="group" aria-label="Temas">{''.join(chips)}</div>
</div>
<p class="count" id="count" aria-live="polite">{len(listed)} ayudas</p>
{_cards(listed, root, today, "Ahora mismo no hay convocatorias abiertas.")}
<h2>Ayudas por municipio</h2>
<ul class="towns">{town_links}</ul>
<h2>Recibe las nuevas ayudas</h2>
<p>Sigue las novedades por {alerts}. Cada municipio y cada tema tiene además su propio RSS.</p>
"""


def _town(name: str, local: list[Item], province: str | None, provincial: list[Item], regional: list[Item],
          closed: list[Item], today: dt.date) -> str:
    root = "../../"
    who = f"del Ayuntamiento de {name}"
    if province:
        who += f", de la Diputación de {places.PROVINCES[province]}"
    parts = [f"<h1>Ayudas en {esc(name)}</h1>",
             f'<p class="lead">Convocatorias abiertas {esc(who)} y de la Generalitat Valenciana.</p>',
             f"<h2>Del Ayuntamiento de {esc(name)}</h2>",
             _cards(local, root, today, "Ahora mismo no hay convocatorias abiertas del ayuntamiento.")]
    if provincial:
        parts += [f"<h2>De la Diputación de {places.PROVINCES[province]}</h2>", _cards(provincial, root, today)]
    if regional:
        parts += ["<h2>Para toda la Comunitat Valenciana</h2>", _cards(regional, root, today)]
    if closed:
        parts += ["<h2>Cerradas recientemente</h2>", _cards(closed, root, today)]
    parts.append(f'<p><a href="feed.xml">RSS de las ayudas de {esc(name)}</a></p>')
    return "\n".join(parts)


def _topic_page(topic: topics.Topic, items: list[Item], today: dt.date) -> str:
    return (f"<h1>{esc(topic.label)}</h1>\n"
            f'<p class="lead">Ayudas de este tema abiertas en la Comunitat Valenciana, con sus plazos y enlaces '
            f"oficiales.</p>\n{_cards(items, '../../', today, 'Ahora mismo no hay convocatorias abiertas de este tema.')}\n"
            f'<p><a href="feed.xml">RSS de este tema</a></p>')


ABOUT = """<h1>Acerca de Ajudes</h1>
<p>Ajudes reúne en un solo sitio las ayudas públicas para personas que publican los ayuntamientos, las
diputaciones, la Generalitat Valenciana y las universidades de la Comunitat Valenciana.</p>
<h2>De dónde salen los datos</h2>
<p>Todas las convocatorias vienen de la <a href="https://www.infosubvenciones.es/bdnstrans/GE/es/convocatorias">Base
de Datos Nacional de Subvenciones</a> (BDNS), el registro oficial del Ministerio de Hacienda donde cada administración
publica sus ayudas. Reutilizamos esos datos según sus
<a href="https://www.infosubvenciones.es/bdnstrans/GE/es/avisolegal">condiciones de uso</a>. La web se actualiza una
vez al día.</p>
<h2>Cómo calculamos los plazos</h2>
<p>Si la convocatoria da una fecha, la mostramos tal cual. Si da un plazo («10 días hábiles desde su publicación»), lo
contamos desde la fecha del boletín oficial sin contar fines de semana. No conocemos todos los festivos, así que el
plazo real puede acabar uno o dos días después. Si aún no sabemos cuándo se publicó, damos la fecha más temprana
posible («al menos hasta…»).</p>
<h2>Temas</h2>
<p>Los temas se asignan automáticamente a partir del título de cada convocatoria, así que alguna puede aparecer en un
tema que no le corresponde.</p>
<h2>Importante</h2>
<p>Esta web no es una administración pública ni tramita ayudas. La información es orientativa: antes de pedir una
ayuda, lee siempre las bases oficiales enlazadas en cada ficha.</p>
"""


def _rss(items: list[Item], title: str, link: str, today: dt.date) -> str:
    entries = sorted((i for i in items if i.status in LISTED), key=lambda i: (i.first_seen, i.code), reverse=True)
    rows = []
    for item in entries[:50]:
        head, detail = deadline_text(item, today)
        published = format_datetime(dt.datetime.combine(item.first_seen, dt.time(6, 0), tzinfo=dt.timezone.utc))
        rows.append(f"<item><title>{esc(item.place.name)} · {esc(item.title)}</title>"
                    f"<link>{esc(item.official_url)}</link><guid isPermaLink=\"false\">bdns-{item.code}</guid>"
                    f"<pubDate>{published}</pubDate><description>{esc(head)}: {esc(detail)}</description></item>\n")
    return ('<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0"><channel>\n'
            f"<title>{esc(title)}</title><link>{esc(link)}</link><description>{esc(title)}</description>"
            f"<language>es</language>\n{''.join(rows)}</channel></rss>\n")


def _sitemap(urls: list[str], today: dt.date) -> str:
    rows = "".join(f"<url><loc>{esc(url)}</loc><lastmod>{today.isoformat()}</lastmod></url>\n" for url in urls)
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n')


def build(items: list[Item], out: Path, today: dt.date, site_url: str = "", telegram_url: str = "") -> dict:
    """Write the whole site into `out` (replacing what was there). Returns a few counts."""
    site_url = site_url.rstrip("/") + "/" if site_url else ""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for asset in ("style.css", "app.js"):
        shutil.copy(STATIC / asset, out / asset)

    def write(path: str, text: str) -> None:
        target = out / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    year = today.year
    listed = [i for i in items if i.status in LISTED]
    regional = [i for i in listed if i.place.kind == "comunitat"]
    provincial = defaultdict(list)
    towns = defaultdict(list)
    for item in items:
        if item.place.kind == "municipio":
            towns[item.place.slug].append(item)
        elif item.place.kind == "diputacion" and item.place.province and item.status in LISTED:
            provincial[item.place.province].append(item)
    town_rows = sorted(((slug, its[0].place.name, sum(i.status in LISTED for i in its)) for slug, its in towns.items()),
                       key=lambda row: normalize(row[1]))
    pages = [""]

    open_now = sum(i.status == "abierta" for i in listed)
    write("index.html", page(
        title=f"Ayudas públicas en la Comunitat Valenciana ({year}) · {SITE_NAME}",
        description=f"{open_now} ayudas abiertas ahora para personas en la Comunitat Valenciana: bebés, colegio, "
                    "alquiler, becas y más. Actualizado cada día con datos oficiales.",
        root="./", body=_home(listed, town_rows, today, telegram_url), today=today, feed="feed.xml",
        canonical=site_url or None))
    write("feed.xml", _rss(items, f"{SITE_NAME}: nuevas ayudas en la Comunitat Valenciana", site_url, today))

    write("acerca.html", page(title=f"Acerca de · {SITE_NAME}", root="./", body=ABOUT, today=today,
                              description="De dónde salen los datos de Ajudes y cómo calculamos los plazos.",
                              canonical=f"{site_url}acerca.html" if site_url else None))
    pages.append("acerca.html")

    for topic in (*topics.TOPICS, topics.OTHER):
        its = [i for i in listed if topic.slug in i.topics]
        path = f"tema/{topic.slug}/"
        write(path + "index.html", page(
            title=f"{topic.label}: ayudas en la Comunitat Valenciana ({year}) · {SITE_NAME}",
            description=f"{topic.label}: ayudas abiertas en la Comunitat Valenciana ({year}), con plazos y enlaces "
                        "oficiales.",
            root="../../", body=_topic_page(topic, its, today), today=today, feed="feed.xml",
            canonical=site_url + path if site_url else None))
        write(path + "feed.xml", _rss(its, f"{SITE_NAME}: {topic.label}", site_url + path, today))
        pages.append(path)

    for slug, its in towns.items():
        name = its[0].place.name
        province = Counter(i.place.province for i in its if i.place.province).most_common(1)
        province = province[0][0] if province else None
        local = [i for i in its if i.status in LISTED]
        closed = [i for i in its if i.status == "cerrada"][:5]
        others = provincial.get(province, [])
        path = f"municipio/{slug}/"
        write(path + "index.html", page(
            title=f"Ayudas en {name} ({year}) · {SITE_NAME}",
            description=f"Ayudas y subvenciones abiertas en {name} ({year}): convocatorias del ayuntamiento, la "
                        "diputación y la Generalitat, con plazos.",
            root="../../", body=_town(name, local, province, others, regional, closed, today), today=today,
            feed="feed.xml", canonical=site_url + path if site_url else None))
        write(path + "feed.xml", _rss(local + others + regional, f"{SITE_NAME}: ayudas en {name}",
                                      site_url + path, today))
        pages.append(path)

    if site_url:
        write("sitemap.xml", _sitemap([site_url + p for p in pages], today))
    write("robots.txt", "User-agent: *\nAllow: /\n" + (f"Sitemap: {site_url}sitemap.xml\n" if site_url else ""))
    return {"listed": len(listed), "open": open_now, "towns": len(towns), "pages": len(pages)}
