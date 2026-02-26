<div align="center">

# SafeHome

### AI 기반 부동산 매물 신뢰도 분석 및 전세사기 위험 탐지 시스템

---

## 1. 프로젝트 개요

### 1.1 배경

- 2023년 전세사기 피해자 수 약 **1만 5천명**, 피해 금액 약 **1조원 이상**
- 허위·과장 매물 비율이 전체 온라인 매물의 약 **15~20%** 로 추정
- 등기부등본 등 전문 지식 부족으로 일반인의 사기 판별이 어려운 구조적 문제

### 1.2 목적

부동산 매물 텍스트의 **허위·과장 표현을 자동 탐지**하고, 전세 매물에 대해서는 **전세사기 위험도를 분석**하여 종합 매물 신뢰도 리포트를 제공한다.

### 1.3 기대 효과

| 효과 | 설명 |
|------|------|
| 정보 비대칭 해소 | 비전문가도 매물의 위험 요소를 쉽게 파악 |
| 전세사기 사전 예방 | 깡통전세, 다중 임대 등 사기 패턴 사전 경고 |
| 거래 안전성 향상 | 등기부등본 자동 해석 및 체크리스트 제공 |

---

## 2. 시스템 요구사항

### 2.1 기능적 요구사항

| ID | 기능 | 설명 | 우선순위 |
|----|------|------|:--------:|
| FR-01 | 매물 텍스트 입력 | 매물 설명 텍스트 직접 입력 또는 붙여넣기 | `필수` |
| FR-02 | 매물 유형 선택 | 전세 / 월세 / 매매 유형 선택 | `필수` |
| FR-03 | 매물 기본 정보 입력 | 주소, 보증금, 면적 등 기본 정보 입력 | `필수` |
| FR-04 | 허위·과장 표현 탐지 | 매물 텍스트에서 과장, 오해 유발, 미끼 표현 탐지 | `필수` |
| FR-05 | 핵심 정보 자동 추출 | 텍스트에서 가격, 면적, 위치, 층수, 옵션 등 추출 | `필수` |
| FR-06 | 실거래가 시세 조회 | 해당 지역 실거래가 데이터 조회 및 시세 비교 | `필수` |
| FR-07 | 전세가율 산출 | 전세가 ÷ 매매가 비율 자동 계산 | `전세` |
| FR-08 | 등기부등본 분석 | 근저당, 압류, 신탁 등 위험 요소 분석 | `전세` |
| FR-09 | 전세사기 위험도 산출 | 전세가율 + 시세 + 등기 분석 결합 위험도 등급 산출 | `전세` |
| FR-10 | 종합 신뢰도 리포트 | 신뢰도 점수(0~100) + 위험 사유 + 체크리스트 | `필수` |
| FR-11 | 안전거래 가이드 | 거래 유형별 필수 확인사항 체크리스트 | `선택` |

### 2.2 비기능적 요구사항

| ID | 항목 | 요구사항 |
|----|------|----------|
| NFR-01 | 응답 시간 | 분석 결과 15초 이내 |
| NFR-02 | 가용성 | 웹 기반, 별도 설치 불필요 |
| NFR-03 | 보안 | API 키 환경변수 관리, 사용자 데이터 미저장 |
| NFR-04 | 확장성 | 파인튜닝 모델 교체 가능한 모듈화 구조 |
| NFR-05 | UX | 비전문가도 이해 가능한 쉬운 표현 |

---

## 3. 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│             Frontend (Next.js + Tailwind CSS)             │
│                                                          │
│  [ 매물 검색 ] [ 매물 분석 ] [ 분석 결과 ] [ 매물 비교 ]  │
│                    (Vercel)                               │
└────────┬────────────▲──────────────────▲─────────────────┘
         │  API Proxy │  (rewrites)      │
┌────────▼────────────┴──────────────────┴─────────────────┐
│                    Backend (FastAPI)                       │
│                       (Render)                            │
│               ┌─ 분석 오케스트레이터 ─┐                    │
│               │                      │                    │
│   ┌───────┐ ┌┴──────┐ ┌───────┐ ┌───┴────────┐          │
│   │텍스트 │ │정보   │ │시세   │ │전세사기     │          │
│   │분석   │ │추출   │ │검증   │ │위험 분석    │          │
│   └───┬───┘ └───┬───┘ └───┬───┘ └───┬────────┘          │
└───────┼─────────┼─────────┼─────────┼────────────────────┘
        │         │         │         │
  ┌─────▼─────────▼──┐  ┌──▼───┐  ┌──▼──────────────┐
  │    LLM API       │  │실거래│  │  카카오맵 API    │
  │(OpenAI / Gemini) │  │가 API│  │(Geocode/Category)│
  └──────────────────┘  └──────┘  └──────────────────┘
