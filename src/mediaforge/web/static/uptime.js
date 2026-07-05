// UpTime dashboard — polls /api/uptime/status and updates cards in place
// (no page reload, no full grid rebuild) for smooth live monitoring.
(function () {
  "use strict";

  const I = {
    online:    t("Online", "Online"),
    offline:   t("Offline", "Offline"),
    degraded:  t("Eingeschränkt", "Degraded"),
    pending:   t("Wartet…", "Pending"),
    untracked: t("Nicht überwacht", "Not tracked"),
    uptime:    t("Uptime", "Uptime"),
    response:  t("Ø Antwort", "Avg response"),
    checks:    t("Prüfungen", "Checks"),
    lastCheck: t("Letzte Prüfung", "Last check"),
    never:     t("noch nie", "never"),
    disabledSource: t("Quelle deaktiviert", "Source disabled"),
    allOperational: t("Alle überwachten Seiten sind online", "All monitored sites are operational"),
    someDown:     t("Einige Seiten sind offline", "Some sites are offline"),
    someDegraded: t("Einige Seiten sind eingeschränkt", "Some sites are degraded"),
    noneTracked:  t("Keine Quellen ausgewählt — in den Integrationen aktivieren", "No sources selected — enable them in Integrations"),
    updated:  t("Aktualisiert", "Updated"),
    checking: t("Prüfe…", "Checking…"),
    degradedMsg:   t("Erreichbar, aber Inhalt nicht verifiziert — evtl. Sperr-/Challenge-Seite", "Reachable, but content unverified — possibly a block/challenge page"),
    unreachableMsg: t("Nicht erreichbar", "Unreachable"),
    lastError: t("Letzter Fehler", "Last error"),
    blockedMsg: t("Sperr-/Blockseite erkannt — nicht die echte Seite", "Block/ISP page detected — not the real site"),
    secAgo: t("s", "s"), minAgo: t("min", "min"), hAgo: t("h", "h"), dAgo: t("d", "d"),
    justNow: t("gerade eben", "just now"),
    legendOnline: t("Online", "Online"),
    legendDegraded: t("Eingeschränkt", "Degraded"),
    legendOffline: t("Offline", "Offline"),
  };

  let timer = null;
  let sig = "";

  function esc(s) { const d = document.createElement("div"); d.textContent = s == null ? "" : String(s); return d.innerHTML; }
  function host(url) { return (url || "").replace(/^https?:\/\//, "").replace(/\/$/, ""); }

  function relTime(ts, now) {
    if (!ts) return I.never;
    const d = Math.max(0, (now || Math.floor(Date.now() / 1000)) - ts);
    if (d < 5) return I.justNow;
    if (d < 60) return d + " " + I.secAgo;
    if (d < 3600) return Math.floor(d / 60) + " " + I.minAgo;
    if (d < 86400) return Math.floor(d / 3600) + " " + I.hAgo;
    return Math.floor(d / 86400) + " " + I.dAgo;
  }

  function statusInfo(src) {
    if (!src.tracked) return { cls: "st-untracked", label: I.untracked };
    switch (src.current_status) {
      case "up":       return { cls: "st-up",       label: I.online };
      case "degraded": return { cls: "st-degraded", label: I.degraded };
      case "down":     return { cls: "st-down",     label: I.offline };
      default:         return { cls: "st-pending",  label: I.pending };
    }
  }

  function errorText(src) {
    if (!src.tracked) return "";
    if (src.current_status === "degraded") return I.degradedMsg;
    if (src.current_status === "down") {
      if (src.last_message === "blocked_page") return I.blockedMsg;
      let m = src.last_message || I.unreachableMsg;
      if (m === "unreachable") m = I.unreachableMsg;
      if (src.last_http_status) m = "HTTP " + src.last_http_status + " · " + m;
      return m;
    }
    return "";
  }

  function barStatusLabel(status) {
    if (status === "up") return I.online;
    if (status === "degraded") return I.degraded;
    if (status === "down") return I.offline;
    return I.pending;
  }

  function barsHtml(bars) {
    if (!bars || !bars.length) return '<span class="uc-bars-empty"></span>';
    return bars.map(function (b) {
      let c = "hb-pending";
      if (b.status === "up") c = "hb-up";
      else if (b.status === "degraded") c = "hb-degraded";
      else if (b.status === "down") c = "hb-down";
      // Hover tooltip: when it was + what state + response time.
      let tip = "";
      if (b.ts) tip += new Date(b.ts * 1000).toLocaleString();
      tip += (tip ? " · " : "") + barStatusLabel(b.status);
      if (b.response_ms != null) tip += " · " + b.response_ms + " ms";
      return '<i class="hb ' + c + '" title="' + esc(tip) + '"></i>';
    }).join("");
  }

  function skeleton(src) {
    return '' +
      '<div class="uptime-card" id="uc-' + esc(src.id) + '" data-id="' + esc(src.id) + '">' +
        '<div class="uc-row">' +
          '<div class="uc-left">' +
            '<span class="uc-dot"></span>' +
            '<div class="uc-title">' +
              '<div class="uc-name-row">' +
                '<span class="uc-name">' + esc(src.label) + "</span>" +
                '<span class="uc-chip" data-role="chip" hidden></span>' +
              "</div>" +
              '<a class="uc-url" data-role="url" target="_blank" rel="noopener noreferrer"></a>' +
            "</div>" +
            '<span class="uc-pill" data-role="pill"></span>' +
          "</div>" +
          '<div class="uc-bars" data-role="bars"></div>' +
          '<div class="uc-stats">' +
            '<div class="uc-stat"><b data-role="pct">—</b><span>' + esc(I.uptime) + "</span></div>" +
            '<div class="uc-stat"><b data-role="avg">—</b><span>' + esc(I.response) + "</span></div>" +
            '<div class="uc-stat"><b data-role="checks">—</b><span>' + esc(I.checks) + "</span></div>" +
            '<div class="uc-stat"><b data-role="last">—</b><span>' + esc(I.lastCheck) + "</span></div>" +
          "</div>" +
        "</div>" +
        '<div class="uc-error" data-role="error" hidden></div>' +
      "</div>";
  }

  function updateCard(src, now) {
    const card = document.getElementById("uc-" + src.id);
    if (!card) return;
    const st = statusInfo(src);
    card.className = "uptime-card " + st.cls + (src.tracked ? "" : " is-untracked");

    const q = function (r) { return card.querySelector('[data-role="' + r + '"]'); };

    const pill = q("pill");
    if (pill) { pill.textContent = st.label; pill.className = "uc-pill " + st.cls; }

    const url = q("url");
    if (url) { url.textContent = host(src.url); url.href = src.url; }

    const chip = q("chip");
    if (chip) {
      if (!src.enabled_source) { chip.textContent = I.disabledSource; chip.hidden = false; }
      else chip.hidden = true;
    }

    const err = q("error");
    if (err) {
      const msg = errorText(src);
      if (msg) {
        err.hidden = false;
        err.className = "uc-error " + (src.current_status === "down" ? "is-down" : "is-warn");
        err.title = (I.lastError || "") + ": " + msg;
        err.innerHTML = '<span class="uc-error-ic">' + (src.current_status === "down" ? "✕" : "!") +
                        '</span><span class="uc-error-msg">' + esc(msg) + "</span>";
      } else { err.hidden = true; err.innerHTML = ""; }
    }

    const bars = q("bars");
    if (bars) bars.innerHTML = barsHtml(src.bars);

    const setv = function (r, v) { const el = q(r); if (el) el.textContent = v; };
    setv("pct", src.tracked && src.uptime_pct != null ? src.uptime_pct + "%" : "—");
    setv("avg", src.tracked && src.avg_ms != null ? src.avg_ms + " ms" : "—");
    setv("checks", src.tracked ? (src.total_checks || 0) : "—");
    setv("last", src.tracked ? relTime(src.last_ts, now) : "—");
  }

  function renderSummary(sources) {
    const el = document.getElementById("uptimeSummary");
    if (!el) return;
    const tracked = sources.filter(function (s) { return s.tracked; });
    if (!tracked.length) {
      el.className = "uptime-summary st-pending";
      el.innerHTML = '<span class="uptime-summary-dot"></span><span>' + esc(I.noneTracked) + "</span>";
      return;
    }
    const down = tracked.filter(function (s) { return s.current_status === "down"; }).length;
    const degraded = tracked.filter(function (s) { return s.current_status === "degraded"; }).length;
    let cls, msg;
    if (down) { cls = "st-down"; msg = I.someDown; }
    else if (degraded) { cls = "st-degraded"; msg = I.someDegraded; }
    else { cls = "st-up"; msg = I.allOperational; }
    el.className = "uptime-summary " + cls;
    let counts = tracked.length + " " + t("Quellen", "sources");
    if (down) counts += " · " + down + " " + I.offline;
    if (degraded) counts += " · " + degraded + " " + I.degraded;
    el.innerHTML = '<span class="uptime-summary-dot"></span><span class="uptime-summary-msg">' + esc(msg) +
                   '</span><span class="uptime-summary-count">' + esc(counts) + "</span>";
  }

  function sortSources(sources) {
    return sources.slice().sort(function (a, b) {
      if (!!a.tracked !== !!b.tracked) return a.tracked ? -1 : 1;
      return 0;
    });
  }

  async function refresh() {
    let data;
    try {
      const resp = await fetch("/api/uptime/status");
      data = await resp.json();
    } catch (e) {
      const grid = document.getElementById("uptimeGrid");
      if (grid && !grid.querySelector(".uptime-card")) grid.innerHTML = '<div class="uptime-empty">⚠ ' + esc(e.message) + "</div>";
      return;
    }
    const now = data.now || Math.floor(Date.now() / 1000);
    const sources = sortSources(data.sources || []);
    const grid = document.getElementById("uptimeGrid");
    renderSummary(sources);

    const newSig = sources.map(function (s) { return s.id + ":" + (s.tracked ? 1 : 0); }).join(",");
    if (grid && newSig !== sig) {
      grid.innerHTML = sources.length ? sources.map(skeleton).join("") : '<div class="uptime-empty">' + esc(I.noneTracked) + "</div>";
      sig = newSig;
    }
    sources.forEach(function (s) { updateCard(s, now); });

    const up = document.getElementById("uptimeUpdated");
    if (up) up.textContent = I.updated + " " + new Date(now * 1000).toLocaleTimeString();
  }

  window.uptimeCheckNow = async function () {
    const btn = document.getElementById("uptimeCheckNow");
    if (btn) { btn.disabled = true; btn.textContent = I.checking; }
    try { await fetch("/api/uptime/check-now", { method: "POST" }); } catch (e) {}
    setTimeout(refresh, 1500);
    setTimeout(refresh, 4000);
    setTimeout(function () { if (btn) { btn.disabled = false; btn.textContent = btn.getAttribute("data-label") || "Check now"; } }, 2500);
  };

  function startPolling() {
    if (timer) return;
    refresh();
    timer = setInterval(refresh, 10000);
  }
  function stopPolling() { if (timer) { clearInterval(timer); timer = null; } }

  document.addEventListener("DOMContentLoaded", function () {
    const btn = document.getElementById("uptimeCheckNow");
    if (btn) btn.setAttribute("data-label", btn.textContent);
    startPolling();
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stopPolling(); else startPolling();
    });
  });
})();
