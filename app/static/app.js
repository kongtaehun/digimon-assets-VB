'use strict';

// ── State ───────────────────────────────────────────────────────────
const S = {
  categories:   [],
  cat:          null,   // selected category id
  dimMeta:      null,   // selected dim ref (from index)
  dimData:      null,   // full dim.json
  assetBase:    '',     // e.g. /assets/data/v/gamma
  monMap:       {},     // id -> digimon (for current dim)
  mon:          null,   // selected digimon
  view:         'tree',
  disabledDims: {},     // { [catId]: Set<dimId> }
};

// ── Stage metadata ──────────────────────────────────────────────────
const STAGE_META = {
  I:   { label: 'Stage I  ·  Baby I',    cls: 's-I',   colorCls: 'stage-i-color'   },
  II:  { label: 'Stage II  ·  Baby II',  cls: 's-II',  colorCls: 'stage-ii-color'  },
  III: { label: 'Stage III  ·  Child',   cls: 's-III', colorCls: 'stage-iii-color' },
  IV:  { label: 'Stage IV  ·  Adult',    cls: 's-IV',  colorCls: 'stage-iv-color'  },
  V:   { label: 'Stage V  ·  Perfect',   cls: 's-V',   colorCls: 'stage-v-color'   },
  VI:  { label: 'Stage VI  ·  Ultimate', cls: 's-VI',  colorCls: 'stage-vi-color'  },
};
const STAGE_ORDER = ['I','II','III','IV','V','VI'];

// ── Sprite animation ────────────────────────────────────────────────
const _ivs = new Map();
function animateSprite(img, u1, u2, ms = 600) {
  stopSprite(img);
  img.src = u1;
  if (!u2) return;
  let f = 1;
  _ivs.set(img, setInterval(() => { f = f === 1 ? 2 : 1; img.src = f === 1 ? u1 : u2; }, ms));
}
function stopSprite(img) { if (_ivs.has(img)) { clearInterval(_ivs.get(img)); _ivs.delete(img); } }
function stopAllSprites() { _ivs.forEach(clearInterval); _ivs.clear(); }

// ── Asset path helper (relative → absolute) ─────────────────────────
const asset = rel => (rel ? `${S.assetBase}/${rel}` : '');

// ── Misc helpers ────────────────────────────────────────────────────
function attrClass(a) {
  return { Vaccine: 'attr-vaccine', Virus: 'attr-virus', Data: 'attr-data', Free: 'attr-free' }[a] || '';
}
function reqText(c) {
  if (!c) return '조건 없음';
  if (c.text !== undefined) {                       // free-text condition (from details.json)
    const t = (c.text || '').replace(/•/g, ' · ').replace(/\s+/g, ' ').replace(/^[·\s]+/, '').trim();
    return (!t || /^no requirements$/i.test(t)) ? '조건 없음' : t;
  }
  const parts = Object.entries(c).filter(([, v]) => v && v !== 'N/A').map(([k, v]) => `${v} ${k}`);
  return parts.length ? parts.join(' · ') : '조건 없음';
}

// ── API ─────────────────────────────────────────────────────────────
const api = {
  index: ()        => fetch('/api/index').then(r => r.json()),
  dim:   (cat, id) => fetch(`/api/dim/${cat}/${id}`).then(r => r.json()),
};

// ── DIM filter / persistence ─────────────────────────────────────────
function getDisabled(cat) { return (S.disabledDims[cat] ||= new Set()); }
function isEnabled(cat, id) { return !getDisabled(cat).has(id); }
function enabledDims(cat) {
  const c = S.categories.find(x => x.id === cat);
  return c ? c.dims.filter(d => isEnabled(cat, d.id)) : [];
}
function hasFilter(cat) { return getDisabled(cat).size > 0; }
function saveFilter(cat) {
  try { localStorage.setItem(`dgm-filter-${cat}`, JSON.stringify([...getDisabled(cat)])); } catch {}
}
function loadFilter(cat) {
  try { const r = localStorage.getItem(`dgm-filter-${cat}`); if (r) S.disabledDims[cat] = new Set(JSON.parse(r)); } catch {}
}
function toggleDim(cat, id) {
  const dis = getDisabled(cat);
  const c = S.categories.find(x => x.id === cat);
  if (!c) return;
  if (dis.has(id)) {
    dis.delete(id);
  } else {
    if (c.dims.filter(d => !dis.has(d.id)).length <= 1) return;  // keep ≥1
    dis.add(id);
    if (S.dimMeta?.id === id) {
      S.dimMeta = c.dims.find(d => !dis.has(d.id)) || null;
      saveFilter(cat); renderHeader(); closeSheet(); loadDim(); return;
    }
  }
  saveFilter(cat); renderHeader(); renderSheet();
}

