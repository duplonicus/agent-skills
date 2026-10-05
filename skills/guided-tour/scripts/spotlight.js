// Guided-tour spotlight. Paste into the browser's javascript_tool after replacing
// the two placeholders on the CONFIG line below (each appears exactly once in this file):
//   target  the control's visible text, aria-label, placeholder or title (case-insensitive substring)
//   label   short tag text, usually the stop number ("3") or "3a"
// Set target to the word CLEAR wrapped in double underscores to remove all highlights.
// Purely cosmetic: it only changes outline styles and adds a floating tag. No clicks, no input.
// Returns "ok: <tag> '<text>'", "cleared", or "not found".
(() => {
  const CONFIG = { target: '__TARGET__', label: '__LABEL__' };

  // Gather documents we can reach: the page, same-origin iframes, and open shadow roots.
  const roots = [];
  const addRoot = (r) => {
    if (!r || roots.includes(r)) return;
    roots.push(r);
    r.querySelectorAll('*').forEach((el) => {
      if (el.shadowRoot) addRoot(el.shadowRoot);
      if (el.tagName === 'IFRAME') {
        try { if (el.contentDocument) addRoot(el.contentDocument); } catch (e) { /* cross-origin, skip */ }
      }
    });
  };
  addRoot(document);

  // Clear previous highlights everywhere.
  roots.forEach((r) => {
    r.querySelectorAll('[data-tour-hl]').forEach((e) => {
      e.style.outline = e.dataset.tourHl === '__none__' ? '' : e.dataset.tourHl;
      e.style.outlineOffset = '';
      e.removeAttribute('data-tour-hl');
    });
    r.querySelectorAll('.tour-tag').forEach((e) => e.remove());
  });
  if (CONFIG.target === '__CLEAR__') return 'cleared';

  const want = CONFIG.target.toLowerCase().trim();
  const labelOf = (e) => [
    e.getAttribute && e.getAttribute('aria-label'),
    e.getAttribute && e.getAttribute('title'),
    e.getAttribute && e.getAttribute('placeholder'),
    e.value,
    e.innerText !== undefined ? e.innerText : e.textContent,
  ].filter(Boolean).join(' ').toLowerCase().replace(/\s+/g, ' ');
  const visible = (e) => {
    const r = e.getBoundingClientRect();
    const s = e.ownerDocument.defaultView.getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };
  const interactive = 'a,button,input,select,textarea,summary,[role=button],[role=tab],[role=link],[role=menuitem],[role=treeitem],[role=option],[role=checkbox],[role=combobox],[role=searchbox],[tabindex]';

  let cands = [];
  roots.forEach((r) => r.querySelectorAll(interactive + ',label,th,h1,h2,h3,h4,legend,span,div,li')
    .forEach((e) => { if (visible(e) && labelOf(e).includes(want)) cands.push(e); }));
  if (!cands.length) return 'not found';

  // Prefer interactive controls, then exact matches, then the smallest element.
  const score = (e) => (e.matches(interactive) ? 0 : 1000)
    + (labelOf(e).trim() === want ? 0 : 100)
    + Math.min(labelOf(e).length, 99);
  cands.sort((a, b) => score(a) - score(b));
  const el = cands[0];

  el.dataset.tourHl = el.style.outline || '__none__';
  el.style.outline = '4px solid #e11d48';
  el.style.outlineOffset = '2px';
  el.scrollIntoView({ block: 'center', inline: 'nearest' });

  const doc = el.ownerDocument;
  const r = el.getBoundingClientRect();
  const tag = doc.createElement('div');
  tag.className = 'tour-tag';
  tag.textContent = CONFIG.label;
  Object.assign(tag.style, {
    position: 'fixed', left: Math.max(4, r.left - 16) + 'px', top: Math.max(4, r.top - 16) + 'px',
    zIndex: '2147483647', background: '#e11d48', color: '#fff', font: 'bold 18px/1.2 sans-serif',
    padding: '2px 9px', borderRadius: '12px', pointerEvents: 'none', boxShadow: '0 1px 4px rgba(0,0,0,.4)',
  });
  doc.body.appendChild(tag);
  return 'ok: ' + CONFIG.label + " '" + labelOf(el).slice(0, 60) + "'";
})();