```

---

## 4. 모듈 상세 설계

### Module 1: 매물 텍스트 분석

- **입력:** 매물 설명 텍스트
- **처리:** LLM API를 통한 과장·허위 표현 탐지
- **출력:** 탐지된 표현 목록 + 카테고리 + 심각도

**탐지 카테고리:**

| 카테고리 | 설명 | 예시 |
|----------|------|------|
| `EXAGGERATION` | 과장 표현 | "초역세권", "풀옵션" |
| `MISLEADING` | 오해 유발 | "리모델링 완료", "신축급" |
| `PRICE_BAIT` | 미끼 가격 | 비정상 저가 |
| `OMISSION` | 중요 정보 누락 | 반지하, 북향 미기재 |
| `NORMAL` | 정상 | 사실 기반 서술 |

### Module 2: 핵심 정보 추출

- **입력:** 매물 설명 텍스트
- **처리:** LLM API를 통한 구조화된 정보 추출
- **출력:** JSON (가격, 면적, 위치, 층수, 옵션 등)

### Module 3: 시세 교차 검증

- **입력:** 주소, 면적, 매물 가격
- **처리:** 실거래가 API 조회 → 주변 시세 비교
- **출력:** 시세 적정성 (적정 / 저가의심 / 고가의심) + 편차율

### Module 4: 전세사기 위험 분석 (전세 전용)

- **입력:** 전세 보증금, 매매 시세, 등기부등본 텍스트(선택)
- **처리:** 전세가율 산출 + 등기부 LLM 분석 + 위험 패턴 매칭
- **출력:** 위험 등급(안전/주의/경고/위험) + 위험 사유 + 체크리스트

---

## 5. 데이터 설계

### 5.1 입력 데이터

```json
{
  "listing_text": "string",
  "listing_type": "전세 | 월세 | 매매",
  "address": "string",
  "deposit": "number (만원)",
  "monthly_rent": "number (만원, 월세일 경우)",
  "area_sqm": "number (㎡)",
  "registry_text": "string (등기부등본, 선택)"
}
```

### 5.2 출력 데이터

```json
{
  "reliability_score": "number (0~100)",
  "reliability_grade": "안전 | 주의 | 경고 | 위험",
  "text_analysis": {
    "suspicious_expressions": [
      {
        "text": "string",
        "category": "EXAGGERATION | MISLEADING | PRICE_BAIT | OMISSION",
        "severity": "LOW | MEDIUM | HIGH",
        "reason": "string"
      }
    ]
  },
  "extracted_info": {
    "price": "string",
    "area": "string",
    "floor": "string",
    "location_claims": ["string"],
    "facilities": ["string"]
  },
  "market_comparison": {
    "avg_market_price": "number",
    "deviation_rate": "number (%)",
    "assessment": "적정 | 저가의심 | 고가의심"
  },
  "jeonse_risk": {
    "jeonse_rate": "number (%)",
    "risk_score": "number (0~100)",
    "risk_grade": "안전 | 주의 | 경고 | 위험",
    "risk_factors": ["string"],
    "registry_analysis": {
      "owner": "string",
      "mortgage": "number",
      "seizure": "boolean",
      "trust": "boolean"
    },
    "checklist": ["string"]
  }
}
```

---

## 6. 전세사기 위험도 산출 기준

### 6.1 점수 산출 규칙

| 항목 | 조건 | 점수 |
|------|------|:----:|
| **전세가율** | 60% 이하 | +0 |
| | 60~70% | +20 |
| | 70~80% | +40 |
| | 80% 이상 | +60 |
| **시세 대비 가격** | ±10% 이내 | +0 |
| | 10~20% 저가 | +15 |
| | 20% 이상 저가 | +30 |
| **근저당** | 없음 | +0 |
| | 매매가 50% 미만 | +10 |
| | 매매가 50% 이상 | +30 |
| **압류/가압류** | 없음 | +0 |
| | 있음 | +30 |
| **신탁등기** | 없음 | +0 |
| | 있음 | +20 |
| **매물 텍스트** | 이상 없음 | +0 |
| | 과장 표현 | +10 |
| | 허위 의심 | +20 |

### 6.2 위험 등급

| 점수 | 등급 | 표시 | 설명 |
|:----:|------|:----:|------|
| 0~20 | 안전 | 🟢 | 특별한 위험 요소 없음 |
| 21~40 | 주의 | 🟡 | 일부 확인 필요 |
| 41~60 | 경고 | 🟠 | 전문가 상담 권장 |
| 61~100 | 위험 | 🔴 | 전세사기 가능성 높음, 거래 재고 권장 |

---

## 7. API 설계

| Method | Endpoint | 설명 |
|:------:|----------|------|
| `POST` | `/api/analyze` | 매물 종합 분석 |
| `POST` | `/api/analyze/text` | 매물 텍스트만 분석 |
| `POST` | `/api/analyze/registry` | 등기부등본 분석 |
| `GET` | `/api/market-price` | 실거래가 시세 조회 |
| `GET` | `/api/health` | 서버 상태 확인 |

---

## 8. 기술 스택

### MVP (현재)

| 구분 | 기술 |
|------|------|
| Backend | Python 3.11+ / FastAPI |
| Frontend | Next.js 16 (TypeScript + Tailwind CSS v4) |
| LLM | OpenAI GPT-4o-mini (기본) / Google Gemini 2.5 Flash |
| 외부 API | 국토교통부 실거래가, 카카오맵 REST, 직방 비공식 API |
| 배포 (Frontend) | **Vercel** |
| 배포 (Backend) | **Render** |

### 추후 고도화

| 구분 | 기술 |
|------|------|
| 파인튜닝 프레임워크 | HuggingFace Transformers + PyTorch |
| Base Model | KcELECTRA-base |
| 파인튜닝 기법 | LoRA / QLoRA |
| 실험 관리 | Weights & Biases |
| DB | PostgreSQL |

---

## 9. 프로젝트 디렉토리 구조

```
safehome/
├── README.md
├── requirements.txt               # Python 의존성
├── render.yaml                    # Render 배포 Blueprint
├── .env.example                   # 백엔드 환경변수 템플릿
├── .gitignore
│
├── app/                           # FastAPI 백엔드
│   ├── main.py                    # FastAPI 진입점 + 라우터
│   ├── config.py                  # 환경변수 설정
│   │
│   ├── models/
│   │   └── schemas.py             # Pydantic 스키마
│   │
│   ├── modules/
│   │   ├── text_analyzer.py       # 허위·과장 표현 탐지
│   │   ├── info_extractor.py      # 핵심 정보 추출
│   │   ├── market_comparator.py   # 시세 교차 검증
│   │   ├── jeonse_analyzer.py     # 전세사기 위험 분석
│   │   └── report_generator.py    # 종합 리포트 생성
│   │
│   ├── services/
│   │   ├── llm_service.py         # LLM API 래퍼 (OpenAI / Gemini)
│   │   ├── real_estate_api.py     # 국토교통부 실거래가 API
│   │   ├── kakao_map_service.py   # 카카오맵 REST API
│   │   ├── listing_scraper.py     # URL 매물 스크래핑
│   │   ├── zigbang_api.py         # 직방 비공식 API
│   │   └── location_verifier.py   # 주변 시설 거리 검증
│   │
│   └── utils/
│       └── scoring.py             # 점수 계산 로직
│
├── frontend/                      # Next.js 프론트엔드
│   ├── package.json
│   ├── next.config.ts             # API 프록시 rewrites
│   ├── vercel.json                # Vercel 설정
│   ├── .env.local.example         # 프론트 환경변수 템플릿
│   └── src/
│       ├── app/
│       │   ├── layout.tsx         # 루트 레이아웃
│       │   ├── page.tsx           # 메인 페이지 (탭 구조)
│       │   └── globals.css
│       ├── components/
│       │   ├── listing-form.tsx       # 매물 입력 폼 + URL 스크래핑
│       │   ├── analysis-report.tsx    # AI 분석 결과 표시
│       │   ├── zigbang-search.tsx     # 직방 매물 검색
│       │   ├── comparison-view.tsx    # 매물 비교함
│       │   ├── score-ring.tsx         # 신뢰도 점수 링
│       │   └── risk-badge.tsx         # 위험 등급 뱃지
│       └── lib/
│           ├── api.ts             # FastAPI 연동 클라이언트
│           └── types.ts           # TypeScript 타입 정의
│
└── tests/
    └── test_modules.py            # 테스트
