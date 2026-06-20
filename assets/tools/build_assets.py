#!/usr/bin/env python3
"""
Build the game-ready Digimon asset package from the raw scrape.

Reads the raw per-DIM scrape (produced by parse.py / fetch_lore.py) and emits a
clean, self-contained, DIM-centric dataset:

    <out>/
    ├── index.json                         ← manifest of every category + DIM
    ├── schema/                            ← JSON Schema for index.json and dim.json
    └── data/<category>/<dim_id>/
        ├── dim.json                       ← one self-contained card (digimon + evolutions + lore)
        ├── digitama.gif
        └── sprites/<digimon_id>/
            ├── frame1.gif
            ├── frame2.gif
            └── artwork.jpg

Each DIM is independent. The same digimon appearing in several DIMs is stored once
per DIM (duplicate appearances are intentionally NOT de-duplicated) so that a DIM
folder is a complete, copy-pasteable unit for a game.

Usage:
    python3 build_assets.py --raw ../../digimon_assets --out ..
    python3 build_assets.py                 # defaults: --raw ./raw  --out ..
"""

import argparse
import json
import re
import shutil
from datetime import date
from pathlib import Path

# category id -> (human label, device family)
CATEGORIES = {
    "v":               ("DIM V",        "VBDM"),
    "vol":             ("DIM Vol.",     "VBDM"),
    "bundled":         ("DIM Bundled",  "VBDM"),
    "ex":              ("DIM EX",       "VBDM"),
    "other":           ("DIM Other",    "VBDM"),
    "anime":           ("BE Anime",     "VBBE"),
    "special_edition": ("BE Special",   "VBBE"),
    "seekers":         ("BE Seekers",   "VBBE"),
}

SCHEMA_VERSION = "1.0"


def folder_name(name: str) -> str:
    # Must match parse.py's safe_name() so we resolve the raw scrape folders.
    # Names like "Imperialdramon: Fighter Mode" become "Imperialdramon_Fighter_Mode"
    # (colon + space collapse to a single "_"); plain "_" would miss their assets.
    name = re.sub(r'[<>:"/\\|?*\s]+', "_", name)
    return name.strip("._") or "_"


def copy_if(src: Path, dst: Path) -> bool:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    return False


def load_details(raw_cat: Path, dim_folder: str, stage: str, mon_name: str) -> dict:
    p = raw_cat / dim_folder / f"Stage_{stage}" / folder_name(mon_name) / "details.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def build_dim(cat_id, raw_cat, dim_meta, lore_en, lore_ko, out_data):
    dim_folder = folder_name(dim_meta["name"])
    dim_json_path = raw_cat / dim_folder / f"{dim_folder}.json"
    if not dim_json_path.exists():
        return None

    raw = json.loads(dim_json_path.read_text())
    dim_id = raw["id"]
    out_dir = out_data / cat_id / dim_id
    sprites_dir = out_dir / "sprites"
    out_dir.mkdir(parents=True, exist_ok=True)

    # digitama
    copy_if(raw_cat / dim_folder / "digitama.gif", out_dir / "digitama.gif")

    member_ids = {m["id"] for m in raw["digimon"]}

    # Evolution edges keyed by (from, to). Structured edges from the dim's
    # top-level `evolution_edges` take priority; we then supplement with the
    # per-digimon `details.json` graph (evolves_from / evolves_to), which is the
    # only source for EX cards and also adds the implicit baby-stage edges.
    edge_map = {}
    for e in raw.get("evolution_edges", []):
        edge_map[(e["from"], e["to"])] = e.get("requirements") or {}

    digimon = []
    for mon in raw["digimon"]:
        mon_id = mon["id"]
        stage = mon["stage"]
        details_full = load_details(raw_cat, dim_folder, stage, mon["name"])
        details = details_full.get("details", {})

        # supplement evolution edges from this digimon's detail card (id-based,
        # intra-DIM only; cross-DIM targets are skipped)
        for t in details.get("evolves_to", []):
            tid = t.get("id")
            if tid in member_ids and (mon_id, tid) not in edge_map:
                edge_map[(mon_id, tid)] = {"text": t.get("conditions", "")}
        for t in details.get("evolves_from", []):
            sid = t.get("id")
            if sid in member_ids and (sid, mon_id) not in edge_map:
                edge_map[(sid, mon_id)] = {"text": t.get("conditions", "")}

        # copy sprite assets into sprites/<id>/
        sd_src = raw_cat / dim_folder / f"Stage_{stage}" / folder_name(mon["name"])
        sd_dst = sprites_dir / mon_id
        has_f1 = copy_if(sd_src / "frame1.gif", sd_dst / "frame1.gif")
        has_f2 = copy_if(sd_src / "frame2.gif", sd_dst / "frame2.gif")
        has_art = copy_if(sd_src / "artwork.jpg", sd_dst / "artwork.jpg")

        le = lore_en.get(mon_id, {})
        lk = lore_ko.get(mon_id, {})

        digimon.append({
            "id": mon_id,
            "name": mon["name"],
            "name_jp": details.get("name_jp") or "",
            "name_ko": lk.get("name_ko") or "",
            "stage": stage,
            "stage_text": mon.get("stage_text") or details.get("stage_text") or "",
            "attribute": mon.get("attribute") or details.get("attribute") or "",
            "activity": mon.get("activity") or details.get("activity") or "",
            "stats": mon.get("stats") or details.get("stats") or {},
            "schedule": details.get("schedule") or {},
            "sprites": {
                "frame1": f"sprites/{mon_id}/frame1.gif" if has_f1 else "",
                "frame2": f"sprites/{mon_id}/frame2.gif" if has_f2 else "",
            },
            "artwork": f"sprites/{mon_id}/artwork.jpg" if has_art else "",
            "lore": {
                "en": le.get("profile_en") or "",
                "ko": lk.get("profile_ko") or "",
            },
            "wikimon_url": le.get("wikimon_url") or "",
        })

    evolutions = [
        {"from": a, "to": b, "conditions": conds}
        for (a, b), conds in edge_map.items()
    ]

    stages = sorted({m["stage"] for m in digimon},
                    key=lambda s: ["I", "II", "III", "IV", "V", "VI"].index(s)
                    if s in ["I", "II", "III", "IV", "V", "VI"] else 99)

    dim_out = {
        "schema_version": SCHEMA_VERSION,
        "id": dim_id,
        "name": dim_meta["name"],
        "category": cat_id,
        "device": CATEGORIES[cat_id][1],
        "release": dim_meta.get("release") or "",
        "emblem_url": dim_meta.get("emblem_url") or "",
        "digitama": "digitama.gif",
        "stages": stages,
        "digimon": digimon,
        "evolutions": evolutions,
    }
    (out_dir / "dim.json").write_text(
        json.dumps(dim_out, ensure_ascii=False, indent=2)
    )

    return {
        "id": dim_id,
        "name": dim_meta["name"],
        "digimon_count": len(digimon),
        "evolution_count": len(evolutions),
        "path": f"data/{cat_id}/{dim_id}",
    }


