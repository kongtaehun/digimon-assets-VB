#!/usr/bin/env python3
"""
Digimon VBDM evolution chart parser.

Parses evolution routes, conditions, 2-frame sprites, illustrations,
and per-digimon detail cards from humulos.com/digimon/vbdm/* pages.

Usage:
    python3 parse.py <URL>
    python3 parse.py <URL> --no-images

Examples:
    python3 parse.py https://humulos.com/digimon/vbdm/vol
    python3 parse.py https://humulos.com/digimon/vbdm/v/
    python3 parse.py https://humulos.com/digimon/vbdm/v/ --no-images

Output (folder name = last URL path segment):
    vol/
    ├── data.json
    └── images/
        ├── Volcanic Beat/
        │   ├── Stage I/
        │   │   └── Mokumon/
        │   │       ├── frame1.gif     ← static pixel art
        │   │       ├── frame2.gif     ← second animation frame
        │   │       ├── artwork.jpg    ← illustration
        │   │       └── details.json   ← per-digimon detail card
        │   ├── Stage II/
        │   └── ...
        └── Blizzard Fang/
            └── ...
"""

import argparse
import json
import re
import shutil
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# ── constants ─────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Legacy endpoint (vbdm pages, onClick="digimonDetailsAJAX(...)")
DETAILS_LEGACY  = "https://humulos.com/digimon/vbdm/php/details_ajax.php"
# Unified endpoint (vbbe pages, onClick="digimonDetailsUnified(..., device, version)")
DETAILS_UNIFIED = "https://humulos.com/digimon/php/details.php"

REQUEST_DELAY = 0.25

STAGE_COLUMNS: dict[str, str] = {
    "baby":     "I",
    "babyII":   "II",
    "child":    "III",
    "adult":    "IV",
    "perfect":  "V",
    "ultimate": "VI",
}

# ── helpers ───────────────────────────────────────────────────────────────────

def abs_url(url: str) -> str:
    """Resolve protocol-relative // URLs to https. Returns '' for blank placeholders."""
    if not url or "blank.gif" in url:
        return ""
    return ("https:" + url) if url.startswith("//") else url


def safe_name(name: str) -> str:
    """Strip characters not allowed in directory names on macOS/Windows. Spaces → _."""
    name = re.sub(r'[<>:"/\\|?*\s]+', "_", name)
    return name.strip("._") or "_"


def download(url: str, dest: Path, session: requests.Session,
             cache: dict[str, Path]) -> bool:
    """
    Download url → dest.
    Uses cache to copy locally if the same URL was already downloaded,
    avoiding redundant network requests for digimon shared across dims.
    """
    if not url:
        return False
    if dest.exists():
        return True
    # Reuse a previously downloaded copy if available
    if url in cache and cache[url].exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cache[url], dest)
        return True
    try:
        r = session.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            cache[url] = dest
            return True
        print(f"    [warn] HTTP {r.status_code} — {url}")
    except Exception as exc:
        print(f"    [warn] download failed {url}: {exc}")
    return False


# ── endpoint detection ────────────────────────────────────────────────────────

def detect_endpoint(soup):
    """
    Inspect the first digimon onClick handler to determine which details
    endpoint this page uses.

    Returns (device, version):
      - ("", "")          → legacy endpoint  (digimonDetailsAJAX)
      - ("14", "")        → unified endpoint (digimonDetailsUnified)
    """
    profile = soup.find("div", class_="profile")
    if profile:
        onclick = profile.get("onclick", "")   # BS4 lowercases attribute names
        m = re.search(
            r"digimonDetailsUnified\('([^']+)','([^']+)','([^']*)'\)", onclick
        )
        if m:
            return m.group(2), m.group(3)   # device, version
    return "", ""


# ── evolution requirement parser ──────────────────────────────────────────────