```

---

## 10. 배포 가이드

### 10.1 사전 준비

- GitHub 리포지토리 생성 후 코드 push
- [Vercel](https://vercel.com) 계정
- [Render](https://render.com) 계정

### 10.2 백엔드 배포 (Render)

1. Render 대시보드 → **New Web Service** → GitHub 리포지토리 연결
2. 설정:
   - **Root Directory:** (비워두기 — 프로젝트 루트)
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Environment:** Python 3
3. 환경변수 추가 (`.env.example` 참조):
   - `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`
   - `GEMINI_API_KEYS`, `GEMINI_MODEL`
   - `REAL_ESTATE_API_KEY`, `KAKAO_API_KEY`
   - `CORS_ORIGINS` → Vercel 배포 도메인 (예: `https://safehome.vercel.app`)
4. 배포 완료 후 URL 확인 (예: `https://safehome-api.onrender.com`)

### 10.3 프론트엔드 배포 (Vercel)

1. Vercel 대시보드 → **New Project** → GitHub 리포지토리 연결
2. 설정:
   - **Framework Preset:** Next.js
   - **Root Directory:** `frontend`
3. 환경변수 추가:
   - `NEXT_PUBLIC_API_URL` → Render 백엔드 URL (예: `https://safehome-api.onrender.com`)
   - `NEXT_PUBLIC_KAKAO_MAP_KEY` → 카카오맵 JavaScript 키
4. Deploy 클릭

### 10.4 로컬 개발

```bash
# 1. 환경변수 설정
cp .env.example .env          # 백엔드 키 입력
cp frontend/.env.local.example frontend/.env.local  # 프론트 키 입력

# 2. 백엔드 의존성 설치 및 실행
pip install -r requirements.txt
npm run dev:api

# 3. 프론트엔드 의존성 설치 및 실행 (별도 터미널)
cd frontend && npm install
npm run dev

# 또는 동시 실행
npm install        # root concurrently 설치
npm run dev        # 백엔드 + 프론트 동시 실행
```

---

<div align="center">

**SafeHome** — 안전한 부동산 거래의 시작

</div>
