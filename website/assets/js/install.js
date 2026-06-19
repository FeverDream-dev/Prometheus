/*
  PROMETHEUS install site enhancement.
  - Reads website/commands.json and reconciles the displayed one-liner per OS tab
    so the page can never drift from the canonical install contract.
  - Implements the WAI-ARIA tabs pattern (arrow-key + Home/End navigation,
    roving tabindex) for the OS tablist.
  - Powers the copy button with a visible "Copied!" confirmation and a graceful
    fallback when the async Clipboard API is unavailable.
  No external dependencies. Respects prefers-reduced-motion (no animation).
*/
(function () {
  "use strict";

  var COMMANDS_URL = "commands.json";

  function $(selector, root) { return (root || document).querySelector(selector); }
  function $all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  /* ----- tabs (WAI-ARIA pattern) ----- */
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

    tabs.forEach(function (tab, i) {
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
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      try {
        var ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'absolute';
        ta.style.left = '-9999px';
        document.body.appendChild(ta);
        ta.select();
        var ok = document.execCommand('copy');
        document.body.removeChild(ta);
        ok ? resolve() : reject(new Error('copy command unavailable'));
      } catch (err) { reject(err); }
    });
  }

  function initCopyButtons() {
    $all('.copy-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cmd = btn.getAttribute('data-command');
        if (!cmd) return;
        copyText(cmd).then(function () { showCopied(btn); }, function () {
          btn.classList.add('copied');
          btn.setAttribute('aria-disabled', 'true');
        });
      });
    });
  }

  /* ----- reconcile displayed commands from commands.json (drift guard) ----- */
  function reconcileCommands(data) {
    if (!data || !Array.isArray(data.tabs)) return;
    var byOs = {};
    data.tabs.forEach(function (t) { byOs[t.id] = t; });

    $all('.cmd[data-os]').forEach(function (code) {
      var t = byOs[code.getAttribute('data-os')];
      if (!t) return;
      if (code.getAttribute('data-command') !== t.command) code.setAttribute('data-command', t.command);
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

  function loadCommands() {
    if (!window.fetch) return;
    fetch(COMMANDS_URL, { cache: 'no-cache' })
      .then(function (r) { if (!r.ok) throw new Error('commands.json HTTP ' + r.status); return r.json(); })
      .then(reconcileCommands)
      .catch(function () { /* static HTML already holds the canonical commands */ });
  }

  function init() { initTabs(); initCopyButtons(); loadCommands(); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
