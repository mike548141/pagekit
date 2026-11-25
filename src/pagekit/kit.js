/* pagekit — reader features for any HTML deliverable.
 *
 * Every feature attaches to plain semantic HTML (a <table> with a <thead> and
 * <tbody>, headings, <details>, <section class="pk-part">), so a page gets
 * them by including this script, whatever produced its markup. Every feature
 * is an enhancement: with scripting off, or on paper, the page shows
 * everything.
 *
 * Built to run inside the locked-down frames that SharePoint, OneDrive and
 * Teams preview a file in: no storage, no history writes, no pop-ups, no
 * print dialog from script. Each of those is tried, never relied on.
 *
 * Opt a table out with  data-pk="off"  (on the table or any ancestor).
 * Change a table's preview with  data-pk-preview="5"  or  "all".
 *
 * A page carries the core (everything outside a fence) and only the features
 * it uses: each optional feature, and each part features share, sits between
 * a  pk:feature NAME  line and a  pk:end NAME  line, and the build leaves
 * out the ones a page does not use (pagekit.FEATURES says which needs which).
 * So the core never calls into a feature: a feature lends its behaviour
 * through on() and the core asks for it through fire(), which does nothing
 * when the feature is not there. A test holds that no part of this file uses
 * a name defined only in a feature it does not need.
 */
(function () {
"use strict";
var doc = document, root = doc.documentElement;
/* A page built by pagekit itself (as opposed to an older page the features
 * were added to) owns its in-page links; an older page keeps its own, unless
 * its build made it into parts (pagekit.mark_parts), when a link has to show
 * the part it points into. */
var OWN = !!doc.getElementById("pk-main") || doc.querySelectorAll(".pk-part").length > 1;
/* Inside someone else's viewer (SharePoint, OneDrive and Teams show a file in
 * a frame), the viewer can take over in-page links before this script sees
 * them: measured on SharePoint Online (November 2026), a click on a part's link
 * scrolled to where the hidden part sat and wrote the link into the viewer's
 * own address bar. So in a frame, in-page links stop being plain "#" links
 * (the target moves to data-pk-href) and this script follows them itself. */
var FRAMED = (function () { try { return window.self !== window.top; } catch (e) { return true; } })();

function each(list, fn) { Array.prototype.forEach.call(list, fn); }
function storeGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
function storeSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
function setHash(id) {
  try { history.replaceState(null, "", "#" + id); } catch (e) {}
}

/* The features this copy of the kit carries, written in by the build. */
var KIT = "@PK-KIT@";
/* What a feature lends the core, by moment: "table" (each table, at load),
 * "start" (before the panel is built), "built" (after it), "open" (make a
 * node visible), "shown" (something hidden just showed), "find" (the reader
 * is about to use find-in-page), "print" and "unprint", "frame" and
 * "relayout" (pinned copies follow the page), "inpane" (a control inside the
 * side pane). Handlers run in the order the features sit in this file. */
var hooks = {};
function on(name, fn) { (hooks[name] = hooks[name] || []).push(fn); }
function fire(name, arg) { (hooks[name] || []).forEach(function (fn) { fn(arg); }); }

/* Tables that are pictures, controls or already managed are left alone:
 * anything opted out and anything in a figure, plus whatever the page names in
 * <meta name="pk-skip" content="selectors"> (pagekit.set_skip): an older
 * page's own layout tables, or tables that manage their own cells. */
var SKIP = '[data-pk="off"], figure';
(function () {
  var m = doc.querySelector('meta[name="pk-skip"]'), s = m && m.getAttribute("content");
  if (!s) return;
  try { doc.querySelector(s); SKIP += ", " + s; } catch (e) {}
})();
function skipped(t) { return !!(t.closest && t.closest(SKIP)); }
function byId(id) {
  if (!id) return null;
  try { return doc.getElementById(decodeURIComponent(id)); } catch (e) { return doc.getElementById(id); }
}
function targetOf(h) { return h && h.length > 1 && h.charAt(0) === "#" ? byId(h.slice(1)) : null; }

var LOCKED = FRAMED && String(window.origin) === "null";

/* The bottom edge of whatever is pinned across the top of the window (a
 * contents bar, the parts bar on a narrow screen), so nothing hides under it. */
function stickyTop() {
  var v = parseFloat(getComputedStyle(root).getPropertyValue("--pk-sticky-top"));
  if (!isNaN(v)) return v;
  var bottom = 0;
  each(doc.querySelectorAll("nav.toc, [data-pk-sticky], .pk-rail"), function (n) {
    var pos = getComputedStyle(n).position;
    if (pos !== "sticky" && pos !== "fixed") return;
    var r = n.getBoundingClientRect();
    if (r.width < innerWidth * 0.5) return;
    if (r.top <= 1 && r.bottom > bottom) bottom = r.bottom;
  });
  return bottom;
}
/* The same edge as it will be once the page has scrolled to a target. */
function stickyHeight() {
  var h = 0;
  each(doc.querySelectorAll("nav.toc, [data-pk-sticky], .pk-rail"), function (n) {
    var pos = getComputedStyle(n).position;
    if (pos !== "sticky" && pos !== "fixed") return;
    var r = n.getBoundingClientRect();
    if (r.width < innerWidth * 0.5) return;
    if (r.height > h) h = r.height;
  });
  return h;
}

/* Once a frame: whatever is pinned to the top follows the page, then the
 * panel marks where the reader is. A relayout makes pinned copies re-measure. */
var pending = false;
function floatAll() {
  if (pending) return;
  pending = true;
  requestAnimationFrame(function () {
    pending = false;
    if (hooks.frame) fire("frame", stickyTop());
    spy();
  });
}
function rebuildAll() { fire("relayout"); floatAll(); }

/* ── 3. The panel: contents, search and controls, down the left ────────────
 * A strip of section names across the top grows into two tiers on a long
 * document and crowds the words, so every page with sections gets one panel
 * on the left instead: a search over the whole document, the light and dark
 * switch, one expand/collapse control, and the contents. Only the current
 * section's sub-sections are listed under it, so the list stays short. It is
 * written for a laptop or desktop screen; on a smaller one it opens from a
 * Contents button.
 *
 * A page made of <section class="pk-part"> shows one part at a time, chosen
 * here; the other parts stay reachable by links, search, find and print. Any
 * other page scrolls, and the panel follows the reader down it. */
var PANEL_MIN = 1100;
var parts = [], current = null, allMode = false, live = null, allBtn = null;
var UNTIL_FOUND = "onbeforematch" in doc.documentElement;
var panel = null, navList = null, tier = [], foldBtn = null, results = null, query = null;

function partOf(el) { return el && el.closest ? el.closest(".pk-part") : null; }
function conceal(p) { if (UNTIL_FOUND) p.setAttribute("hidden", "until-found"); else p.hidden = true; }

/* Words from separate elements (a section number, then its title) are kept
 * apart: "02 Background", not "02Background". Reading-time notes and
 * controls inside a heading are not part of its name. */
function words(el) {
  var c = el.cloneNode(true);
  each(c.querySelectorAll(".len, button, .sr-only, .pk-sr, script, style"), function (n) { n.parentNode.removeChild(n); });
  var out = [];
  (function walk(n) {
    if (n.nodeType === 3) out.push(n.nodeValue);
    else { out.push(" "); each(n.childNodes, walk); out.push(" "); }
  })(c);
  return out.join("").replace(/\s+/g, " ").trim();
}
/* "Part 2 · How the service runs" → ["2", "How the service runs"]. */
function split(label) {
  var m = label.match(/^Part\s+([0-9A-Z]+)\s*[·:.\-–—]\s*(.+)$/i) ||
          label.match(/^(\d+(?:\.\d+)*|[A-Z])\s*[·.:]?\s+(.{3,})$/);
  return m ? [m[1], m[2]] : ["", label];
}
function before(a, b) { return !!(a.compareDocumentPosition(b) & 4); }
function idFor(el, hint) {
  if (!el.id) el.id = "pk-" + hint;
  return el.id;
}
var OUTSIDE = ".pk-panel, .pk-float, .pk-partnav, .pk-tablist, .pk-pane, .pk-copymenu, .pk-toast, nav, header, footer, figure, .pane, .toolbar, script, style";
/* A page can keep a region out of the panel's contents (data-pk-nav="off": a
 * tree of folds is not sub-sections) and out of the panel's search
 * (data-pk-find="off": text the page keeps hidden for its own script). */
var NAV_OFF = '[data-pk-nav="off"]', FIND_OFF = '[data-pk-find="off"]';

/* The entries, read from what the page already says about itself: its parts;
 * else its own contents bar; else its h2 headings; else its panel titles. */
function gather() {
  if (parts.length >= 2) {
    /* A part titled "Part 2 · Costs" keeps its own number; when any part does,
     * a part without one goes unnumbered rather than out of step. */
    var ent = parts.map(function (p) {
      var t = p.getAttribute("data-pk-title") || words(p.querySelector("h2") || p);
      return { p: p, t: t, m: t.match(/^Part\s+([0-9A-Z]+)\s*[·:.\-–—]\s*(.+)$/i) };
    });
    var own = ent.some(function (x) { return x.m; });
    return ent.map(function (x, i) {
      return { el: x.p, num: x.m ? x.m[1] : (own ? "" : String(i + 1)), title: x.m ? x.m[2] : x.t, part: x.p };
    });
  }
  var list = [], toc = doc.querySelector("nav.toc");
  if (toc) {
    var links = toc.querySelectorAll(".parts a[href^='#']");
    if (!links.length) links = toc.querySelectorAll("a[href^='#']");
    each(links, function (a) {
      var el = byId(a.getAttribute("href").slice(1)), sp = split(words(a));
      if (!el) return;
      var grp = toc.querySelector('.grp[data-part="' + el.id + '"]'), kids = null;
      if (grp) {
        kids = [];
        each(grp.querySelectorAll("a[href^='#']"), function (c) {
          var t = byId(c.getAttribute("href").slice(1));
          if (t) kids.push({ el: t, title: words(c) });
        });
      }
      list.push({ el: el, num: sp[0], title: sp[1], kids: kids });
    });
    if (list.length >= 2) return list;
    list = [];
  }
  var hs = [].filter.call(doc.querySelectorAll("h2"), function (h) {
    return !h.closest(OUTSIDE) && !h.closest(NAV_OFF) && !h.classList.contains("pk-part-title") && words(h);
  });
  if (hs.length < 2) hs = [].filter.call(doc.querySelectorAll("details > summary"), function (s) {
    return !s.closest(OUTSIDE) && !s.closest(NAV_OFF) && !s.parentNode.parentNode.closest("details") && words(s);
  });
  return hs.length >= 2 ? hs.map(function (h) { var sp = split(words(h)); return { el: h, num: sp[0], title: sp[1] }; }) : [];
}

/* A section's sub-sections: its own list where the page gave one, else the
 * h3 headings and panel titles between it and the next section. */
function kidsOf(i) {
  var e = tier[i];
  if (e.kids) return e.kids;
  var from = e.el, to = tier[i + 1] ? tier[i + 1].el : null, out = [];
  var scope = e.part || doc;
  each(scope.querySelectorAll("h3, h2, details > summary"), function (h) {
    if (h === from || h.closest(OUTSIDE) || h.closest(NAV_OFF) || h.classList.contains("pk-part-title")) return;
    if (!e.part) {
      if (h.tagName === "H2" && !e.part) return;
      if (!(from.contains(h) || before(from, h))) return;
      if (to && !before(h, to)) return;
    }
    if (h.tagName === "SUMMARY" && h.querySelector("h2, h3")) return;
    var t = words(h);
    if (t) out.push({ el: h, title: t });
  });
  if (e.part) {
    var h2 = out.filter(function (o) { return o.el.tagName === "H2"; });
    if (h2.length >= 2) out = h2;
  }
  e.kids = out.slice(0, 40);
  return e.kids;
}

var ICON = {
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M20.5 20.5 16 16"/></svg>',
  moon: '<svg class="pk-moon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 13.2A8.5 8.5 0 1 1 10.8 3.5a6.6 6.6 0 0 0 9.7 9.7z"/></svg>',
  sun: '<svg class="pk-sun" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4.2"/><path d="M12 2v2.4M12 19.6V22M4.9 4.9l1.7 1.7M17.4 17.4l1.7 1.7M2 12h2.4M19.6 12H22M4.9 19.1l1.7-1.7M17.4 6.6l1.7-1.7"/></svg>',
  menu: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h17M3.5 12h17M3.5 17.5h17"/></svg>',
  shut: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M11.5 6 5.5 12l6 6M18.5 6l-6 6 6 6"/></svg>',
  open: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12.5 6l6 6-6 6M5.5 6l6 6-6 6"/></svg>'
};

function el(tag, cls, html) {
  var n = doc.createElement(tag);
  if (cls) n.className = cls;
  if (html) n.innerHTML = html;
  return n;
}
function clip(t, n) { return t.length <= n ? t : t.slice(0, n).replace(/\s+\S*$/, "") + "…"; }
function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
function num(el, a) { var v = parseFloat(el.getAttribute(a)); return isNaN(v) ? null : v; }
function boxOf(svg) {
  var vb = svg.viewBox && svg.viewBox.baseVal;
  return vb && vb.width ? { w: vb.width, h: vb.height } : null;
}

function buildPanel() {
  if (root.getAttribute("data-pk-panel") === "off") return;
  tier = gather();
  if (tier.length < 2) return;
  panel = el("aside", "pk-panel");
  panel.id = "pk-panel";
  panel.setAttribute("aria-label", "Contents, search and page controls");
  var top = el("div", "pk-ptop");
  var box = el("label", "pk-search", ICON.search);
  query = el("input");
  query.type = "search";
  query.placeholder = "Search this document";
  query.setAttribute("aria-label", "Search this document");
  query.setAttribute("autocomplete", "off");
  box.appendChild(query);
  top.appendChild(box);
  var tools = el("div", "pk-tools");
  var folds = doc.querySelectorAll("details");
  if ([].some.call(folds, function (d) { return !d.closest(".pk-panel"); })) {
    foldBtn = el("button", "pk-tool pk-foldall");
    foldBtn.type = "button";
    foldBtn.addEventListener("click", function () {
      var open = !allFoldsOpen();
      each(doc.querySelectorAll("details"), function (d) { if (!d.closest(".pk-panel")) d.open = open; });
      foldLabel();
    });
    tools.appendChild(foldBtn);
  }
  var th = el("button", "pk-tool pk-themebtn", ICON.moon + ICON.sun);
  th.type = "button";
  th.setAttribute("data-pk-theme", "");
  tools.appendChild(th);
  var fold = el("button", "pk-tool pk-slimbtn", ICON.shut);
  fold.type = "button";
  fold.title = "Fold the panel away";
  fold.setAttribute("aria-label", "Fold the panel away to a narrow bar");
  fold.addEventListener("click", function () { slim(true); });
  tools.appendChild(fold);
  top.appendChild(tools);
  panel.appendChild(top);
  panel.appendChild(slimBar());
  results = el("div", "pk-results");
  results.hidden = true;
  results.setAttribute("aria-live", "polite");
  panel.appendChild(results);
  var nav = el("nav", "pk-nav");
  nav.setAttribute("aria-label", "Contents");
  navList = el("ol", "pk-l1");
  tier.forEach(function (e, i) {
    var li = el("li", "pk-i1"), a = el("a", "pk-a1");
    a.href = "#" + idFor(e.el, "s" + (i + 1));
    if (e.num) a.appendChild(el("span", "pk-pn")).textContent = e.num;
    a.appendChild(el("span", "pk-pt")).textContent = e.title;
    li.appendChild(a);
    e.li = li;
    e.a = a;
    navList.appendChild(li);
  });
  nav.appendChild(navList);
  panel.appendChild(nav);
  if (parts.length >= 2) {
    allBtn = el("button", "pk-btn pk-allbtn");
    allBtn.type = "button";
    allBtn.addEventListener("click", function () {
      if (allMode) showPart(current || parts[0], { scroll: "top" });
      else { showAll(); scrollToEl(doc.getElementById("pk-main") || parts[0]); }
    });
    panel.appendChild(allBtn);
  }
  doc.body.appendChild(panel);
  var opener = el("button", "pk-navbtn", ICON.menu + "<span>Contents</span>");
  opener.type = "button";
  opener.setAttribute("aria-controls", "pk-panel");
  opener.setAttribute("aria-expanded", "false");
  opener.addEventListener("click", function () { drawer(!root.classList.contains("pk-drawer")); });
  doc.body.appendChild(opener);
  var scrim = el("div", "pk-scrim");
  scrim.addEventListener("click", function () { drawer(false); });
  doc.body.appendChild(scrim);
  root.classList.add("pk-paneled");
  panel.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[data-pk-href], a[href^='#']") : null;
    if (!a) return;
    e.preventDefault();
    var id = linkTarget(a).slice(1), t = byId(id);
    if (t) go(t, id);
    if (innerWidth < PANEL_MIN) drawer(false);
  });
  query.addEventListener("input", function () { clearTimeout(query._t); query._t = setTimeout(search, 120); });
  query.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { query.value = ""; search(); }
    if (e.key === "Enter") { var f = results.querySelector("a"); if (f) f.click(); }
  });
  foldLabel();
  tame(panel);
  mark(true);
  if (storeGet("pagekit-panel") === "slim") slim(true, true);
}

