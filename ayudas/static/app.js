// Filters the list on the home page by topic and free text. The page works without it.
(() => {
  const search = document.getElementById("q");
  if (!search) return;
  const cards = [...document.querySelectorAll(".cards .card")];
  const chips = [...document.querySelectorAll("[data-filter]")];
  const count = document.getElementById("count");
  const plain = (text) => text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  let topic = "";

  function apply() {
    const words = plain(search.value).split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const card of cards) {
      const show = (!topic || card.dataset.topics.split(" ").includes(topic))
        && words.every((word) => card.dataset.search.includes(word));
      card.hidden = !show;
      if (show) shown += 1;
    }
    count.textContent = shown === 1 ? "1 ayuda" : `${shown} ayudas`;
  }

  for (const chip of chips) {
    chip.addEventListener("click", () => {
      topic = chip.dataset.filter;
      for (const other of chips) other.setAttribute("aria-pressed", String(other === chip));
      apply();
    });
  }
  search.addEventListener("input", apply);
})();
