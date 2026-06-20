"""Data models for the Digimon asset package."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

STAGE_ORDER = ["I", "II", "III", "IV", "V", "VI"]


def stage_rank(stage: str) -> int:
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else 99


@dataclass
class Digimon:
    """A single digimon as it appears inside one DIM."""
    id: str
    name: str
    stage: str
    name_jp: str = ""
    name_ko: str = ""
    stage_text: str = ""
    attribute: str = ""
    activity: str = ""
    stats: Dict[str, str] = field(default_factory=dict)
    schedule: Dict[str, str] = field(default_factory=dict)
    lore_en: str = ""
    lore_ko: str = ""
    wikimon_url: str = ""
    _base: Path = field(default=Path("."), repr=False)
    _sprites: Dict[str, str] = field(default_factory=dict, repr=False)
    _artwork: str = field(default="", repr=False)

    # ── asset paths (absolute, resolved against the DIM folder) ──
    @property
    def frame1_path(self) -> Optional[Path]:
        rel = self._sprites.get("frame1")
        return self._base / rel if rel else None

    @property
    def frame2_path(self) -> Optional[Path]:
        rel = self._sprites.get("frame2")
        return self._base / rel if rel else None

    @property
    def artwork_path(self) -> Optional[Path]:
        return self._base / self._artwork if self._artwork else None

    @property
    def rank(self) -> int:
        return stage_rank(self.stage)

    @classmethod
    def from_json(cls, d: dict, base: Path) -> "Digimon":
        return cls(
            id=d["id"],
            name=d["name"],
            stage=d.get("stage", ""),
            name_jp=d.get("name_jp", ""),
            name_ko=d.get("name_ko", ""),
            stage_text=d.get("stage_text", ""),
            attribute=d.get("attribute", ""),
            activity=d.get("activity", ""),
            stats=d.get("stats", {}) or {},
            schedule=d.get("schedule", {}) or {},
            lore_en=(d.get("lore") or {}).get("en", ""),
            lore_ko=(d.get("lore") or {}).get("ko", ""),
            wikimon_url=d.get("wikimon_url", ""),
            _base=base,
            _sprites=d.get("sprites", {}) or {},
            _artwork=d.get("artwork", "") or "",
        )


@dataclass
class Evolution:
    """A directed evolution edge with its in-game requirements."""
    src: str
    dst: str
    conditions: Dict[str, str] = field(default_factory=dict)

    def condition_text(self) -> str:
        c = self.conditions
        if "text" in c:                       # free-text condition (from details.json)
            t = " ".join(c["text"].replace("•", " · ").split()).lstrip("· ").strip()
            return "" if (not t or t.lower() == "no requirements") else t
        parts = [f"{v} {k}" for k, v in c.items() if v and v != "N/A"]
        return " · ".join(parts) if parts else "조건 없음"


@dataclass
class Dim:
    """One DIM card: a self-contained evolution chart."""
    id: str
    name: str
    category: str
    device: str
    release: str
    emblem_url: str
    base: Path
    digimon: List[Digimon]
    evolutions: List[Evolution]
    stages: List[str] = field(default_factory=list)

    def __post_init__(self):
        self._by_id = {m.id: m for m in self.digimon}

    # ── lookup ──
    def get(self, digimon_id: str) -> Optional[Digimon]:
        return self._by_id.get(digimon_id)

    @property
    def digitama_path(self) -> Path:
        return self.base / "digitama.gif"

    def by_stage(self) -> Dict[str, List[Digimon]]:
        out: Dict[str, List[Digimon]] = {}
        for m in sorted(self.digimon, key=lambda x: x.rank):
            out.setdefault(m.stage, []).append(m)
        return out

    # ── graph queries ──
    def evolutions_from(self, digimon_id: str) -> List[Evolution]:
        return [e for e in self.evolutions if e.src == digimon_id]

    def evolutions_to(self, digimon_id: str) -> List[Evolution]:
        return [e for e in self.evolutions if e.dst == digimon_id]

    def next(self, digimon_id: str) -> List[Digimon]:
        return [self._by_id[e.dst] for e in self.evolutions_from(digimon_id)
                if e.dst in self._by_id]

    def prev(self, digimon_id: str) -> List[Digimon]:
        return [self._by_id[e.src] for e in self.evolutions_to(digimon_id)
                if e.src in self._by_id]

    def roots(self) -> List[Digimon]:
        """Digimon with no incoming evolution (chart entry points)."""
        has_parent = {e.dst for e in self.evolutions}
        return [m for m in self.digimon if m.id not in has_parent]

    def leaves(self) -> List[Digimon]:
        """Digimon with no outgoing evolution (final forms)."""
        has_child = {e.src for e in self.evolutions}
        return [m for m in self.digimon if m.id not in has_child]

    def tree(self, root_id: Optional[str] = None) -> List[dict]:
        """Nested evolution tree from a root (or every root)."""
        def build(mid, seen):
            if mid in seen:
                return {"digimon": self._by_id.get(mid), "children": []}
            seen = seen | {mid}
            return {
                "digimon": self._by_id.get(mid),
                "children": [build(e.dst, seen) for e in self.evolutions_from(mid)],
            }
        roots = [self._by_id[root_id]] if root_id else self.roots()
        return [build(r.id, set()) for r in roots]

    def paths(self, src_id: str, dst_id: str) -> List[List[str]]:
        """All evolution paths from src to dst (as id lists)."""
        out: List[List[str]] = []

        def walk(cur, path):
            if cur == dst_id:
                out.append(path)
                return
            for e in self.evolutions_from(cur):
                if e.dst not in path:
                    walk(e.dst, path + [e.dst])

        walk(src_id, [src_id])
        return out

    @classmethod
    def from_json(cls, d: dict, base: Path) -> "Dim":
        return cls(
            id=d["id"],
            name=d["name"],
            category=d.get("category", ""),
            device=d.get("device", ""),
            release=d.get("release", ""),
            emblem_url=d.get("emblem_url", ""),
            base=base,
            stages=d.get("stages", []),
            digimon=[Digimon.from_json(m, base) for m in d.get("digimon", [])],
            evolutions=[Evolution(e["from"], e["to"], e.get("conditions", {}) or {})
                        for e in d.get("evolutions", [])],
        )


@dataclass
class DimRef:
    """Lightweight DIM reference from the index (no digimon loaded)."""
    id: str
    name: str
    category: str
    digimon_count: int
    path: str


@dataclass
class Category:
    id: str
    label: str
    device: str
    source_url: str
    dims: List[DimRef]