/* Folded away, the panel is a narrow bar down the left holding the same
 * controls as icons; a click on the bar, or its open button, brings the panel
 * back. Laptop and desktop only: a smaller screen already hides it. The choice
 * is remembered where the browser allows (not inside a file viewer). */
var slimFold = null;
function slimBar() {
  var bar = el("div", "pk-slimbar");
  function tool(cls, html, label, fn) {
    var b = el("button", "pk-tool " + cls, html);
    b.type = "button";
    b.title = label;
    b.setAttribute("aria-label", label);
    if (fn) b.addEventListener("click", function (e) { e.stopPropagation(); fn(); });
    bar.appendChild(b);
    return b;
  }
  tool("pk-slimopen", ICON.open, "Open the panel", function () { slim(false); });
  tool("pk-slimsearch", ICON.search, "Search this document", function () {
    slim(false);
    try { query.focus({ preventScroll: true }); } catch (e) {}
  });
  if (foldBtn) slimFold = tool("pk-slimfold", "", "", function () { foldBtn.click(); });
  tool("pk-themebtn", ICON.moon + ICON.sun, "Light or dark", null).setAttribute("data-pk-theme", "");
  bar.addEventListener("click", function (e) { if (!e.target.closest("button")) slim(false); });
  return bar;
}
function slim(on, quiet) {
  root.classList.toggle("pk-slim", on);
  if (!quiet) storeSet("pagekit-panel", on ? "slim" : "open");
  /* The page's width changes, so pinned headings and wide tables re-measure
   * once the panel has finished moving. */
  setTimeout(rebuildAll, 220);
}

function drawer(on) {
  root.classList.toggle("pk-drawer", on);
  var b = doc.querySelector(".pk-navbtn");
  if (b) b.setAttribute("aria-expanded", on ? "true" : "false");
  if (on && query) try { query.focus({ preventScroll: true }); } catch (e) {}
}

function allFoldsOpen() {
  return ![].some.call(doc.querySelectorAll("details"), function (d) { return !d.open && !d.closest(".pk-panel"); });
}
/* One control that says what it will do next, rather than two buttons of
 * which one always does nothing. */
function foldLabel() {
  if (!foldBtn) return;
  var open = allFoldsOpen();
  foldBtn.innerHTML = '<span aria-hidden="true">' + (open ? "−" : "+") + "</span> " + (open ? "Collapse all" : "Expand all");
  foldBtn.setAttribute("aria-label", open ? "Collapse every section" : "Expand every section");
  if (slimFold) {
    slimFold.innerHTML = '<span aria-hidden="true">' + (open ? "−" : "+") + "</span>";
    slimFold.title = open ? "Collapse all" : "Expand all";
    slimFold.setAttribute("aria-label", foldBtn.getAttribute("aria-label"));
  }
}

/* Which section, and which sub-section, the reader is in; only that section
 * lists its sub-sections. */
var curI = -1, spyList = [];
function mark(force) {
  if (!tier.length) return;
  var i = 0, line = stickyTop() + 120;
  if (parts.length >= 2) i = allMode ? -1 : parts.indexOf(current);
  else {
    /* At the foot of the page the last sections can never scroll up to the
     * line, so there the last one on screen is the one being read. */
    var foot = pageYOffset + innerHeight >= doc.documentElement.scrollHeight - 2;
    tier.forEach(function (e, k) {
      var r = e.el.getBoundingClientRect();
      if ((r.height || r.width) && r.top <= (foot ? innerHeight * 0.85 : line)) i = k;
    });
  }
  if (i !== curI || force) {
    curI = i;
    tier.forEach(function (e, k) {
      var on = k === i;
      e.li.classList.toggle("pk-cur", on);
      if (on) e.a.setAttribute("aria-current", "true"); else e.a.removeAttribute("aria-current");
      var old = e.li.querySelector(".pk-l2");
      if (old && !on) e.li.removeChild(old);
      if (on && !old) {
        var ks = kidsOf(k);
        if (ks.length >= 2) {
          var ol = el("ol", "pk-l2");
          ks.forEach(function (c, n) {
            var li = el("li"), a = el("a");
            a.href = "#" + idFor(c.el, (e.el.id || "s" + k) + "-" + (n + 1));
            a.textContent = c.title;
            li.appendChild(a);
            ol.appendChild(li);
            c.a = a;
          });
          e.li.appendChild(ol);
          tame(ol);
        }
      }
    });
    spyList = i >= 0 ? (tier[i].kids || []) : [];
    keepInView(i >= 0 ? tier[i].a : null);
  }
  var here = null;
  spyList.forEach(function (c) { var r = c.el.getBoundingClientRect(); if (r.height && r.top <= line) here = c; });
  if (!here && spyList.length) here = null;
  spyList.forEach(function (c) { if (c.a) c.a.classList.toggle("pk-here", c === here); });
  if (here && here.a) keepInView(here.a);
}
function keepInView(a) {
  if (!a || !panel || panel.scrollHeight <= panel.clientHeight) return;
  var r = a.getBoundingClientRect(), p = panel.getBoundingClientRect();
  if (r.top < p.top + 90 || r.bottom > p.bottom - 20) panel.scrollTop += r.top - p.top - p.height / 3;
}
function spy() { if (!searching()) mark(false); }
function searching() { return results && !results.hidden; }

/* ── 4. Search the whole document ─────────────────────────────────────────
 * Finds the words anywhere in the file, including parts not on screen, rows
 * a long table is not showing and closed sections; a result opens whatever
 * holds it. */
var BLOCKS = "p, li, td, th, dd, dt, h1, h2, h3, h4, summary, figcaption, caption, blockquote, pre";
var blocks = null;
function index() {
  if (blocks) return blocks;
  blocks = [].filter.call(doc.querySelectorAll(BLOCKS), function (b) {
    return !b.closest(OUTSIDE) && !b.closest(FIND_OFF) && !b.querySelector(BLOCKS) && b.textContent.trim();
  });
  return blocks;
}
function sectionOf(b) {
  var p = partOf(b);
  if (p && parts.length) return tier[parts.indexOf(p)];
  var found = null;
  tier.forEach(function (e) { if (e.el === b || e.el.contains(b) || before(e.el, b)) found = e; });
  return found;
}
function search() {
  var q = query.value.trim().toLowerCase();
  results.innerHTML = "";
  if (q.length < 2) { results.hidden = true; panel.classList.remove("pk-finding"); mark(true); return; }
  results.hidden = false;
  panel.classList.add("pk-finding");
  var hits = [], LIMIT = 80;
  index().some(function (b) {
    var t = b.textContent.replace(/\s+/g, " "), at = t.toLowerCase().indexOf(q);
    if (at < 0) return false;
    hits.push({ b: b, t: t, at: at });
    return hits.length > LIMIT;
  });
  var more = hits.length > LIMIT;
  if (more) hits.length = LIMIT;
  results.appendChild(el("p", "pk-rcount")).textContent = hits.length
    ? (more ? "More than " + LIMIT + " matches; the first " + LIMIT + ":" : hits.length + (hits.length === 1 ? " match" : " matches"))
    : "No matches";
  var lastSec = {}, ol = null;
  hits.forEach(function (h, n) {
    var s = sectionOf(h.b);
    if (s !== lastSec) {
      lastSec = s;
      results.appendChild(el("p", "pk-rsec")).textContent = s ? ((s.num ? s.num + "  " : "") + s.title) : "Introduction";
      ol = results.appendChild(el("ol", "pk-rlist"));
    }
    var a = el("a");
    a.href = "#" + idFor(h.b, "hit-" + n + "-" + Math.random().toString(36).slice(2, 7));
    var from = Math.max(0, h.at - 50), to = Math.min(h.t.length, h.at + q.length + 70);
    a.appendChild(doc.createTextNode((from ? "…" : "") + h.t.slice(from, h.at)));
    a.appendChild(el("mark")).textContent = h.t.slice(h.at, h.at + q.length);
    a.appendChild(doc.createTextNode(h.t.slice(h.at + q.length, to) + (to < h.t.length ? "…" : "")));
    a.addEventListener("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      go(h.b, h.b.id, true);
      if (innerWidth < PANEL_MIN) drawer(false);
    });
    ol.appendChild(el("li")).appendChild(a);
  });
}

