// Homepage Dev Info warning banners -- dismiss-and-remember behaviour.
// Warning-type Dev Info posts (see app.py's index() view) are rendered as
// banner cards at the top of the homepage. Dismissing one hides it and
// remembers the post's id in localStorage so it stays hidden across visits;
// a newer warning post (different id) always shows even if older ones were
// dismissed, since dismissal is tracked per-id, not globally.

(function devInfoWarningBanners() {
  const STORAGE_KEY = "mediaforge_dismissed_devinfo_warnings";
  const container = document.getElementById("devinfoWarningBanners");
  if (!container) return; // no active warnings on this page load

  function getDismissed() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      return [];
    }
  }

  function addDismissed(id) {
    const dismissed = getDismissed();
    const idStr = String(id);
    if (!dismissed.includes(idStr)) {
      dismissed.push(idStr);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(dismissed));
      } catch (e) { /* localStorage unavailable (private mode, quota, ...) -- ignore */ }
    }
  }

  const dismissedIds = getDismissed();
  const banners = container.querySelectorAll(".devinfo-warning-banner");

  banners.forEach(function (banner) {
    const id = banner.getAttribute("data-devinfo-id");
    if (id != null && dismissedIds.includes(String(id))) {
      banner.style.display = "none";
      return;
    }

    const dismissBtn = banner.querySelector(".devinfo-warning-dismiss");
    if (!dismissBtn) return;
    dismissBtn.addEventListener("click", function () {
      banner.style.display = "none";
      if (id != null) addDismissed(id);
    });
  });
})();
