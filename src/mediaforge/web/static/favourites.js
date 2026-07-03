// Favourites page logic

async function loadFavourites() {
  const container = document.getElementById("favouritesList");
  try {
    const resp = await fetch("/api/favourites");
    const data = await resp.json();
    renderFavourites(data.favourites || [], container);
  } catch (e) {
    container.innerHTML = '<div class="stats-loading">' + t('Fehler beim Laden der Favoriten.', 'Error loading favourites.') + '</div>';
  }
}

function renderFavourites(favs, container) {
  if (!favs.length) {
    container.innerHTML =
      '<div class="queue-empty">' + t('Keine Favoriten gespeichert.<br>Füge Serien über die Suche hinzu.', 'No favourites saved.<br>Add series via the search page.') + '</div>';
    return;
  }
  console.log(favs);
  
  container.innerHTML = favs
    .map(
      (f) => `
      
    <div class="result-card" data-url="${f.series_url}">
      <div class="result-poster-wrap">
        <img class="result-poster"
             src="${proxyImg(f.poster_url || '')}"
             alt="${f.title}"
             onload="this.closest('.result-card').classList.add('loaded')"
             onerror="this.closest('.result-card').classList.add('loaded'); this.style.display='none'"
             loading="lazy" />
      </div>
      <div class="result-info">
        <div class="result-title">${f.title}</div>
        <div class="result-meta">${f.created_at ? f.created_at.slice(0, 10) : ''}</div>
      </div>
      <div class="result-actions">
        <button class="btn btn-sm btn-primary" onclick="openFavourite('${encodeURIComponent(f.series_url).replace(/'/g, "%27")}')">${t('Öffnen', 'Open')}</button>
        <button class="btn btn-sm btn-danger" onclick="removeFavourite('${f.series_url.replace(/'/g, "&apos;")}', this)">${t('Entfernen', 'Remove')}</button>
      </div>
    </div>`
    )
    .join("");
}

window.openFavourite = function(encodedUrl) {
  window.location.href = "/?open=" + encodedUrl;
};

window.removeFavourite = async function (seriesUrl, btn) {
  btn.disabled = true;
  try {
    await fetch("/api/favourites", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ series_url: seriesUrl }),
    });
    const card = btn.closest(".result-card");
    if (card) card.remove();
    if (window.showToast) showToast(t("Aus Favoriten entfernt", "Removed from favourites"));
  } catch (e) {
    btn.disabled = false;
    if (window.showToast) showToast(t("Fehler: ", "Error: ") + e.message);
  }
};

loadFavourites();