function say(text) { if (live) { live.textContent = ""; setTimeout(function () { live.textContent = text; }, 30); } }

function scrollToEl(t) {
  var y = t.getBoundingClientRect().top + pageYOffset - stickyHeight() - 16;
  try { scrollTo({ top: Math.max(0, y), behavior: "instant" }); } catch (e) { scrollTo(0, Math.max(0, y)); }
}

function label(all) {
  if (allBtn) allBtn.textContent = all ? "Show one part at a time" : "Show all parts on one page";
}

function showPart(p, opts) {
  opts = opts || {};
  allMode = false;
  root.classList.remove("pk-all");
  root.classList.add("pk-one");
  parts.forEach(function (q) { if (q === p) q.removeAttribute("hidden"); else conceal(q); });
  current = p;
  label(false);
  fire("shown");
  rebuildAll();
  mark(true);
  if (!opts.quiet) say("Showing part " + (parts.indexOf(p) + 1) + " of " + parts.length + ": " + (p.getAttribute("data-pk-title") || ""));
  if (opts.hash !== false) setHash(p.id);
  if (opts.scroll !== false) {
    var main = doc.getElementById("pk-main") || p;
    if (main.getBoundingClientRect().top < 0 || opts.scroll === "top") scrollToEl(main);
    if (opts.focus) { var h = p.querySelector(".pk-part-title"); if (h) { h.setAttribute("tabindex", "-1"); try { h.focus({ preventScroll: true }); } catch (e) {} } }
  }
}

function showAll() {
  allMode = true;
  root.classList.remove("pk-one");
  root.classList.add("pk-all");
  parts.forEach(function (q) { q.removeAttribute("hidden"); });
  label(true);
  fire("shown");
  rebuildAll();
  mark(true);
}

function initParts() {
  parts = [].slice.call(doc.querySelectorAll(".pk-part"));
  if (parts.length < 2) { parts = []; return; }
  live = el("div", "pk-sr");
  live.setAttribute("aria-live", "polite");
  doc.body.appendChild(live);
  parts.forEach(function (p, i) {
    var nav2 = el("nav", "pk-partnav");
    nav2.setAttribute("aria-label", "Next and previous part");
    [[parts[i - 1], "pk-prev", "← Previous part"], [parts[i + 1], "pk-next", "Next part →"]].forEach(function (x) {
      if (!x[0]) return;
      var a = el("a", x[1], "<small></small><b></b>");
      a.href = "#" + x[0].id;
      a.firstChild.textContent = x[2];
      a.lastChild.textContent = x[0].getAttribute("data-pk-title") || "";
      nav2.appendChild(a);
    });
    p.appendChild(nav2);
    p.addEventListener("beforematch", function () { if (!allMode && current !== p) showPart(p, { scroll: false, quiet: true, hash: false }); });
  });
}

/* ── 5. In-page links that always land ────────────────────────────────────
 * A link into a closed fold, a collapsed table or a part not on screen opens
 * what holds the target, then scrolls it clear of anything pinned at the top.
 * On a pagekit page the script does the scrolling itself, because some
 * previewers take over in-page links (SharePoint's does, measured). */
function reveal(t) {
  var d = t.closest ? t.closest("details") : null;
  if (t.tagName === "SUMMARY") d = t.parentNode;
  while (d) { d.open = true; d = d.parentElement ? d.parentElement.closest("details") : null; }
  var p = partOf(t);
  if (p && parts.length && !allMode && p !== current) showPart(p, { scroll: false, hash: false, quiet: false });
  /* Then a tab, then a long table holding it: showing a tab can fold a table
   * that could not be measured while the tab was hidden, so the table opens
   * last. */
  fire("open", t);
}

function go(t, id, flash) {
  reveal(t);
  if (parts.length && t.classList.contains("pk-part")) { showPart(t, { scroll: "top", focus: true }); return; }
  requestAnimationFrame(function () {
    scrollToEl(t.tagName === "SUMMARY" ? t.parentNode : t);
    if (!t.hasAttribute("tabindex") && !/^(A|BUTTON|INPUT|SELECT|TEXTAREA|SUMMARY)$/.test(t.tagName)) {
      t.setAttribute("tabindex", "-1");
      t.setAttribute("data-pk-landed", "");
    }
    try { t.focus({ preventScroll: true }); } catch (e) {}
    if (flash) { t.classList.remove("pk-flash"); void t.offsetWidth; t.classList.add("pk-flash"); }
    if (id) setHash(id);
    floatAll();
  });
}

function tame(scope) {
  if (!FRAMED) return;
  each((scope || doc).querySelectorAll('a[href^="#"]'), function (a) {
    var h = a.getAttribute("href");
    if (h.length < 2) return;
    /* A page's own contents bar keeps its links as written: the page's own
     * script may read them, and the panel stands in for the bar on screen.
     * The click handler below still follows them. */
    if (a.closest("nav.toc")) return;
    a.setAttribute("data-pk-href", h);
    a.removeAttribute("href");
    a.setAttribute("role", "link");
    if (!a.hasAttribute("tabindex")) a.tabIndex = 0;
  });
}
function linkTarget(a) { return a.getAttribute("data-pk-href") || a.getAttribute("href") || ""; }

/* ── 6. Light and dark ────────────────────────────────────────────────────
 * A sun and a moon, the switch most sites use, so nobody has to be taught it.
 * The moon shows in light, the sun in dark: the icon
 * is the scheme you will get. Pinned heading copies carry colours, so a
 * change of scheme rebuilds them; a composed page's parts each scope their
 * own stylesheet, so the scheme is mirrored onto each part as well. */
function mirrorTheme() {
  var t = root.getAttribute("data-theme");
  each(doc.querySelectorAll("[data-pk-scoped]"), function (n) {
    if (t) n.setAttribute("data-theme", t); else n.removeAttribute("data-theme");
  });
}
function watchScheme() {
  mirrorTheme();
  try { new MutationObserver(function () { mirrorTheme(); rebuildAll(); themeLabels(); }).observe(root, { attributes: true, attributeFilter: ["data-theme"] }); } catch (e) {}
  try { var mq = matchMedia("(prefers-color-scheme: dark)");
    if (mq.addEventListener) mq.addEventListener("change", rebuildAll); else mq.addListener(rebuildAll); } catch (e) {}
}
function themeLabels() {
  var dark = root.getAttribute("data-theme") === "dark";
  each(doc.querySelectorAll("[data-pk-theme]"), function (b) {
    b.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    b.title = dark ? "Light mode" : "Dark mode";
  });
}
function initTheme() {
  if (!root.getAttribute("data-theme")) {
    var dark = false;
    try { dark = matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) {}
    root.setAttribute("data-theme", dark ? "dark" : "light");
  }
  each(doc.querySelectorAll("[data-pk-theme]"), function (btn) {
    btn.hidden = false;
    if (!btn.querySelector("svg")) btn.innerHTML = ICON.moon + ICON.sun;
    btn.addEventListener("click", function () {
      var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      storeSet("pagekit-theme", next);
    });
  });
  themeLabels();
}

/* pk:feature tabs */
/* ── 12. Tabs within a section ────────────────────────────────────────────
 * A <div class="pk-tabs"> holding two or more <section class="pk-tab"> shows
 * one pane at a time under a row of tabs: options side by side in a decision
 * paper, say. A tab is named by its pane's data-pk-title, else by the pane's
 * first heading, which the tab then stands in for on screen. The tabs follow
 * the usual pattern for tabs: Left and Right move between them (Home and End
 * to the ends) and the pane follows. A pane not shown is hidden "until found"
 * where the browser offers it, so find-in-page still reaches it; elsewhere
 * the find shortcut shows every pane. Search, links and print reach every
 * pane. With scripting off, or on paper, every pane shows under its heading. */
var tabGroups = [];
function tabOf(n) { return n && n.closest ? n.closest(".pk-tabs > .pk-tab") : null; }
function selectTab(g, i, opts) {
  opts = opts || {};
  g.every = false;
  g.box.classList.remove("pk-tabs-every");
  g.panes.forEach(function (p, k) {
    var picked = k === i;
    g.tabs[k].setAttribute("aria-selected", picked ? "true" : "false");
    g.tabs[k].tabIndex = picked ? 0 : -1;
    if (picked) p.removeAttribute("hidden"); else conceal(p);
  });
  g.current = i;
  if (opts.focus) try { g.tabs[i].focus(); } catch (e) {}
  if (opts.hash) setHash(g.panes[i].id);
  fire("shown");
  rebuildAll();
}
/* Every pane at once, each under its own heading: for find-in-page where
 * the browser cannot reveal a hidden match. A tab click returns to one. */
function everyTab(g) {
  g.every = true;
  g.box.classList.add("pk-tabs-every");
  g.panes.forEach(function (p, k) { p.removeAttribute("hidden"); g.tabs[k].setAttribute("aria-selected", "false"); });
  fire("shown");
  rebuildAll();
}
/* Opens the pane holding n, and any pane holding that, outward. */
function openTabHolding(n) {
  var p = tabOf(n);
  while (p) {
    tabGroups.forEach(function (g) {
      var i = g.panes.indexOf(p);
      if (i >= 0 && !g.every && i !== g.current) selectTab(g, i);
    });
    p = tabOf(p.parentElement);
  }
}
function initTabs() {
  each(doc.querySelectorAll(".pk-tabs"), function (box, gi) {
    var panes = [].filter.call(box.children, function (c) { return c.classList.contains("pk-tab"); });
    if (panes.length < 2 || box.querySelector(":scope > .pk-tablist")) return;
    var list = el("div", "pk-tablist"), g = { box: box, panes: panes, tabs: [], current: 0, every: false };
    list.setAttribute("role", "tablist");
    var name = box.getAttribute("aria-label") || box.getAttribute("data-pk-title");
    if (name) list.setAttribute("aria-label", name);
    panes.forEach(function (p, k) {
      var h = p.querySelector("h2, h3, h4, h5"), own = p.getAttribute("data-pk-title");
      var b = el("button");
      b.type = "button";
      b.setAttribute("role", "tab");
      b.id = "pk-tabbtn-" + (gi + 1) + "-" + (k + 1);
      b.textContent = own || (h ? words(h) : "") || "Tab " + (k + 1);
      /* The tab names the pane on screen, so a heading it was named from is
       * kept for screen readers, every-pane view and paper only. */
      if (!own && h && h === p.firstElementChild) h.classList.add("pk-tabhead");
      idFor(p, "tab-" + (gi + 1) + "-" + (k + 1));
      b.setAttribute("aria-controls", p.id);
      p.setAttribute("role", "tabpanel");
      p.setAttribute("aria-labelledby", b.id);
      if (!p.hasAttribute("tabindex")) p.tabIndex = 0;
      b.addEventListener("click", function () { selectTab(g, k, { hash: true }); });
      p.addEventListener("beforematch", function () { if (!g.every && g.current !== k) selectTab(g, k); });
      list.appendChild(b);
      g.tabs.push(b);
    });
    list.addEventListener("keydown", function (e) {
      var n = g.tabs.length, i = g.tabs.indexOf(e.target), j = -1;
      if (i < 0) return;
      if (e.key === "ArrowRight") j = (i + 1) % n;
      else if (e.key === "ArrowLeft") j = (i + n - 1) % n;
      else if (e.key === "Home") j = 0;
      else if (e.key === "End") j = n - 1;
      if (j < 0) return;
      e.preventDefault();
      selectTab(g, j, { focus: true, hash: true });
    });
    box.insertBefore(list, panes[0]);
    box.classList.add("pk-tabbed");
    tabGroups.push(g);
    selectTab(g, 0);
  });
}
on("start", initTabs);
on("open", openTabHolding);
on("find", function () { if (!UNTIL_FOUND) tabGroups.forEach(function (g) { if (!g.every) everyTab(g); }); });
/* pk:end tabs */

