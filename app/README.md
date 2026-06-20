# Digimon Evolution Viewer

`../assets` 데이터 패키지를 모바일에 최적화해 보여주는 웹 뷰어입니다. **트리뷰**(스테이지별 진화 계통도)와 **진화뷰**(디지몬 상세)를 하단 탭으로 전환합니다.

---

## 실행

```bash
pip install -r requirements.txt
python3 server.py
# → http://localhost:6519
```

`server.py`는 `../assets`를 자동으로 찾아 `assets/lib/python`의 `digimon_data` 라이브러리로 데이터를 읽습니다. 포트는 **6519** 고정입니다.

---

## 기능

- **카테고리 탭** — DIM V / Vol / Bundled / EX / Other / Anime / Special / Seekers (8종)
- **DIM 칩 바** — 카테고리 안의 DIM을 디지타마 스프라이트와 함께 선택
- **트리뷰** — Stage I~VI를 색상으로 구분, 카드 사이를 SVG 곡선으로 연결. 선택한 디지몬의 진화 경로는 파란색으로 강조
- **진화뷰** — 일러스트, 2프레임 스프라이트 애니메이션, DP/HP/AP, 활동 스케줄, 진화 전/후 목록(탭하면 이동), 한/영 도감 설명
- **DIM 선택 시트** — ⚙ 버튼 → 보고 싶은 DIM만 토글로 활성화/비활성화 (`localStorage` 저장, 최소 1개 유지)
- 2프레임 도트 스프라이트 실시간 애니메이션

---

## API

| 엔드포인트 | 설명 |
|-----------|------|
| `GET /api/index` | 카테고리 + DIM 목록 + 개수 (매니페스트 기반) |
| `GET /api/dim/{category}/{dim_id}` | 자기완결 `dim.json` (+ `asset_base`) |
| `GET /assets/...` | 정적 에셋 (스프라이트·일러스트·디지타마) |
| `GET /` | 프론트엔드 SPA |

`dim.json`에 도감 설명이 포함돼 있어 별도 lore 요청이 필요 없습니다. 이미지 경로는 `asset_base + sprites.frameN` 으로 만듭니다.

---

## 구성

```
app/
├── server.py              # FastAPI: 2개 API + 정적 마운트
├── requirements.txt
└── static/
    ├── index.html         # 헤더 / 2개 뷰 / 탭바 / DIM 시트
    ├── style.css          # 모바일 다크 테마
    └── app.js             # 상태·렌더·이벤트 (의존성 없는 바닐라 JS)
```

데이터 구조·스키마·접근 라이브러리는 [`../assets/README.md`](../assets/README.md) 참고.
