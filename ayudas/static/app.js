/* Ajudes: the in-browser part.
 * The profile and the saved aid live only in this browser (localStorage). The site downloads
 * the public list of aid and does the matching here; nothing personal is ever sent anywhere. */
(() => {
  "use strict";

  const ROOT = document.body.dataset.root || "./";
  const PAGE = document.body.dataset.page || "";
  const KEYS = { profile: "ajudes.profile.v1", saved: "ajudes.saved.v1" };
  const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
    "octubre", "noviembre", "diciembre"];
  const MONTHS_SHORT = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const KIND_LABELS = { 1: "Particulares", 3: "Autónomos y pymes", 4: "Grandes empresas" };
  const BDNS = "https://www.infosubvenciones.es/bdnstrans";
  const DAY = 86400000;
  const TODAY = startOfDay(new Date());
  const PAGE_SIZE = 30;
  const GRACE = { x: 0, c: 3, l: 20 };

  const WHO_CHOICES = [
    [1, "Para mí y mi familia", "Ayudas para particulares: familia, estudios, vivienda…"],
    [3, "Mi negocio", "Autónomos y pequeñas o medianas empresas"],
    [4, "Una gran empresa", "Más de 250 personas o 50 millones de facturación"],
  ];
  const AGES = [["", "Prefiero no decirlo"], ["<18", "Menos de 18"], ["18-35", "De 18 a 35"],
    ["36-64", "De 36 a 64"], ["65+", "65 o más"]];
  const PERSON_INTERESTS = [
    ["bebes", "Tengo hijos o espero un bebé", ["bebes", "colegio"]],
    ["estudios", "Estudio o quiero estudiar", ["estudios"]],
    ["empleo", "Busco trabajo o formación", ["empleo"]],
    ["vivienda", "Vivo de alquiler o quiero comprar casa", ["vivienda"]],
    ["facturas", "Me cuesta llegar a fin de mes", ["facturas", "social"]],
    ["salud", "Discapacidad o dependencia", ["salud"]],
    ["mayores", "Soy una persona mayor", ["mayores"]],
    ["emergencias", "Me afectó una catástrofe", ["emergencias"]],
    ["deporte", "Hago deporte", ["deporte"]],
    ["cultura", "Cultura y ocio", ["cultura", "premios"]],
  ];
  const BUSINESS_INTERESTS = [
    ["emprender", "Empezar o hacer crecer el negocio", ["emprender"]],
    ["digital", "Digitalización", ["digital"]],
    ["contratacion", "Contratar personal", ["contratacion"]],
    ["energia", "Energía y sostenibilidad", ["energia"]],
    ["idi", "Innovación e I+D", ["idi"]],
    ["internacional", "Vender fuera de España", ["internacional"]],
    ["industria", "Inversión y maquinaria", ["industria"]],
  ];
  const SECTOR_GROUPS = [
    ["", "Cualquier sector", []], ["agro", "Agricultura, ganadería y pesca", ["A"]],
    ["industria", "Industria y energía", ["B", "C", "D", "E"]], ["construccion", "Construcción", ["F"]],
    ["comercio", "Comercio", ["G"]], ["transporte", "Transporte y logística", ["H"]],
    ["hosteleria", "Hostelería y turismo", ["I"]], ["tic", "Tecnología y comunicación", ["J", "K"]],
    ["finanzas", "Finanzas e inmobiliaria", ["L", "M"]], ["servicios", "Servicios profesionales", ["N", "O"]],
    ["educacion", "Educación", ["Q"]], ["salud", "Salud y servicios sociales", ["R"]],
    ["cultura", "Cultura, deporte y ocio", ["S"]], ["otros", "Otros servicios", ["P", "T", "U", "V"]],
  ];
  const STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3.6l2.6 5.3 5.8.9-4.2 4.1 1 5.8L12 17l-5.2 2.7 1-5.8-4.2-4.1 5.8-.9z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/></svg>';
  const LOCK = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4.5" y="10.5" width="15" height="10" rx="2.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>';
  const ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14m-5-5 5 5-5 5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  /* ---------------------------------------------------------------- helpers */

  const $ = (selector, element = document) => element.querySelector(selector);
  const $$ = (selector, element = document) => [...element.querySelectorAll(selector)];
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const plain = (value) => String(value || "").normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/’/g, "'").toLowerCase();
  const slugify = (value) => plain(value).replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  const number = (value) => String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const money = (value) => `${number(Math.round(value))} €`;
  function startOfDay(date) { return new Date(date.getFullYear(), date.getMonth(), date.getDate()); }
  function parseDate(iso) {
    if (!iso) return null;
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  const daysBetween = (from, to) => Math.round((to - from) / DAY);
  function fecha(date) {
    const text = `${date.getDate()} de ${MONTHS[date.getMonth()]}`;
    return date.getFullYear() === TODAY.getFullYear() ? text : `${text} de ${date.getFullYear()}`;
  }
  const officialUrl = (code) => `${BDNS}/GE/es/convocatoria/${encodeURIComponent(code)}`;
  const documentUrl = (id) => `${BDNS}/api/convocatorias/documentos?idDocumento=${encodeURIComponent(id)}`;

  const storage = {
    get(key, fallback) {
      try { const value = localStorage.getItem(key); return value ? JSON.parse(value) : fallback; } catch { return fallback; }
    },
    set(key, value) {
      try { localStorage.setItem(key, JSON.stringify(value)); return true; } catch { return false; }
    },
    remove(key) { try { localStorage.removeItem(key); } catch { /* storage blocked */ } },
  };

  /* ---------------------------------------------------------------- data */

  const requests = new Map();
  function getJSON(path) {
    if (!requests.has(path)) {
      requests.set(path, fetch(ROOT + path).then((response) => {
        if (!response.ok) throw new Error(`${path}: ${response.status}`);
        return response.json();
      }));
    }
    return requests.get(path);
  }

  let META = null;
  const TOPIC = {};
  const PROVINCE = {};
  const REGION = {};
  async function loadMeta() {
    if (META) return META;
    META = await getJSON("data/meta.json");
    for (const topic of META.topics) TOPIC[topic.slug] = topic;
    for (const region of META.regions) {
      REGION[region.code] = region;
      for (const province of region.provinces) PROVINCE[province.code] = { ...province, region: region.code };
    }
    return META;
  }

  /** All aid that applies to the given regions, plus the aid for all of Spain. null = every region. */
  async function loadItems(regions) {
    const meta = await loadMeta();
    const names = ["ES", ...(regions === null ? meta.regions.map((r) => r.code) : regions.filter(Boolean))];
    const lists = await Promise.all([...new Set(names)].map((name) => getJSON(`data/r/${name}.json`).catch(() => [])));
    const seen = new Set();
    const items = [];
    for (const list of lists) {
      for (const item of list) {
        if (!seen.has(item.c)) { seen.add(item.c); items.push(item); }
      }
    }
    return items;
  }

  /* ---------------------------------------------------------------- deadlines */

  function status(item) {
    const start = parseDate(item.s);
    const end = parseDate(item.e);
    if (start && TODAY < start) return "proxima";
    if (!end) return "sin_fecha";
    if (TODAY <= end) return "abierta";
    if (daysBetween(end, TODAY) <= GRACE[item.x || "x"]) return "revisar";
    return "cerrada";
  }

  function badge(item, state) {
    const start = parseDate(item.s);
    const end = parseDate(item.e);
    if (state === "proxima") return ["upcoming", "Abre", start.getDate(), MONTHS_SHORT[start.getMonth()]];
    if (state === "sin_fecha") return ["none", "Plazo", "—", "ver bases"];
    if (state === "revisar") return ["check", "Plazo", "?", "revisar"];
    if (state === "cerrada") return ["none", "Cerrada", end.getDate(), MONTHS_SHORT[end.getMonth()]];
    const left = daysBetween(TODAY, end);
    const tone = left <= 3 ? "urgent" : left <= 10 ? "soon" : "open";
    let bottom = left === 0 ? "hoy" : left === 1 ? "mañana" : `${left} días`;
    if (item.x === "c") bottom = "aprox.";
    if (item.x === "l") bottom = "al menos";
    return [tone, MONTHS_SHORT[end.getMonth()], end.getDate(), bottom];
  }

  function deadlineText(item, state) {
    const end = parseDate(item.e);
    if (state === "proxima") return ["Próximamente", `se abre el ${fecha(parseDate(item.s))}`];
    if (state === "sin_fecha") return ["Plazo", item.n || "consulta las bases"];
    if (state === "cerrada") return ["Cerrada", `el ${fecha(end)}`];
    if (state === "revisar") return ["Puede haber cerrado", `plazo de ${item.pl || "solicitud"} desde su publicación; comprueba las bases`];
    if (item.x === "c") return ["Abierta", `plazo de ${item.pl} desde su publicación: hasta el ${fecha(end)} aprox.`];
    if (item.x === "l") return ["Abierta", `plazo de ${item.pl} desde su publicación: al menos hasta el ${fecha(end)}`];
    const left = daysBetween(TODAY, end);
    const tail = left === 0 ? "último día" : left === 1 ? "queda 1 día" : `quedan ${left} días`;
    return ["Abierta", `hasta el ${fecha(end)} (${tail})`];
  }

  const ORDER = { abierta: 0, proxima: 1, revisar: 2, sin_fecha: 3, cerrada: 4 };
  const isNiche = (item) => item.g[0] === "premios" || item.k === "o";  // prizes, universities, foundations
  function byDeadline(a, b) {
    const sa = a._status;
    const sb = b._status;
    if (ORDER[sa] !== ORDER[sb]) return ORDER[sa] - ORDER[sb];
    const nicheA = isNiche(a);
    const nicheB = isNiche(b);
    if (nicheA !== nicheB) return nicheA ? 1 : -1;
    if (sa === "abierta") return a.e.localeCompare(b.e);
    if (sa === "proxima") return a.s.localeCompare(b.s);
    return (b.rv || b.f).localeCompare(a.rv || a.f);
  }

  /* ---------------------------------------------------------------- cards */

  function placeLine(item) {
    if (item.k === "e") return `${item.o} · Toda España`;
    if ((item.k === "m" || item.k === "a") && item.p && PROVINCE[item.p]) return `${item.o} · ${PROVINCE[item.p].name}`;
    if (item.k === "o" && item.r && REGION[item.r]) return `${item.o} · ${REGION[item.r].name}`;
    return item.o;
  }

  function cardHTML(item, match) {
    const state = item._status || status(item);
    const [tone, top, big, bottom] = badge(item, state);
    const topic = TOPIC[item.g[0]] || { slug: "otras", label: "Otras ayudas" };
    const url = officialUrl(item.c);
    const tags = [];
    if (match) for (const reason of match.reasons) tags.push(`<span class="tag tag-match">${esc(reason)}</span>`);
    tags.push(`<a class="tag" href="${ROOT}tema/${esc(topic.slug)}/">${esc(topic.label)}</a>`);
    for (const kind of item.b || []) if (KIND_LABELS[kind]) tags.push(`<span class="tag tag-soft">${KIND_LABELS[kind]}</span>`);
    if (item.a) tags.push(`<span class="tag tag-money">${money(item.a)}</span>`);
    const [head, detail] = deadlineText(item, state);
    const rows = [`<dt>Plazo</dt><dd>${esc(head)}: ${esc(detail)}</dd>`];
    if (item.w) rows.push(`<dt>Para quién</dt><dd>${esc(item.w)}</dd>`);
    if (item.sec && item.sec.length < 8 && META) {
      rows.push(`<dt>Sectores</dt><dd>${esc(item.sec.map((s) => META.sections[s] || s).join(", "))}</dd>`);
    }
    if (item.rv) rows.push(`<dt>Registrada</dt><dd>${fecha(parseDate(item.rv))} · código BDNS ${esc(item.c)}</dd>`);
    const links = [`<a href="${url}" target="_blank" rel="noopener">Ficha oficial</a>`];
    if (item.d) links.push(`<a href="${documentUrl(item.d)}" target="_blank" rel="noopener">${item.dp ? "Bases (PDF)" : "Documento"}</a>`);
    if (item.bu) links.push(`<a href="${esc(item.bu)}" target="_blank" rel="noopener">Boletín oficial</a>`);
    if (item.se) links.push(`<a href="${esc(item.se)}" target="_blank" rel="noopener">Sede electrónica</a>`);
    if (item.e && state === "abierta") links.push('<button class="link-button" type="button" data-ics>Añadir al calendario</button>');
    return `<article class="aid" data-code="${esc(item.c)}"${item.e ? ` data-end="${esc(item.e)}"` : ""}>`
      + `<div class="aid-date tone-${tone}"><span class="aid-top">${esc(top)}</span><span class="aid-big">${esc(big)}</span>`
      + `<span class="aid-bottom">${esc(bottom)}</span></div><div class="aid-body">`
      + `<h3 class="aid-title"><a href="${url}" target="_blank" rel="noopener">${esc(item.t)}</a></h3>`
      + `<p class="aid-org">${esc(placeLine(item))}</p><p class="aid-tags">${tags.join("")}</p>`
      + `<details class="aid-more"><summary>Detalles</summary><dl>${rows.join("")}</dl>`
      + `<p class="aid-links">${links.join("")}</p></details></div></article>`;
  }

  /** Adds the save star (and shows the calendar button) on every card in `container`. */
  function enhance(container = document) {
    const savedCodes = new Set(saved.list().map((entry) => entry.c));
    for (const card of $$(".aid", container)) {
      if ($(".aid-save", card)) continue;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "aid-save";
      button.dataset.save = "";
      button.innerHTML = STAR;
      const isSaved = savedCodes.has(card.dataset.code);
      button.setAttribute("aria-pressed", String(isSaved));
      button.setAttribute("aria-label", isSaved ? "Quitar de guardadas" : "Guardar esta ayuda");
      card.append(button);
      for (const hidden of $$("[data-ics][hidden]", card)) hidden.hidden = false;
    }
  }

  function snapshot(card) {
    const link = $(".aid-title a", card);
    return { c: card.dataset.code, t: link ? link.textContent : "", u: link ? link.href : "",
      o: ($(".aid-org", card) || {}).textContent || "", e: card.dataset.end || "" };
  }

  const saved = {
    list: () => storage.get(KEYS.saved, []),
    toggle(entry) {
      const list = saved.list();
      const index = list.findIndex((x) => x.c === entry.c);
      if (index >= 0) list.splice(index, 1); else list.unshift(entry);
      storage.set(KEYS.saved, list);
      return index < 0;
    },
  };

  function downloadCalendar(entry) {
    const end = parseDate(entry.e);
    if (!end) return;
    const pad = (n) => String(n).padStart(2, "0");
    const ymd = (d) => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
    const next = new Date(end.getTime() + DAY);
    const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+Z$/, "Z");
    const text = (s) => String(s).replace(/\\/g, "\\\\").replace(/([,;])/g, "\\$1").replace(/\r?\n/g, "\\n");
    const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Ajudes//ES", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
      "BEGIN:VEVENT", `UID:bdns-${entry.c}@ajudes`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${ymd(end)}`,
      `DTEND;VALUE=DATE:${ymd(next)}`, `SUMMARY:${text(`Último día: ${entry.t}`)}`,
      `DESCRIPTION:${text(`${entry.o}\n${entry.u}`)}`, `URL:${entry.u}`,
      "BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${text(`Quedan 3 días: ${entry.t}`)}`, "TRIGGER:-P3D", "END:VALARM",
      "END:VEVENT", "END:VCALENDAR"];
    const blob = new Blob([`${lines.join("\r\n")}\r\n`], { type: "text/calendar;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `ayuda-${entry.c}.ics`;
    document.body.append(link);
    link.click();
    setTimeout(() => { URL.revokeObjectURL(link.href); link.remove(); }, 1000);
  }

  document.addEventListener("click", (event) => {
    const star = event.target.closest("[data-save]");
    if (star) {
      const card = star.closest(".aid");
      const nowSaved = saved.toggle(snapshot(card));
      star.setAttribute("aria-pressed", String(nowSaved));
      star.setAttribute("aria-label", nowSaved ? "Quitar de guardadas" : "Guardar esta ayuda");
      document.dispatchEvent(new CustomEvent("ajudes:saved"));
      return;
    }
    const calendar = event.target.closest("[data-ics]");
    if (calendar) { downloadCalendar(snapshot(calendar.closest(".aid"))); return; }
    if (event.target.closest("[data-open-profile]")) { event.preventDefault(); openProfile(); return; }
    if (event.target.closest("[data-clear-data]")) {
      if (window.confirm("¿Borrar tu perfil y tus ayudas guardadas de este dispositivo?")) {
        storage.remove(KEYS.profile);
        storage.remove(KEYS.saved);
        refreshProfileButton();
        window.alert("Listo: no queda ningún dato tuyo en este dispositivo.");
      }
    }
  });

  /* ---------------------------------------------------------------- profile and matching */

  const getProfile = () => storage.get(KEYS.profile, null);

  function interestTopics(profile) {
    const wanted = new Set();
    for (const [key, , slugs] of [...PERSON_INTERESTS, ...BUSINESS_INTERESTS]) {
      if ((profile.interests || []).includes(key)) slugs.forEach((slug) => wanted.add(slug));
    }
    return wanted;
  }

  const sectorSections = (profile) => (SECTOR_GROUPS.find(([key]) => key === profile.sector) || [, , []])[2];

  function townMatches(name, slug) {
    if (!name || !slug) return false;
    return slugify(name) === slug || name.split("/").some((part) => slugify(part) === slug);
  }

  function placeMatches(item, profile) {
    const scope = item.sc && item.sc.length ? item.sc : ["ES"];
    if (!profile.province) return scope.includes("ES");
    if (item.k === "m" || item.k === "a") {
      if (!profile.town) return false;
      if (item.p && item.p !== profile.province) return false;
      if (!item.p && item.r && item.r !== profile.region) return false;
      if (item.k === "m") return townMatches(item.tn, profile.town);
      // A mancomunidad or consortium: only when its name mentions the user's town.
      const organ = slugify(item.o);
      return (profile.townName || "").split("/").some((part) => slugify(part) && organ.includes(slugify(part)));
    }
    return scope.some((code) => code === "ES" || profile.province.startsWith(code));
  }

  /** null if the item is not for this profile; otherwise why it matches and how well. */
  function match(item, profile) {
    const kinds = item.b && item.b.length ? item.b : [5];
    if (!kinds.includes(5) && !kinds.some((kind) => profile.who.includes(kind))) return null;
    if (!placeMatches(item, profile)) return null;
    const sections = sectorSections(profile);
    const businessOnly = !kinds.includes(1) && !kinds.includes(5);
    if (businessOnly && sections.length && item.sec && item.sec.length && item.sec.length < 8
        && !item.sec.some((s) => sections.includes(s))) return null;
    const business = profile.who.includes(3) || profile.who.includes(4);
    if (item.og && !business) return null;  // the title says it is for organisations
    const topics = item.g || [];
    if (topics.includes("jovenes") && (profile.age === "36-64" || profile.age === "65+")) return null;
    if (topics[0] === "mayores" && profile.age && profile.age !== "65+") return null;
    const wanted = interestTopics(profile);
    // Prizes and university calls only for people who said they care about culture or studies.
    if (topics[0] === "premios" && !wanted.has("premios")) return null;
    if (item.k === "o" && !business && !wanted.has("estudios")) return null;
    const reasons = [];
    let score = 0;
    if (item.k === "m") { reasons.push("Tu ayuntamiento"); score += 2; }
    if (topics.some((slug) => wanted.has(slug))) { reasons.push("Te interesa"); score += 3; }
    return { score, reasons };
  }

  function profileSummary(profile) {
    const parts = [];
    const who = profile.who.map((kind) => KIND_LABELS[kind]).filter(Boolean);
    if (who.length) parts.push(who.join(" y "));
    if (profile.townName) parts.push(profile.townName);
    if (profile.province && PROVINCE[profile.province]) parts.push(PROVINCE[profile.province].name);
    else if (profile.region && REGION[profile.region]) parts.push(REGION[profile.region].name);
    const age = AGES.find(([key]) => key && key === profile.age);
    if (age) parts.push(`${age[1]} años`.replace("65 o más años", "65 años o más").replace("Menos de 18 años", "Menor de 18"));
    const interests = [...PERSON_INTERESTS, ...BUSINESS_INTERESTS].filter(([key]) => (profile.interests || []).includes(key));
    if (interests.length) parts.push(`${interests.length} ${interests.length === 1 ? "interés" : "intereses"}`);
    const sector = SECTOR_GROUPS.find(([key]) => key && key === profile.sector);
    if (sector) parts.push(sector[1]);
    return parts;
  }

  function refreshProfileButton() {
    const profile = getProfile();
    for (const button of $$(".profile-button")) button.classList.toggle("has-profile", Boolean(profile));
    for (const label of $$("[data-profile-label]")) label.textContent = profile ? "Mi perfil" : "Crear perfil";
  }

  /* ---------------------------------------------------------------- profile dialog */

  let dialog = null;

  async function openProfile() {
    await loadMeta().catch(() => null);
    if (!META) { window.alert("No se pudieron cargar los datos. Inténtalo de nuevo en un momento."); return; }
    const current = getProfile();
    const draft = current ? JSON.parse(JSON.stringify(current))
      : { v: 1, who: [1], region: "", province: "", town: "", townName: "", age: "", interests: [], sector: "" };
    let step = 0;
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.className = "sheet";
      dialog.setAttribute("aria-labelledby", "profile-title");
      document.body.append(dialog);
    }

    const steps = () => {
      const list = ["who", "where"];
      if (draft.who.includes(1)) list.push("person");
      if (draft.who.includes(3) || draft.who.includes(4)) list.push("business");
      return list;
    };

    function render() {
      const names = steps();
      const name = names[step];
      const progress = names.map((_, i) => `<span class="${i <= step ? "done" : ""}"></span>`).join("");
      let title = "";
      let intro = "";
      let body = "";
      if (name === "who") {
        title = "¿Para quién buscas ayudas?";
        intro = "Puedes marcar más de una opción.";
        body = `<div class="choices">${WHO_CHOICES.map(([kind, label, help]) => `<label class="choice">
          <input type="checkbox" name="who" value="${kind}" ${draft.who.includes(kind) ? "checked" : ""}>
          <strong>${label}</strong><span>${help}</span></label>`).join("")}</div>
          <p class="privacy-note">${LOCK}<span>Tus respuestas se guardan solo en este navegador. No hay cuentas ni
          servidores: nadie más puede verlas.</span></p>`;
      } else if (name === "where") {
        title = "¿Dónde vives o tienes la actividad?";
        intro = "Así vemos las ayudas de tu ayuntamiento, tu provincia y tu comunidad.";
        const region = META.regions.find((r) => r.code === draft.region);
        const towns = (META.towns[draft.province] || []);
        body = `<label class="field"><span>Comunidad autónoma</span><select name="region" required>
          <option value="">Elige tu comunidad</option>${META.regions.map((r) => `<option value="${r.code}" ${r.code === draft.region ? "selected" : ""}>${esc(r.name)}</option>`).join("")}
          </select></label>
          <label class="field"><span>Provincia o isla</span><select name="province" ${region ? "" : "disabled"} required>
          <option value="">Elige tu provincia</option>${region ? region.provinces.map((p) => `<option value="${p.code}" ${p.code === draft.province ? "selected" : ""}>${esc(p.name)}</option>`).join("") : ""}
          </select></label>
          <label class="field"><span>Municipio <small>(para ver las ayudas de tu ayuntamiento)</small></span>
          <input type="text" name="town" list="town-list" autocomplete="off" placeholder="${draft.province ? "Escribe tu municipio" : "Elige antes la provincia"}"
            value="${esc(draft.townName)}" ${draft.province ? "" : "disabled"}>
          <datalist id="town-list">${towns.map(([, townName]) => `<option value="${esc(townName)}"></option>`).join("")}</datalist></label>`;
      } else if (name === "person") {
        title = "Sobre ti";
        intro = "Opcional. Nos ayuda a ordenar y descartar ayudas que no son para ti.";
        body = `<label class="field"><span>Edad</span><select name="age">${AGES.map(([key, label]) => `<option value="${key}" ${key === draft.age ? "selected" : ""}>${label}</option>`).join("")}</select></label>
          <fieldset class="field"><legend>¿Algo de esto va contigo?</legend><div class="chips">${PERSON_INTERESTS.map(([key, label]) => `<label class="chip"><input type="checkbox" name="interests" value="${key}" ${draft.interests.includes(key) ? "checked" : ""}>${label}</label>`).join("")}</div></fieldset>`;
      } else {
        title = "Sobre tu negocio";
        intro = "Opcional. Lo usamos para quitar ayudas de otros sectores y destacar lo que buscas.";
        body = `<label class="field"><span>Sector</span><select name="sector">${SECTOR_GROUPS.map(([key, label]) => `<option value="${key}" ${key === draft.sector ? "selected" : ""}>${label}</option>`).join("")}</select></label>
          <fieldset class="field"><legend>¿Qué te interesa?</legend><div class="chips">${BUSINESS_INTERESTS.map(([key, label]) => `<label class="chip"><input type="checkbox" name="interests" value="${key}" ${draft.interests.includes(key) ? "checked" : ""}>${label}</label>`).join("")}</div></fieldset>`;
      }
      const last = step === names.length - 1;
      dialog.innerHTML = `<form method="dialog" novalidate>
        <div class="sheet-head"><div class="progress">${progress}</div><h2 id="profile-title">${title}</h2><p>${intro}</p></div>
        <div class="sheet-body">${body}<p class="error" data-error hidden></p></div>
        <div class="sheet-foot">
          ${current ? '<button class="link-button spacer" type="button" data-delete>Borrar perfil</button>' : '<span class="spacer"></span>'}
          <button class="btn btn-ghost" type="button" data-cancel>${step ? "Atrás" : "Cancelar"}</button>
          <button class="btn btn-primary" type="submit">${last ? "Ver mis ayudas" : "Siguiente"}</button>
        </div></form>`;
      wire(name, last);
    }

    function collect(name) {
      const form = $("form", dialog);
      if (name === "who") draft.who = $$('input[name="who"]:checked', form).map((input) => Number(input.value));
      if (name === "where") {
        draft.region = form.region.value;
        draft.province = form.province.value;
        const typed = form.town.value.trim();
        const known = (META.towns[draft.province] || []).find(([, townName]) => plain(townName) === plain(typed));
        draft.townName = known ? known[1] : typed;
        draft.town = typed ? slugify(draft.townName) : "";
      }
      if (name === "person" || name === "business") {
        const keys = (name === "person" ? PERSON_INTERESTS : BUSINESS_INTERESTS).map(([key]) => key);
        const others = draft.interests.filter((key) => !keys.includes(key));
        draft.interests = [...others, ...$$('input[name="interests"]:checked', form).map((input) => input.value)];
        if (name === "person") draft.age = form.age.value;
        if (name === "business") draft.sector = form.sector.value;
      }
    }

    function problem(name) {
      if (name === "who" && !draft.who.length) return "Marca al menos una opción.";
      if (name === "where" && (!draft.region || !draft.province)) return "Elige tu comunidad y tu provincia.";
      return "";
    }

    function wire(name, last) {
      const form = $("form", dialog);
      if (name === "where") {
        form.region.addEventListener("change", () => {
          draft.region = form.region.value;
          const region = META.regions.find((r) => r.code === draft.region);
          draft.province = region && region.provinces.length === 1 ? region.provinces[0].code : "";
          draft.town = ""; draft.townName = "";
          render();
        });
        form.province.addEventListener("change", () => {
          draft.province = form.province.value;
          draft.town = ""; draft.townName = "";
          render();
        });
      }
      $("[data-cancel]", dialog).addEventListener("click", () => {
        if (step === 0) { dialog.close(); return; }
        collect(name);
        step -= 1;
        render();
      });
      const remove = $("[data-delete]", dialog);
      if (remove) {
        remove.addEventListener("click", () => {
          if (!window.confirm("¿Borrar tu perfil de este dispositivo?")) return;
          storage.remove(KEYS.profile);
          dialog.close();
          refreshProfileButton();
          document.dispatchEvent(new CustomEvent("ajudes:profile"));
        });
      }
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        collect(name);
        const message = problem(name);
        const error = $("[data-error]", dialog);
        if (message) { error.textContent = message; error.hidden = false; return; }
        if (!last) { step += 1; render(); return; }
        draft.updated = new Date().toISOString().slice(0, 10);
        storage.set(KEYS.profile, draft);
        dialog.close();
        refreshProfileButton();
        document.dispatchEvent(new CustomEvent("ajudes:profile"));
        if (PAGE !== "home" && PAGE !== "search") window.location.href = `${ROOT}buscar.html?me=1`;
      });
      const first = $("input, select", form);
      if (first) first.focus();
    }

    render();
    if (!dialog.open) dialog.showModal();
  }

  /* ---------------------------------------------------------------- home: "Para ti" */

  async function renderForYou() {
    const section = $("#para-ti");
    if (!section) return;
    const profile = getProfile();
    const hero = $(".hero");
    if (hero) {  // returning visitors see their aid first; the welcome shrinks to today's figures
      hero.classList.toggle("hero-compact", Boolean(profile));
      if (profile) hero.before(section);
      else hero.after(section);
    }
    if (!profile) { section.innerHTML = ""; return; }
    section.innerHTML = '<div class="wrap"><div class="foryou-card"><p>Buscando tus ayudas…</p></div></div>';
    let items;
    try { items = await loadItems([profile.region]); } catch {
      section.innerHTML = '<div class="wrap"><div class="foryou-card"><p class="error">No se pudieron cargar las ayudas. Recarga la página para intentarlo de nuevo.</p></div></div>';
      return;
    }
    const mine = [];
    for (const item of items) {
      item._status = status(item);
      if (item._status === "cerrada") continue;
      const found = match(item, profile);
      if (found) mine.push([item, found]);
    }
    mine.sort((a, b) => byDeadline(a[0], b[0]));
    const open = mine.filter(([item]) => item._status === "abierta");
    const week = open.filter(([item]) => daysBetween(TODAY, parseDate(item.e)) <= 7);
    const fresh = mine.filter(([item]) => daysBetween(parseDate(item.rv || item.f), TODAY) < 7);
    const soon = open.filter(([item]) => daysBetween(TODAY, parseDate(item.e)) <= 10).slice(0, 3);
    const shown = new Set(soon.map(([item]) => item.c));
    const picks = [...mine].filter(([item]) => !shown.has(item.c))
      .sort((a, b) => (b[1].score - a[1].score) || byDeadline(a[0], b[0])).slice(0, 4);
    const savedCount = saved.list().length;
    const list = (entries) => entries.map(([item, found]) => cardHTML(item, found)).join("");
    section.innerHTML = `<div class="wrap"><div class="foryou-card">
      <div class="foryou-head"><div><h2>Tus ayudas</h2><ul class="profile-summary">${profileSummary(profile).map((part) => `<li>${esc(part)}</li>`).join("")}</ul></div>
      <div class="hero-actions"><button class="btn btn-ghost btn-small" type="button" data-open-profile>Editar perfil</button>
      <a class="btn btn-primary btn-small" href="${ROOT}buscar.html?me=1&amp;st=all">Ver las ${number(mine.length)} ${ARROW}</a></div></div>
      <div class="kpis"><div class="kpi"><strong>${number(open.length)}</strong><span>abiertas para ti</span></div>
      <div class="kpi kpi-warn"><strong>${number(week.length)}</strong><span>cierran en 7 días</span></div>
      <div class="kpi"><strong>${number(fresh.length)}</strong><span>nuevas esta semana</span></div>
      <div class="kpi"><strong>${number(savedCount)}</strong><span><a href="${ROOT}buscar.html?fav=1">guardadas</a></span></div></div>
      ${soon.length ? `<h3 class="group-title">Cierran pronto <span class="count">${soon.length}</span></h3><div class="aids">${list(soon)}</div>` : ""}
      ${picks.length ? `<h3 class="group-title">Recomendadas para ti</h3><div class="aids">${list(picks)}</div>` : ""}
      ${mine.length ? "" : `<p class="empty">Ahora mismo no encontramos ayudas abiertas para tu perfil. Prueba a añadir tu municipio o a marcar más opciones.</p>`}
      ${profile.town ? "" : '<p class="privacy-note">Añade tu municipio en el perfil para ver también las ayudas de tu ayuntamiento.</p>'}
      </div></div>`;
    enhance(section);
  }

  /* ---------------------------------------------------------------- search page */

  const search = {
    items: [],
    loadedKey: null,
    shown: PAGE_SIZE,
    state: {},
  };

  function readState() {
    const params = new URLSearchParams(window.location.search);
    const profile = getProfile();
    const asked = params.has("me") ? params.get("me") === "1"
      : !params.has("c") && !params.has("g") && !params.has("q") && !params.has("fav");
    return {
      me: Boolean(profile) && asked,
      q: params.get("q") || "",
      c: params.get("c") || "",
      p: params.get("p") || "",
      m: params.get("m") || "",
      b: (params.get("b") || "").split(",").filter(Boolean).map(Number),
      g: params.get("g") || "",
      st: params.get("st") || "open",
      soon: params.get("soon") === "1",
      fav: params.get("fav") === "1",
      sort: params.get("sort") || "end",
    };
  }

  function writeState() {
    const s = search.state;
    const params = new URLSearchParams();
    if (s.me) params.set("me", "1"); else if (getProfile()) params.set("me", "0");
    if (s.q) params.set("q", s.q);
    if (!s.me) {
      if (s.c) params.set("c", s.c);
      if (s.p) params.set("p", s.p);
      if (s.m) params.set("m", s.m);
      if (s.b.length) params.set("b", s.b.join(","));
    }
    if (s.g) params.set("g", s.g);
    if (s.st !== "open") params.set("st", s.st);
    if (s.soon) params.set("soon", "1");
    if (s.fav) params.set("fav", "1");
    if (s.sort !== "end") params.set("sort", s.sort);
    const query = params.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }

  function renderFilters() {
    const s = search.state;
    const profile = getProfile();
    const region = META.regions.find((r) => r.code === s.c);
    const towns = META.towns[s.p] || [];
    const topicOptions = (family) => META.topics.filter((t) => t.family === family && t.count)
      .map((t) => `<option value="${t.slug}" ${t.slug === s.g ? "selected" : ""}>${esc(t.label)}</option>`).join("");
    const me = profile
      ? `<div class="toggle-me"><label class="check"><input type="checkbox" name="me" ${s.me ? "checked" : ""}> Solo las que encajan conmigo</label>
         <p>${esc(profileSummary(profile).join(" · "))} · <button class="link-button" type="button" data-open-profile>editar</button></p></div>`
      : `<div class="toggle-me"><p>Crea tu perfil y te mostramos solo las ayudas para ti.</p>
         <p><button class="btn btn-primary btn-small" type="button" data-open-profile>Crear mi perfil</button></p></div>`;
    $("[data-filters]").innerHTML = `${me}
      <label class="field"><span>Buscar</span><input type="search" name="q" value="${esc(s.q)}" placeholder="bebé, alquiler, digitalización…"></label>
      <div ${s.me ? "hidden" : ""}>
        <label class="field"><span>Comunidad autónoma</span><select name="c"><option value="">Toda España</option>
          ${META.regions.map((r) => `<option value="${r.code}" ${r.code === s.c ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></label>
        <label class="field"><span>Provincia o isla</span><select name="p" ${region ? "" : "disabled"}><option value="">Todas</option>
          ${region ? region.provinces.map((p) => `<option value="${p.code}" ${p.code === s.p ? "selected" : ""}>${esc(p.name)}</option>`).join("") : ""}</select></label>
        <label class="field"><span>Municipio</span><select name="m" ${towns.length ? "" : "disabled"}><option value="">Todos</option>
          ${towns.map(([slug, name, count]) => `<option value="${slug}" ${slug === s.m ? "selected" : ""}>${esc(name)} (${count})</option>`).join("")}</select></label>
        <fieldset class="field"><legend>Para quién</legend>
          ${[1, 3, 4].map((kind) => `<label class="check"><input type="checkbox" name="b" value="${kind}" ${s.b.includes(kind) ? "checked" : ""}> ${KIND_LABELS[kind]}</label>`).join("")}</fieldset>
      </div>
      <label class="field"><span>Tema</span><select name="g"><option value="">Todos los temas</option>
        <optgroup label="Personas y familias">${topicOptions("personas")}</optgroup>
        <optgroup label="Autónomos y empresas">${topicOptions("empresas")}</optgroup></select></label>
      <fieldset class="field"><legend>Plazo</legend>
        ${[["open", "Abiertas ahora"], ["next", "Abiertas y próximas"], ["all", "Todas, también sin fecha"]].map(([key, label]) => `<label class="check"><input type="radio" name="st" value="${key}" ${s.st === key ? "checked" : ""}> ${label}</label>`).join("")}
        <label class="check"><input type="checkbox" name="soon" ${s.soon ? "checked" : ""}> Cierran en 7 días</label>
        <label class="check"><input type="checkbox" name="fav" ${s.fav ? "checked" : ""}> Solo mis guardadas</label></fieldset>
      <button class="btn btn-ghost btn-small" type="button" data-reset>Quitar filtros</button>`;
  }

  function regionsNeeded() {
    const s = search.state;
    const profile = getProfile();
    if (s.me && profile) return [profile.region];
    if (s.c) return [s.c];
    return null;
  }

  const GROUPS = {
    abierta: "Abiertas ahora",
    niche: "Premios, universidades y otros organismos",
    proxima: "Abren pronto",
    revisar: "Plazo recién vencido: compruébalo",
    sin_fecha: "Sin fecha de cierre publicada",
  };
  const groupOf = (item) => (item._status === "abierta" && isNiche(item) ? "niche" : item._status);

  async function runSearch(resetPage = true) {
    const s = search.state;
    const results = $("[data-results]");
    const needed = regionsNeeded();
    const key = needed === null ? "all" : needed.join(",");
    if (search.loadedKey !== key) {
      results.innerHTML = `<p class="empty">Cargando ayudas${needed === null ? " de toda España" : ""}…</p>`;
      try {
        search.items = await loadItems(needed);
        for (const item of search.items) item._status = status(item);
        search.loadedKey = key;
      } catch {
        results.innerHTML = '<p class="empty">No se pudieron cargar las ayudas. Recarga la página para intentarlo de nuevo.</p>';
        return;
      }
    }
    if (resetPage) search.shown = PAGE_SIZE;
    const profile = getProfile();
    const words = plain(s.q).split(/\s+/).filter(Boolean);
    const savedCodes = new Set(saved.list().map((entry) => entry.c));
    const week = new Date(TODAY.getTime() + 7 * DAY);
    const found = [];
    for (const item of search.items) {
      const state = item._status;
      if (state === "cerrada") continue;
      if (s.st === "open" && state !== "abierta") continue;
      if (s.st === "next" && state !== "abierta" && state !== "proxima") continue;
      if (s.soon && !(state === "abierta" && parseDate(item.e) <= week)) continue;
      if (s.fav && !savedCodes.has(item.c)) continue;
      if (s.g && !item.g.includes(s.g)) continue;
      let why = null;
      if (s.me && profile) {
        why = match(item, profile);
        if (!why) continue;
      } else {
        const scope = item.sc && item.sc.length ? item.sc : ["ES"];
        if (s.p) {
          if (item.k === "m" ? item.p !== s.p : !scope.some((code) => code === "ES" || s.p.startsWith(code))) continue;
        } else if (s.c) {
          if (!scope.some((code) => code === "ES" || code.startsWith(s.c) || s.c.startsWith(code))) continue;
        }
        if (s.m && !(item.k === "m" && item.ts === s.m && item.p === s.p)) continue;
        if (s.b.length && !(item.b || [5]).some((kind) => kind === 5 || s.b.includes(kind))) continue;
        if (item.og && s.b.length && !s.b.includes(3) && !s.b.includes(4)) continue;
      }
      if (words.length) {
        if (!item._text) item._text = plain(`${item.t} ${item.o} ${item.tn || ""} ${(item.g || []).map((g) => (TOPIC[g] || {}).label).join(" ")}`);
        if (!words.every((word) => item._text.includes(word))) continue;
      }
      found.push([item, why]);
    }
    if (s.sort === "new") found.sort((a, b) => ((b[0].rv || b[0].f).localeCompare(a[0].rv || a[0].f)) || byDeadline(a[0], b[0]));
    else if (s.sort === "amount") found.sort((a, b) => ((b[0].a || 0) - (a[0].a || 0)) || byDeadline(a[0], b[0]));
    else if (s.me) found.sort((a, b) => byDeadline(a[0], b[0]) || (b[1].score - a[1].score));
    else found.sort((a, b) => byDeadline(a[0], b[0]));

    const pills = [];
    if (s.q) pills.push(["q", `“${s.q}”`]);
    if (!s.me && s.c) pills.push(["c", REGION[s.c] ? REGION[s.c].name : s.c]);
    if (!s.me && s.p) pills.push(["p", PROVINCE[s.p] ? PROVINCE[s.p].name : s.p]);
    if (!s.me && s.m) pills.push(["m", ((META.towns[s.p] || []).find(([slug]) => slug === s.m) || [, s.m])[1]]);
    if (!s.me) for (const kind of s.b) pills.push([`b${kind}`, KIND_LABELS[kind]]);
    if (s.g) pills.push(["g", (TOPIC[s.g] || {}).label || s.g]);
    if (s.soon) pills.push(["soon", "Cierran en 7 días"]);
    if (s.fav) pills.push(["fav", "Guardadas"]);
    $("[data-results-bar]").innerHTML = `<span class="results-count">${number(found.length)} ${found.length === 1 ? "ayuda" : "ayudas"}${s.me ? " para ti" : ""}</span>
      <button class="btn btn-ghost btn-small filters-toggle" type="button" data-toggle-filters>Filtros</button>
      <label><span class="visually-hidden">Ordenar</span><select name="sort" aria-label="Ordenar">
        <option value="end" ${s.sort === "end" ? "selected" : ""}>Cierre más próximo</option>
        <option value="new" ${s.sort === "new" ? "selected" : ""}>Más recientes</option>
        <option value="amount" ${s.sort === "amount" ? "selected" : ""}>Mayor presupuesto</option></select></label>
      ${pills.length ? `<div class="pills">${pills.map(([key, label]) => `<button class="pill" type="button" data-unset="${esc(key)}" aria-label="Quitar ${esc(label)}">${esc(label)} ✕</button>`).join("")}</div>` : ""}`;
    const summary = $("[data-search-summary]");
    if (summary) {
      summary.textContent = s.me && profile ? `Las ayudas que encajan con tu perfil: ${profileSummary(profile).join(" · ")}.`
        : "Filtra por lugar, por tema y por quién puede pedirlas.";
    }
    if (!found.length) {
      results.innerHTML = `<p class="empty">${s.fav ? "Aún no has guardado ninguna ayuda. Pulsa la estrella de una ficha para guardarla aquí." : "No hay ayudas con estos filtros. Prueba a quitar alguno."}</p>`;
    } else {
      let group = null;
      results.innerHTML = found.slice(0, search.shown).map(([item, why]) => {
        const next = s.sort === "end" ? groupOf(item) : null;
        const head = next && next !== group ? `<h2 class="results-group">${GROUPS[next]}</h2>` : "";
        group = next;
        return head + cardHTML(item, why);
      }).join("");
      enhance(results);
    }
    const more = $("[data-more]");
    more.hidden = found.length <= search.shown;
    more.textContent = `Mostrar más (${number(found.length - search.shown)} restantes)`;
  }

  function onFilterChange(event) {
    const s = search.state;
    const target = event.target;
    if (!target.name) return;
    if (target.name === "me") s.me = target.checked;
    else if (target.name === "q") s.q = target.value.trim();
    else if (target.name === "c") { s.c = target.value; s.p = ""; s.m = ""; }
    else if (target.name === "p") { s.p = target.value; s.m = ""; }
    else if (target.name === "m") s.m = target.value;
    else if (target.name === "b") s.b = $$('input[name="b"]:checked').map((input) => Number(input.value));
    else if (target.name === "g") s.g = target.value;
    else if (target.name === "st") s.st = target.value;
    else if (target.name === "soon") s.soon = target.checked;
    else if (target.name === "fav") s.fav = target.checked;
    else if (target.name === "sort") s.sort = target.value;
    else return;
    writeState();
    if (["me", "c", "p"].includes(target.name)) renderFilters();
    runSearch();
  }

  async function startSearch() {
    try { await loadMeta(); } catch {
      $("[data-results]").innerHTML = '<p class="empty">No se pudieron cargar los datos. Recarga la página para intentarlo de nuevo.</p>';
      return;
    }
    search.state = readState();
    renderFilters();
    const filters = $("[data-filters]");
    let typing = null;
    filters.addEventListener("change", onFilterChange);
    filters.addEventListener("input", (event) => {
      if (event.target.name !== "q") return;
      clearTimeout(typing);
      typing = setTimeout(() => onFilterChange(event), 250);
    });
    filters.addEventListener("click", (event) => {
      if (!event.target.closest("[data-reset]")) return;
      const keepMe = search.state.me;
      search.state = { ...readState(), me: keepMe, q: "", c: "", p: "", m: "", b: [], g: "", st: "open", soon: false, fav: false, sort: "end" };
      writeState();
      renderFilters();
      runSearch();
    });
    const bar = $("[data-results-bar]");
    bar.addEventListener("change", onFilterChange);
    bar.addEventListener("click", (event) => {
      if (event.target.closest("[data-toggle-filters]")) { filters.classList.toggle("open"); return; }
      const pill = event.target.closest("[data-unset]");
      if (!pill) return;
      const key = pill.dataset.unset;
      const s = search.state;
      if (key === "q") s.q = "";
      else if (key === "c") { s.c = ""; s.p = ""; s.m = ""; }
      else if (key === "p") { s.p = ""; s.m = ""; }
      else if (key === "m") s.m = "";
      else if (key.startsWith("b")) s.b = s.b.filter((kind) => kind !== Number(key.slice(1)));
      else if (key === "g") s.g = "";
      else if (key === "soon") s.soon = false;
      else if (key === "fav") s.fav = false;
      writeState();
      renderFilters();
      runSearch();
    });
    $("[data-more]").addEventListener("click", () => { search.shown += PAGE_SIZE; runSearch(false); });
    document.addEventListener("ajudes:profile", () => {
      search.state.me = Boolean(getProfile());
      writeState();
      renderFilters();
      runSearch();
    });
    document.addEventListener("ajudes:saved", () => { if (search.state.fav) runSearch(false); });
    runSearch();
  }

  /* ---------------------------------------------------------------- start */

  refreshProfileButton();
  enhance();
  if (PAGE === "home") {
    loadMeta().then(renderForYou).catch(() => {});
    document.addEventListener("ajudes:profile", () => { renderForYou(); });
    if (window.location.hash === "#para-ti" && !getProfile()) openProfile();
  }
  if (PAGE === "search") startSearch();
  for (const link of $$('a[href$="#para-ti"]')) {
    link.addEventListener("click", (event) => {
      if (getProfile()) return;
      event.preventDefault();
      openProfile();
    });
  }
})();