/* pk:feature long-tables */
/* ── 1. Long tables show their first rows ─────────────────────────────────
 * A table whose rows are taller than one screen shows its first PREVIEW
 * rows, with a button that says how many more there are. Height, not a row
 * count, is the test: ten short rows fit on a screen and gain nothing from a
 * click, while six rows of long prose may not. A table that cannot be
 * measured yet (in a closed fold, or a part not on screen) is decided when
 * it first shows. The cut never splits a cell that spans rows. Find-in-page,
 * printing and links into a hidden row all open the table first. */
var PREVIEW = 3, MIN_ROWS = 6, seq = 0;
var longTables = [], undecided = [];

function rowsOf(t) {
  var out = [];
  each(t.tBodies, function (tb) { each(tb.rows, function (r) { out.push(r); }); });
  return out;
}

function tooTall(t) {
  var h = 0;
  each(t.tBodies, function (b) { h += b.getBoundingClientRect().height; });
  return h > Math.max(innerHeight, 600);
}

function setOpen(rec, open, keepPlace) {
  rec.open = open;
  rec.table.classList.toggle("pk-collapsed", !open);
  rec.btn.setAttribute("aria-expanded", open ? "true" : "false");
  rec.btn.textContent = open
    ? "Show the first " + rec.cut + " rows only"
    : "Show all " + rec.total.toLocaleString("en-NZ") + " rows";
  rec.note.textContent = open ? "" : "Showing " + rec.cut + " of " + rec.total.toLocaleString("en-NZ") + " rows.";
  if (!open && keepPlace) {
    var top = rec.box.getBoundingClientRect().top;
    if (top < 0) rec.box.scrollIntoView({ block: "start" });
  }
  floatAll();
}

function hiddenNow(t) {
  return !t.getClientRects().length || t.closest("details:not([open])") ||
    t.closest(".pk-part[hidden], .pk-tab[hidden]");
}

function initLong(t) {
  if (skipped(t) || t.hasAttribute("data-pk-done")) return;
  var rows = rowsOf(t), want = t.getAttribute("data-pk-preview");
  if (want === "all") return;
  var preview = parseInt(want, 10) || PREVIEW;
  if (rows.length < Math.max(MIN_ROWS, preview + 2)) return;
  if (!want) {
    /* Chrome lays out a closed fold's content at zero size rather than not at
     * all, and a part hidden "until found" keeps its old boxes, so "has a
     * box" is not "can be measured": ask about the fold and the part. */
    if (hiddenNow(t)) { if (undecided.indexOf(t) < 0) undecided.push(t); return; }
    if (!tooTall(t)) return;
  }
  var cut = preview;
  for (var i = 0; i < cut && i < rows.length; i++)
    each(rows[i].cells, function (c) { if (c.rowSpan > 1) cut = Math.max(cut, i + c.rowSpan); });
  if (rows.length - cut < 2) return;
  t.setAttribute("data-pk-done", "");
  rows.forEach(function (r, n) { if (n >= cut) r.classList.add("pk-more"); });
  rows[cut - 1].classList.add("pk-edge");
  /* The control sits after the table's scroll wrapper, so it stays in view
   * when a wide table is scrolled sideways. */
  var p = t.parentElement, box = t;
  if (p && p.children.length === 1 && /(auto|scroll)/.test(getComputedStyle(p).overflowX)) box = p;
  var bar = doc.createElement("div");
  bar.className = "pk-morebar";
  var btn = doc.createElement("button");
  btn.type = "button";
  btn.className = "pk-morebtn";
  btn.setAttribute("aria-controls", [].map.call(t.tBodies, function (b) {
    if (!b.id) b.id = "pk-tb" + (++seq);
    return b.id;
  }).join(" "));
  var note = doc.createElement("span");
  note.className = "pk-morenote";
  note.setAttribute("aria-live", "polite");
  bar.appendChild(btn);
  bar.appendChild(note);
  box.parentNode.insertBefore(bar, box.nextSibling);
  var rec = { table: t, box: box, btn: btn, note: note, cut: cut, total: rows.length, open: false };
  btn.addEventListener("click", function () { setOpen(rec, !rec.open, true); });
  longTables.push(rec);
  setOpen(rec, false, false);
  initTools(rec, rows);
}

/* ── 1b. Filter and sort a long table ─────────────────────────────────────
 * A table long enough to fold to its first rows also gets a filter box above
 * it and sortable column headings. The filter matches the words in a row,
 * ignoring case and macrons, shows every matching row (the fold opens while a
 * filter is set) and says how many match. A heading is a button: ascending,
 * then descending, then the table's own order again, said to a screen reader
 * through aria-sort. Numbers sort as numbers (thousands separators and a
 * trailing % allowed), everything else in New Zealand English order with
 * numbers inside words compared as numbers, and empty cells last either way.
 * Not on a table with more than one body or heading row, or whose cells span
 * rows or whose headings span columns, where moving a row would break the
 * rows around it; off with data-pk-tools="off". On paper every row prints. */
function plain(s) { return String(s).normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }
function toolsFit(t, rows) {
  if (t.closest('[data-pk-tools="off"]') || t.tBodies.length !== 1 || !t.tHead || t.tHead.rows.length !== 1) return false;
  var spans = false;
  each(t.tHead.rows[0].cells, function (c) { if (c.colSpan > 1 || c.rowSpan > 1) spans = true; });
  rows.forEach(function (r) { each(r.cells, function (c) { if (c.rowSpan > 1) spans = true; }); });
  return !spans;
}
function sortKey(text) {
  var s = text.replace(/[\s,]/g, "").replace(/%$/, "");
  return /^[-+]?(\d+\.?\d*|\.\d+)$/.test(s) ? parseFloat(s) : null;
}
var COLLATE = window.Intl && Intl.Collator ? new Intl.Collator("en-NZ", { numeric: true, sensitivity: "base" }) : null;
function initTools(rec, rows) {
  var t = rec.table;
  if (!toolsFit(t, rows)) return;
  var body = t.tBodies[0], original = rows.slice();
  /* Cells joined by a space: a filter matches words a reader can see, never
   * the end of one cell run into the start of the next. */
  var words = original.map(function (r) {
    return plain([].map.call(r.cells, function (c) { return c.textContent; }).join(" ").replace(/\s+/g, " "));
  });
  var tools = el("div", "pk-tabletools"), box = el("input", "pk-filter"), count = el("span", "pk-filtercount");
  box.type = "search";
  box.placeholder = "Filter these " + rec.total.toLocaleString("en-NZ") + " rows";
  box.setAttribute("aria-label", "Filter the rows of this table");
  count.setAttribute("aria-live", "polite");
  tools.appendChild(box);
  tools.appendChild(count);
  rec.box.parentNode.insertBefore(tools, rec.box);
  var wasOpen = null, timer = null;
  function filter() {
    var q = plain(box.value.trim()), shown = 0;
    original.forEach(function (r, i) {
      var hit = !q || words[i].indexOf(q) >= 0;
      r.classList.toggle("pk-filtered", !hit);
      if (hit) shown++;
    });
    if (q) {
      if (wasOpen === null) wasOpen = rec.open;
      if (!rec.open) setOpen(rec, true, false);
      rec.btn.parentNode.hidden = true;
      count.textContent = shown.toLocaleString("en-NZ") + " of " + rec.total.toLocaleString("en-NZ") + " rows match";
    } else {
      rec.btn.parentNode.hidden = false;
      if (wasOpen !== null && wasOpen !== rec.open) setOpen(rec, wasOpen, false);
      wasOpen = null;
      count.textContent = "";
    }
    rebuildAll();
  }
  box.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(filter, 120); });
  rec.clearFilter = function () { if (box.value) { box.value = ""; filter(); } };
  var heads = [].slice.call(t.tHead.rows[0].cells), state = { col: -1, dir: 0 };
  heads.forEach(function (th, col) {
    if (!th.textContent.trim()) return;
    var b = el("button", "pk-sortbtn"), mark = el("span", "pk-sortmark");
    b.type = "button";
    mark.setAttribute("aria-hidden", "true");
    while (th.firstChild) b.appendChild(th.firstChild);
    b.appendChild(mark);
    th.appendChild(b);
    th.setAttribute("data-pk-col", String(col));
    th.setAttribute("aria-sort", "none");
    b.addEventListener("click", function () { sortBy(col); });
  });
  function sortBy(col) {
    var dir = state.col === col ? (state.dir + 1) % 3 : 1;
    state = { col: col, dir: dir };
    var order = original.slice();
    if (dir) {
      var vals = order.map(function (r) { return r.cells[col] ? cellText(r.cells[col]) : ""; });
      var nums = vals.map(sortKey);
      var numeric = vals.every(function (v, i) { return !v || nums[i] !== null; }) && nums.some(function (n) { return n !== null; });
      var idx = order.map(function (r, i) { return i; });
      idx.sort(function (a, b) {
        var va = vals[a], vb = vals[b];
        if (!va || !vb) return !va && !vb ? a - b : (!va ? 1 : -1);
        var d = numeric ? nums[a] - nums[b] : (COLLATE ? COLLATE.compare(va, vb) : (va < vb ? -1 : va > vb ? 1 : 0));
        return (dir === 2 ? -d : d) || a - b;
      });
      order = idx.map(function (i) { return original[i]; });
    }
    order.forEach(function (r) { body.appendChild(r); });
    order.forEach(function (r, n) {
      r.classList.toggle("pk-more", n >= rec.cut);
      r.classList.toggle("pk-edge", n === rec.cut - 1);
    });
    heads.forEach(function (th, i) {
      if (th.hasAttribute("data-pk-col"))
        th.setAttribute("aria-sort", i === col && dir ? (dir === 1 ? "ascending" : "descending") : "none");
    });
    rebuildAll();
  }
}
function retryUndecided() {
  var wait = undecided;
  undecided = [];
  wait.forEach(initLong);
}

function openTableHolding(el) {
  if (!el || !el.closest) return;
  var hid = el.closest("tr.pk-filtered");
  if (hid) longTables.forEach(function (r) { if (r.table.contains(hid) && r.clearFilter) r.clearFilter(); });
  var t = el.closest("table.pk-collapsed");
  if (!t) return;
  longTables.forEach(function (r) { if (r.table === t) setOpen(r, true, false); });
}
function openAllTables() { longTables.forEach(function (r) { if (!r.open) setOpen(r, true, false); }); }
var shutForPrint = [];
on("table", initLong);
on("shown", retryUndecided);
on("open", openTableHolding);
on("find", openAllTables);
on("print", function () {
  shutForPrint = longTables.filter(function (r) { return !r.open; });
  shutForPrint.forEach(function (r) { setOpen(r, true, false); });
});
on("unprint", function () {
  shutForPrint.forEach(function (r) { setOpen(r, false, false); });
  shutForPrint = [];
});
/* pk:end long-tables */

/* pk:feature cells */
function cellText(c) {
  var k = cleanCell(c);
  each(k.querySelectorAll("br"), function (b) { b.replaceWith(" "); });
  return k.textContent.replace(/\s+/g, " ").trim();
}
/* A cell as the reader sees it, without the page's own controls. */
function cleanCell(c) {
  var k = c.cloneNode(true);
  each(k.querySelectorAll(".pk-sortmark"), function (n) { n.remove(); });
  each(k.querySelectorAll(".pk-sortbtn"), function (n) { n.replaceWith.apply(n, [].slice.call(n.childNodes)); });
  each(k.querySelectorAll("button, script, style, svg, .pk-sr, .sr-only, [aria-hidden=true], [hidden]"), function (n) { n.remove(); });
  return k;
}
/* pk:end cells */

/* pk:feature pinned-headings */
/* ── 2. Table headings stay in view ────────────────────────────────────────
 * When a table's own heading row has scrolled off the top and the table is
 * still on screen, a copy of the heading row is pinned to the top, matched
 * column for column and following any sideways scroll. A copy, not CSS
 * `position: sticky`, because sticky cannot escape the sideways-scroll
 * wrapper that wide tables need. The copy is hidden from screen readers,
 * which already have the real heading row. */
var floats = [];

var COPY = ["backgroundColor", "color", "fontWeight", "fontSize", "fontFamily",
  "textAlign", "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
  "borderBottomWidth", "borderBottomStyle", "borderBottomColor", "lineHeight",
  "verticalAlign", "letterSpacing", "textTransform", "whiteSpace"];

