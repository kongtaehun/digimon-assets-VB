# Digimon Asset Package

반다이 **Vital Bracelet 시리즈**(VBDM / VBBE)에 수록된 디지몬의 **스프라이트·일러스트·진화 계통**과 도감 설명을 가져와, 게임 개발에 바로 쓸 수 있도록 정규화한 데이터 패키지입니다.

- **8 카테고리 · 51 DIM · 861 디지몬 등장** (고유 id 기준 623)
- 스프라이트 GIF 1,725개 · 일러스트 JPG 837개 (~40MB)
- 참고 자료: [humulos.com](https://humulos.com/digimon/) · 도감: [wikimon.net](https://wikimon.net/), digimon.net(KR)

> 설계 원칙: **각 DIM은 자기완결적(self-contained)**. 같은 디지몬이 여러 DIM에 등장해도 DIM별로 따로 저장합니다(중복 제거 안 함). DIM 폴더 하나만 복사하면 그 진화 계통 전체가 동작합니다.

---

## 디렉토리 구조

```
assets/
├── index.json                  # 전체 매니페스트 (카테고리·DIM 목록·개수)
├── schema/                     # JSON Schema (index / dim)
├── data/
│   └── <category>/<dim_id>/
│       ├── dim.json            # ★ 자기완결 카드: 디지몬 + 진화 + 도감 전부 포함
│       ├── digitama.gif        # 디지타마 스프라이트
│       └── sprites/<digimon_id>/
│           ├── frame1.gif      # 도트 애니메이션 프레임 1
│           ├── frame2.gif      # 프레임 2
│           └── artwork.jpg     # 일러스트
├── lib/
│   ├── python/digimon_data/    # Python 접근 라이브러리
│   └── js/digimon-data.js      # JS 접근 라이브러리 (브라우저/Node)
└── tools/
    ├── parse.py                # 원본 스크레이퍼
    ├── fetch_lore.py           # 도감 수집기
    ├── build_assets.py         # raw → 정규화 빌더
    └── raw/                    # 원본 스크레이프 (재빌드 소스)
```

### 카테고리

| id | 라벨 | 기기 | DIM |
|----|------|------|----:|
| `v` | DIM V | VBDM | 5 |
| `vol` | DIM Vol. | VBDM | 8 |
| `bundled` | DIM Bundled | VBDM | 6 |
| `ex` | DIM EX | VBDM | 11 |
| `other` | DIM Other | VBDM | 7 |
| `anime` | BE Anime | VBBE | 5 |
| `special_edition` | BE Special | VBBE | 5 |
| `seekers` | BE Seekers | VBBE | 4 |

---

## `dim.json` 스키마

한 DIM의 모든 정보를 담은 자기완결 파일입니다. 이미지 경로는 **DIM 폴더 기준 상대 경로**라서 폴더째 이동해도 깨지지 않습니다.

```jsonc
{
  "schema_version": "1.0",
  "id": "gamma",
  "name": "Gammamon",
  "category": "v",
  "device": "VBDM",
  "release": "JP: Oct 2021 - Retail ...",
  "emblem_url": "https://...",          // 엠블렘은 원격 URL만 보유
  "digitama": "digitama.gif",
  "stages": ["I", "II", "III", "IV", "V", "VI"],
  "digimon": [
    {
      "id": "gamma",
      "name": "Gammamon",
      "name_jp": "ガンマモン",
      "name_ko": "감마몬",             // 432/861만 보유 (없으면 "")
      "stage": "III",
      "stage_text": "Stage III (Child)",
      "attribute": "Virus",            // Vaccine | Virus | Data | Free
      "activity": "Normal",
      "stats": { "dp": "10 (★1)", "hp": "3", "ap": "2" },
      "schedule": { "awake_hours": "09:00 - 21:00", "critical_hit": "Turn 3" },
      "sprites": { "frame1": "sprites/gamma/frame1.gif", "frame2": "sprites/gamma/frame2.gif" },
      "artwork": "sprites/gamma/artwork.jpg",
      "lore": { "en": "A very rare...", "ko": "..." },
      "wikimon_url": "https://wikimon.net/Gammamon"
    }
  ],
  "evolutions": [
    // 구조화된 조건 (top-level evolution_edges 출처)
    { "from": "gamma", "to": "betelgamma",
      "conditions": { "Trophies": "10+", "Vital Values": "1,100+", "Battles": "8+", "Win Ratio": "N/A" } },
    // 자유 텍스트 조건 (디지몬별 details.json 출처 — EX·베이비 단계 등)
    { "from": "agu", "to": "grey",
      "conditions": { "text": "5+ Trophies, 1,200+ Vital Values, 8+ Battles" } }
  ]
}
```

> **`conditions` 형식 두 가지**: 사이트가 표로 제공하는 카드는 구조화된 객체(`{Trophies, Vital Values, ...}`), 디지몬 상세에서만 얻는 카드(EX 등)는 `{ "text": "..." }`입니다. 접근 라이브러리의 `condition_text()`가 두 형식을 모두 사람이 읽는 문자열로 변환합니다.

`index.json`은 전체 목록입니다:

```jsonc
{
  "schema_version": "1.0",
  "totals": { "categories": 8, "dims": 51, "digimon": 861 },
  "categories": [
    { "id": "v", "label": "DIM V", "device": "VBDM",
      "dims": [ { "id": "gamma", "name": "Gammamon", "digimon_count": 14, "path": "data/v/gamma" } ] }
  ]
}
```

---

## 접근 라이브러리

JSON을 직접 읽어도 되지만, 그래프 탐색(진화 전/후, 경로, 트리)을 위한 작은 라이브러리를 제공합니다.

### Python (`lib/python/digimon_data`)

```python
import sys; sys.path.insert(0, "assets/lib/python")
from digimon_data import DigimonDB

db = DigimonDB("assets")                       # index.json이 있는 경로

db.totals                                       # {'categories': 8, 'dims': 51, 'digimon': 861}
[c.id for c in db.categories()]                 # ['v', 'vol', ...]

dim = db.load_dim("v", "gamma")                 # 하나의 진화 계통
dim.by_stage()                                  # {'I': [Curimon], 'III': [Gammamon], ...}
dim.roots()                                     # 진입점 (부모 없는 디지몬)
dim.leaves()                                    # 최종 진화형

dim.next("gamma")                               # [Betel Gammamon, Kaus Gammamon, ...]
dim.prev("betelgamma")                          # [Gammamon]
dim.evolutions_from("gamma")[0].condition_text()# "10+ Trophies · 1,100+ Vital Values · 8+ Battles"
dim.paths("gamma", "chaosdra")                  # 모든 진화 경로 (id 리스트들)
dim.tree("gamma")                               # 중첩 진화 트리

gamma = dim.get("gamma")
gamma.frame1_path                               # 절대 경로 (Path), .artwork_path 등
gamma.lore_ko, gamma.attribute, gamma.stats

db.find_digimon("agumon")                       # 전 DIM 검색 → [(Dim, Digimon), ...]
```

### JavaScript (`lib/js/digimon-data.js`)

```js
import { DigimonDB } from "./assets/lib/js/digimon-data.js";

// 브라우저
const db = new DigimonDB({ base: "/assets" });
// Node
// const db = new DigimonDB({ base: "./assets", fs: true });
await db.init();

const dim = await db.loadDim("v", "gamma");
dim.byStage();                 // Map { 'I' => [...], ... }
dim.next("gamma");             // [Digimon, ...]
dim.paths("gamma", "chaosdra");
dim.tree("gamma");
dim.assetURL(dim.get("gamma").sprites.frame1);  // → "/assets/data/v/gamma/sprites/gamma/frame1.gif"
```

---

## 데이터 재빌드

`tools/raw/`(원본 스크레이프)에서 `data/` + `index.json`을 다시 생성합니다:

```bash
cd assets/tools
python3 build_assets.py --raw raw --out ..
```

원본을 처음부터 다시 수집하려면(네트워크 필요):

```bash
pip install -r tools/requirements.txt
python3 tools/parse.py https://humulos.com/digimon/vbdm/v/
python3 tools/fetch_lore.py
# 그 결과를 raw/로 모은 뒤 build_assets.py 실행
```

---

## 알려진 한계

- **진화 엣지가 없는 DIM이 3개** (`ex/blitz_ex`, `ex/wolf_ex`, `ex/louwe_ex`): 원본에 해당 카드의 dim 내부 진화 정보가 없습니다(디지몬·스프라이트·스탯은 정상). 그 외 EX 카드는 `details.json`에서 복원됩니다. 단 하이브리드 라인(agni/fairi/chack_ex)은 진화 상당수가 다른 EX 카드로 이어지는 구조라 dim 내부 엣지가 희소합니다.
- **한국어 이름/설명은 432/861만 보유**: 없으면 빈 문자열입니다.
- **frame1 변종**: 7개 id가 카드마다 미세하게 다른 스프라이트를 갖지만, DIM별 저장이므로 각 DIM 안에서는 일관됩니다.
- **엠블렘 이미지는 원격 URL만** 있고 로컬 파일은 없습니다.

> 진화 엣지는 두 출처를 병합합니다: 사이트의 top-level 진화표(구조화 조건) + 디지몬별 상세 카드(`details.json`의 `evolves_from`/`evolves_to`, id 기반 dim 내부 매칭). 후자 덕분에 EX 카드(255 엣지)와 베이비 단계(I→II→III)도 연결됩니다.

---

## 저작권 / 면책

> Digimon, Digital Monster, Vital Bracelet, all related characters, and associated images are owned by Bandai Co., Ltd., Akiyoshi Hongo, and Toei Animation Co., Ltd.

이 패키지에 포함된 스프라이트·일러스트·도감 텍스트 등 모든 에셋의 저작권은 위 권리자에게 있습니다. 본 패키지는 권리자와 무관한 **비공식·비상업적 팬 정리물**로, 구조 정보는 [humulos.com](https://humulos.com/digimon/) 등 공개 자료를 **참고**해 구성했습니다. 에셋을 게임 등에 재사용할 경우 위 저작권을 따라야 하며, 그 책임은 사용자에게 있습니다.
