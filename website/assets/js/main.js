/*
  PROMETHEUS site behaviour. Vanilla JS, no dependencies.
    1. Theme (light/dark): resolves stored > system preference, persists choice.
    2. OS install tabs: WAI-ARIA pattern (arrows + Home/End, roving tabindex).
    3. Copy buttons: async Clipboard with graceful fallback + "Copied" feedback.
    4. Install-command drift guard: reconciles the page against commands.json so
       the rendered one-liner can never drift from the canonical contract.
    5. Package comparison: renders an accessible table + card grid from
       packages.json (itself asserted against config/bundles-v2 by the test
       suite), with a tier filter and a table/card view toggle.
  Respects prefers-reduced-motion (no animation is used).
*/
(function () {
  "use strict";

  var COMMANDS_URL = "commands.json";
  var PACKAGES_URL = "packages.json";
  var THEME_KEY = "prometheus-theme";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (attrs[k] != null) node.setAttribute(k, attrs[k]);
    }
    if (children) children.forEach(function (c) {
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return node;
  }
  function fmt(n) { return (Math.round(n * 10) / 10).toString(); }

  /* ----- theme ----- */
  function preferredTheme() {
    try { var v = localStorage.getItem(THEME_KEY); if (v === "light" || v === "dark") return v; } catch (e) {}
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }
  function applyTheme(t) {
    if (t === "light") document.documentElement.setAttribute("data-theme", "light");
    else document.documentElement.setAttribute("data-theme", "dark");
    var btn = $(".theme-toggle");
    if (btn) btn.setAttribute("aria-pressed", t === "light" ? "true" : "false");
  }
  function initTheme() {
    applyTheme(preferredTheme());
    var btn = $(".theme-toggle");
    if (btn) btn.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
      try { localStorage.setItem(THEME_KEY, next); } catch (e) {}
      applyTheme(next);
    });
  }

  /* ----- install tabs (WAI-ARIA) ----- */
  function initTabs() {
    var root = $('[data-tablist-root]');
    if (!root) return;
    var tabs = $all('[role="tab"]', root);
    var panels = {};
    $all('[role="tabpanel"]', root).forEach(function (p) { panels[p.id] = p; });

    function activate(tab, focus) {
      tabs.forEach(function (t) {
        var selected = (t === tab);
        t.setAttribute('aria-selected', selected ? 'true' : 'false');
        t.tabIndex = selected ? 0 : -1;
        var panel = panels[t.getAttribute('aria-controls')];
        if (panel) panel.hidden = !selected;
      });
      if (focus !== false) tab.focus();
    }
    function indexFor(tab) { return tabs.indexOf(tab); }

    tabs.forEach(function (tab) {
      tab.addEventListener('click', function () { activate(tab); });
      tab.addEventListener('keydown', function (e) {
        var last = tabs.length - 1;
        var i0 = indexFor(tab);
        var target = null;
        if (e.key === 'ArrowRight' || e.key === 'Right') target = tabs[i0 === last ? 0 : i0 + 1];
        else if (e.key === 'ArrowLeft' || e.key === 'Left') target = tabs[i0 === 0 ? last : i0 - 1];
        else if (e.key === 'Home') target = tabs[0];
        else if (e.key === 'End') target = tabs[last];
        else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); activate(tab); }
        else if (e.key === 'ArrowDown' || e.key === 'Down') {
          var panel = panels[tab.getAttribute('aria-controls')];
          if (panel) { e.preventDefault(); activate(tab, false); panel.focus(); }
        }
        if (target) { e.preventDefault(); activate(target); }
      });
    });
  }

  /* ----- copy buttons ----- */
  function showCopied(btn) {
    btn.classList.add('copied');
    btn.setAttribute('aria-live', 'polite');
    window.setTimeout(function () { btn.classList.remove('copied'); }, 1800);
  }
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      try {
        var ta = document.createElement('textarea');
        ta.value = text; ta.setAttribute('readonly', '');
        ta.style.position = 'absolute'; ta.style.left = '-9999px';
        document.body.appendChild(ta); ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        ok ? resolve() : reject(new Error('copy unavailable'));
      } catch (err) { reject(err); }
    });
  }
  function initCopyButtons() {
    $all('.copy-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cmd = btn.getAttribute('data-command');
        if (!cmd) return;
        copyText(cmd).then(function () { showCopied(btn); }, function () {
          btn.classList.add('copied'); btn.setAttribute('aria-disabled', 'true');
        });
      });
    });
  }

  /* ----- install-command drift guard ----- */
  function reconcileCommands(data) {
    if (!data || !Array.isArray(data.tabs)) return;
    var byOs = {};
    data.tabs.forEach(function (t) { byOs[t.id] = t; });
    $all('.cmd[data-os]').forEach(function (code) {
      var t = byOs[code.getAttribute('data-os')];
      if (!t) return;
      code.setAttribute('data-command', t.command);
      code.textContent = t.command;
    });
    $all('.copy-btn[data-os]').forEach(function (btn) {
      var t = byOs[btn.getAttribute('data-os')];
      if (t) btn.setAttribute('data-command', t.command);
    });
    $all('[data-manual-os]').forEach(function (code) {
      var t = byOs[code.getAttribute('data-manual-os')];
      if (t && typeof t.manual === 'string') code.textContent = t.manual;
    });
  }

  function fetchJSON(url) {
    if (!window.fetch) return Promise.resolve(null);
    return fetch(url, { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error(url + ' HTTP ' + r.status); return r.json(); });
  }

  function loadCommands() {
    fetchJSON(COMMANDS_URL).then(reconcileCommands).catch(function () { /* HTML holds the canonical copy */ });
  }

  /* ----- package comparison ----- */
  var TIER_LABEL = {
    "cpu": "CPU",
    "gpu-8": "8 GB GPU",
    "gpu-12": "12 GB GPU",
    "gpu-24": "24 GB GPU",
    "addon": "Add-on"
  };

  function roleLabel(role) {
    return role.charAt(0).toUpperCase() + role.slice(1);
  }
  function capsShort(caps) {
    var want = { text: "text", image: "vision", tools: "tools", coding: "coding", json: "JSON", thinking: "reasoning", embeddings: "embed", agentic_coding: "agentic", repository_navigation: "nav", reasoning: "reasoning", coding_review: "review" };
    return caps.map(function (c) { return want[c] || c; }).join(", ");
  }
  function hwFit(p) {
    if (p.addon) return "Review add-on (no controller)";
    if (p.min_vram_gb === 0) return "CPU · " + p.min_ram_gb + "+ GB RAM";
    return p.rec_vram_gb || p.min_vram_gb + "+ GB VRAM";
  }

  function renderTable(container, packages) {
    container.innerHTML = "";
    var tbl = el("table", { class: "pk-table" });
    var caption = el("caption", {}, ["PROMETHEUS model packages: roles, approximate download size, hardware fit, modalities, and status."]);
    var thead = el("thead", {}, [el("tr", {}, [
      el("th", { scope: "col" }, ["Package"]),
      el("th", { scope: "col", class: "hide-sm" }, ["Hardware fit"]),
      el("th", { scope: "col" }, ["Roles (model)"]),
      el("th", { scope: "col", class: "num hide-sm" }, ["~Download"]),
      el("th", { scope: "col", class: "num hide-sm" }, ["Context"]),
      el("th", { scope: "col", class: "hide-sm" }, ["Status"])
    ])]);
    var tbody = el("tbody", {});
    packages.forEach(function (p) {
      var rolesCell = el("td", {});
      p.roles.forEach(function (r, i) {
        if (i) rolesCell.appendChild(el("br"));
        rolesCell.appendChild(el("span", { class: "pk-role-line" }, [roleLabel(r.role) + ": "]));
        rolesCell.appendChild(el("code", {}, [r.model]));
        if (r.optional) rolesCell.appendChild(el("span", { class: "opt" }, [" (opt)"]));
      });
      var tr = el("tr", { class: "tier-" + p.tier + " status-" + p.status }, [
        el("td", {}, [
          el("span", { class: "pk-dot" }),
          el("span", { class: "pk-name" }, [p.name]),
          el("div", { class: "pk-sub" }, [p.subtitle])
        ]),
        el("td", { class: "hide-sm" }, [hwFit(p)]),
        rolesCell,
        el("td", { class: "num hide-sm" }, ["~" + fmt(p.core_download_gb) + " GB"]),
        el("td", { class: "num hide-sm" }, [fmt(p.default_context / 1000) + "K" + (p.context_ceiling > p.default_context ? "→" + fmt(p.context_ceiling / 1000) + "K" : "")]),
        el("td", { class: "hide-sm" }, [p.status === "stable" ? "Stable" : "Experimental"])
      ]);
      tbody.appendChild(tr);
    });
    tbl.appendChild(caption); tbl.appendChild(thead); tbl.appendChild(tbody);
    container.appendChild(tbl);
  }

  function renderCards(container, packages) {
    container.innerHTML = "";
    var grid = el("div", { class: "pk-grid" });
    packages.forEach(function (p) {
      var head = el("div", { class: "pk-card-head" }, [
        el("h3", {}, [el("span", { class: "pk-dot" }), p.name]),
        el("span", { class: "badge " + (p.status === "stable" ? "ok" : "warn") }, [p.status === "stable" ? "Stable" : "Experimental"])
      ]);
      var sub = el("div", { class: "pk-sub" }, [p.subtitle + " · " + hwFit(p)]);
      var desc = el("p", { class: "pk-desc" }, [p.description]);
      var roles = el("div", { class: "pk-roles" });
      p.roles.forEach(function (r) {
        var line = [el("span", { class: "role-tag" }, [roleLabel(r.role)])];
        line.push(el("code", {}, [r.model]));
        line.push(el("span", { class: "opt" }, ["  ~" + fmt(r.download_gb) + " GB" + (r.optional ? " · optional" : "")]));
        roles.appendChild(el("div", { class: "pk-role" }, line));
      });
      var meta = el("div", { class: "pk-meta" }, [
        el("span", {}, ["Context: " + fmt(p.default_context / 1000) + "K" + (p.context_ceiling > p.default_context ? "–" + fmt(p.context_ceiling / 1000) + "K" : "")]),
        el("span", {}, ["Core ~" + fmt(p.core_download_gb) + " GB"]),
        el("span", {}, [p.unlimited_local_sessions ? "Quota-free local" : "Metered"])
      ]);
      grid.appendChild(el("div", { class: "pk-card tier-" + p.tier + " status-" + p.status }, [head, sub, desc, roles, meta]));
    });
    container.appendChild(grid);
  }

  function initPackages() {
    var root = $("#packages");
    if (!root) return;
    var tableHost = $(".pk-table-host", root);
    var cardHost = $(".pk-cards-host", root);
    if (!tableHost || !cardHost) return;

    var state = { data: [], filter: "all", view: "table" };

    function filtered() {
      if (state.filter === "all") return state.data;
      return state.data.filter(function (p) { return p.tier === state.filter; });
    }
    function paint() {
      var list = filtered();
      var status = $(".pk-status", root);
      if (status) status.textContent = list.length + " of " + state.data.length + " packages";
      if (state.view === "table") {
        tableHost.hidden = false; cardHost.hidden = true;
        renderTable(tableHost, list);
      } else {
        tableHost.hidden = true; cardHost.hidden = false;
        renderCards(cardHost, list);
      }
    }

    var filter = $(".pk-filter", root);
    if (filter) filter.addEventListener("change", function () { state.filter = filter.value; paint(); });
    $all(".pk-view button", root).forEach(function (b) {
      b.addEventListener("click", function () {
        state.view = b.getAttribute("data-view");
        $all(".pk-view button", root).forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
        paint();
      });
    });

    fetchJSON(PACKAGES_URL).then(function (doc) {
      if (!doc || !Array.isArray(doc.packages) || !doc.packages.length) return;
      state.data = doc.packages;
      paint();
    }).catch(function () { /* static fallback already present */ });
  }

  function init() { initTheme(); initTabs(); initCopyButtons(); initPackages(); loadCommands(); }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
