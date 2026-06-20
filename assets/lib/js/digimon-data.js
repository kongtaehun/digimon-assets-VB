/**
 * digimon-data.js — read the Digimon asset package in the browser or Node.
 *
 * Works with any async fetcher that maps a relative path → parsed JSON / URL.
 * In the browser, pass a base URL; in Node, pass a directory + a json loader.
 *
 * Browser:
 *   const db = new DigimonDB({ base: '/assets' });
 *   await db.init();
 *   const dim = await db.loadDim('v', 'gamma');
 *   dim.next('gamma');                 // → [Digimon, ...]
 *   db.assetURL(dim, gamma.sprites.frame1);   // → '/assets/data/v/gamma/sprites/gamma/frame1.gif'
 *
 * Node:
 *   import { DigimonDB } from './digimon-data.js';
 *   const db = new DigimonDB({ base: './assets', fs: true });
 *   await db.init();
 */

const STAGE_ORDER = ['I', 'II', 'III', 'IV', 'V', 'VI'];
const stageRank = (s) => { const i = STAGE_ORDER.indexOf(s); return i < 0 ? 99 : i; };

// ── Dim wrapper with graph helpers ──────────────────────────────────
class Dim {
  constructor(json, assetBase) {
    Object.assign(this, json);          // id, name, category, device, digimon, evolutions, ...
    this._assetBase = assetBase;        // e.g. '/assets/data/v/gamma'
    this._byId = new Map(this.digimon.map((m) => [m.id, m]));
  }

  get(id) { return this._byId.get(id); }

  byStage() {
    const out = new Map();
    [...this.digimon].sort((a, b) => stageRank(a.stage) - stageRank(b.stage))
      .forEach((m) => {
        if (!out.has(m.stage)) out.set(m.stage, []);
        out.get(m.stage).push(m);
      });
    return out;
  }

  evolutionsFrom(id) { return this.evolutions.filter((e) => e.from === id); }
  evolutionsTo(id)   { return this.evolutions.filter((e) => e.to   === id); }

  next(id) { return this.evolutionsFrom(id).map((e) => this._byId.get(e.to)).filter(Boolean); }
  prev(id) { return this.evolutionsTo(id).map((e) => this._byId.get(e.from)).filter(Boolean); }

  roots() {
    const hasParent = new Set(this.evolutions.map((e) => e.to));
    return this.digimon.filter((m) => !hasParent.has(m.id));
  }

  leaves() {
    const hasChild = new Set(this.evolutions.map((e) => e.from));
    return this.digimon.filter((m) => !hasChild.has(m.id));
  }

  tree(rootId) {
    const build = (mid, seen) => {
      if (seen.has(mid)) return { digimon: this._byId.get(mid), children: [] };
      const s = new Set(seen).add(mid);
      return {
        digimon: this._byId.get(mid),
        children: this.evolutionsFrom(mid).map((e) => build(e.to, s)),
      };
    };
    const roots = rootId ? [this._byId.get(rootId)] : this.roots();
    return roots.map((r) => build(r.id, new Set()));
  }

  paths(srcId, dstId) {
    const out = [];
    const walk = (cur, path) => {
      if (cur === dstId) { out.push(path); return; }
      for (const e of this.evolutionsFrom(cur))
        if (!path.includes(e.to)) walk(e.to, [...path, e.to]);
    };
    walk(srcId, [srcId]);
    return out;
  }

  /** Absolute URL/path for a relative asset path inside this DIM. */
  assetURL(rel) {
    if (!rel) return '';
    return `${this._assetBase}/${rel}`;
  }
}

// ── Top-level DB ────────────────────────────────────────────────────
class DigimonDB {
  /**
   * @param {object} opts
   * @param {string} opts.base   Base URL (browser) or directory (Node) of the package.
   * @param {boolean} [opts.fs]  Use Node fs instead of fetch.
   */
  constructor({ base = '/assets', fs = false } = {}) {
    this.base = base.replace(/\/$/, '');
    this._fs = fs;
    this.index = null;
  }

  async _json(relPath) {
    if (this._fs) {
      const { readFile } = await import('node:fs/promises');
      const { join } = await import('node:path');
      return JSON.parse(await readFile(join(this.base, relPath), 'utf8'));
    }
    const r = await fetch(`${this.base}/${relPath}`);
    if (!r.ok) throw new Error(`fetch ${relPath} → ${r.status}`);
    return r.json();
  }

  async init() {
    this.index = await this._json('index.json');
    return this;
  }

  get totals() { return this.index?.totals ?? {}; }
  categories() { return this.index?.categories ?? []; }

  category(id) { return this.categories().find((c) => c.id === id) ?? null; }

  dims(categoryId) {
    const cats = categoryId ? this.categories().filter((c) => c.id === categoryId)
                            : this.categories();
    return cats.flatMap((c) => c.dims.map((d) => ({ ...d, category: c.id })));
  }

  async loadDim(categoryId, dimId) {
    const json = await this._json(`data/${categoryId}/${dimId}/dim.json`);
    return new Dim(json, `${this.base}/data/${categoryId}/${dimId}`);
  }

  /** Convenience: absolute URL for a digimon's sprite/artwork. */
  assetURL(dim, rel) { return dim.assetURL(rel); }
}

// ESM export (use `import`, or `<script type="module">` in the browser).
// Also exposed as a window global for convenience in module scripts.
if (typeof window !== 'undefined') {
  window.DigimonDB = DigimonDB;
  window.DigimonDim = Dim;
}
export { DigimonDB, Dim, STAGE_ORDER, stageRank };
