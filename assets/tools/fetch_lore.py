#!/usr/bin/env python3
"""
Fetches lore descriptions for all parsed Digimon from:
  - Wikimon (English + Japanese official profiles)
  - Namu.wiki (Korean official translation)

Outputs:
  lore_en.json  — {id: {name, name_jp, name_ko, profile_en, profile_jp, wikimon_url}}
  lore_ko.json  — {id: {name, name_ko, profile_ko, namu_url}}
"""

import json
import re
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
DELAY = 0.4
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ── helpers ─────────────────────────────────────────────────────────────────

def get(url: str, retries=3):
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 200:
                return r
            if r.status_code == 404:
                return None
        except requests.RequestException as e:
            print(f"  [warn] {e} (attempt {attempt+1})")
            time.sleep(1)
    return None


def collect_digimon():
    """Return {id: name} for all unique Digimon found in details.json files."""
    seen: dict[str, str] = {}
    for path in BASE_DIR.rglob("details.json"):
        try:
            data = json.loads(path.read_text())
            did = data.get("id", "")
            name = data.get("name", "")
            if did and did not in seen:
                seen[did] = name
        except Exception:
            pass
    return seen


# ── Wikimon ──────────────────────────────────────────────────────────────────

def wikimon_url(name: str) -> str:
    # capitalize each word for Wikimon URL
    slug = name.replace(" ", "_")
    return f"https://wikimon.net/{slug}"


def parse_wikimon(name: str) -> dict:
    """Fetch English profile, Japanese profile, and Korean name from Wikimon."""
    url = wikimon_url(name)
    resp = get(url)
    if not resp:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.find("div", class_="mw-parser-output")
    if not content:
        return {}

    tables = content.find_all("table")
    if not tables:
        return {}

    result = {"wikimon_url": url}

    # First table contains the profile section
    t = tables[0]
    cells = t.find_all("td")

    profile_en = ""
    profile_jp = ""
    name_ko = ""
    name_jp = ""

    for td in cells:
        text = td.get_text(strip=True)

        # English profile: cell starts with "⇨ Japanese" and contains ASCII profile text
        if not profile_en and text.startswith("⇨ Japanese") and len(text) > 50:
            candidate = text[len("⇨ Japanese"):].strip()
            # Must be primarily ASCII (English)
            ascii_ratio = sum(1 for c in candidate if ord(c) < 128) / max(len(candidate), 1)
            if ascii_ratio > 0.7:
                profile_en = candidate

        # Japanese profile: cell starts with "⇨ English" and contains Japanese text
        if not profile_jp and text.startswith("⇨ English") and len(text) > 20:
            candidate = text[len("⇨ English"):].strip()
            # Must contain Japanese characters
            if re.search(r"[぀-鿿]", candidate):
                profile_jp = candidate

        # Korean name from "Other Languages" cell
        if not name_ko and "Other Languages" in text:
            # Find Hangul text, excluding footnote numbers
            ko_match = re.search(r"[가-힣]+(?:[가-힣\s]+)?", text)
            if ko_match:
                name_ko = ko_match.group(0).strip()

        # Japanese name (Kanji/Kana field)
        if not name_jp and "Kanji/Kana:" in text:
            jp_match = re.search(r"Kanji/Kana:([ァ-ヶぁ-ん一-龯ー]+)", text)
            if jp_match:
                name_jp = jp_match.group(1)

        if profile_en and profile_jp and name_ko and name_jp:
            break

    if profile_en:
        result["profile_en"] = profile_en
    if profile_jp:
        result["profile_jp"] = profile_jp
    if name_ko:
        result["name_ko"] = name_ko
    if name_jp:
        result["name_jp"] = name_jp

    return result


# ── Namu.wiki ────────────────────────────────────────────────────────────────

def namu_url(name_ko: str) -> str:
    return "https://namu.wiki/w/" + urllib.parse.quote(name_ko)


def parse_namu(name_ko: str) -> dict:
    """Fetch Korean official profile (디지몬 웹도감) from namu.wiki."""
    url = namu_url(name_ko)
    resp = get(url)
    if not resp:
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    # "디지몬 웹도감" section contains the official Korean profile
    idx = text.find("디지몬 웹도감")
    if idx < 0:
        return {}

    # Extract text up to next section marker
    section = text[idx + len("디지몬 웹도감"):].strip()
    # Stop at next numbered section like "3. 작중 등장" or "2. 종족 특성"
    stop_match = re.search(r"\d+\.\s+[가-힣]", section)
    if stop_match:
        section = section[:stop_match.start()].strip()
    # Also stop at [편집]
    edit_idx = section.find("[편집]")
    if edit_idx >= 0:
        section = section[:edit_idx].strip()

    if not section:
        return {}

    return {"profile_ko": section, "namu_url": url}


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Collecting Digimon list...")
    digimon = collect_digimon()
    print(f"Found {len(digimon)} unique Digimon")

    # Load existing progress if any
    en_path = BASE_DIR / "lore_en.json"
    ko_path = BASE_DIR / "lore_ko.json"
    lore_en: dict = json.loads(en_path.read_text()) if en_path.exists() else {}
    lore_ko: dict = json.loads(ko_path.read_text()) if ko_path.exists() else {}

    todo = [(did, name) for did, name in sorted(digimon.items()) if did not in lore_en]
    print(f"Remaining: {len(todo)} (already done: {len(lore_en)})")

    for i, (did, name) in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {name} ({did})")

        # 1. Wikimon
        wk = parse_wikimon(name)
        if not wk:
            print(f"  [skip] not found on Wikimon")
            lore_en[did] = {"name": name, "status": "not_found"}
            lore_ko[did] = {"name": name, "status": "not_found"}
        else:
            en_entry = {"name": name}
            en_entry.update({k: v for k, v in wk.items() if k != "name_ko"})
            lore_en[did] = en_entry

            name_ko = wk.get("name_ko", "")
            if name_ko:
                print(f"  Korean name: {name_ko}")
                # 2. Namu.wiki
                time.sleep(DELAY)
                namu = parse_namu(name_ko)
                ko_entry = {"name": name, "name_ko": name_ko}
                ko_entry.update(namu)
                lore_ko[did] = ko_entry
                if namu.get("profile_ko"):
                    print(f"  KO profile: {namu['profile_ko'][:60]}...")
                else:
                    print(f"  [warn] no Korean profile on namu.wiki")
            else:
                print(f"  [warn] no Korean name found")
                lore_ko[did] = {"name": name, "status": "no_ko_name"}

        # Save progress every 20 entries
        if i % 20 == 0:
            en_path.write_text(json.dumps(lore_en, ensure_ascii=False, indent=2))
            ko_path.write_text(json.dumps(lore_ko, ensure_ascii=False, indent=2))
            print(f"  [saved progress at {i}]")

        time.sleep(DELAY)

    # Final save
    en_path.write_text(json.dumps(lore_en, ensure_ascii=False, indent=2))
    ko_path.write_text(json.dumps(lore_ko, ensure_ascii=False, indent=2))

    # Summary
    en_found = sum(1 for v in lore_en.values() if v.get("profile_en"))
    jp_found = sum(1 for v in lore_en.values() if v.get("profile_jp"))
    ko_found = sum(1 for v in lore_ko.values() if v.get("profile_ko"))
    print(f"\nDone!")
    print(f"  English profiles: {en_found}/{len(lore_en)}")
    print(f"  Japanese profiles: {jp_found}/{len(lore_en)}")
    print(f"  Korean profiles:  {ko_found}/{len(lore_ko)}")
    print(f"  Saved: {en_path.name}, {ko_path.name}")


if __name__ == "__main__":
    main()