// ── Render: header ──────────────────────────────────────────────────
function renderHeader() {
  document.getElementById('cat-nav').innerHTML = S.categories.map(c =>
    `<button class="cat-btn${c.id === S.cat ? ' active' : ''}" data-cat="${c.id}">${c.label}</button>`
  ).join('');

  const cat = S.categories.find(c => c.id === S.cat);
  if (!cat) { document.getElementById('dim-bar').innerHTML = ''; return; }

  const chips = enabledDims(S.cat).map(d =>
    `<button class="dim-chip${d.id === S.dimMeta?.id ? ' active' : ''}" data-dim="${d.id}">
      <img src="${d.digitama}" alt="" onerror="this.style.display='none'">${d.name}
    </button>`
  ).join('');

  document.getElementById('dim-bar').innerHTML =
    chips + `<button class="dim-filter-btn${hasFilter(S.cat) ? ' filtered' : ''}" id="dim-filter-btn">⚙</button>`;
}

// ── Render: tree view ───────────────────────────────────────────────
let _resizeObs = null;
function renderTree() {
  const el = document.getElementById('view-tree');
  stopAllSprites();

  if (!S.dimData) { el.innerHTML = '<div class="loading"></div>'; return; }

  const byStage = {};
  for (const d of S.dimData.digimon) (byStage[d.stage] ||= []).push(d);
  const stages = STAGE_ORDER.filter(s => byStage[s]);

  let html = '<div class="tree-wrapper" id="tree-wrap">'
    + '<svg class="tree-svg" id="tree-svg" xmlns="http://www.w3.org/2000/svg"></svg>';
  for (const stage of stages) {
    const meta = STAGE_META[stage] || { label: `Stage ${stage}`, cls: '' };
    html += `<div class="stage-block ${meta.cls}">
      <div class="stage-label">${meta.label}</div><div class="stage-row">`;
    for (const d of byStage[stage]) {
      const f1 = asset(d.sprites?.frame1), f2 = asset(d.sprites?.frame2);
      html += `<div class="digi-card${S.mon?.id === d.id ? ' selected' : ''}"
        data-id="${d.id}" data-f1="${f1}" data-f2="${f2}">
        <img class="digi-sprite" src="${f1}" alt="${d.name}" loading="lazy">
        <div class="digi-name">${d.name}</div></div>`;
    }
    html += `</div></div>`;
  }
  html += '</div>';
  el.innerHTML = html;

  el.querySelectorAll('.digi-card').forEach(card =>
    animateSprite(card.querySelector('.digi-sprite'), card.dataset.f1, card.dataset.f2));

  requestAnimationFrame(() => { drawConnections(); setTimeout(drawConnections, 400); });

  _resizeObs?.disconnect();
  const wrap = document.getElementById('tree-wrap');
  if (wrap) { _resizeObs = new ResizeObserver(drawConnections); _resizeObs.observe(wrap); }
}

// ── SVG tree connections ─────────────────────────────────────────────
function drawConnections() {
  const wrap = document.getElementById('tree-wrap');
  const svg  = document.getElementById('tree-svg');
  if (!wrap || !svg || !S.dimData) return;
  const edges = S.dimData.evolutions;
  if (!edges?.length) return;

  const cards = {};
  wrap.querySelectorAll('.digi-card').forEach(c => { cards[c.dataset.id] = c; });

  const wr = wrap.getBoundingClientRect();
  const W = Math.max(wrap.scrollWidth, wrap.clientWidth), H = wrap.scrollHeight;
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.style.width = `${W}px`; svg.style.height = `${H}px`;

  let m = '';
  for (const e of edges) {
    const a = cards[e.from], b = cards[e.to];
    if (!a || !b) continue;
    const ar = a.getBoundingClientRect(), br = b.getBoundingClientRect();
    // getBoundingClientRect already reflects scroll → just subtract wrapper origin
    const x1 = ar.left - wr.left + ar.width / 2, y1 = ar.top - wr.top + ar.height;
    const x2 = br.left - wr.left + br.width / 2, y2 = br.top - wr.top;
    const midY = (y1 + y2) / 2;
    const on = S.mon && (e.from === S.mon.id || e.to === S.mon.id);
    const col = on ? '#4a9eff' : 'rgba(255,255,255,0.09)', w = on ? 2 : 1;
    m += `<path d="M${x1},${y1} C${x1},${midY} ${x2},${midY} ${x2},${y2}" fill="none" stroke="${col}" stroke-width="${w}"/>`;
    if (on) m += `<polygon points="${x2},${y2} ${x2-4},${y2-8} ${x2+4},${y2-8}" fill="${col}"/>`;
  }
  svg.innerHTML = m;
}

