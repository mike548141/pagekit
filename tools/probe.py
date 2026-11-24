#!/usr/bin/env python3
"""Drive a pagekit page in real browser engines and report what broke.

Runs each page in Chromium (the engine of Chrome and Edge) and WebKit (the
engine of Safari), two ways each:

* **direct**, as if opened from disk or a mail attachment;
* **sandboxed**, inside a frame with the same lock-down the SharePoint,
  OneDrive and Teams file viewer uses (``sandbox="allow-scripts allow-forms"``,
  measured on SharePoint Online in November 2026): no storage, no
  pop-ups, no downloads, no print dialog from script, no history writes;
* **viewer**, sandboxed as above and with a script that takes over in-page
  links before the page sees them, as that viewer was measured to do;
* **srcdoc**, sandboxed and loaded as ``about:srcdoc``, the way the Teams
  file viewer loads a page (seen in the same measurement). Teams is reported to break
  in-page links there, but this mode did not reproduce a break when the link
  fix was switched off, so it proves the page runs in such a
  frame, not that Teams' own handling is covered. The **viewer** mode does
  reproduce SharePoint's: with the fix off, its link checks fail.

and at a laptop width and a phone width. It records every script error, then
exercises the features the page has (parts, long tables, pinned headings,
links into hidden places, charts that draw when seen, copying a table or a
diagram out and a link to a section (by real mouse clicks), tabs within a
section (by real clicks and keys), a link arriving
into a closed section, the theme switch, reduced motion, print) and checks each did what
it should. Screenshots go to ``--shots``.

Needs Playwright (``python3 -m playwright``). On a machine whose browser
cache is newer than the library, pass the engines' paths with
``--chromium`` / ``--webkit``.

    python3 tools/probe.py PAGE.html [--shots DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CACHE = Path.home() / "Library/Caches/ms-playwright"
SANDBOX = "allow-scripts allow-forms"

# A viewer that takes over in-page links before the page's own script sees
# them, as SharePoint Online's file viewer was measured to do: it
# scrolls to the target itself and records the link in its own address bar.
HIJACK = ("<script>addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a[href^=\"#\"]');"
          "if(!a)return;e.preventDefault();var t=document.getElementById(a.getAttribute('href').slice(1));"
          "if(t)t.scrollIntoView();},true);</script>")

HOST = """<!DOCTYPE html><html><head><meta charset="utf-8"><style>html,body{margin:0;height:100%}
iframe{border:0;width:100%;height:100%;display:block}</style></head><body>
<iframe id="f" sandbox="@SANDBOX@"></iframe><script>
var s = @PAGE@, f = document.getElementById('f');
if (@SRCDOC@) f.srcdoc = s; else f.src = URL.createObjectURL(new Blob([s], {type: 'text/html'}));
</script></body></html>"""

# Each check runs in the page and returns [name, ok, detail]. They act on
# what the page has, so one probe serves any pagekit page.
CHECKS = r"""
async () => {
  const out = [], d = document, wait = ms => new Promise(r => setTimeout(r, ms));
  const shut = el => { const d = el.closest('details:not([open])'); if (!d) return false; const s = d.querySelector(':scope > summary'); return !(s && s.contains(el)); };
  const vis = el => !!(el && el.getClientRects().length && el.getBoundingClientRect().height > 0 && getComputedStyle(el).visibility !== 'hidden' && !el.closest('.pk-part[hidden]') && !shut(el));
  const inView = el => { const r = el.getBoundingClientRect(); return r.bottom > 0 && r.top < innerHeight; };
  const add = (n, ok, det) => out.push([n, !!ok, det || '']);
  // Waits for a condition rather than a fixed time, so a loaded machine slows the probe, not fails it.
  const until = async (fn, ms = 2500) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { if (fn()) return true; await wait(60); } return !!fn(); };
  const hrefOf = a => a.getAttribute('href') || a.getAttribute('data-pk-href') || '';
  const LINKS = 'a[href^="#"], a[data-pk-href]';
  add('script ran', d.documentElement.classList.contains('pk-js'));
  const mk = d.getElementById('pk-mark-top');
  if (mk) { const mb = d.getElementById('pk-mark-bottom'), r1 = mk.getBoundingClientRect(), r2 = mb && mb.getBoundingClientRect();
    const meta = d.querySelector('meta[name="protective-marking"]');
    const first = [...d.querySelectorAll('header, main, #pk-main')].find(vis);
    add('marking at the top and bottom of the screen, and in the file', r1.top <= 0.5 && r2 && Math.abs(r2.bottom - innerHeight) <= 1
        && meta && meta.content === mk.textContent && (!first || first.getBoundingClientRect().top >= r1.bottom - 1),
        mk.textContent + ' · ' + getComputedStyle(mk).color); }
  const wm = d.getElementById('pk-watermark');
  if (wm) add('watermark lets clicks through', getComputedStyle(wm).pointerEvents === 'none', wm.textContent);
  add('charset utf-8', d.characterSet.toLowerCase() === 'utf-8', d.characterSet);
  const mac = (d.body.innerText.match(/[āēīōūĀĒĪŌŪ]/g) || []).length;
  add('macrons stored as single characters', !/\u0304/.test(d.body.textContent), mac + ' macron letters on screen');
  const moving = [...d.querySelectorAll('.pk-mo')].filter(vis);
  if (moving.length) {
    const m = moving.find(e => e.getBoundingClientRect().top > innerHeight) || moving[0];
    const below = m.getBoundingClientRect().top > innerHeight, early = m.classList.contains('pk-in');
    m.scrollIntoView({block: 'center', behavior: 'instant'}); await wait(2600);
    const bar = m.querySelector('.pk-bar, .pk-tbar, .cbarfill'), lab = m.querySelector('.pk-mlab');
    const done = bar && getComputedStyle(bar).transform === 'none' && (!lab || getComputedStyle(lab).opacity === '1');
    add('a chart draws when it comes into view', (!below || !early) && m.classList.contains('pk-in') && done,
        moving.length + ' moving; ' + (below ? (early ? 'drew before it was seen' : 'waited until seen') : 'in view at load'));
    scrollTo(0, 0); await wait(150);
  }
  const parts = [...d.querySelectorAll('.pk-part')];
  if (parts.length >= 2) {
    add('one part shown at load', parts.filter(vis).length === 1, parts.filter(vis).map(p => p.id).join());
    const links = [...d.querySelectorAll('.pk-panel .pk-a1')];
    links[1].click(); await wait(250);
    add('selector shows part 2 only', vis(parts[1]) && parts.filter(vis).length === 1 && links[1].getAttribute('aria-current') === 'true');
    const loud = d.querySelector('.pk-toast.pk-on');
    add('a part change is announced to screen readers only', !loud, loud ? 'shown on screen: ' + loud.textContent : '');
    const nx = parts[1].querySelector('.pk-partnav .pk-next');
    if (nx) { nx.click(); await wait(250); add('next-part link moves on', vis(parts[2]) && !vis(parts[1])); }
    links[0].click(); await wait(250);
    const xl = [...parts[0].querySelectorAll(LINKS)].find(a => { const t = d.getElementById(hrefOf(a).slice(1)); return t && t.closest('.pk-part') && t.closest('.pk-part') !== parts[0]; });
    if (xl) { const t = d.getElementById(hrefOf(xl).slice(1)); xl.click(); await wait(400);
      add('link into another part lands', vis(t) && inView(t), hrefOf(xl)); }
    const all = d.querySelector('.pk-allbtn');
    if (all) { all.click(); await wait(250); add('all parts on one page', parts.every(vis));
      all.click(); await wait(250); add('back to one part', parts.filter(vis).length === 1); }
    // The part with the most sub-sections (outside its pictures) lists them.
    const subs = p => [...p.querySelectorAll('h3')].filter(h => !h.closest('figure, .pk-pane, .pane')).length;
    const most = parts.reduce((m, p, i) => subs(p) > subs(parts[m]) ? i : m, 0);
    if (subs(parts[most]) >= 2) { links[most].click(); await wait(300);
      const toc = d.querySelectorAll('.pk-panel .pk-l2 a');
      add('contents of the part listed', toc.length >= 2, toc.length + ' entries for part ' + (most + 1)); }
    links[0].click(); await wait(250);
  } else if (d.querySelector('.pk-panel')) {
    const links = [...d.querySelectorAll('.pk-panel .pk-a1')];
    add('panel lists the sections', links.length >= 2, links.length + ' sections');
    const k = Math.min(2, links.length - 1), t = d.getElementById(hrefOf(links[k]).slice(1));
    links[k].click(); await until(() => t && inView(t) && links[k].closest('li').classList.contains('pk-cur'));
    add('a section in the panel lands', t && inView(t) && links[k].closest('li').classList.contains('pk-cur'), hrefOf(links[k]));
    scrollTo(0, 0); await wait(200);
  }
  const panel = d.querySelector('.pk-panel');
  if (panel) {
    const q = panel.querySelector('input[type=search]');
    const para = [...d.querySelectorAll('p')].find(p => !p.closest('.pk-panel, header, footer') && /[a-z]{7,}/.test(p.textContent));
    const word = para ? para.textContent.match(/[a-z]{7,}/)[0] : 'the';
    q.value = word; q.dispatchEvent(new Event('input', {bubbles: true})); await wait(400);
    const hits = panel.querySelectorAll('.pk-rlist a');
    add('search finds the words', hits.length > 0, hits.length + ' results for "' + word + '"');
    if (hits.length) { hits[0].click(); await wait(500); const id = hrefOf(hits[0]).slice(1), t = d.getElementById(id);
      add('a search result lands', t && vis(t) && inView(t), id); }
    q.value = ''; q.dispatchEvent(new Event('input', {bubbles: true})); await wait(200);
    const fb = panel.querySelector('.pk-foldall');
    if (fb) { const ds = [...d.querySelectorAll('details')].filter(x => !x.closest('.pk-panel'));
      fb.click(); await wait(150); const allOpen = ds.every(x => x.open), l1 = fb.textContent;
      fb.click(); await wait(150); const allShut = ds.every(x => !x.open), l2 = fb.textContent;
      add('one control expands and collapses all', allOpen && allShut && l1 !== l2, l1.trim() + ' / ' + l2.trim()); }
    const sb = panel.querySelector('.pk-slimbtn');
    if (sb && vis(sb)) { const w0 = panel.getBoundingClientRect().width;
      sb.click(); await until(() => panel.getBoundingClientRect().width < 70 && parseFloat(getComputedStyle(d.body).paddingLeft) < 70);
      const w1 = panel.getBoundingClientRect().width, pad = parseFloat(getComputedStyle(d.body).paddingLeft);
      const ctl = [...panel.querySelectorAll('.pk-slimbar button')].filter(vis).length;
      panel.querySelector('.pk-slimopen').click(); await until(() => Math.abs(panel.getBoundingClientRect().width - w0) < 1);
      const w2 = panel.getBoundingClientRect().width;
      add('panel folds to a narrow bar and back', w1 < 70 && pad < 70 && ctl >= 3 && Math.abs(w2 - w0) < 1,
          Math.round(w0) + ' -> ' + Math.round(w1) + ' -> ' + Math.round(w2) + 'px, ' + ctl + ' controls on the bar'); }
    scrollTo(0, 0); await wait(150);
  }
  const btns = [...d.querySelectorAll('.pk-morebtn')].filter(vis);
  if (btns.length) {
    add('long tables collapsed', true, d.querySelectorAll('table.pk-collapsed').length + ' collapsed');
    const b = btns[0], t = d.getElementById(b.getAttribute('aria-controls').split(' ')[0]).closest('table');
    const hidden0 = [...t.tBodies[0].rows].filter(r => !vis(r)).length;
    t.scrollIntoView({block: 'start', behavior: 'instant'}); scrollBy(0, 40); await wait(250);
    b.click(); await wait(250);
    const hidden1 = [...t.tBodies[0].rows].filter(r => !vis(r)).length;
    add('show-all opens the table', hidden0 > 0 && hidden1 === 0, hidden0 + ' hidden, then ' + hidden1);
    t.querySelector('tbody').rows[Math.floor(t.tBodies[0].rows.length / 2)].scrollIntoView({block: 'center', behavior: 'instant'});
    await wait(300);
    const fl = [...d.querySelectorAll('.pk-float')].filter(f => f.style.display === 'block');
    let aligned = false;
    if (fl.length) { const c = fl[0].querySelector('th'), o = t.tHead.querySelector('th');
      aligned = Math.abs(c.getBoundingClientRect().left - o.getBoundingClientRect().left) < 2; }
    add('headings stay in view', fl.length === 1 && aligned, fl.length + ' pinned, aligned ' + aligned);
    b.click(); await wait(200);
  }
  const deep = [...d.querySelectorAll(LINKS)].find(a => { const t = d.getElementById(hrefOf(a).slice(1)); return t && t.closest('tr.pk-more'); });
  if (deep) { const t = d.getElementById(hrefOf(deep).slice(1));
    const p = deep.closest('.pk-part'); if (p) { const l = [...d.querySelectorAll('.pk-panel .pk-a1')].find(a => hrefOf(a) === '#' + p.id); l && l.click(); await wait(250); }
    deep.click(); await wait(400); add('link into a hidden row lands', vis(t) && inView(t), hrefOf(deep)); }
  const away = a => !(a.getAttribute('href') || a.getAttribute('data-pk-href') || '').startsWith('#');
  const allRefs = [...d.querySelectorAll('a.pk-ref[data-pk-ref]')].filter(a => !a.closest('.pk-part[hidden], tr.pk-more'));
  const pick = allRefs.find(a => vis(a) && away(a)) || allRefs.find(away) || allRefs.find(vis);
  if (pick) { let p = pick.closest('details:not([open])'); while (p) { p.open = true; p = p.parentElement.closest('details:not([open])'); } await wait(100); }
  const refs = pick && vis(pick) ? [pick] : [];
  if (refs.length) {
    const r = refs[0];
    // A scroll hides an open card, so the page settles before the pointer arrives.
    r.scrollIntoView({block: 'center', behavior: 'instant'}); await wait(400);
    r.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
    await until(() => { const t = d.querySelector('.pk-tip'); return t && getComputedStyle(t).display !== 'none'; });
    const tip = d.querySelector('.pk-tip'), shown = tip && getComputedStyle(tip).display !== 'none' && tip.textContent.includes(r.dataset.pkRef);
    r.dispatchEvent(new MouseEvent('mouseout', {bubbles: true}));
    add('an identifier shows its card on hover', shown, r.dataset.pkRef);
    if (!(r.getAttribute('href') || r.getAttribute('data-pk-href') || '').startsWith('#')) {
      r.click(); await until(() => d.documentElement.classList.contains('pk-paneopen'));
      const pane = d.querySelector('.pk-pane'), open = d.documentElement.classList.contains('pk-paneopen') && pane && pane.textContent.includes(r.dataset.pkRef);
      d.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true})); await wait(300);
      add('a click opens its full entry in the pane, Escape closes it', open && !d.documentElement.classList.contains('pk-paneopen'), r.dataset.pkRef);
    }
    scrollTo(0, 0); await wait(100);
  }
  const tb = [...d.querySelectorAll('[data-pk-theme]')].find(b => b.closest('.pk-panel')) || d.querySelector('[data-pk-theme]');
  if (tb) { const was = d.documentElement.getAttribute('data-theme'); tb.click(); await wait(100);
    const now = d.documentElement.getAttribute('data-theme');
    add('theme switch', was !== now && getComputedStyle(d.body).backgroundColor !== '', was + ' -> ' + now); tb.click(); }
  const fold = d.querySelector('details.pk-fold:not([open])');
  if (fold) { fold.querySelector('summary').click(); await wait(100); add('fold opens', fold.open); fold.open = false; }
  return out;
}
"""

PRINT_CHECK = r"""() => [...document.querySelectorAll('.pk-part, .pk-tab')].map(p => p.getBoundingClientRect().height > 0)
  .concat([...document.querySelectorAll('tr.pk-more')].slice(0, 50).map(r => r.getClientRects().length > 0))
  .concat([...document.querySelectorAll('.pk-mo .pk-bar, .pk-mo .pk-tbar, .pk-mo .cbarfill')].slice(0, 50)
    .map(b => getComputedStyle(b).transform === 'none'))"""


# Copying out needs a real click (a browser only lets a page copy in answer to
# one), so these checks drive the mouse from here rather than from the page.
# A listener records what each copy put on the clipboard.
COPY_PICK = r"""async (kind) => {
  if (!window.__pkcopy) { window.__pkcopy = [];
    addEventListener('copy', e => window.__pkcopy.push({html: e.clipboardData.getData('text/html'), text: e.clipboardData.getData('text/plain')})); }
  const d = document, shut = el => !!el.closest('details:not([open]), .pk-part[hidden]');
  d.querySelectorAll('[data-probe]').forEach(x => x.removeAttribute('data-probe'));
  // What a button copies is the nearest earlier sibling the kit marked: a
  // "Show all rows" bar can come between them when a closed section opens.
  const boxOf = x => { let e = x.previousElementSibling; while (e && !e.hasAttribute('data-pk-copy-done')) e = e.previousElementSibling; return e; };
  const all = [...d.querySelectorAll('.pk-copybtn')].filter(x => x.getAttribute('aria-label').includes(kind) && !x.closest('.pk-part[hidden]'));
  let b = all.find(x => boxOf(x) && boxOf(x).getBoundingClientRect().height > 0 && !shut(x));
  // Only in closed sections: open the first one's, as a reader would.
  if (!b && all.length) { b = all[0]; let p = b.closest('details:not([open])'); while (p) { p.open = true; p = p.parentElement.closest('details:not([open])'); } }
  if (!b || !(boxOf(b).getBoundingClientRect().height > 0)) return null;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(r, 150)))); // let an opened section settle
  const box = boxOf(b), hidden = getComputedStyle(b).opacity === '0';
  box.scrollIntoView({block: 'center', behavior: 'instant'});
  box.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
  b.setAttribute('data-probe', '1');
  const t = box.matches('table') ? box : box.querySelector('table');
  return {hidden, rows: t ? t.rows.length : 0, n: window.__pkcopy.length};
}"""
COPY_LAST = "() => (window.__pkcopy || []).slice(-1)[0] || null"
COPY_LISTEN = r"""() => { if (!window.__pkcopy) { window.__pkcopy = [];
  addEventListener('copy', e => window.__pkcopy.push({html: e.clipboardData.getData('text/html'), text: e.clipboardData.getData('text/plain')})); } }"""
COPY_PANE = r"""async () => { const t0 = Date.now(); let im, toast;
  while (Date.now() - t0 < 6000) { im = document.querySelector('.pk-paneopen .pk-pane img.pk-copyimg');
    toast = [...document.querySelectorAll('.pk-toast.pk-on')].find(t => /Picture/.test(t.textContent));
    if ((im && im.naturalWidth > 0) || toast) break; await new Promise(r => setTimeout(r, 80)); }
  return {pane: !!(im && im.naturalWidth > 0), w: im ? im.naturalWidth : 0, toast: toast ? toast.textContent : ''}; }"""


def copy_checks(pg, frame, mode: str) -> list:
    out: list = []
    locked = mode != "direct"

    def menu(kind: str):
        got = frame.evaluate(COPY_PICK, kind)
        if got:
            frame.locator('[data-probe="1"]').click()
            frame.locator(".pk-copymenu").wait_for(timeout=3000)
        return got

    def item(name: str):
        return frame.locator(".pk-copymenu .pk-copyitem", has_text=name)

    t = menu("table")
    if t:
        # The pointer moves from a diagram to the table: only the table's shows.
        on = frame.evaluate(r"""() => { const d = document, seen = e => e.getBoundingClientRect().height > 0;
          const boxes = [...d.querySelectorAll('[data-pk-copy-done]')].filter(seen);
          const fig = boxes.find(b => !b.matches('table, .tablewrap, div') || b.matches('svg, figure'));
          const tab = d.querySelector('[data-probe="1"]');
          let e = tab.previousElementSibling; while (e && !e.hasAttribute('data-pk-copy-done')) e = e.previousElementSibling;
          if (fig) fig.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
          e.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
          return [d.querySelectorAll('.pk-copybtn.pk-on').length, !!fig]; }""")
        out.append(["one copy button shows at a time", on[0] == 1, f"{on[0]} showing (after a diagram: {on[1]})"])
        item("Copy table").click()
        pg.wait_for_timeout(200)
        c = frame.evaluate(COPY_LAST)
        lines = len(c["text"].rstrip("\n").split("\n")) if c else 0
        out.append(["a table copies as a table and as cells", c and "<table" in c["html"] and "\t" in c["text"]
                    and lines == t["rows"] and t["hidden"], f"{lines} of {t['rows']} rows; button hidden until pointed at: {t['hidden']}"])
    g = menu("diagram")
    if g:
        names = frame.locator(".pk-copymenu .pk-copyitem b").all_inner_texts()
        saves = [n for n in names if n.startswith("Save")]
        out.append(["save offered only where the page may save", bool(saves) != locked, ", ".join(names)])
        item("Copy as SVG").click()
        pg.wait_for_timeout(200)
        c = frame.evaluate(COPY_LAST)
        out.append(["a diagram copies as SVG with its styles", c and c["text"].startswith("<svg") and "xmlns" in c["text"]
                    and "fill:" in c["text"], f"{len(c['text']) if c else 0} characters"])
        menu("diagram")
        frame.locator(".pk-copymenu .pk-copyitem").first.click()
        r = frame.evaluate(COPY_PANE)
        ok = r["pane"] if locked else (r["pane"] or "Picture copied" in r["toast"])
        out.append(["a diagram copies as a picture, or opens one to copy", ok,
                    f"picture {r['w']}px wide in the pane" if r["pane"] else r["toast"] or "nothing happened"])
        pg.keyboard.press("Escape")
        if not locked:
            menu("diagram")
            with pg.expect_download(timeout=8000) as dl:
                item("Save as PNG").click()
            name = dl.value.suggested_filename
            out.append(["a diagram saves as a PNG file", name.endswith(".png"), name])
            pg.keyboard.press("Escape")
    return out


# A block's labelled copy button (code or message). The block may sit in a part
# not on screen: an in-page link to it, followed by the kit as a reader's would
# be, shows that part first. The button must be visible before the pointer is
# anywhere near it.
BLOCK_PICK = r"""async (kind) => { const d = document;
  if (!window.__pkcopy) { window.__pkcopy = [];
    addEventListener('copy', e => window.__pkcopy.push({html: e.clipboardData.getData('text/html'), text: e.clipboardData.getData('text/plain')})); }
  d.querySelectorAll('[data-probe]').forEach(x => x.removeAttribute('data-probe'));
  const want = kind === 'code' ? 'pre' : '.pk-message';
  const wrap = [...d.querySelectorAll('.pk-blockwrap')].find(w => w.querySelector(':scope > ' + want));
  if (!wrap) return null;
  if (wrap.closest('.pk-part[hidden]')) {
    wrap.id = wrap.id || 'pk-probe-block';
    const a = d.createElement('a'); a.setAttribute('data-pk-href', '#' + wrap.id); d.body.appendChild(a); a.click(); a.remove();
    const t0 = Date.now(); while (Date.now() - t0 < 2500 && wrap.closest('.pk-part[hidden]')) await new Promise(r => setTimeout(r, 60));
  }
  wrap.scrollIntoView({block: 'center', behavior: 'instant'});
  await new Promise(r => setTimeout(r, 200));
  const b = wrap.querySelector('.pk-blockcopy'), block = wrap.querySelector(':scope > ' + want), cs = getComputedStyle(b);
  const shown = b.getBoundingClientRect().height > 0 && cs.opacity === '1' && cs.visibility === 'visible';
  const text = kind === 'code' ? block.textContent.replace(/\n$/, '') : (block.innerText || '').replace(/\n{3,}/g, '\n\n').trim();
  b.setAttribute('data-probe', '1');
  return {shown, label: b.textContent.trim(), text, n: window.__pkcopy.length}; }"""


# A long table's filter and sort, driven by real typing and real clicks.
TOOLS_PICK = r"""async () => { const d = document;
  d.querySelectorAll('[data-probe]').forEach(x => x.removeAttribute('data-probe'));
  const tools = [...d.querySelectorAll('.pk-tabletools')].find(x => !x.closest('.pk-part[hidden], details:not([open])'));
  if (!tools) return null;
  let t = tools.nextElementSibling; t = t.matches('table') ? t : t.querySelector('table');
  tools.scrollIntoView({block: 'start', behavior: 'instant'});
  await new Promise(r => setTimeout(r, 150));
  tools.querySelector('.pk-filter').setAttribute('data-probe', 'filter');
  const rows = [...t.tBodies[0].rows], heads = [...t.tHead.rows[0].cells];
  // A column whose every cell is a number, and a word from a row deep in the table.
  const num = heads.findIndex((h, i) => h.querySelector('.pk-sortbtn') && rows.every(r => /^[-+]?[\d,]*\.?\d+%?$/.test(r.cells[i].textContent.trim())));
  // A word that some rows hold and some do not, so the filter has work to show.
  const plain = s => s.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const texts = rows.map(r => plain([...r.cells].map(c => c.textContent).join(' ')));
  let word = '';
  for (const r of rows.slice(Math.min(rows.length - 1, 30)).concat(rows)) {
    for (const w of [...r.cells].map(c => c.textContent).join(' ').split(/[\s,;:()]+/)) {
      if (w.length < 3) continue;
      const n = texts.filter(x => x.includes(plain(w))).length;
      if (n > 0 && n < rows.length) { word = w; break; }
    }
    if (word) break;
  }
  if (!word) return null;
  tools.setAttribute('data-probe', 'tools');
  if (num >= 0) heads[num].querySelector('.pk-sortbtn').setAttribute('data-probe', 'sort');
  t.setAttribute('data-probe', 'table');
  return {num, word, total: rows.length}; }"""
TOOLS_STATE = r"""(q) => { const t = document.querySelector('table[data-probe="table"]'), seen = r => r.getClientRects().length > 0;
  const plain = s => s.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const rows = [...t.tBodies[0].rows], shown = rows.filter(seen), text = r => plain([...r.cells].map(c => c.textContent).join(' '));
  return {shown: shown.length, all: rows.length, matching: rows.filter(r => !q || text(r).includes(plain(q))).length,
    allMatch: shown.every(r => !q || text(r).includes(plain(q))),
    count: (document.querySelector('[data-probe="tools"] .pk-filtercount') || {}).textContent || ''}; }"""
TOOLS_ORDER = r"""(col) => { const t = document.querySelector('table[data-probe="table"]');
  const v = [...t.tBodies[0].rows].map(r => parseFloat(r.cells[col].textContent.replace(/[,%\s]/g, '')));
  const th = t.tHead.rows[0].cells[col];
  return {v, sort: th.getAttribute('aria-sort'), first: t.tBodies[0].rows[0].id || t.tBodies[0].rows[0].textContent.slice(0, 20)}; }"""


def tools_checks(pg, frame, mode: str) -> list:
    out: list = []
    got = frame.evaluate(TOOLS_PICK)
    if not got:
        return out
    first0 = frame.evaluate(TOOLS_ORDER, max(got["num"], 0))["first"]
    before = frame.evaluate(TOOLS_STATE, "")["shown"]
    f = frame.locator('[data-probe="filter"]')
    f.click()
    f.press_sequentially(got["word"], delay=30)
    pg.wait_for_timeout(500)
    s = frame.evaluate(TOOLS_STATE, got["word"])
    out.append(["a long table's filter shows only and all matching rows",
                s["allMatch"] and s["shown"] == s["matching"] and 0 < s["shown"] < s["all"] and f"{s['shown']} of" in s["count"].replace(",", ""),
                f"{got['word']!r}: {s['shown']} shown, {s['matching']} match, of {s['all']}; says {s['count'].strip()!r}"])
    f.fill("")
    f.press("Backspace")
    pg.wait_for_timeout(500)
    s = frame.evaluate(TOOLS_STATE, "")
    out.append(["clearing the filter puts the table back as it was", s["shown"] == before and not s["count"].strip().endswith("match"),
                f"{s['shown']} of {s['all']} rows shown, {before} before filtering"])
    if got["num"] >= 0:
        b = frame.locator('[data-probe="sort"]')
        b.click()
        pg.wait_for_timeout(250)
        up = frame.evaluate(TOOLS_ORDER, got["num"])
        b.click()
        pg.wait_for_timeout(250)
        down = frame.evaluate(TOOLS_ORDER, got["num"])
        b.click()
        pg.wait_for_timeout(250)
        back = frame.evaluate(TOOLS_ORDER, got["num"])
        ok = (up["v"] == sorted(up["v"]) and up["sort"] == "ascending" and down["v"] == sorted(down["v"], reverse=True)
              and down["sort"] == "descending" and back["sort"] == "none" and back["first"] == first0)
        out.append(["a heading sorts up, down, then back to the table's order", ok,
                    f"{up['sort']}, {down['sort']}, {back['sort']}; first row back to {back['first']!r}"])
    return out


# A citation of a listed source: its card on hover names the source and when it
# was read; a click lands on the source's row.
SOURCE_PICK = r"""async () => { const d = document;
  d.querySelectorAll('[data-probe]').forEach(x => x.removeAttribute('data-probe'));
  const hrefOf = a => a.getAttribute('data-pk-href') || a.getAttribute('href') || '';
  const cite = [...d.querySelectorAll('a.pk-ref[data-pk-ref]')].find(a => {
    const t = hrefOf(a).startsWith('#') && d.getElementById(hrefOf(a).slice(1));
    return t && t.closest('[data-pk-ref="off"]') && !a.closest('[data-pk-ref="off"]'); });
  if (!cite) return null;
  if (cite.closest('.pk-part[hidden]')) {
    cite.id = cite.id || 'pk-probe-cite';
    const a = d.createElement('a'); a.setAttribute('data-pk-href', '#' + cite.id); d.body.appendChild(a); a.click(); a.remove();
    const t0 = Date.now(); while (Date.now() - t0 < 2500 && cite.closest('.pk-part[hidden]')) await new Promise(r => setTimeout(r, 60));
  }
  let f = cite.closest('details:not([open])'); while (f) { f.open = true; f = f.parentElement.closest('details:not([open])'); }
  cite.scrollIntoView({block: 'center', behavior: 'instant'});
  await new Promise(r => setTimeout(r, 400));
  const row = d.getElementById(hrefOf(cite).slice(1));
  cite.setAttribute('data-probe', 'cite');
  return {id: cite.dataset.pkRef, target: row.id, cells: [...row.cells].map(c => c.textContent.trim())}; }"""
SOURCE_TIP = r"""() => { const t = document.querySelector('.pk-tip');
  return t && getComputedStyle(t).display !== 'none' ? t.textContent : ''; }"""
SOURCE_LANDED = r"""(id) => { const r = document.getElementById(id); if (!r) return false;
  const b = r.getBoundingClientRect(); return b.height > 0 && b.top >= 0 && b.bottom <= innerHeight; }"""


def source_checks(pg, frame, mode: str) -> list:
    out: list = []
    got = frame.evaluate(SOURCE_PICK)
    if not got:
        return out
    c = frame.locator('[data-probe="cite"]')
    c.hover()
    pg.wait_for_timeout(600)
    tip = frame.evaluate(SOURCE_TIP)
    title, when = got["cells"][1], got["cells"][-1]
    out.append(["a cited source shows its card on hover", got["id"] in tip and title in tip and when in tip,
                f"{got['id']}: card {'names it and when it was read' if title in tip and when in tip else repr(tip[:80])}"])
    pg.mouse.move(2, 2)
    pg.wait_for_timeout(200)
    c.click()
    pg.wait_for_timeout(700)
    landed = frame.evaluate(SOURCE_LANDED, got["target"])
    out.append(["a click on a citation lands on its source", landed, got["target"]])
    return out


def block_checks(pg, frame, mode: str) -> list:
    out: list = []
    for kind, label in (("code", "Copy code"), ("message", "Copy message")):
        got = frame.evaluate(BLOCK_PICK, kind)
        if not got:
            continue
        frame.locator('[data-probe="1"]').click()
        pg.wait_for_timeout(250)
        c = frame.evaluate(COPY_LAST)
        after = frame.locator('[data-probe="1"]').inner_text()
        fresh = bool(c) and frame.evaluate("() => (window.__pkcopy || []).length") > got["n"]
        same = fresh and c["text"].strip() == got["text"].strip() and (kind == "code" or "<p>" in c["html"])
        out.append([f"a {kind} block's labelled button copies it", got["shown"] and got["label"] == label and same
                    and after.strip() == "Copied",
                    f"shown without pointing: {got['shown']}; label {got['label']!r}; "
                    f"copied {len(c['text']) if fresh else 0} of {len(got['text'])} characters; then {after.strip()!r}"])
    return out


LINK_PICK = r"""() => { const d = document, shut = el => !!el.closest('details:not([open]), .pk-part[hidden]');
  d.querySelectorAll('[data-probe]').forEach(x => x.removeAttribute('data-probe'));
  const b = [...d.querySelectorAll('.pk-linkbtn')].find(x => !shut(x) && x.getBoundingClientRect().height > 0);
  if (!b) return null;
  b.parentElement.scrollIntoView({block: 'center', behavior: 'instant'});
  b.setAttribute('data-probe', '1');
  return b.parentElement.id; }"""
# A section in a closed fold, reached by a link arriving from outside.
LINK_ARRIVE = r"""async () => { const d = document;
  const t = [...d.querySelectorAll('summary[id], details:not([open]) :is(h2, h3, h4)[id]')]
    .find(x => x.closest('details:not([open])') && !x.closest('.pk-part[hidden], .pk-panel') && x.querySelector(':scope > .pk-linkbtn'));
  if (!t) return null;
  // An instant scroll: a smooth one still gliding would fight the link's own.
  scrollTo({top: 0, behavior: 'instant'}); await new Promise(r => setTimeout(r, 100)); location.hash = '#' + t.id;
  // A closed fold's title is on screen before the link is acted on, so wait
  // for the fold to open as well, not for the title to be visible.
  const open = () => t.tagName === 'SUMMARY' ? t.parentElement.open : !t.closest('details:not([open])');
  const t0 = Date.now(), seen = () => { const r = t.getBoundingClientRect(); return r.height > 0 && r.top >= 0 && r.top < innerHeight; };
  while (Date.now() - t0 < 2500 && !(open() && seen())) await new Promise(r => setTimeout(r, 60));
  await new Promise(r => setTimeout(r, 400));  // and let the scroll finish
  return [t.id, seen(), open()]; }"""


def link_checks(pg, frame, mode: str) -> list:
    out: list = []
    ident = frame.evaluate(LINK_PICK)
    if ident:
        frame.evaluate(COPY_LISTEN)
        frame.locator('[data-probe="1"]').click()
        pg.wait_for_timeout(200)
        c = frame.evaluate(COPY_LAST)
        text = c["text"] if c else ""
        ok = text == "#" + ident if mode != "direct" else (text.endswith("#" + ident) and "<a href" in c["html"])
        out.append(["a heading's icon copies a link to it", ok, text[-70:] or "nothing copied"])
        pg.mouse.move(2, 2)  # off the page's content, so no copy button stays shown
        pg.wait_for_timeout(400)
    # Setting the tag on a page loaded from a blob: address makes Chromium try
    # to load it afresh, which no viewer does (SharePoint hands the tag over
    # with the page), so arrival is checked where a tag is a plain jump.
    a = frame.evaluate(LINK_ARRIVE) if mode in ("direct", "srcdoc") else None
    if a:
        out.append(["a link into a closed section opens it and lands", a[1] and a[2], "#" + a[0]])
    return out


# Tabs within a section: the first group, brought on screen (its part shown
# first), then driven by real clicks and keys from Python.
TAB_PICK = r"""async () => { const d = document, wait = ms => new Promise(r => setTimeout(r, ms));
  const g = [...d.querySelectorAll('.pk-tabs')].find(x => x.querySelector(':scope > .pk-tablist'));
  if (!g) return null;
  const part = g.closest('.pk-part');
  if (part && part.hidden) { const a = [...d.querySelectorAll('.pk-panel .pk-a1')].find(l => (l.getAttribute('href') || l.getAttribute('data-pk-href')) === '#' + part.id); if (a) { a.click(); await wait(300); } }
  d.querySelectorAll('[data-probe-tab]').forEach(x => x.removeAttribute('data-probe-tab'));
  [...g.querySelectorAll('[role=tab]')].forEach((b, i) => b.setAttribute('data-probe-tab', i));
  g.scrollIntoView({block: 'start', behavior: 'instant'}); await wait(150);
  return true; }"""
TAB_STATE = r"""() => { const d = document, g = d.querySelector('[data-probe-tab]').closest('.pk-tabs');
  const panes = [...g.children].filter(c => c.classList.contains('pk-tab'));
  const tabs = [...g.querySelectorAll('[role=tab]')];
  const shown = panes.map(p => !p.hidden && p.getBoundingClientRect().height > 0);
  const head = panes[0].querySelector('.pk-tabhead');
  return {shown, selected: tabs.map(t => t.getAttribute('aria-selected') === 'true'),
          focus: tabs.indexOf(d.activeElement), n: panes.length,
          head: head ? head.getBoundingClientRect().height <= 1 : null}; }"""
# A link on screen whose target sits in a pane not shown; clicked, then landed.
TAB_LINK = r"""() => { const d = document, hrefOf = a => a.getAttribute('href') || a.getAttribute('data-pk-href') || '';
  d.querySelectorAll('[data-probe-link]').forEach(x => x.removeAttribute('data-probe-link'));
  const a = [...d.querySelectorAll('a[href^="#"], a[data-pk-href]')].find(a => {
    const t = d.getElementById(hrefOf(a).slice(1)), p = t && t.closest('.pk-tab');
    return p && p.hidden && a.getBoundingClientRect().height > 0 && !a.closest('.pk-panel, .pk-part[hidden], .pk-tab[hidden]'); });
  if (!a) return null;
  a.scrollIntoView({block: 'center', behavior: 'instant'});
  a.setAttribute('data-probe-link', '1');
  return hrefOf(a).slice(1); }"""
TAB_LANDED = r"""async (id) => { const t = document.getElementById(id), p = t.closest('.pk-tab'), t0 = Date.now();
  const ok = () => !p.hidden && p.getBoundingClientRect().height > 0 && (r => r.bottom > 0 && r.top < innerHeight)(p.getBoundingClientRect());
  while (Date.now() - t0 < 2500 && !ok()) await new Promise(r => setTimeout(r, 60));
  const b = document.getElementById(p.getAttribute('aria-labelledby'));
  return ok() && b.getAttribute('aria-selected') === 'true'; }"""
# The panel's search, for words only a pane not shown holds.
TAB_SEARCH = r"""async () => { const d = document, wait = ms => new Promise(r => setTimeout(r, ms));
  const q = d.querySelector('.pk-panel input[type=search]');
  const p = [...d.querySelectorAll('.pk-tabbed > .pk-tab')].find(x => x.hidden && !x.closest('.pk-part[hidden]'));
  if (!q || !p) return null;
  const para = [...p.querySelectorAll('p, li')].find(x => /[a-z]{6,}/i.test(x.textContent));
  if (!para) return null;
  const word = para.textContent.match(/[a-z]{6,}/i)[0];
  q.value = word; q.dispatchEvent(new Event('input', {bubbles: true})); await wait(400);
  const hit = [...d.querySelectorAll('.pk-panel .pk-rlist a')].find(a => {
    const t = d.getElementById((a.getAttribute('href') || '').slice(1)); return t && p.contains(t); });
  if (hit) { hit.click(); await wait(500); }
  const ok = !!hit && !p.hidden && p.getBoundingClientRect().height > 0;
  q.value = ''; q.dispatchEvent(new Event('input', {bubbles: true})); await wait(150);
  return [word, ok]; }"""


def tab_checks(pg, frame, mode: str) -> list:
    out: list = []
    if not frame.evaluate(TAB_PICK):
        return out
    s = frame.evaluate(TAB_STATE)
    out.append(["tabs show one pane at a time", s["shown"] == [i == 0 for i in range(s["n"])] and s["selected"][0]
                and s["head"] is not False, f"{sum(s['shown'])} of {s['n']} panes shown"])
    frame.locator('[data-probe-tab="1"]').click()
    pg.wait_for_timeout(200)
    s = frame.evaluate(TAB_STATE)
    out.append(["a tab shows its pane", s["shown"][1] and sum(s["shown"]) == 1 and s["selected"][1],
                f"shown {s['shown']}"])
    pg.keyboard.press("ArrowRight")
    pg.wait_for_timeout(200)
    s = frame.evaluate(TAB_STATE)
    nxt = 2 % s["n"]
    right = s["shown"][nxt] and sum(s["shown"]) == 1 and s["focus"] == nxt
    pg.keyboard.press("Home")
    pg.wait_for_timeout(200)
    s = frame.evaluate(TAB_STATE)
    out.append(["arrow keys and Home move between tabs", right and s["shown"][0] and s["focus"] == 0,
                f"right to tab {nxt + 1}: {right}; Home to tab 1: {s['shown'][0] and s['focus'] == 0}"])
    ident = frame.evaluate(TAB_LINK)
    if ident:
        frame.locator('[data-probe-link="1"]').click()
        out.append(["a link into a pane not shown opens its tab and lands", frame.evaluate(TAB_LANDED, ident),
                    "#" + ident])
    found = frame.evaluate(TAB_SEARCH)
    if found:
        out.append(["search reaches a pane not shown and opens it", found[1], repr(found[0])])
    return out


def engines(p, chromium: str | None, webkit: str | None):
    c = chromium or next(iter(glob.glob(str(CACHE / "chromium_headless_shell-*/*/chrome-headless-shell"))), None)
    w = webkit or next(iter(sorted(glob.glob(str(CACHE / "webkit-*/pw_run.sh")))[::-1]), None)
    yield "chromium", p.chromium.launch(executable_path=c) if c else p.chromium.launch()
    yield "webkit", p.webkit.launch(executable_path=w) if w else p.webkit.launch()


def run(page_path: Path, shots: Path | None, chromium: str | None, webkit: str | None) -> list[dict]:
    html = page_path.read_text(encoding="utf-8")
    results = []
    with sync_playwright() as p:
        for name, browser in engines(p, chromium, webkit):
            for width, height in ((1440, 900), (390, 844)):
                for mode in ("direct", "sandboxed", "viewer", "srcdoc"):
                    ctx = browser.new_context(viewport={"width": width, "height": height})
                    pg = ctx.new_page()
                    errors: list[str] = []
                    pg.on("pageerror", lambda e, errs=errors: errs.append(str(e)))
                    pg.on("console", lambda m, errs=errors: errs.append(m.text) if m.type == "error" else None)
                    if mode == "direct":
                        pg.goto(page_path.resolve().as_uri())
                        frame = pg.main_frame
                    else:
                        doc = html.replace("<head>", "<head>" + HIJACK, 1) if mode == "viewer" else html
                        pg.set_content(HOST.replace("@SANDBOX@", SANDBOX)
                                       .replace("@SRCDOC@", "true" if mode == "srcdoc" else "false")
                                       .replace("@PAGE@", json.dumps(doc).replace("</", "<\\/")))
                        pg.wait_for_timeout(800)
                        frame = pg.frames[1]
                    frame.wait_for_load_state()
                    pg.wait_for_timeout(500)
                    if shots:
                        pg.screenshot(path=str(shots / f"{page_path.stem}-{name}-{width}-{mode}.png"))
                    try:
                        checks = frame.evaluate(CHECKS)
                    except Exception as e:  # the page navigated away or broke mid-check
                        checks = [["the page's checks ran to the end", False, str(e).splitlines()[0][:160]]]
                    try:
                        checks += link_checks(pg, frame, mode)
                    except Exception as e:
                        checks.append(["section links", False, str(e).splitlines()[0][:160]])
                    try:
                        checks += source_checks(pg, frame, mode)
                    except Exception as e:
                        checks.append(["citing a source", False, str(e).splitlines()[0][:160]])
                    try:
                        checks += tools_checks(pg, frame, mode)
                    except Exception as e:
                        checks.append(["filtering and sorting a table", False, str(e).splitlines()[0][:160]])
                    try:
                        checks += tab_checks(pg, frame, mode)
                    except Exception as e:
                        checks.append(["tabs within a section", False, str(e).splitlines()[0][:160]])
                    try:
                        checks += block_checks(pg, frame, mode)
                    except Exception as e:
                        checks.append(["copying a block", False, str(e).splitlines()[0][:160]])
                    try:
                        checks += copy_checks(pg, frame, mode)
                    except Exception as e:  # a missing control or a refused download is a failure, not a crash
                        checks.append(["copying out", False, str(e).splitlines()[0][:160]])
                    if mode == "direct" and width == 1440:
                        pg.emulate_media(media="print")
                        pr = frame.evaluate(PRINT_CHECK)
                        checks.append(["print shows every part, pane, row and chart in full", all(pr), f"{sum(pr)} of {len(pr)}"])
                        pg.emulate_media(media="screen")
                        still = browser.new_context(viewport={"width": width, "height": height}, reduced_motion="reduce")
                        sp = still.new_page()
                        sp.goto(page_path.resolve().as_uri())
                        n = sp.evaluate("document.querySelectorAll('.pk-mo').length")
                        checks.append(["no motion when the reader asks for less", n == 0, f"{n} moving"])
                        still.close()
                    if shots and width == 1440 and mode == "direct":
                        pg.evaluate("window.scrollTo(0,0)")
                        frame.evaluate("document.documentElement.setAttribute('data-theme','dark')")
                        pg.screenshot(path=str(shots / f"{page_path.stem}-{name}-{width}-dark.png"))
                    results.append({"engine": name, "version": browser.version, "width": width,
                                    "mode": mode, "errors": errors, "checks": checks})
                    ctx.close()
            browser.close()
    return results


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", type=Path, nargs="+")
    ap.add_argument("--shots", type=Path)
    ap.add_argument("--chromium")
    ap.add_argument("--webkit")
    ap.add_argument("--json", type=Path, help="write the full results here")
    a = ap.parse_args()
    if a.shots:
        a.shots.mkdir(parents=True, exist_ok=True)
    bad = 0
    every = {}
    for pth in a.pages:
        res = run(pth, a.shots, a.chromium, a.webkit)
        every[str(pth)] = res
        for r in res:
            fails = [c for c in r["checks"] if not c[1]]
            bad += len(fails) + len(r["errors"])
            mark = "PASS" if not fails and not r["errors"] else "FAIL"
            print(f"{mark} {pth.name} · {r['engine']} {r['version']} · {r['width']}px · {r['mode']}"
                  f" · {len(r['checks']) - len(fails)}/{len(r['checks'])} checks")
            for c in fails:
                print(f"     ✗ {c[0]}: {c[2]}")
            for e in r["errors"][:5]:
                print(f"     ! script error: {e[:200]}")
    if a.json:
        a.json.write_text(json.dumps(every, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