def write_schemas(schema_dir: Path):
    schema_dir.mkdir(parents=True, exist_ok=True)

    dim_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Digimon DIM",
        "type": "object",
        "required": ["id", "name", "category", "digimon", "evolutions"],
        "properties": {
            "schema_version": {"type": "string"},
            "id": {"type": "string"},
            "name": {"type": "string"},
            "category": {"type": "string"},
            "device": {"type": "string", "enum": ["VBDM", "VBBE"]},
            "release": {"type": "string"},
            "emblem_url": {"type": "string"},
            "digitama": {"type": "string", "description": "relative path to digitama gif"},
            "stages": {"type": "array", "items": {"type": "string"}},
            "digimon": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "name", "stage"],
                    "properties": {
                        "id": {"type": "string"},
                        "name": {"type": "string"},
                        "name_jp": {"type": "string"},
                        "name_ko": {"type": "string"},
                        "stage": {"type": "string"},
                        "stage_text": {"type": "string"},
                        "attribute": {"type": "string"},
                        "activity": {"type": "string"},
                        "stats": {"type": "object"},
                        "schedule": {"type": "object"},
                        "sprites": {
                            "type": "object",
                            "properties": {
                                "frame1": {"type": "string"},
                                "frame2": {"type": "string"},
                            },
                        },
                        "artwork": {"type": "string"},
                        "lore": {
                            "type": "object",
                            "properties": {
                                "en": {"type": "string"},
                                "ko": {"type": "string"},
                            },
                        },
                        "wikimon_url": {"type": "string"},
                    },
                },
            },
            "evolutions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["from", "to"],
                    "properties": {
                        "from": {"type": "string"},
                        "to": {"type": "string"},
                        "conditions": {"type": "object"},
                    },
                },
            },
        },
    }

    index_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Digimon Asset Index",
        "type": "object",
        "required": ["schema_version", "categories"],
        "properties": {
            "schema_version": {"type": "string"},
            "generated": {"type": "string"},
            "source": {"type": "string"},
            "totals": {"type": "object"},
            "categories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id", "label", "dims"],
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "device": {"type": "string"},
                        "source_url": {"type": "string"},
                        "dims": {"type": "array"},
                    },
                },
            },
        },
    }

    (schema_dir / "dim.schema.json").write_text(
        json.dumps(dim_schema, ensure_ascii=False, indent=2))
    (schema_dir / "index.schema.json").write_text(
        json.dumps(index_schema, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="./raw", help="raw scrape directory")
    ap.add_argument("--out", default="..", help="output asset package root")
    args = ap.parse_args()

    raw = Path(args.raw).resolve()
    out = Path(args.out).resolve()
    out_data = out / "data"

    lore_en = json.loads((raw / "lore_en.json").read_text()) if (raw / "lore_en.json").exists() else {}
    lore_ko = json.loads((raw / "lore_ko.json").read_text()) if (raw / "lore_ko.json").exists() else {}

    if out_data.exists():
        shutil.rmtree(out_data)
    out_data.mkdir(parents=True, exist_ok=True)

    categories_index = []
    total_dims = total_digimon = 0

    for cat_id, (label, device) in CATEGORIES.items():
        cat_data_path = raw / cat_id / "data.json"
        if not cat_data_path.exists():
            continue
        cat_data = json.loads(cat_data_path.read_text())
        raw_cat = raw / cat_id

        dims_index = []
        for dim_meta in cat_data["dims"]:
            entry = build_dim(cat_id, raw_cat, dim_meta, lore_en, lore_ko, out_data)
            if entry:
                dims_index.append(entry)
                total_dims += 1
                total_digimon += entry["digimon_count"]

        categories_index.append({
            "id": cat_id,
            "label": label,
            "device": device,
            "source_url": cat_data.get("source_url", ""),
            "dim_count": len(dims_index),
            "dims": dims_index,
        })
        print(f"  {cat_id:16s} {len(dims_index):2d} DIMs")

    index = {
        "schema_version": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "source": "https://humulos.com/digimon/",
        "totals": {
            "categories": len(categories_index),
            "dims": total_dims,
            "digimon": total_digimon,
        },
        "categories": categories_index,
    }
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2))
    write_schemas(out / "schema")

    print(f"\n빌드 완료: {len(categories_index)} 카테고리, {total_dims} DIM, {total_digimon} 디지몬")
    print(f"출력: {out}")


if __name__ == "__main__":
    main()
