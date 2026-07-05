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

  function barsSig(bars) {
    return (bars || []).map(function (b) {
      return (b.ts || 0) + ":" + (b.status || "") + ":" + (b.response_ms == null ? "" : b.response_ms);
    }).join(",");
  }

  function barsHtml(bars) {
    if (!bars || !bars.length) return '<span class="uc-bars-empty"></span>';
    return bars.map(function (b) {
      let c = "hb-pending";
      if (b.status === "up") c = "hb-up";
      else if (b.status === "degraded") c = "hb-degraded";
      else if (b.status === "down") c = "hb-down";
      return '<i class="hb ' + c + '" tabindex="0"' +
        ' data-ts="' + (b.ts || "") + '"' +
        ' data-status="' + esc(b.status || "") + '"' +
        ' data-ms="' + (b.response_ms == null ? "" : b.response_ms) + '"' +
        ' data-msg="' + esc(b.message || "") + '"></i>';
    }).join("");
  }

  function barMessage(status, msg) {
    if (status === "degraded") return I.degradedMsg;
    if (status === "down") {
      if (msg === "blocked_page") return I.blockedMsg;
      if (!msg || msg === "unreachable") return I.unreachableMsg;
      return msg;
    }
    return "";
  }

  // ── Custom heartbeat tooltip (works on hover AND tap/click, mobile too) ──
  let _tipEl = null, _pinnedBar = null;
  function _ensureTip() {
    if (!_tipEl) {
      _tipEl = document.createElement("div");
      _tipEl.className = "hb-tip";
      _tipEl.style.display = "none";
      document.body.appendChild(_tipEl);
    }
    return _tipEl;
  }
  function showTip(hb) {
    if (!hb || !document.body.contains(hb)) { hideTip(); return; }
    const tip = _ensureTip();
    const status = hb.getAttribute("data-status");
    const ts = parseInt(hb.getAttribute("data-ts") || "0", 10);
    const ms = hb.getAttribute("data-ms");
    const msg = hb.getAttribute("data-msg");
    const stCls = status === "up" ? "st-up" : status === "degraded" ? "st-degraded" : status === "down" ? "st-down" : "st-pending";
    let html = '<div class="hb-tip-status ' + stCls + '">' + esc(barStatusLabel(status)) + "</div>";
    if (ts) html += '<div class="hb-tip-time">' + esc(new Date(ts * 1000).toLocaleString()) + "</div>";
    const em = barMessage(status, msg);
    if (em) html += '<div class="hb-tip-msg">' + esc(em) + "</div>";
    if (ms !== "" && ms != null) html += '<div class="hb-tip-rt">' + esc(ms) + " ms</div>";
    tip.innerHTML = html;
    tip.style.display = "block";
    const r = hb.getBoundingClientRect();
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = r.left + r.width / 2 - tw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tw - 8));
    let top = r.top - th - 10, below = false;
    if (top < 8) { top = r.bottom + 10; below = true; }
    tip.style.left = left + "px";
    tip.style.top = top + "px";
    tip.setAttribute("data-below", below ? "1" : "0");
    tip.style.setProperty("--arrow-x", (r.left + r.width / 2 - left) + "px");
  }
  function hideTip() { if (_tipEl) _tipEl.style.display = "none"; }
  function initTipEvents() {
    const grid = document.getElementById("uptimeGrid");
    if (grid) {
      grid.addEventListener("mouseover", function (e) { const hb = e.target.closest(".hb"); if (hb && !_pinnedBar) showTip(hb); });
      grid.addEventListener("mouseout", function (e) { const hb = e.target.closest(".hb"); if (hb && !_pinnedBar) hideTip(); });
      grid.addEventListener("focusin", function (e) { const hb = e.target.closest(".hb"); if (hb) { _pinnedBar = hb; showTip(hb); } });
      grid.addEventListener("click", function (e) {
        const hb = e.target.closest(".hb");
        if (!hb) return;
        e.stopPropagation();
        if (_pinnedBar === hb) { _pinnedBar = null; hideTip(); }
        else { _pinnedBar = hb; showTip(hb); }
      });
    }
    document.addEventListener("click", function (e) {
      if (!e.target.closest(".hb") && !e.target.closest(".hb-tip")) { _pinnedBar = null; hideTip(); }
    });
    window.addEventListener("scroll", function () {
      if (_pinnedBar && document.body.contains(_pinnedBar)) showTip(_pinnedBar);
      else { _pinnedBar = null; hideTip(); }
    }, true);
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
    if (bars) {
      const sig = barsSig(src.bars);
      if (bars.getAttribute("data-sig") !== sig) {
        bars.innerHTML = barsHtml(src.bars);
        bars.setAttribute("data-sig", sig);
      }
    }

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
    initTipEvents();
    startPolling();
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stopPolling(); else startPolling();
    });
  });
})();
