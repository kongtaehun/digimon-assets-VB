"""Entry point for reading the Digimon asset package."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from .models import Category, Dim, DimRef


def _find_root(start: Optional[Path]) -> Path:
    """Locate the asset package root (the folder holding index.json)."""
    if start:
        p = Path(start).resolve()
        if (p / "index.json").exists():
            return p
        if (p / "assets" / "index.json").exists():
            return p / "assets"
        raise FileNotFoundError(f"index.json not found under {p}")
    # auto-detect: walk up from this file looking for an `assets/index.json`
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "index.json").exists():
            return parent
        if (parent / "assets" / "index.json").exists():
            return parent / "assets"
    raise FileNotFoundError("Could not auto-detect the asset package root")


class DigimonDB:
    """Read-only access to the Digimon asset package.

    >>> db = DigimonDB("assets")
    >>> [c.id for c in db.categories()]
    ['v', 'vol', ...]
    >>> dim = db.load_dim("v", "gamma")
    >>> dim.roots()[0].name
    'Curimon'
    >>> [m.name for m in dim.next("gamma")]
    ['Betel Gammamon', 'Kaus Gammamon', ...]
    """

    def __init__(self, root: Optional[str] = None):
        self.root = _find_root(Path(root) if root else None)
        self._index = json.loads((self.root / "index.json").read_text())

    # ── index ──
    @property
    def totals(self) -> Dict[str, int]:
        return self._index.get("totals", {})

    def categories(self) -> List[Category]:
        out = []
        for c in self._index["categories"]:
            dims = [DimRef(d["id"], d["name"], c["id"], d["digimon_count"], d["path"])
                    for d in c["dims"]]
            out.append(Category(c["id"], c["label"], c.get("device", ""),
                                c.get("source_url", ""), dims))
        return out

    def category(self, category_id: str) -> Optional[Category]:
        return next((c for c in self.categories() if c.id == category_id), None)

    def dims(self, category_id: Optional[str] = None) -> List[DimRef]:
        out: List[DimRef] = []
        for c in self._index["categories"]:
            if category_id and c["id"] != category_id:
                continue
            for d in c["dims"]:
                out.append(DimRef(d["id"], d["name"], c["id"], d["digimon_count"], d["path"]))
        return out

    # ── dim loading (cached) ──
    @lru_cache(maxsize=None)
    def load_dim(self, category_id: str, dim_id: str) -> Dim:
        base = self.root / "data" / category_id / dim_id
        dim_json = base / "dim.json"
        if not dim_json.exists():
            raise FileNotFoundError(f"DIM not found: {category_id}/{dim_id}")
        return Dim.from_json(json.loads(dim_json.read_text()), base)

    def iter_dims(self):
        """Yield every fully-loaded Dim in the package."""
        for ref in self.dims():
            yield self.load_dim(ref.category, ref.id)

    # ── convenience search across all dims ──
    def find_digimon(self, name_or_id: str):
        """Return [(Dim, Digimon)] for every appearance matching name or id."""
        q = name_or_id.lower()
        hits = []
        for dim in self.iter_dims():
            for m in dim.digimon:
                if m.id.lower() == q or q in m.name.lower():
                    hits.append((dim, m))
        return hits
