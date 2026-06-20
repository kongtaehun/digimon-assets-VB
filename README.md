# Digimon Evolution Parsing

반다이 **Vital Bracelet 시리즈**(VBDM / VBBE)에 수록된 디지몬의 **스프라이트·일러스트·진화 계통**과 도감 데이터를 가져와 정규화하고, 모바일 뷰어로 탐색하는 프로젝트입니다.

```
digimon_evol_parsing/
├── assets/        ← 데이터 패키지 (게임 개발용)   →  assets/README.md
└── app/           ← 모바일 웹 뷰어                →  app/README.md
```

두 영역은 **독립적으로 관리**됩니다. `assets/`는 다른 게임/프로젝트에 그대로 복사해 쓸 수 있는 데이터 + 접근 라이브러리이고, `app/`은 그 데이터를 소비하는 한 예시 뷰어입니다.

---

## 한눈에 보기

| | |
|---|---|
| 카테고리 | 8 (DIM V/Vol/Bundled/EX/Other, BE Anime/Special/Seekers) |
| DIM 카드 | 51 |
| 디지몬 등장 | 861 (고유 id 623) |
| 스프라이트 / 일러스트 | GIF 1,725 / JPG 837 (~40MB) |
| 참고 자료 | [humulos.com](https://humulos.com/digimon/), [wikimon.net](https://wikimon.net/), digimon.net(KR) |

---

## 빠른 시작

### 데이터 사용 (게임 개발)

```python
import sys; sys.path.insert(0, "assets/lib/python")
from digimon_data import DigimonDB

db = DigimonDB("assets")
dim = db.load_dim("v", "gamma")
print(dim.next("gamma"))          # 진화 가능한 디지몬들
print(dim.get("gamma").frame1_path)
```

JS 버전과 전체 스키마는 → [`assets/README.md`](assets/README.md)

### 뷰어 실행

```bash
cd app
pip install -r requirements.txt
python3 server.py          # http://localhost:6519
```

자세한 내용 → [`app/README.md`](app/README.md)

---

## 데이터 파이프라인

```
humulos.com ─(parse.py)→ raw/ ─(build_assets.py)→ assets/data + index.json
wikimon/digimon.net ─(fetch_lore.py)→ lore_*.json ──┘
```

- `assets/tools/parse.py` — 진화 차트·스프라이트·일러스트 스크레이퍼
- `assets/tools/fetch_lore.py` — 한/영 도감 설명 수집
- `assets/tools/build_assets.py` — 원본을 게임용 정규화 구조로 변환
- `assets/tools/raw/` — 원본 스크레이프 (재빌드 소스)

---

## 저작권 / 면책

> Digimon, Digital Monster, Vital Bracelet, all related characters, and associated images are owned by Bandai Co., Ltd., Akiyoshi Hongo, and Toei Animation Co., Ltd.

이 저장소의 스프라이트·일러스트 등 모든 에셋의 저작권은 위 권리자에게 있습니다. 본 프로젝트는 권리자와 무관한 **비공식·비상업적 팬 정리물**이며, 데이터는 [humulos.com](https://humulos.com/digimon/) 등 공개 자료를 **참고**해 구성했습니다. 에셋을 재사용할 경우 위 저작권을 따르며, 책임은 사용자에게 있습니다.
