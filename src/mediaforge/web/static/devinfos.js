// Dev Infos -- sidebar badge poll (mirrors queue.js's seerrBadge IIFE) plus a
// light client-side refresh for the Dev Infos page itself.

// Sidebar badge -- fetch the cached post count on every page and keep it
// fresh. Loaded globally (see base.html) so the badge works no matter which
// page is open, same as the Seerr badge in queue.js -- always runs
// unconditionally, no enable/disable gate (Dev Infos is always-on).
(function startDevInfoBadgePoll() {

  async function updateDevInfoBadge() {
    const badge = document.getElementById("devinfoBadge");
    if (!badge) return;
    try {
      const resp = await fetch("/api/devinfos/status");
      if (!resp.ok) return;
      const data = await resp.json();
      const n = data.count || 0;
      badge.textContent = n;
      badge.style.display = n > 0 ? "" : "none";
    } catch (e) { /* ignore -- remote Dev Info server may be unreachable */ }
  }

  updateDevInfoBadge();
  setInterval(updateDevInfoBadge, 60000); // refresh every 60s
})();

// Dev Infos page -- keep the list itself reasonably fresh without a full
// reload, in case new posts arrive while the page is open.
(function devInfoPageRefresh() {
  const list = document.getElementById("devinfosList");
  if (!list) return; // not on the devinfos page

  function typeLabel(type) {
    if (type === "feature") return t("Feature", "Feature");
    if (type === "fix") return t("Fix", "Fix");
    if (type === "warning") return t("Warnung", "Warning");
    return t("Ankündigung", "Announcement");
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function render(posts) {
    if (!posts || !posts.length) {
      list.innerHTML = '<div class="devinfos-empty">' + t("Noch keine Dev Infos.", "No dev infos yet.") + '</div>';
      return;
    }
    list.innerHTML = posts.map(function (post) {
      const type = post.type || "announcement";
      return (
        '<div class="devinfo-card" data-type="' + escapeHtml(type) + '">' +
          '<div class="devinfo-card-head">' +
            '<span class="devinfo-tag devinfo-tag-' + escapeHtml(type) + '">' + typeLabel(type) + '</span>' +
            '<span class="devinfo-meta">' +
              (post.author ? '<span class="devinfo-author">' + escapeHtml(post.author) + '</span>' : '') +
              '<span class="devinfo-time">' + escapeHtml(post.formatted_time || post.remote_created_at || "") + '</span>' +
            '</span>' +
          '</div>' +
          '<h3 class="devinfo-title">' + escapeHtml(post.title) + '</h3>' +
          '<div class="devinfo-body devinfo-markdown">' + (post.body_html != null ? post.body_html : escapeHtml(post.body)) + '</div>' +
        '</div>'
      );
    }).join("");
  }

  async function refresh() {
    try {
      const resp = await fetch("/api/devinfos/status");
      if (!resp.ok) return;
      const data = await resp.json();
      render(data.posts || []);
    } catch (e) { /* keep the server-rendered list on failure */ }
  }

  // The template already server-renders the initial list. The page's own
  // visit just asked the poller to refetch immediately (see
  // routes/devinfos.py's devinfos_page()), so poll a couple of times soon
  // after load to pick that up without a full reload, then settle into the
  // normal 60s background cadence for as long as the tab stays open.
  setTimeout(refresh, 2000);
  setTimeout(refresh, 5000);
  setInterval(refresh, 60000);
})();
