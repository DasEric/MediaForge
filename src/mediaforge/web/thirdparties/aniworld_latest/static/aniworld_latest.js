// AniWorld Latest — "Die 50 neuesten Episoden" list page (see routes.py and
// service.py in this same folder). Fetches the scraped newest-episode list
// and renders it as a compact list.
//
// Each row is enriched with the same TMDB -> Crunchyroll -> Fernsehserien.de
// provider pills the Home/Browse cards use (enrichCardWithTmdb, app.js,
// loaded first). NOTE: the row deliberately does NOT carry the "browse-card"
// class -- that class opts a node into the app's global card behaviours
// (hover overlay, and the skeleton-loader appearance mode's perpetual
// shimmer on any .browse-card without a loaded poster image), which made the
// rows shimmer forever. enrichCardWithTmdb() only needs a ".browse-info"
// child, not the class, so we pass the row element directly.
//
// Clicking a row opens the cross-provider search modal Advanced Search uses
// (openAniSearchModal, app.js), searching the SERIES title (already stripped
// of any "St. 1 Ep. 3" suffix server-side) across AniWorld/S.to/FilmPalast/
// MegaKino.

(function () {
  const listEl = document.getElementById("awlList");
  const loadingEl = document.getElementById("awlLoading");
  const emptyEl = document.getElementById("awlEmpty");
  if (!listEl) return;

  // esc()/t() come from app.js; fall back defensively if unavailable.
  const _esc = (typeof esc === "function")
    ? esc
    : (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => (
        { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
      ));
  const _t = (typeof t === "function") ? t : (de, en) => de;

  // Flag name -> fully-resolved static URL, built server-side in the template
  // (see aniworld_latest.html). Never concatenate a filename onto a directory
  // url_for() -- that yields "/static/flags/?v=123japanese-germanSub.svg",
  // because url_for() puts its cache-busting query on the directory itself.
  const flagUrls = window.AWL_FLAGS || {};

  // Defensive: drop a trailing season/episode suffix from the search query
  // (the backend already does this, but a stray "St. 1 Ep. 3" should never
  // reach the search modal). Keyword-anchored so numbers in real titles stay.
  function stripSeasonEpisode(title) {
    return (title || "")
      .replace(/\s+St\.?\s*\d+\s*Ep\.?\s*\d+\s*$/i, "")
      .replace(/\s+Staffel\s*\d+\s*Folge\s*\d+\s*$/i, "")
      .replace(/\s+(?:St\.?|Staffel)\s*\d+\s*$/i, "")
      .replace(/\s+(?:Ep\.?|Folge)\s*\d+\s*$/i, "")
      .trim();
  }

  // Human-readable tooltips for the language variants.
  const FLAG_LABELS = {
    "german": "Deutsch",
    "english": "Englisch",
    "japanese-germanSub": "Japanisch, deutscher Untertitel",
    "japanese-englishSub": "Japanisch, englischer Untertitel",
    "english-germanSub": "Englisch, deutscher Untertitel",
  };

  function flagImg(name) {
    // AniWorld's flag filenames are mapped to MediaForge's local flags/ names
    // server-side (see service.py's _FLAG_MAP). An unknown name simply
    // renders nothing rather than a broken image.
    const src = flagUrls[name];
    if (!src) return "";
    const label = FLAG_LABELS[name] || name;
    return `<img class="awl-flag" src="${_esc(src)}" alt="${_esc(label)}" title="${_esc(label)}" loading="lazy">`;
  }

  function renderRows(items) {
    listEl.innerHTML = "";
    items.forEach((item) => {
      const title = stripSeasonEpisode(item.title || "");

      const row = document.createElement("div");
      row.className = "awl-row";
      if (item.is_new) row.classList.add("awl-row-new");
      row.style.cursor = "pointer";

      row.onclick = () => {
        const tmdbId = row.dataset.tmdbId ? parseInt(row.dataset.tmdbId, 10) : null;
        const type = item.is_movie ? "movie" : "tv";
        if (window.openAniSearchModal) {
          openAniSearchModal(title, tmdbId, type, "", "");
        }
      };

      const flags = (item.languages || []).map(flagImg).join("");
      const newBadge = item.is_new
        ? `<span class="awl-new-badge">${_t("Neu!", "New!")}</span>`
        : "";
      const dateHtml = item.date_label
        ? `<span class="awl-date">${_esc(item.date_label)}</span>`
        : "";

      // ".browse-info" is required: enrichCardWithTmdb() appends its
      // ".browse-tmdb-meta" (the provider pills) into it. The title lives
      // inside it so the pills render right after the title text.
      row.innerHTML =
        `<span class="awl-se">${_esc(item.se_label || "")}</span>` +
        `<span class="awl-flags">${flags}</span>` +
        `<span class="awl-title-cell">` +
          `<span class="browse-info">` +
            `<span class="browse-title awl-title" title="${_esc(title)}">${_esc(title)}</span>` +
          `</span>` +
        `</span>` +
        `<span class="awl-meta">${newBadge}${dateHtml}</span>`;

      listEl.appendChild(row);

      // Same lazy CineInfo/Crunchyroll/Fernsehserien.de pipeline the Home
      // page cards use. Duplicate titles (same series, different language
      // rows) are batched together by title in app.js, so each distinct
      // title is only looked up once.
      if (typeof enrichCardWithTmdb === "function") {
        enrichCardWithTmdb(row, title);
      }
    });
  }

  async function load() {
    // Populate the settings globals enrichCardWithTmdb() reads (whether TMDB
    // is configured, provider toggles) before rendering, same as the other
    // integration pages do.
    try {
      await Promise.all([
        (typeof loadCineinfoSettings === "function") ? loadCineinfoSettings() : Promise.resolve(),
        (typeof loadGeneralSettings === "function") ? loadGeneralSettings() : Promise.resolve(),
      ]);
    } catch (e) { /* best-effort */ }

    let items = null;
    try {
      const resp = await fetch("/api/aniworld-latest");
      const data = await resp.json();
      if (resp.ok && data.items && data.items.length) items = data.items;
    } catch (e) {
      items = null;
    } finally {
      // Always leave the loading state, no matter what happened above.
      loadingEl.style.display = "none";
    }

    if (items) {
      listEl.style.display = "block";
      renderRows(items);
    } else {
      emptyEl.style.display = "block";
    }
  }

  load();
})();