function initFloat(t) {
  if (skipped(t) || !t.tHead || !t.tHead.rows.length) return;
  var p = t.parentElement, scroller = null;
  if (p && /(auto|scroll)/.test(getComputedStyle(p).overflowX)) scroller = p;
  var shell = doc.createElement("div");
  shell.className = "pk-float";
  shell.setAttribute("aria-hidden", "true");
  var copy = doc.createElement("table");
  copy.className = t.className.replace(/\bpk-\S+/g, "").trim();
  shell.appendChild(copy);
  doc.body.appendChild(shell);
  var rec = { table: t, scroller: scroller, shell: shell, copy: copy, built: 0 };
  if (scroller) scroller.addEventListener("scroll", function () { place(rec, stickyTop()); }, { passive: true });
  floats.push(rec);
}

function build(rec) {
  var head = rec.table.tHead, ths = head.querySelectorAll("th, td");
  var clone = head.cloneNode(true);
  each(clone.querySelectorAll("[id]"), function (n) { n.removeAttribute("id"); });
  if (clone.id) clone.removeAttribute("id");
  var cells = clone.querySelectorAll("th, td");
  each(ths, function (th, i) {
    var cs = getComputedStyle(th), w = th.getBoundingClientRect().width, c = cells[i];
    COPY.forEach(function (k) { c.style[k] = cs[k]; });
    if (cs.backgroundColor === "rgba(0, 0, 0, 0)" || cs.backgroundColor === "transparent")
      c.style.backgroundColor = getComputedStyle(doc.body).backgroundColor;
    c.style.width = c.style.minWidth = c.style.maxWidth = w + "px";
    c.style.boxSizing = "border-box";
  });
  each(clone.querySelectorAll("button"), function (b) { b.tabIndex = -1; });
  rec.copy.innerHTML = "";
  rec.copy.appendChild(clone);
  rec.copy.style.width = rec.table.getBoundingClientRect().width + "px";
  rec.built = rec.table.getBoundingClientRect().width;
}

/* A table in a closed section is not on screen, yet both engines still lay it
 * out and report a box for it (the section's contents are hidden, not
 * removed), so its box alone would pin its heading over whatever is there. */
function place(rec, top) {
  var t = rec.table, r = t.getBoundingClientRect(), hh = t.tHead.getBoundingClientRect().height;
  var show = r.width > 0 && r.top < top && r.bottom - hh * 2 > top && t.getClientRects().length &&
    !t.closest(".pk-part[hidden], .pk-tab[hidden], details:not([open])");
  if (!show) { if (rec.shell.style.display !== "none") rec.shell.style.display = "none"; return; }
  if (Math.abs(rec.built - r.width) > 0.5 || !rec.copy.firstChild) build(rec);
  var clip = rec.scroller ? rec.scroller.getBoundingClientRect() : r;
  rec.shell.style.display = "block";
  rec.shell.style.top = top + "px";
  rec.shell.style.left = clip.left + "px";
  rec.shell.style.width = clip.width + "px";
  rec.copy.style.transform = "translateX(" + (r.left - clip.left) + "px)";
}
/* A heading clicked in a pinned copy sorts the real table. */
function sortFromCopy(e) {
  var b = e.target && e.target.closest ? e.target.closest(".pk-float .pk-sortbtn") : null;
  if (!b) return;
  var th = b.closest("th, td"), shell = b.closest(".pk-float");
  floats.forEach(function (f) {
    if (f.shell !== shell) return;
    var real = f.table.querySelector('th[data-pk-col="' + th.getAttribute("data-pk-col") + '"] .pk-sortbtn');
    if (real) real.click();
  });
}
on("table", initFloat);
on("built", function () { doc.addEventListener("click", sortFromCopy); });
on("frame", function (top) { floats.forEach(function (f) { place(f, top); }); });
on("relayout", function () { floats.forEach(function (f) { f.built = -1; }); });
/* pk:end pinned-headings */

/* pk:feature charts */
/* ── 7. Charts draw themselves when they come into view ───────────────────
 * Bars rise from their baseline, timeline bars grow left to right in date
 * order, and the bars inside table cells fill, each once, when the reader
 * scrolls the figure onto the screen (or opens the part or fold holding it),
 * not at page load, when nobody is looking at it.
 *
 * Nothing is marked up for it: a bar chart is found as rects standing on a
 * long horizontal line, a timeline as rects laid over a grid of long vertical
 * lines. Read from the attributes, so a figure in a hidden part is found too.
 * Off with  data-pk-motion="off"  on the figure, or on <html> for the page.
 * Never runs when the reader's system asks for reduced motion, without
 * IntersectionObserver, or on paper: those show the finished figure. */
var motion = [];
function rectsOf(svg) {
  var out = [];
  each(svg.querySelectorAll("rect"), function (r) {
    if (r.hasAttribute("transform") || r.closest("[transform*=rotate], [transform*=matrix]")) return;
    var x = num(r, "x") || 0, y = num(r, "y") || 0, w = num(r, "width"), h = num(r, "height");
    if (w > 0 && h > 0) out.push({ el: r, x: x, y: y, w: w, h: h });
  });
  return out;
}
function lines(svg) {
  var out = [];
  each(svg.querySelectorAll("line"), function (l) {
    var x1 = num(l, "x1"), x2 = num(l, "x2"), y1 = num(l, "y1"), y2 = num(l, "y2");
    if (x1 !== null && x2 !== null && y1 !== null && y2 !== null) out.push({ el: l, x1: x1, x2: x2, y1: y1, y2: y2 });
  });
  return out;
}
/* Labels and marks that belong to a bar (its value, its range whisker) wait
 * until the bar has arrived, so nothing floats over empty space. */
function labelsOver(svg, test) {
  var got = [];
  each(svg.querySelectorAll("text, line, circle"), function (el) {
    if (el.classList.contains("pk-bar") || el.classList.contains("pk-tbar")) return;
    var x, y;
    if (el.tagName === "line") {
      var lx1 = num(el, "x1"), lx2 = num(el, "x2");
      if (lx1 === null || lx2 === null || Math.abs(lx2 - lx1) > 40) return;
      x = (lx1 + lx2) / 2; y = Math.min(num(el, "y1"), num(el, "y2"));
    }
    else if (el.tagName === "circle") { x = num(el, "cx"); y = num(el, "cy"); }
    else { x = num(el, "x"); y = num(el, "y"); }
    if (x === null || y === null) return;
    if (test(x, y)) got.push(el);
  });
  return got;
}
function asBarChart(svg, box) {
  var bases = {};
  lines(svg).forEach(function (l) {
    if (Math.abs(l.y1 - l.y2) < 0.5 && Math.abs(l.x2 - l.x1) > box.w * 0.5) bases[Math.round(l.y1)] = true;
  });
  var groups = {};
  rectsOf(svg).forEach(function (r) {
    var b = Math.round(r.y + r.h);
    if (bases[b] && r.w < box.w * 0.25) (groups[b] = groups[b] || []).push(r);
  });
  var best = null;
  Object.keys(groups).forEach(function (k) {
    var g = groups[k], hs = {};
    g.forEach(function (r) { hs[Math.round(r.h)] = 1; });
    if (g.length >= 3 && Object.keys(hs).length >= 2 && (!best || g.length > best.bars.length)) best = { base: +k, bars: g };
  });
  if (!best) return false;
  /* A stacked bar is one column: the segments above the one on the baseline
   * share its x and width, and the whole column rises from the baseline. */
  var all = rectsOf(svg), base = best.base, vb = svg.viewBox.baseVal, step = Math.min(90, 700 / best.bars.length);
  best.bars.sort(function (a, b) { return a.x - b.x; });
  best.bars.forEach(function (r, i) {
    var d = i * step;
    all.forEach(function (s) {
      if (Math.abs(s.x - r.x) > 0.5 || Math.abs(s.w - r.w) > 0.5 || s.y + s.h > base + 0.5) return;
      s.el.classList.add("pk-bar");
      s.el.style.setProperty("--pk-d", d + "ms");
      if (vb.x || vb.y) s.el.style.transformBox = "fill-box";
      else s.el.style.transformOrigin = "0 " + base + "px";
    });
    labelsOver(svg, function (x, y) { return x >= r.x - 4 && x <= r.x + r.w + 4 && y < base; })
      .forEach(function (el) { el.classList.add("pk-mlab"); el.style.setProperty("--pk-d", (d + 650) + "ms"); });
  });
  return true;
}
function asTimeline(svg, box) {
  var vs = lines(svg).filter(function (l) { return Math.abs(l.x1 - l.x2) < 0.5 && Math.abs(l.y2 - l.y1) > box.h * 0.4; });
  if (vs.length < 6) return false;
  var x0 = Math.min.apply(null, vs.map(function (l) { return l.x1; }));
  var x1 = Math.max.apply(null, vs.map(function (l) { return l.x1; }));
  var span = x1 - x0;
  var bars = rectsOf(svg).filter(function (r) { return r.h <= 48 && r.x >= x0 - 2 && r.x + r.w <= x1 + 2 && r.w < span * 0.98; });
  if (bars.length < 3) return false;
  bars.forEach(function (r) {
    var d = Math.round((r.x - x0) / span * 900);
    r.el.classList.add("pk-tbar");
    r.el.style.setProperty("--pk-d", d + "ms");
    labelsOver(svg, function (x, y) { return x >= r.x - 2 && x <= r.x + r.w + 2 && y >= r.y && y <= r.y + r.h + 2; })
      .forEach(function (el) { el.classList.add("pk-mlab"); el.style.setProperty("--pk-d", (d + 450) + "ms"); });
  });
  /* Links between bars and the milestones on them follow once the bars are
   * drawn, so no arrow points at a bar that is not there yet. */
  each(svg.querySelectorAll("path, polyline, circle"), function (el) {
    if (el.classList.contains("pk-mlab") || el.closest("defs, marker")) return;
    el.classList.add("pk-mlab");
    el.style.setProperty("--pk-d", "1300ms");
  });
  return true;
}
function landed(el) { el.classList.add("pk-in"); }
function initMotion() {
  var reduce = false;
  try { reduce = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  if (reduce || !("IntersectionObserver" in window) || root.getAttribute("data-pk-motion") === "off") return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      var seen = e.intersectionRect.height, room = e.rootBounds ? e.rootBounds.height : innerHeight;
      if (e.isIntersecting && (e.intersectionRatio >= 0.3 || seen >= room * 0.5)) { landed(e.target); io.unobserve(e.target); }
    });
  }, { threshold: [0, 0.1, 0.2, 0.3, 0.5] });
  each(doc.querySelectorAll("svg"), function (svg) {
    if (svg.closest('[data-pk-motion="off"], .pk-panel, button, .pk-float')) return;
    var box = boxOf(svg);
    if (!box) return;
    try {
      if (asBarChart(svg, box) || asTimeline(svg, box)) { svg.classList.add("pk-mo"); motion.push(svg); io.observe(svg); }
    } catch (e) { svg.classList.remove("pk-mo"); }
  });
  each(doc.querySelectorAll("table"), function (t) {
    if (t.closest('[data-pk-motion="off"], .pk-float')) return;
    var fills = t.querySelectorAll(".cbarfill");
    if (!fills.length) return;
    each(fills, function (f, i) { f.style.setProperty("--pk-d", Math.min(i, 12) * 40 + "ms"); });
    t.classList.add("pk-mo");
    motion.push(t);
    io.observe(t);
  });
}
on("built", initMotion);
on("print", function () { motion.forEach(landed); });
/* pk:end charts */

/* pk:feature pane */
/* The pane down the right holds whatever a control opens in it: an
 * identifier's whole entry, or a picture to copy. A control inside it that is
 * not its close button is handed to whichever feature put it there. */
var pane = null, paneFrom = null;
function paneShow(head, body, foot, label, from) {
  if (!pane) {
    pane = el("aside", "pk-pane");
    pane.setAttribute("role", "dialog");
    pane.setAttribute("aria-modal", "false");
    pane.tabIndex = -1;
    doc.body.appendChild(pane);
    pane.addEventListener("click", function (e) {
      var x = e.target.closest ? e.target.closest(".pk-paneclose, .pk-inpane") : null;
      if (!x) return;
      e.preventDefault();
      if (x.classList.contains("pk-paneclose")) closePane(); else fire("inpane", x);
    });
  }
  pane.innerHTML = '<div class="pk-panehead">' + head +
    '<button type="button" class="pk-paneclose" aria-label="Close">×</button></div>' +
    '<div class="pk-panebody">' + body + "</div>" + (foot ? '<div class="pk-panefoot">' + foot + "</div>" : "");
  pane.setAttribute("aria-label", label);
  if (from) paneFrom = from;
  root.classList.add("pk-paneopen");
  pane.scrollTop = 0;
  try { pane.focus({ preventScroll: true }); } catch (e) {}
  return pane;
}
function closePane() {
  root.classList.remove("pk-paneopen");
  if (paneFrom) try { paneFrom.focus({ preventScroll: true }); } catch (e) {}
  paneFrom = null;
}
/* A click outside the pane, or Escape, closes it, whatever opened it. */
function initPane() {
  doc.addEventListener("click", function (e) {
    if (!pane || !root.classList.contains("pk-paneopen") || !e.target.closest) return;
    if (e.target.closest(".pk-pane, a.pk-ref[data-pk-ref], .pk-copymenu")) return;
    closePane();
  }, true);
  doc.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && root.classList.contains("pk-paneopen")) closePane();
  });
}
on("built", initPane);
/* pk:end pane */