def parse_requirements(req_col) -> list[dict]:
    """
    Parse evolution conditions from a *_Req_column div.

    Returns a list of condition blocks, each with:
        from_digimon: [list of predecessor IDs that trigger this block]
        requirements: {stat → value}  — keys vary by device
            vbdm:  Trophies / Vital Values / Battles / Win Ratio
            vbbe:  PP / Vital Values / Battles / Win Ratio / (Area Cleared)

    Multiple blocks appear when different predecessors have different
    conditions (e.g. Brachiomon). Multiple from_digimon in one block
    means all those predecessors share the same requirements (e.g. Canoweissmon).
    """
    results: list[dict] = []
    if not req_col:
        return results

    for row in req_col.find_all("div", class_="row", recursive=False):
        reqs_div = row.find("div", class_="reqs_vbdm")
        if not reqs_div:
            continue

        reqs: dict[str, str] = {}
        for item in reqs_div.find_all("div", recursive=False):
            title = item.get("title", "")
            p     = item.find("p")
            if title and p:
                reqs[title] = p.get_text(strip=True)
            # vbbe "Stage X Cleared" area requirement (class="vbWide", no title)
            elif "vbWide" in item.get("class", []) and p:
                reqs["Area"] = p.get_text(strip=True)

        # CSS line-marker classes in the inner column encode predecessor IDs:
        # pattern is  {dim}_{prev_digimon}_line
        from_ids: list[str] = []
        line_col = row.find("div", class_="column")
        if line_col:
            for d in line_col.find_all("div"):
                cls_str = " ".join(d.get("class", []))
                if re.search(r"(lineOut|Req_line)", cls_str):
                    continue
                m = re.search(r"\b[a-zA-Z0-9]+_([a-zA-Z0-9]+)_line\b", cls_str)
                if m:
                    from_id = m.group(1)
                    if from_id not in from_ids:
                        from_ids.append(from_id)

        if reqs:
            results.append({"from_digimon": from_ids, "requirements": reqs})

    return results


# ── detail card parser ────────────────────────────────────────────────────────

def parse_details(mon_id: str, session: requests.Session,
                  device: str = "", version: str = "") -> dict:
    """
    Fetch the detail popup card and return structured data.

    Uses the unified endpoint when device is set (vbbe pages),
    otherwise falls back to the legacy vbdm endpoint.

    vbdm stats:  dp (DP: X (★N)), hp, ap  |  schedule: awake_hours, critical_hit
    vbbe stats:  bp (BP: X), hp, ap        |  schedule: activity_type, critical_hit
    """
    try:
        if device:
            r = session.get(
                DETAILS_UNIFIED,
                params={"digimon": mon_id, "device": device, "version": version},
                headers=HEADERS, timeout=15,
            )
        else:
            r = session.get(
                DETAILS_LEGACY,
                params={"digimon": mon_id},
                headers=HEADERS, timeout=15,
            )
        if r.status_code != 200:
            return {}
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception as exc:
        print(f"    [warn] details fetch failed for {mon_id}: {exc}")
        return {}

    details: dict = {}

    if el := soup.find(class_="sub"):
        details["name_jp"] = el.get_text(strip=True)
    if el := soup.find(class_="dub"):
        details["name_en"] = el.get_text(strip=True)

    if baseinfo := soup.find(class_="baseinfo"):
        if attr_el := baseinfo.find("div", {"attribute": True}):
            details["attribute"] = attr_el.get("attribute")
        activity_types = {"Normal", "Stoic", "Active", "Indoor", "Lazy"}
        for d in baseinfo.find_all("div"):
            txt = d.get_text(strip=True)
            if txt.startswith("Stage"):
                details["stage_text"] = txt
            if txt in activity_types:
                details["activity"] = txt

    stats: dict[str, str] = {}
    schedule: dict[str, str] = {}
    for bj in soup.find_all(class_="bj"):
        for d in bj.find_all("div"):
            txt = d.get_text(strip=True)
            # vbdm: DP / vbbe: BP
            for key, prefix in (
                ("dp", "DP:"), ("bp", "BP:"),
                ("hp", "HP:"), ("ap", "AP:"),
            ):
                if txt.startswith(prefix):
                    stats[key] = txt[len(prefix):].strip()
            if "Awake from:" in txt:
                schedule["awake_hours"] = txt.replace("Awake from:", "").strip()
            if "Activity Type:" in txt:
                schedule["activity_type"] = txt.replace("Activity Type:", "").strip()
                if not details.get("activity"):
                    details["activity"] = schedule["activity_type"]
            if "Critical Hit:" in txt:
                schedule["critical_hit"] = txt.replace("Critical Hit:", "").strip()
    if stats:
        details["stats"] = stats
    if schedule:
        details["schedule"] = schedule

    def _evo_list(section_class: str) -> list[dict]:
        section = soup.find(class_=section_class)
        if not section:
            return []
        items = []
        for item in section.find_all(class_="evolutions"):
            mon = item.get("id", "").replace("_clicker", "")
            name_el = item.find(class_="names")
            deets = item.find_next_sibling("p", class_="deets")
            items.append({
                "id": mon,
                "name": name_el.get_text(strip=True) if name_el else "",
                "conditions": deets.get_text(strip=True) if deets else "",
            })
        return items

    details["evolves_from"] = _evo_list("prevo")
    details["evolves_to"]   = _evo_list("evo")

    return details


# ── stage column parser ───────────────────────────────────────────────────────