// ── Render: evolution detail view ───────────────────────────────────
function renderEvo() {
  const el = document.getElementById('view-evo');
  if (!S.mon || !S.dimData) {
    el.innerHTML = `<div class="evo-empty"><div class="evo-empty-icon">🥚</div>
      <div class="evo-empty-text">트리뷰에서 디지몬을 선택하세요</div></div>`;
    return;
  }

  const d = S.mon;
  const edges = S.dimData.evolutions || [];
  const from = edges.filter(e => e.to === d.id);
  const to   = edges.filter(e => e.from === d.id);
  const meta = STAGE_META[d.stage] || {};

  const f1 = asset(d.sprites?.frame1), f2 = asset(d.sprites?.frame2), art = asset(d.artwork);
  const nameOf = id => S.monMap[id]?.name || id;
  const sprOf  = id => asset(S.monMap[id]?.sprites?.frame1);

  const evoItem = (id, conds) => `<div class="evo-item" data-id="${id}">
      ${sprOf(id) ? `<img class="evo-item-sprite" src="${sprOf(id)}" alt="${nameOf(id)}" loading="lazy">` : ''}
      <div class="evo-item-body">
        <div class="evo-item-name">${nameOf(id)}</div>
        <div class="evo-item-cond">${reqText(conds)}</div>
      </div></div>`;

  const fromHtml = from.length ? from.map(e => evoItem(e.from, e.conditions)).join('')
    : '<div class="evo-none">없음 (시작 디지몬)</div>';
  const toHtml = to.length ? to.map(e => evoItem(e.to, e.conditions)).join('')
    : '<div class="evo-none">없음 (최종 진화)</div>';

  const sc = d.schedule || {};
  const hasSc = sc.awake_hours || sc.critical_hit;
  const displayName = d.name_ko ? `${d.name} <span style="font-size:13px;color:var(--muted)">${d.name_ko}</span>` : d.name;

  el.innerHTML = `<div class="evo-card">
    <div class="evo-artwork">
      <img src="${art}" alt="${d.name}"
        onerror="this.outerHTML='<div class=evo-artwork-missing>아트워크 없음</div>'">
    </div>
    <div class="evo-header">
      <div class="evo-sprite-box"><img id="evo-sprite" class="evo-sprite" src="${f1}" alt="${d.name}"></div>
      <div class="evo-title">
        <div class="evo-name">${displayName}</div>
        <div class="evo-meta">
          <span class="badge ${meta.colorCls || ''}">${d.stage_text || `Stage ${d.stage}`}</span>
          ${d.attribute ? `<span class="badge ${attrClass(d.attribute)}">${d.attribute}</span>` : ''}
          ${d.activity ? `<span class="badge">${d.activity}</span>` : ''}
        </div>
      </div>
    </div>
    <div class="evo-stats">
      <div class="stat-box"><div class="stat-label">DP</div><div class="stat-val stage-iv-color">${d.stats?.dp || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">HP</div><div class="stat-val attr-virus">${d.stats?.hp || '—'}</div></div>
      <div class="stat-box"><div class="stat-label">AP</div><div class="stat-val attr-vaccine">${d.stats?.ap || '—'}</div></div>
    </div>
    ${hasSc ? `<div class="evo-schedule">
      ${sc.awake_hours ? `<div class="sched-item"><div class="sched-key">활동 시간</div><div class="sched-val">${sc.awake_hours}</div></div>` : ''}
      ${sc.critical_hit ? `<div class="sched-item"><div class="sched-key">크리티컬</div><div class="sched-val">${sc.critical_hit}</div></div>` : ''}
    </div>` : ''}
    <div class="evo-section"><div class="section-title">진화 전 (Evolves From)</div>${fromHtml}</div>
    <div class="evo-section"><div class="section-title">진화 후 (Evolves To)</div>${toHtml}</div>
    ${d.lore?.ko ? `<div class="evo-lore"><div class="section-title">도감 설명</div><div class="lore-body">${d.lore.ko}</div></div>` : ''}
    ${d.lore?.en ? `<div class="evo-lore"><div class="section-title">Profile (EN)</div><div class="lore-body">${d.lore.en}</div></div>` : ''}
  </div>`;

  const sp = document.getElementById('evo-sprite');
  if (sp) animateSprite(sp, f1, f2);
}