/* pk:feature cards */
/* ── 8. Identifiers explain themselves ────────────────────────────────────
 * An identifier the page's build linked (a.pk-ref, with its entry in the
 * page's #pk-refdata block) shows a short card when the pointer rests on it or
 * it takes keyboard focus: what it is, its level and its name. A click opens
 * the whole entry in a pane down the right, with a link to its source; an
 * identifier whose entry is on this page goes there instead. Ctrl- or
 * Cmd-click follows the link as written. */
var refData = {}, tip = null, tipFor = null, tipT = 0;
function refOf(a) { return refData[a.getAttribute("data-pk-ref")]; }
function chip(l) { return l ? '<span class="pk-lvl">' + esc(l.toUpperCase()) + "</span>" : ""; }
function inPage(a) { var h = a.getAttribute("data-pk-href") || a.getAttribute("href") || ""; return h.charAt(0) === "#"; }
function showTip(a) {
  var r = refOf(a);
  if (!r) return;
  if (!tip) { tip = el("div", "pk-tip"); tip.setAttribute("role", "tooltip"); tip.id = "pk-tip"; doc.body.appendChild(tip); }
  tip.innerHTML = '<div class="pk-tiphead"><b>' + esc(r.k || a.getAttribute("data-pk-ref")) + "</b>" + chip(r.l) +
    '<span class="pk-tipsrc">' + esc(r.n || "") + "</span></div>" +
    (r.t || r.s ? '<div class="pk-tipbody">' + esc(clip(r.t || r.s, 240)) + "</div>" : "") +
    (r.m ? '<div class="pk-tipmeta">' + esc(clip(r.m, 160)) + "</div>" : "") +
    '<div class="pk-tiphint">' + (inPage(a) ? "Click to go to it on this page" : r.k ? "Click for the whole meaning" : "Click for the full description") + "</div>";
  tip.style.display = "block";
  var b = a.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  var left = Math.max(8, Math.min(b.left, innerWidth - w - 8)), top = b.bottom + 8;
  if (top + h > innerHeight - 8 && b.top - h - 8 > 8) top = b.top - h - 8;
  tip.style.left = left + "px";
  tip.style.top = top + "px";
  a.setAttribute("aria-describedby", "pk-tip");
  tipFor = a;
}
function hideTip() {
  clearTimeout(tipT);
  if (tip) tip.style.display = "none";
  if (tipFor) tipFor.removeAttribute("aria-describedby");
  tipFor = null;
}
function paragraphs(t) {
  return String(t).split(/\n\s*\n/).map(function (p) { return "<p>" + linkIds(esc(p.trim())) + "</p>"; }).join("");
}
/* Identifiers inside an entry (its related requirements, say) open their own
 * entry in turn, where this page carries it. */
function linkIds(h) {
  var ids = Object.keys(refData).filter(function (k) { return k.indexOf("term:") !== 0; });
  if (!ids.length) return h;
  var rx = new RegExp("\\b(" + ids.map(function (i) { return i.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }).join("|") + ")\\b", "g");
  return h.replace(rx, '<button type="button" class="pk-ref pk-inpane" data-pk-ref="$1">$1</button>');
}
function openPane(a) {
  var id = a.getAttribute("data-pk-ref"), r = refData[id];
  if (!r) return;
  hideTip();
  var body = "";
  if (r.t) body += '<p class="pk-panetitle">' + esc(r.t) + "</p>";
  if (r.s) body += paragraphs(r.s);
  (r.f || []).forEach(function (f) { body += '<h3 class="pk-panelab">' + esc(f[0]) + "</h3>" + paragraphs(f[1]); });
  if (r.m && r.k) body += '<p class="pk-tipmeta">' + esc(r.m) + "</p>";
  var src = r.u ? '<a class="pk-panesrc">' + (r.x ? "Open it at the source" : r.k ? "See it in the list of terms" : "Read it in full in its own document") + " ↗</a>" : "";
  var name = r.k || id;
  paneShow('<span class="pk-paneid">' + esc(name) + "</span>" + chip(r.l) + '<span class="pk-tipsrc">' + esc(r.n || "") + "</span>",
    body, src, name + (r.t ? ": " + r.t : ""), a.classList.contains("pk-inpane") ? null : a);
  var out = pane.querySelector(".pk-panesrc");
  /* Only a relative or http(s) address: the build refuses any other scheme,
   * and the page holds to that whatever its data says. */
  if (out && /^[\s\x00-\x20]*[a-z][a-z0-9+.\-]*:/i.test(r.u || "") && !/^[\s\x00-\x20]*https?:/i.test(r.u)) { out.remove(); out = null; }
  if (out) {
    out.setAttribute("href", r.u);
    if (r.x) { out.target = "_blank"; out.rel = "noopener"; }
  }
}
function initRefs() {
  var block = doc.getElementById("pk-refdata");
  if (!block) return;
  try { refData = JSON.parse(block.textContent); } catch (e) { return; }
  each(doc.querySelectorAll("a.pk-ref[data-pk-ref]"), function (a) {
    if (a.title) { a.setAttribute("data-pk-title", a.title); a.removeAttribute("title"); }
  });
  doc.addEventListener("mouseover", function (e) {
    var a = e.target.closest ? e.target.closest("a.pk-ref[data-pk-ref]") : null;
    if (!a || a.closest(".pk-pane")) return;
    clearTimeout(tipT);
    tipT = setTimeout(function () { showTip(a); }, 220);
  });
  doc.addEventListener("mouseout", function (e) {
    var a = e.target.closest ? e.target.closest("a.pk-ref[data-pk-ref]") : null;
    if (a && !(e.relatedTarget && a.contains(e.relatedTarget))) hideTip();
  });
  doc.addEventListener("focusin", function (e) {
    var a = e.target.closest ? e.target.closest("a.pk-ref[data-pk-ref]") : null;
    if (a && !a.closest(".pk-pane")) showTip(a); else hideTip();
  });
  addEventListener("scroll", hideTip, { passive: true });
  doc.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a.pk-ref[data-pk-ref]") : null;
    if (!a) return;
    if (a.closest(".pk-pane") || e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || inPage(a)) return;
    e.preventDefault();
    openPane(a);
  }, true);
  doc.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });
}
on("built", initRefs);
on("inpane", openPane);
/* pk:end cards */

/* pk:feature clipboard */
/* What copying out shares: the copy command, a notice that says what was
 * copied, the copy icon, and the places no copy button goes. */
var COPY_OFF = '[data-pk-copy="off"], [data-pk="off"], .pk-panel, .pk-pane, .pk-float, .pk-copymenu, button, a';
var toast = null, toastT = 0;
ICON.copy = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8.5" y="8.5" width="11" height="12" rx="2"/><path d="M15.5 8.5V5.5a2 2 0 0 0-2-2h-7a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h2"/></svg>';
function notify(msg) {
  if (!toast) { toast = el("div", "pk-toast"); toast.setAttribute("role", "status"); doc.body.appendChild(toast); }
  toast.textContent = msg;
  toast.classList.add("pk-on");
  clearTimeout(toastT);
  toastT = setTimeout(function () { toast.classList.remove("pk-on"); }, 3200);
}
/* The copy command, carrying what we choose. It needs a selection in some
 * browsers, so a throwaway one is made and the focus put back after. */
function copyAs(flavours) {
  var done = false, back = doc.activeElement, hold = el("span", "pk-sr");
  hold.textContent = "copy";
  doc.body.appendChild(hold);
  function grab(e) {
    Object.keys(flavours).forEach(function (k) { e.clipboardData.setData(k, flavours[k]); });
    e.preventDefault();
    done = true;
  }
  doc.addEventListener("copy", grab, true);
  try {
    var s = getSelection(), r = doc.createRange();
    r.selectNodeContents(hold); s.removeAllRanges(); s.addRange(r);
    doc.execCommand("copy");
    s.removeAllRanges();
  } catch (e) {}
  doc.removeEventListener("copy", grab, true);
  hold.remove();
  try { if (back) back.focus({ preventScroll: true }); } catch (e) {}
  return done;
}
/* pk:end clipboard */

/* pk:feature copy-out */
/* ── 9. Take a copy of a table or a diagram ──────────────────────────────
 * A small copy button sits at the top right of every table and diagram, shown
 * when the pointer is over it or the button has keyboard focus. Its menu:
 *   a table:   Copy table (pastes as a table into Word, Excel or an email:
 *              HTML for documents, tab-separated text for spreadsheets),
 *              Save as CSV;
 *   a diagram: Copy as picture (PNG), Copy as SVG (for drawing tools),
 *              Save as PNG, Save as SVG.
 * Pictures and SVG are always taken in the light scheme, at twice the screen
 * size, with the styles each shape is drawn with written into it, so they
 * look the same pasted anywhere.
 *
 * Measured in SharePoint Online's file viewer (November 2026, Chrome 158): the
 * frame is sandboxed "allow-scripts allow-forms" with no clipboard permission,
 * so the browser's clipboard API is refused, downloads and pop-ups are
 * blocked, but the older copy command works (a table arrived as HTML and as
 * tab-separated text, macrons intact) and a diagram can still be drawn as a
 * picture. So: text and tables go by the copy command everywhere; a picture
 * goes by the clipboard API where a page is allowed it, and otherwise opens in
 * the pane, where the browser's own Copy image and Save image work; and the
 * Save items are not offered inside such a frame (a sandboxed frame has an
 * opaque origin, which is how it is recognised).
 * Off for one table or figure with  data-pk-copy="off". */
var copyMenu = null, copyFor = null, copyShown = null;
function saveAs(name, blob) {
  var a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  doc.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(function () { URL.revokeObjectURL(a.href); }, 4000);
}
function nameFor(box) {
  var cap = box.querySelector && box.querySelector("figcaption, caption");
  var t = cap ? cap.textContent : "";
  if (!t) {
    var n = box, h = null;
    while (n && !h) {
      var p = n.previousElementSibling;
      while (p && !/^H[1-4]$/.test(p.tagName)) p = p.previousElementSibling;
      h = p; n = n.parentElement;
    }
    t = h ? h.textContent : (doc.title || "copy");
  }
  return t.normalize("NFKD").replace(/[̀-ͯ]/g, "").replace(/[^A-Za-z0-9]+/g, " ").trim().slice(0, 60).replace(/ /g, "-") || "copy";
}