def parse_column(col, dim_id: str, dim_name: str,
                 stage_roman: str, anchor) -> list[dict]:
    """
    Extract all digimon entries from one stage column div.

    Each entry records which dim + stage it belongs to via `appearances`,
    which drives the hierarchical image folder structure.
    """
    entries: list[dict] = []

    for row in col.find_all("div", class_="row", recursive=False):
        mon_id: str = row.get("id") or ""
        if not mon_id:
            dmon = row.find("div", class_="digimon")
            mon_id = (dmon.get("id") or "") if dmon else ""
        if not mon_id or mon_id in ("blank", "rest"):
            continue

        dmon_div = row.find("div", class_="digimon")
        if not dmon_div:
            continue

        f2  = dmon_div.find("img", class_="frame2")
        f1  = dmon_div.find("img", class_="frame1")
        art = dmon_div.find("img", class_="art")

        name = ""
        frame1_url = ""
        frame2_url = ""
        artwork_url = ""

        if f1:
            name       = f1.get("title") or f1.get("alt") or ""
            frame1_url = abs_url(f1.get("data-src", ""))
        if f2:
            frame2_url = abs_url(f2.get("data-src", ""))
        if art:
            artwork_url = abs_url(art.get("data-src", ""))
            if not name:
                name = art.get("title") or art.get("alt") or ""

        req_col    = anchor.find("div", id=f"{dim_id}_{mon_id}_Req_column")
        conditions = parse_requirements(req_col)

        entries.append({
            "id":          mon_id,
            "name":        name,
            "frame1_url":  frame1_url,
            "frame2_url":  frame2_url,
            "artwork_url": artwork_url,
            "appearances": [{"dim_id": dim_id, "dim_name": dim_name,
                             "stage": stage_roman}],
            "evolution_conditions": conditions,
        })

    return entries


# ── main orchestrator ─────────────────────────────────────────────────────────