// ── DIM selector sheet ──────────────────────────────────────────────
function openSheet() {
  renderSheet();
  document.getElementById('dim-sheet').classList.remove('hidden');
  document.getElementById('sheet-overlay').classList.remove('hidden');
}
function closeSheet() {
  document.getElementById('dim-sheet').classList.add('hidden');
  document.getElementById('sheet-overlay').classList.add('hidden');
}
function renderSheet() {
  const cat = S.categories.find(c => c.id === S.cat);
  if (!cat) return;
  const dis = getDisabled(S.cat);
  const enabledCnt = cat.dims.length - dis.size;
  document.getElementById('sheet-subtitle').textContent =
    `${cat.label} · ${enabledCnt} / ${cat.dims.length} 개 활성화`;
  document.getElementById('sheet-list').innerHTML = cat.dims.map(d => {
    const on = !dis.has(d.id), last = enabledCnt <= 1 && on, cur = S.dimMeta?.id === d.id;
    return `<div class="sheet-item${on ? '' : ' off'}" data-dim-toggle="${d.id}" style="${last ? 'opacity:0.5' : ''}">
      <img class="sheet-item-sprite" src="${d.digitama}" alt="" onerror="this.style.display='none'">
      <div class="sheet-item-name">${d.name}${cur ? ' <span style="color:var(--blue);font-size:10px">▶ 현재</span>' : ''}
        <span style="font-size:10px;color:var(--muted)"> · ${d.digimon_count}마리</span></div>
      <div class="toggle${on ? ' on' : ''}"></div>
    </div>`;
  }).join('');
}

// ── Load DIM data ───────────────────────────────────────────────────
async function loadDim() {
  if (!S.dimMeta || !S.cat) return;
  const sp = document.getElementById('evo-sprite');
  if (sp) stopSprite(sp);

  S.dimData = null; S.mon = null; S.monMap = {};
  renderTree(); renderEvo();

  const data = await api.dim(S.cat, S.dimMeta.id);
  S.dimData = data;
  S.assetBase = data.asset_base || '';
  S.monMap = Object.fromEntries(data.digimon.map(m => [m.id, m]));
  renderTree(); renderEvo();
}

// ── View switch ─────────────────────────────────────────────────────
function switchView(v) {
  S.view = v;
  document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById(`view-${v}`)?.classList.add('active');
  document.querySelector(`.tab[data-tab="${v}"]`)?.classList.add('active');
}

// ── Events ──────────────────────────────────────────────────────────
function setupEvents() {
  document.getElementById('cat-nav').addEventListener('click', e => {
    const b = e.target.closest('.cat-btn');
    if (!b || b.dataset.cat === S.cat) return;
    S.cat = b.dataset.cat; loadFilter(S.cat);
    const c = S.categories.find(x => x.id === S.cat);
    S.dimMeta = enabledDims(S.cat)[0] || c?.dims[0] || null;
    renderHeader(); loadDim();
  });

  document.getElementById('dim-bar').addEventListener('click', e => {
    if (e.target.closest('#dim-filter-btn')) { openSheet(); return; }
    const chip = e.target.closest('.dim-chip');
    if (!chip || chip.dataset.dim === S.dimMeta?.id) return;
    const c = S.categories.find(x => x.id === S.cat);
    S.dimMeta = c?.dims.find(d => d.id === chip.dataset.dim) || null;
    renderHeader(); loadDim();
  });

  document.getElementById('view-tree').addEventListener('click', e => {
    const card = e.target.closest('.digi-card');
    if (!card) return;
    const mon = S.monMap[card.dataset.id];
    if (!mon) return;
    S.mon = mon; renderTree(); renderEvo(); switchView('evo');
  });

  document.getElementById('view-evo').addEventListener('click', e => {
    const item = e.target.closest('.evo-item');
    if (!item) return;
    const mon = S.monMap[item.dataset.id];
    if (!mon) return;
    S.mon = mon; renderTree(); renderEvo();
  });

  document.getElementById('tab-bar').addEventListener('click', e => {
    const b = e.target.closest('.tab');
    if (b) switchView(b.dataset.tab);
  });

  document.getElementById('sheet-overlay').addEventListener('click', closeSheet);
  document.getElementById('sheet-close').addEventListener('click', closeSheet);
  document.getElementById('sheet-list').addEventListener('click', e => {
    const row = e.target.closest('[data-dim-toggle]');
    if (row) toggleDim(S.cat, row.dataset.dimToggle);
  });

  document.getElementById('view-tree').addEventListener('scroll', drawConnections, { passive: true });
  window.addEventListener('resize', () => requestAnimationFrame(drawConnections));
}

// ── Bootstrap ───────────────────────────────────────────────────────
async function init() {
  setupEvents();
  const idx = await api.index();
  S.categories = idx.categories;
  if (S.categories.length) {
    S.cat = S.categories[0].id; loadFilter(S.cat);
    S.dimMeta = enabledDims(S.cat)[0] || S.categories[0].dims[0] || null;
  }
  renderHeader();
  await loadDim();
}
document.addEventListener('DOMContentLoaded', init);