/* A table as rows of plain cells, with spans filled so every row lines up. */
function grid(t) {
  var rows = [], taken = [];
  each(t.rows, function (tr, y) {
    if (tr.closest("table") !== t || tr.classList.contains("pk-filtered")) return;
    var row = rows[y] = rows[y] || [], x = 0;
    each(tr.cells, function (c) {
      while (row[x] !== undefined) x++;
      var txt = cellText(c);
      for (var dy = 0; dy < c.rowSpan; dy++)
        for (var dx = 0; dx < c.colSpan; dx++) {
          var r = rows[y + dy] = rows[y + dy] || [];
          r[x + dx] = dy || dx ? "" : txt;
        }
      x += c.colSpan;
    });
  });
  return rows.filter(Boolean);
}
function tableHtml(t) {
  var out = doc.createElement("table");
  out.setAttribute("style", "border-collapse:collapse;font-family:Calibri,Aptos,Arial,sans-serif;font-size:11pt");
  each(t.rows, function (tr) {
    if (tr.closest("table") !== t || tr.classList.contains("pk-filtered")) return;
    var r = out.insertRow(-1);
    each(tr.cells, function (c) {
      var n = doc.createElement(c.tagName === "TH" ? "th" : "td"), k = cleanCell(c);
      each(k.querySelectorAll("*"), function (x) {
        if (x.tagName === "A") {
          var h = x.getAttribute("href") || "";
          if (!/^https?:/i.test(h)) { x.replaceWith.apply(x, [].slice.call(x.childNodes)); return; }
        }
        [].slice.call(x.attributes).forEach(function (at) { if (at.name !== "href") x.removeAttribute(at.name); });
      });
      while (k.firstChild) n.appendChild(k.firstChild);
      if (c.colSpan > 1) n.colSpan = c.colSpan;
      if (c.rowSpan > 1) n.rowSpan = c.rowSpan;
      n.setAttribute("style", "border:1px solid #9aa0a6;padding:4px 7px;vertical-align:top;text-align:left" +
        (c.tagName === "TH" ? ";background:#eef1f4;font-weight:bold" : ""));
      r.appendChild(n);
    });
  });
  return '<meta charset="utf-8">' + out.outerHTML;
}
function copyTable(t) {
  var rows = grid(t);
  var tsv = rows.map(function (r) { return r.map(function (v) { return (v || "").replace(/\t/g, " "); }).join("\t"); }).join("\n") + "\n";
  if (copyAs({ "text/html": tableHtml(t), "text/plain": tsv }))
    notify("Table copied (" + rows.length + " rows). Paste it into Word, Excel or an email.");
  else notify("This browser would not copy the table. Select it and use Copy instead.");
}
function saveCsv(t) {
  var csv = grid(t).map(function (r) {
    return r.map(function (v) { v = v || ""; return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }).join(",");
  }).join("\r\n") + "\r\n";
  saveAs(nameFor(t) + ".csv", new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
}

/* A diagram as a standalone SVG: each shape carries the styles it is drawn
 * with, read in the light scheme (the switch happens and is undone inside one
 * task, so the reader never sees it). Labels a chart holds back until it is
 * seen are copied as finished. */
var PAINT = ["fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray",
  "stroke-linecap", "stroke-linejoin", "opacity", "font-family", "font-size", "font-weight", "font-style",
  "text-anchor", "dominant-baseline", "letter-spacing", "text-decoration", "visibility", "marker-start",
  "marker-mid", "marker-end", "paint-order"];
function standalone(svg) {
  var was = root.getAttribute("data-theme");
  if (was !== "light") { root.setAttribute("data-theme", "light"); mirrorTheme(); }
  var b = svg.getBoundingClientRect(), vb = boxOf(svg);
  var w = b.width || (vb && vb.w) || 600, h = b.height || (vb && vb.h) || 400;
  var k = svg.cloneNode(true), from = [svg].concat([].slice.call(svg.querySelectorAll("*")));
  var to = [k].concat([].slice.call(k.querySelectorAll("*")));
  from.forEach(function (o, i) {
    var cs = getComputedStyle(o), st = [];
    PAINT.forEach(function (p) {
      if (p === "opacity" && o.classList.contains("pk-mlab")) return;
      var v = cs.getPropertyValue(p);
      if (v && v !== "normal" && v !== "none" || p === "fill" || p === "stroke") st.push(p + ":" + v);
    });
    if (cs.display === "none") st.push("display:none");
    to[i].setAttribute("style", st.join(";"));
    to[i].removeAttribute("class");
  });
  var bg = getComputedStyle(doc.body).backgroundColor;
  if (was !== "light") { if (was) root.setAttribute("data-theme", was); else root.removeAttribute("data-theme"); mirrorTheme(); }
  k.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  k.setAttribute("width", Math.round(w));
  k.setAttribute("height", Math.round(h));
  if (!k.getAttribute("viewBox")) k.setAttribute("viewBox", "0 0 " + Math.round(w) + " " + Math.round(h));
  k.removeAttribute("aria-hidden");
  return { text: new XMLSerializer().serializeToString(k), w: w, h: h, bg: /rgba\(0, 0, 0, 0\)|transparent/.test(bg) ? "#fff" : bg };
}
function picture(svg) {
  var s = standalone(svg);
  return new Promise(function (ok, no) {
    var im = new Image();
    im.onload = function () {
      var scale = Math.min(2, 8000 / Math.max(s.w, s.h)), c = el("canvas");
      c.width = Math.round(s.w * scale); c.height = Math.round(s.h * scale);
      var x = c.getContext("2d");
      x.fillStyle = s.bg; x.fillRect(0, 0, c.width, c.height);
      x.drawImage(im, 0, 0, c.width, c.height);
      try { c.toBlob(function (bl) { bl ? ok(bl) : no(new Error("no picture")); }, "image/png"); } catch (e) { no(e); }
    };
    im.onerror = function () { no(new Error("the diagram would not draw")); };
    im.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(s.text);
  });
}
/* Where a page may not put a picture on the clipboard, the picture opens in
 * the pane, and the browser's own menu on it copies or saves it. */
function picturePane(svg, from) {
  picture(svg).then(function (bl) {
    var r = new FileReader();
    r.onload = function () {
      var p = paneShow('<span class="pk-paneid">Picture of this diagram</span>',
        '<p>Right-click the picture and choose <b>Copy image</b>, or <b>Save image as</b>. ' +
        "The viewer this page is open in does not let a page put a picture on the clipboard or save a file itself.</p>" +
        '<img class="pk-copyimg" alt="">', "", "Picture of this diagram", from);
      var im = p.querySelector(".pk-copyimg");
      im.src = r.result;
      im.alt = svg.getAttribute("aria-label") || (svg.querySelector("title") || {}).textContent || "The diagram";
    };
    r.readAsDataURL(bl);
  }, function () { notify("This diagram could not be turned into a picture."); });
}
function copyPicture(svg, from) {
  var made;
  try {
    if (LOCKED || !navigator.clipboard || !window.ClipboardItem) throw new Error("no clipboard");
    made = navigator.clipboard.write([new ClipboardItem({ "image/png": picture(svg) })]);
  } catch (e) { picturePane(svg, from); return; }
  /* Playwright's WebKit has been seen to leave the request unanswered, so after a
   * few seconds without an answer the picture opens in the pane anyway. */
  var settled = false, late = setTimeout(function () { if (!settled) { settled = true; picturePane(svg, from); } }, 3000);
  made.then(function () { if (settled) return; settled = true; clearTimeout(late);
    notify("Picture copied. Paste it into a document, a slide or an email."); },
    function () { if (settled) return; settled = true; clearTimeout(late); picturePane(svg, from); });
}
function copySvg(svg) {
  if (copyAs({ "text/plain": standalone(svg).text })) notify("SVG copied. Paste it into a drawing tool, or into a file ending .svg.");
  else notify("This browser would not copy the SVG.");
}

function closeCopyMenu() {
  if (!copyMenu) return;
  copyMenu.remove();
  copyMenu = null;
  if (copyFor) { copyFor.btn.setAttribute("aria-expanded", "false"); copyFor.btn.classList.remove("pk-on"); }
  copyFor = null;
}
function openCopyMenu(rec) {
  closeCopyMenu();
  var items = rec.kind === "table"
    ? [["Copy table", "For Word, Excel or an email", function () { copyTable(rec.target); }],
       !LOCKED && ["Save as CSV", "A file for a spreadsheet", function () { saveCsv(rec.target); }]]
    : [[LOCKED ? "Picture to copy or save" : "Copy as picture", "PNG, for a document, slide or email", function () { copyPicture(rec.target, rec.btn); }],
       ["Copy as SVG", "For a drawing tool", function () { copySvg(rec.target); }],
       !LOCKED && ["Save as PNG", "A picture file", function () {
         picture(rec.target).then(function (bl) { saveAs(nameFor(rec.box) + ".png", bl); }, function () { notify("This diagram could not be turned into a picture."); }); }],
       !LOCKED && ["Save as SVG", "A file for a drawing tool", function () {
         saveAs(nameFor(rec.box) + ".svg", new Blob([standalone(rec.target).text], { type: "image/svg+xml" })); }]];
  copyMenu = el("div", "pk-copymenu");
  copyMenu.setAttribute("role", "menu");
  copyMenu.setAttribute("aria-label", rec.btn.getAttribute("aria-label"));
  items.filter(Boolean).forEach(function (it) {
    var b = el("button", "pk-copyitem", "<b></b><span></span>");
    b.type = "button";
    b.setAttribute("role", "menuitem");
    b.firstChild.textContent = it[0];
    b.lastChild.textContent = it[1];
    b.addEventListener("click", function (e) { e.stopPropagation(); closeCopyMenu(); it[2](); });
    copyMenu.appendChild(b);
  });
  doc.body.appendChild(copyMenu);
  var r = rec.btn.getBoundingClientRect(), w = copyMenu.offsetWidth;
  copyMenu.style.left = Math.max(8, Math.min(r.right - w, innerWidth - w - 8)) + scrollX + "px";
  copyMenu.style.top = r.bottom + 4 + scrollY + "px";
  rec.btn.setAttribute("aria-expanded", "true");
  rec.btn.classList.add("pk-on");
  copyFor = rec;
  copyMenu.firstChild.focus({ preventScroll: true });
}
/* The button lives just after what it copies, so the keyboard reaches it
 * straight after the table or figure, and is placed over its top right corner
 * whenever it is shown. */
/* Where the button's positioning box sits is measured, not worked out:
 * offsetParent can name a table cell that does not position anything. */
function placeCopy(rec) {
  var b = rec.box.getBoundingClientRect(), btn = rec.btn;
  btn.style.left = "0px";
  btn.style.top = "0px";
  var z = btn.getBoundingClientRect();
  var right = Math.min(b.right, innerWidth - 4), x = right - btn.offsetWidth / 2 - 6;
  /* The first point down the box's right edge where the box itself is on
   * top: below any bar or marking fixed over the top of the screen. */
  var top = Math.max(b.top, 0) + 6, stop = Math.min(b.bottom, innerHeight) - 40;
  btn.style.visibility = "hidden";
  while (top < stop) {
    var ok = [2, btn.offsetHeight - 2].every(function (dy) {
      var hit = doc.elementFromPoint(x, top + dy);
      return !hit || hit === rec.box || rec.box.contains(hit);
    });
    if (ok) break;
    top += 8;
  }
  btn.style.visibility = "";
  btn.style.left = Math.round(right - btn.offsetWidth - 6 - z.left) + "px";
  btn.style.top = Math.round(top - z.top) + "px";
}
/* One button shows at a time: the one for the innermost table or diagram
 * under the pointer (a table can sit inside a figure that is a diagram). */
var copyRecs = [], copyHideT = 0;
function showCopy(rec) {
  clearTimeout(copyHideT);
  copyRecs.forEach(function (r) { if (r !== rec && r !== copyFor) r.btn.classList.remove("pk-on"); });
  if (copyShown !== rec || !rec.btn.classList.contains("pk-on")) placeCopy(rec);
  rec.btn.classList.add("pk-on");
  copyShown = rec;
}
function hideCopy() {
  clearTimeout(copyHideT);
  copyHideT = setTimeout(function () {
    copyRecs.forEach(function (r) { if (r !== copyFor) r.btn.classList.remove("pk-on"); });
    copyShown = null;
  }, 250);
}
function hoverCopy(e) {
  var t = e.target;
  if (!t || !t.closest || t.closest(".pk-copymenu")) return;
  for (var n = t; n && n !== doc.body; n = n.parentElement) if (n.__pkCopy) { showCopy(n.__pkCopy); return; }
  if (copyShown) hideCopy();
}
function addCopy(kind, target, box) {
  if (box.hasAttribute("data-pk-copy-done")) return;
  box.setAttribute("data-pk-copy-done", "");
  var btn = el("button", "pk-copybtn", ICON.copy);
  btn.type = "button";
  btn.setAttribute("aria-haspopup", "menu");
  btn.setAttribute("aria-expanded", "false");
  btn.setAttribute("aria-label", kind === "table" ? "Copy this table" : "Copy this diagram");
  btn.title = kind === "table" ? "Copy or save this table" : "Copy or save this diagram";
  var rec = { kind: kind, target: target, box: box, btn: btn };
  box.parentNode.insertBefore(btn, box.nextSibling);
  box.__pkCopy = btn.__pkCopy = rec;
  copyRecs.push(rec);
  btn.addEventListener("focus", function () { showCopy(rec); });
  btn.addEventListener("blur", hideCopy);
  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    if (copyFor === rec) closeCopyMenu(); else { placeCopy(rec); openCopyMenu(rec); }
  });
}
function bigSvg(svg) {
  if (svg.closest(COPY_OFF) || (svg.parentElement && svg.parentElement.closest("svg"))) return false;
  var vb = boxOf(svg), r = svg.getBoundingClientRect();
  var w = r.width || (vb && vb.w) || num(svg, "width") || 0, h = r.height || (vb && vb.h) || num(svg, "height") || 0;
  return w >= 200 && h >= 90;
}
function initCopy() {
  each(doc.querySelectorAll("table"), function (t) {
    if (t.closest(COPY_OFF) || (t.parentElement && t.parentElement.closest("table")) || t.rows.length < 2) return;
    if (![].some.call(t.rows, function (r) { return r.cells.length >= 2; })) return;
    var p = t.parentElement, box = t;
    if (p && p.children.length === 1 && /(auto|scroll)/.test(getComputedStyle(p).overflowX)) box = p;
    addCopy("table", t, box);
  });
  var svgs = [].filter.call(doc.querySelectorAll("svg"), bigSvg);
  svgs.forEach(function (svg) {
    var f = svg.closest("figure");
    /* The whole figure, unless it holds other drawings or a table of its own,
     * whose buttons would then sit where this one does. */
    var box = f && svgs.filter(function (s) { return f.contains(s); }).length === 1 &&
      !f.querySelector("[data-pk-copy-done]") ? f : svg;
    addCopy("diagram", svg, box);
  });
  doc.addEventListener("click", function (e) { if (copyMenu && !copyMenu.contains(e.target)) closeCopyMenu(); });
  doc.addEventListener("mouseover", hoverCopy, { passive: true });
  root.addEventListener("mouseleave", hideCopy);
  doc.addEventListener("keydown", function (e) {
    if (!copyMenu) return;
    var items = [].slice.call(copyMenu.querySelectorAll("button")), at = items.indexOf(doc.activeElement);
    if (e.key === "Escape") { var b = copyFor && copyFor.btn; closeCopyMenu(); if (b) b.focus(); e.stopPropagation(); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      items[(at + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
    }
    else if (e.key === "Tab") closeCopyMenu();
  }, true);
  addEventListener("resize", closeCopyMenu);
  /* Opening a section can move everything below it (a long table inside it
   * folds to its first rows), so a button on show is put back in its place. */
  function replace() { if (copyShown) requestAnimationFrame(function () { if (copyShown) placeCopy(copyShown); }); }
  doc.addEventListener("toggle", replace, true);
  addEventListener("resize", replace);
}
on("built", initCopy);
/* pk:end copy-out */

/* pk:feature copy-blocks */
/* ── 11. Copy a code or message block ─────────────────────────────────────
 * A block a reader will want to paste somewhere else carries a labelled copy
 * button above its top right corner, always visible: every <pre> code or text
 * box ("Copy code"), every .pk-message block such as a draft message ("Copy
 * message"), and any element naming its own label with data-pk-copy-label.
 * The copy goes by the copy command, which works inside SharePoint's,
 * OneDrive's and Teams' viewers where the clipboard API is refused: plain text
 * for code, plain text and formatted HTML for a message, so it pastes into an
 * email keeping its paragraphs. Where even that is refused, the block's text
 * is selected for the reader's own Ctrl+C. Off for a block, or everything
 * inside an element, with data-pk-copy="off". */
var BLOCKCOPY = 'pre, .pk-message, [data-pk-copy-label]';
var BLOCKCOPY_OFF = COPY_OFF + ', .pane, .toolbar, [role="dialog"], figure, table, header, nav';
function blockLabel(b) {
  var own = b.getAttribute("data-pk-copy-label");
  if (own) return own;
  return b.tagName === "PRE" ? "Copy code" : "Copy message";
}
function blockFlavours(b) {
  if (b.tagName === "PRE") return { "text/plain": b.textContent.replace(/\n$/, "") };
  var k = b.cloneNode(true);
  each(k.querySelectorAll("button, script, style, .pk-sr, .sr-only, [aria-hidden=true], [hidden]"), function (n) { n.remove(); });
  return { "text/plain": (b.innerText || b.textContent).replace(/\n{3,}/g, "\n\n").trim(), "text/html": k.innerHTML.trim() };
}
function selectBlock(b) {
  try { var s = getSelection(), r = doc.createRange(); r.selectNodeContents(b); s.removeAllRanges(); s.addRange(r); } catch (e) {}
}
function addBlockCopy(b) {
  var label = blockLabel(b), wrap = el("div", "pk-blockwrap"), bar = el("div", "pk-blockbar");
  var btn = el("button", "pk-blockcopy", ICON.copy + "<span>" + esc(label) + "</span>");
  btn.type = "button";
  b.parentNode.insertBefore(wrap, b);
  bar.appendChild(btn);
  wrap.appendChild(bar);
  wrap.appendChild(b);
  b.setAttribute("data-pk-copy-done", "");
  var span = btn.querySelector("span"), back = null;
  btn.addEventListener("click", function () {
    if (copyAs(blockFlavours(b))) {
      span.textContent = "Copied";
      notify("Copied to the clipboard");
    } else {
      selectBlock(b);
      span.textContent = label;
      notify("Press Ctrl+C (⌘C on a Mac) to copy the selected text");
      return;
    }
    clearTimeout(back);
    back = setTimeout(function () { span.textContent = label; }, 2000);
  });
}
function initBlockCopy() {
  each(doc.querySelectorAll(BLOCKCOPY), function (b) {
    if (b.closest(BLOCKCOPY_OFF) || b.hasAttribute("data-pk-copy-done") || !b.parentNode) return;
    if (b.parentElement && b.parentElement.closest(BLOCKCOPY)) return;
    if (!b.textContent.trim()) return;
    addBlockCopy(b);
  });
}
on("built", initBlockCopy);
/* pk:end copy-blocks */

/* pk:feature section-links */
/* ── 10. A link to any section ────────────────────────────────────────────
 * A link icon beside every heading and fold title that has an id (the build
 * gives each one an id made from its words), shown when the pointer is on the
 * heading or the icon has keyboard focus. A click copies a link to that
 * section: as a titled link for a document or an email, and as the address
 * for anywhere else. A link that arrives opens whatever holds the section.
 *
 * Inside a SharePoint, OneDrive or Teams viewer the page cannot see its own
 * web address (measured on SharePoint Online, November 2026: the page runs as
 * about:srcdoc inside a blob: frame, with no referrer), so it cannot make a
 * whole link there. A page whose build gave it its published address
 * (<meta name="pk-home">) links from that; otherwise the reader is given the
 * section's tag to add to the file's own link. SharePoint passes a tag on
 * its address through to the page (seen in the same measurement).
 * Off for one heading, or everything inside an element, with
 * data-pk-link="off". */
ICON.link = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10.6 13.4a4.2 4.2 0 0 0 6 0l3.2-3.2a4.2 4.2 0 0 0-6-6l-1.4 1.4"/><path d="M13.4 10.6a4.2 4.2 0 0 0-6 0l-3.2 3.2a4.2 4.2 0 0 0 6 6l1.4-1.4"/></svg>';
/* Not on the page's furniture (its own side panes, toolbars and dialogs, as
 * search leaves them out too), nor on a heading inside a figure, which labels
 * part of a picture rather than a section. */
var LINK_OFF = '[data-pk-link="off"], .pk-panel, .pk-pane, .pk-float, .pk-copymenu, .pk-partnav, header, nav, ' +
  'button, a, .pane, .toolbar, [role="dialog"], figure';
function homeOf() {
  var m = doc.querySelector('meta[name="pk-home"]');
  return m && /^https?:\/\//i.test(m.content) ? m.content.split("#")[0] : "";
}
function sectionUrl(id) {
  var home = homeOf();
  if (home) return home + "#" + encodeURIComponent(id);
  if (LOCKED) return "";
  return location.href.split("#")[0] + "#" + encodeURIComponent(id);
}
function copyLink(h) {
  var id = h.id, url = sectionUrl(id), name = clip(h.textContent.replace(/\s+/g, " ").trim(), 80);
  if (!url) {
    notify(copyAs({ "text/plain": "#" + id })
      ? "Copied #" + id + ". This viewer hides the file's own address: add #" + id + " to the end of the file's link to point at this section."
      : "This browser would not copy the link.");
    return;
  }
  if (!LOCKED && !homeOf()) setHash(id);
  /* Built through the DOM: a link checker reading a page may take any link
   * written as text, scripts included, as one of the page's own. */
  var link = el("a");
  link.setAttribute("href", url);
  link.textContent = name;
  var ok = copyAs({ "text/html": link.outerHTML, "text/plain": url });
  notify(!ok ? "This browser would not copy the link."
    : location.protocol === "file:" && !homeOf()
      ? "Link to \u201c" + name + "\u201d copied. It points at this copy of the file, on this computer."
      : "Link to \u201c" + name + "\u201d copied.");
}
function initLinks() {
  each(doc.querySelectorAll("h2[id], h3[id], h4[id], summary[id]"), function (h) {
    if (h.closest(LINK_OFF) || h.querySelector(".pk-linkbtn")) return;
    var b = el("button", "pk-linkbtn", ICON.link);
    b.type = "button";
    b.setAttribute("aria-label", "Copy a link to this section");
    b.title = "Copy a link to this section";
    b.addEventListener("click", function (e) { e.preventDefault(); e.stopPropagation(); copyLink(h); });
    b.addEventListener("keydown", function (e) { if (e.key === " " || e.key === "Enter") e.stopPropagation(); });
    h.appendChild(b);
  });
}
on("built", initLinks);
/* pk:end section-links */

/* ── wiring ─────────────────────────────────────────────────────────────── */
function init() {
  root.classList.add("pk", "pk-js");
  root.setAttribute("data-pk-kit", KIT);
  each(doc.querySelectorAll("table"), function (t) {
    if (t.closest(".pk-float")) return;
    fire("table", t);
  });
  if (OWN) initParts();
  fire("start");
  buildPanel();
  fire("built");
  initTheme();
  watchScheme();
  tame(doc);
  if (parts.length) {
    var start = partOf(targetOf(location.hash));
    showPart(start || parts[0], { scroll: false, quiet: true, hash: false });
  }
  addEventListener("scroll", floatAll, { passive: true });
  addEventListener("resize", function () { rebuildAll(); if (innerWidth >= PANEL_MIN) drawer(false); });
  doc.addEventListener("toggle", function () { fire("shown"); rebuildAll(); foldLabel(); }, true);
  /* Find-in-page cannot search rows that are not drawn, or a part where the
   * browser cannot reveal hidden matches, so the shortcut opens them first:
   * the parts, then every tab, then the long tables, so a table that could
   * not be measured until its part or tab showed opens too. */
  doc.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && !e.altKey && (e.key === "f" || e.key === "F")) {
      if (parts.length && !UNTIL_FOUND && !allMode) showAll();
      fire("find");
    }
    if (e.key === "Escape" && root.classList.contains("pk-drawer")) drawer(false);
  });
  function follow(e, a) {
    var id = linkTarget(a).slice(1), t = byId(id);
    if (!t) return;
    /* A page the kit was added to keeps its own links, except inside a
     * viewer's frame, where the browser cannot follow a "#" link in a
     * sandboxed document and the kit has to (measured in both engines). */
    if (!OWN && !FRAMED) { fire("open", t); return; }
    e.preventDefault();
    go(t, id);
  }
  doc.addEventListener("click", function (e) {
    if (e.button || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var a = e.target && e.target.closest ? e.target.closest('a[href^="#"], a[data-pk-href]') : null;
    if (!a || a.closest(".pk-panel") || (e.defaultPrevented && !a.hasAttribute("data-pk-href"))) return;
    follow(e, a);
  });
  doc.addEventListener("keydown", function (e) {
    if (e.key !== "Enter" || !e.target.hasAttribute || !e.target.hasAttribute("data-pk-href")) return;
    if (e.target.closest(".pk-panel")) { e.preventDefault(); e.target.click(); return; }
    follow(e, e.target);
  });
  function arrive() {
    var t = targetOf(location.hash);
    if (!t) return;
    if (OWN) go(t, location.hash.slice(1));
    /* A page the kit was added to keeps its own links. A link into a closed
     * fold needs nothing more (Chromium and WebKit open the fold themselves),
     * but a link to a fold's title, which is on screen already, opens nothing,
     * so the fold it names is opened here (measured in both engines). */
    else if (t.tagName === "SUMMARY" && t.parentNode && !t.parentNode.open) { reveal(t); }
    else if (t.closest && t.closest("table.pk-collapsed, .pk-tabs > .pk-tab[hidden]")) { fire("open", t); try { t.scrollIntoView(); } catch (e) {} }
  }
  addEventListener("hashchange", arrive);
  if (location.hash) arrive();
  var was = null;
  addEventListener("beforeprint", function () {
    fire("print");
    if (parts.length && !allMode) { was = current; showAll(); }
  });
  addEventListener("afterprint", function () {
    fire("unprint");
    if (was) { showPart(was, { scroll: false, quiet: true }); was = null; }
  });
  floatAll();
}
if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
else init();
})();