def parse_chart(url: str, download_images: bool = True,
                name: str = None) -> None:
    folder = name or urlparse(url).path.rstrip("/").split("/")[-1] or "output"
    out = Path(folder)

    session = requests.Session()
    dl_cache: dict[str, Path] = {}   # url → first local path, for copy-reuse

    print(f"[*] Fetching {url}")
    resp = session.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # Detect which details endpoint this page uses
    ep_device, ep_version = detect_endpoint(soup)
    if ep_device:
        print(f"[*] Endpoint: unified (device={ep_device})")
    else:
        print(f"[*] Endpoint: legacy")

    dims_list:   list[dict] = []
    all_digimon: dict[str, dict] = {}

    anchors = soup.find_all("div", class_="anchor")
    print(f"[*] Found {len(anchors)} dim card(s)")

    for anchor in anchors:
        anchor_id = anchor.get("id", "")
        dim_id    = anchor_id.replace("_anchor", "")

        emblem    = anchor.find("img", class_="emblem")
        h4        = anchor.find("h4")
        digi_img  = anchor.find("img", class_="digitama_image")
        unified   = anchor.find("div", class_="digitamaUnified")
        release_p = unified.find("p") if unified else None

        dim_name = h4.get_text(strip=True) if h4 else dim_id

        dim: dict = {
            "id":           dim_id,
            "name":         dim_name,
            "release":      release_p.get_text(strip=True) if release_p else "",
            "emblem_url":   abs_url(emblem.get("src", "")) if emblem else "",
            "digitama_url": abs_url(digi_img.get("src", "")) if digi_img else "",
            "digimon_ids":  [],
        }

        chart = anchor.find("div", class_="chart")
        if chart:
            for col in chart.find_all("div", class_="column", recursive=False):
                col_classes = col.get("class", [])
                if "branches" in col_classes:
                    continue
                stage_key = next(
                    (c for c in col_classes if c in STAGE_COLUMNS), None
                )
                if not stage_key:
                    continue

                for entry in parse_column(
                    col, dim_id, dim_name,
                    STAGE_COLUMNS[stage_key], anchor
                ):
                    mon_id = entry["id"]
                    if mon_id in all_digimon:
                        # Shared across dims: add another appearance
                        all_digimon[mon_id]["appearances"].extend(
                            entry["appearances"]
                        )
                    else:
                        all_digimon[mon_id] = entry
                    if mon_id not in dim["digimon_ids"]:
                        dim["digimon_ids"].append(mon_id)

        dims_list.append(dim)

    total = len(all_digimon)
    print(f"[*] Found {total} unique digimon — fetching details & assets...")

    for i, (mon_id, mon_data) in enumerate(all_digimon.items(), 1):
        label = mon_data["name"] or mon_id
        print(f"  [{i:3d}/{total}] {label}")

        details = parse_details(mon_id, session, ep_device, ep_version)
        mon_data["details"] = details

        mon_name_folder = safe_name(mon_data["name"] or mon_id)
        for appearance in mon_data["appearances"]:
            img_dir = (
                out
                / safe_name(appearance["dim_name"])
                / safe_name(f"Stage_{appearance['stage']}")
                / mon_name_folder
            )
            img_dir.mkdir(parents=True, exist_ok=True)

            # Save details.json co-located with images inside the digimon folder
            with open(img_dir / "details.json", "w", encoding="utf-8") as f:
                json.dump(mon_data, f, ensure_ascii=False, indent=2)

            if download_images:
                if mon_data["frame1_url"]:
                    download(mon_data["frame1_url"],  img_dir / "frame1.gif",
                             session, dl_cache)
                if mon_data["frame2_url"]:
                    download(mon_data["frame2_url"],  img_dir / "frame2.gif",
                             session, dl_cache)
                if mon_data["artwork_url"]:
                    ext = mon_data["artwork_url"].rsplit(".", 1)[-1]
                    download(mon_data["artwork_url"], img_dir / f"artwork.{ext}",
                             session, dl_cache)

        time.sleep(REQUEST_DELAY)

    # ── per-dim evolution tree JSONs + digitama image ────────────────────────
    for dim in dims_list:
        dim_folder = out / safe_name(dim["name"])
        if not dim_folder.exists():
            continue

        # Digitama (egg) image → dim folder root
        if download_images and dim.get("digitama_url"):
            ext = dim["digitama_url"].rsplit(".", 1)[-1]
            download(dim["digitama_url"], dim_folder / f"digitama.{ext}",
                     session, dl_cache)

        digimon_list = []
        edges: list[dict] = []

        for mon_id in dim["digimon_ids"]:
            if mon_id not in all_digimon:
                continue
            mon     = all_digimon[mon_id]
            details = mon.get("details", {})

            # Resolve stage for this specific dim
            appearance = next(
                (a for a in mon["appearances"] if a["dim_id"] == dim["id"]),
                mon["appearances"][0],
            )
            stage = appearance["stage"]

            digimon_list.append({
                "id":          mon_id,
                "name":        mon["name"],
                "stage":       stage,
                "stage_text":  details.get("stage_text", ""),
                "attribute":   details.get("attribute", ""),
                "activity":    details.get("activity", ""),
                "stats":       details.get("stats", {}),
                "frame1_url":  mon["frame1_url"],
                "frame2_url":  mon["frame2_url"],
                "artwork_url": mon["artwork_url"],
            })

            # Build directed edges: predecessor → this digimon
            for block in mon["evolution_conditions"]:
                for from_id in block["from_digimon"]:
                    from_name = all_digimon.get(from_id, {}).get("name", from_id)
                    edges.append({
                        "from":         from_id,
                        "from_name":    from_name,
                        "to":           mon_id,
                        "to_name":      mon["name"],
                        "requirements": block["requirements"],
                    })

        tree = {
            "id":           dim["id"],
            "name":         dim["name"],
            "release":      dim["release"],
            "emblem_url":   dim["emblem_url"],
            "digitama_url": dim["digitama_url"],
            "digimon":      digimon_list,
            "evolution_edges": edges,
        }
        tree_path = dim_folder / f"{safe_name(dim['name'])}.json"
        with open(tree_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, ensure_ascii=False, indent=2)

    # ── global data.json ──────────────────────────────────────────────────────
    output = {
        "source_url":    url,
        "total_dims":    len(dims_list),
        "total_digimon": total,
        "dims":          dims_list,
        "digimon":       all_digimon,
    }
    with open(out / "data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # Summary
    print(f"\n[✓] Output written to ./{out}/")
    print(f"    data.json   — {len(dims_list)} dims, {total} digimon")
    dim_dirs = sorted(p for p in out.iterdir() if p.is_dir())
    print(f"    {len(dim_dirs)} dim folder(s)")
    for dim_dir in dim_dirs:
        details_n = len(list(dim_dir.rglob("details.json")))
        frames    = len(list(dim_dir.rglob("frame*.gif")))
        artwork   = len(list(dim_dir.rglob("artwork.*")))
        print(f"      {dim_dir.name:30s}  {details_n:3d} digimon  "
              f"({frames} frames + {artwork} artwork + {details_n} details.json)")


# ── entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parse Digimon VBDM evolution charts from humulos.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("url", help="URL of the evolution chart page to parse")
    ap.add_argument(
        "--no-images",
        action="store_true",
        help="Skip downloading sprite and artwork images",
    )
    ap.add_argument(
        "--name",
        help="Override the output folder name (default: last URL path segment)",
    )
    args = ap.parse_args()
    parse_chart(args.url, download_images=not args.no_images, name=args.name)


if __name__ == "__main__":
    main()
