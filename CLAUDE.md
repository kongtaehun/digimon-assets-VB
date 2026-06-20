# CLAUDE.md

이 저장소에서 작업할 때의 가이드입니다.

## 저장소 구조

두 영역을 **독립적으로** 관리합니다.

- **`assets/`** — 게임 개발용 데이터 패키지. 정규화된 JSON + 이미지 + 접근 라이브러리(Python/JS). 다른 프로젝트에 통째로 복사해 쓰는 것이 목표.
- **`app/`** — `assets/`를 소비하는 모바일 웹 뷰어. FastAPI + 바닐라 JS SPA, 포트 **6519**.

각 영역에 자체 `README.md`가 있으니 세부 사항은 그쪽을 먼저 보세요.

## 핵심 설계 원칙

- **각 DIM은 자기완결(self-contained)**: `assets/data/<category>/<dim_id>/dim.json` 하나에 그 카드의 디지몬·스탯·진화·도감이 모두 들어있고, 이미지는 같은 폴더 기준 **상대 경로**다. 폴더째 옮겨도 동작해야 한다.
- **중복 등장은 정규화하지 않는다**: 같은 디지몬이 여러 DIM에 나와도 DIM별로 따로 저장한다. (의도된 설계 — 사용자가 명시적으로 요청)
- **데이터는 빌드 산출물**: `data/`와 `index.json`은 `tools/raw/`에서 `build_assets.py`로 생성된다. 데이터를 수정해야 하면 `dim.json`을 직접 고치지 말고 빌더/원본을 고치고 재빌드하는 것을 우선 고려한다.

## 데이터 재빌드

```bash
cd assets/tools && python3 build_assets.py --raw raw --out ..
```

`raw/`(원본 스크레이프)에서 `assets/data` + `index.json` + `schema/`를 다시 만든다.

## 앱 실행 / 검증

```bash
cd app && python3 server.py          # http://localhost:6519
```

UI 변경을 검증할 때는 Playwright(headless, 390×844 모바일 뷰포트)로 실제 구동해 확인한다. 단위 테스트나 타입체크가 아니라 **앱을 실제로 띄워서** 콘솔 에러 0, 스프라이트 `naturalWidth>0`, SVG 엣지 수 등을 관찰한다.

## 접근 라이브러리 (데이터 다룰 때 우선 사용)

JSON을 직접 파싱하기 전에 라이브러리를 쓴다:

```python
import sys; sys.path.insert(0, "assets/lib/python")
from digimon_data import DigimonDB
db = DigimonDB("assets")
dim = db.load_dim("v", "gamma")      # .next/.prev/.roots/.leaves/.paths/.tree/.by_stage
```

JS는 `assets/lib/js/digimon-data.js` (브라우저 `fetch` 또는 Node `fs:true`).

## 진화 엣지 출처 (중요)

`evolutions`는 두 출처를 병합해 만든다:
1. dim JSON의 top-level `evolution_edges` (구조화 조건 `{Trophies, ...}`)
2. 각 디지몬 `details.json`의 `evolves_from`/`evolves_to` (id 기반 dim 내부 매칭, 조건은 `{text: "..."}`)

(2) 덕분에 **EX 카드(255 엣지)와 베이비 단계 엣지**가 살아난다. 과거엔 (1)만 읽어 EX가 전부 비어 보였다 — 이건 데이터가 아니라 빌더 버그였고 수정됨. 조건이 두 형식이므로 렌더러(`reqText` / `condition_text`)는 `text` 키를 먼저 처리한다.

## 알려진 데이터 한계 (버그 아님)

- **3개 DIM만 진화 엣지가 비어있다** (`ex/blitz_ex`, `ex/wolf_ex`, `ex/louwe_ex`): 원본에 dim 내부 진화 정보가 아예 없다. 하이브리드 라인(agni/fairi/chack_ex)은 진화가 대부분 타 EX 카드로 나가 dim 내부 엣지가 희소하다 — 자기완결 설계상 cross-DIM 엣지는 담지 않는다.
- **한국어 이름/설명은 432/861만** 존재. 없으면 빈 문자열.

이런 항목을 "고쳐야 할 버그"로 오해하지 말 것. 데이터 출처의 한계다.

## 컨벤션

- 프론트엔드는 **의존성 없는 바닐라 JS** 유지 (빌드 스텝 없음).
- UI 문구는 한국어, 코드/식별자는 영어.
- 스테이지 색상·속성 색상은 `app/static/style.css`의 CSS 변수로 통일돼 있다.
