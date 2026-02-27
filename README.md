<div align="center">

# 🏠 SafeHome

**AI 기반 부동산 매물 신뢰도 분석 및 전세사기 위험 탐지 시스템**

[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o-412991?logo=openai&logoColor=white)](https://openai.com/)
[![Vercel](https://img.shields.io/badge/Deploy-Vercel-000?logo=vercel)](https://vercel.com/)
[![Render](https://img.shields.io/badge/Deploy-Render-46E3B7?logo=render)](https://render.com/)

</div>

---

## 📋 목차

- [프로젝트 개요](#-프로젝트-개요)
- [주요 기능](#-주요-기능)
- [시스템 아키텍처](#-시스템-아키텍처)
- [기술 스택](#-기술-스택)
- [전세사기 위험도 산출 기준](#-전세사기-위험도-산출-기준)
- [API 명세](#-api-명세)
- [프로젝트 구조](#-프로젝트-구조)
- [환경 변수](#-환경-변수)
- [시작하기](#-시작하기)
- [테스트](#-테스트)
- [배포 가이드](#-배포-가이드)

---

## 🎯 프로젝트 개요

### 배경

> 2023년 전세사기 피해자 수 약 **1만 5천명**, 피해 금액 약 **1조원 이상**  
> 허위·과장 매물 비율이 전체 온라인 매물의 약 **15~20%** 로 추정

등기부등본·건축물대장 등 전문 지식 부족으로 일반인의 사기 판별이 어려운 구조적 문제를 해결하기 위해,  
부동산 매물 텍스트의 **허위·과장 표현을 AI로 자동 탐지**하고 **전세사기 위험도**와 **건축물대장**을 분석하여 종합 리포트를 제공합니다.

### 기대 효과

| | 효과 | 설명 |
|:---:|------|------|
| 🔍 | **정보 비대칭 해소** | 비전문가도 매물의 위험 요소를 쉽게 파악 |
| 🛡️ | **전세사기 사전 예방** | 깡통전세, 위반건축물, 다중 임대 등 사기 패턴 사전 경고 |
| ✅ | **거래 안전성 향상** | 등기부등본·건축물대장 자동 해석 및 체크리스트 제공 |

---

## ✨ 주요 기능

### 📝 매물 분석
- **URL 스크래핑** — 네이버 부동산, 다방(직방) 링크에서 매물 정보 자동 추출 (주소·가격·면적·층수·거래유형). 주소가 불완전하면 건물명·좌표로 카카오 API 역지오코딩하여 보강.
- **도로명주소 검색** — 카카오 주소 API 연동 (정규 주소·법정동코드·행정구역 반환).
- **면적 자동 변환** — ㎡ ↔ 평 실시간 변환 (1평 ≈ 3.3058㎡).
- **가격 단위 표시** — 30000 → 3억 자동 표시.
- **등기부등본 입력** — 폼 입력 또는 원문 붙여넣기. 이미지/PDF 업로드 시 LLM으로 텍스트 추출 후 위험 요소 분석.

### 🤖 AI 종합 분석
- **허위·과장 표현 탐지** — LLM 기반: 과장(EXAGGERATION), 오해 유발(MISLEADING), 미끼 가격(PRICE_BAIT), 정보 누락(OMISSION), 정상(NORMAL) 분류 및 심각도(LOW/MEDIUM/HIGH).
- **실거래가 시세 비교** — 국토교통부 실거래가 API 기반, 최근 1년 데이터. 같은 건물·동·시군구 순으로 범위 확대. 전세/월세/매매 유형별 평균·편차·적정성(매우적정~과소의심) 산출.
  - 전세 분석 시 전세만, 매매 분석 시 매매만 표시.
  - 거래 내역 없을 때 **유사 평수(±25㎡)** 근처 데이터로 폴백.
- **전세가율** — 같은 아파트·같은 평수 매매 실거래가 대비 전세가율 산출 (국토연구원 기준: 60% 이하 안전, 80% 이상 위험).
- **전세사기 위험도** — 전세가율, 총 부담률, 경매안전율, 등기부등본(압류/신탁), 시세 편차, 매물 텍스트 위험을 결합하여 0~100 점수 및 등급(안전/주의/경고/위험).
- **건축물대장 조회** — 위반건축물·주용도·건축년도·세대수 등 자동 확인 (HUG 보증보험 가입 불가 사전 경고).
- **주변 시설 거리 검증** — "도보 5분 지하철역" 등 매물 텍스트 주장을 카카오맵으로 검증 (공원·은행·학교 등 실제 시설만 필터링).
- **종합 신뢰도 리포트** — 0~100 점수 + 위험 등급 + AI 상세 섹션(매매/월세/전세별 프롬프트) + 체크리스트.

### 📊 매물 비교
- 분석된 매물을 **비교함**에 저장 (로컬 스토리지, 최대 20건). 항목별 나란히 비교·삭제·다시 보기.

---

## 🏗️ 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│               Frontend (Next.js 16 + Tailwind CSS 4)          │
│                                                               │
│    [ 매물 분석 ]  [ 분석 결과 ]  [ 매물 비교 ]                  │
│    /api/* → next.config rewrites → Backend (프록시)             │
│    등기부 파일 업로드 → NEXT_PUBLIC_BACKEND_URL 직접 호출       │
│                         Vercel                                │
└─────────┬───────────────▲─────────────────────────────────────┘
          │  NEXT_PUBLIC_API_URL (rewrite로 프록시)
┌─────────▼───────────────┴─────────────────────────────────────┐
│                     Backend (FastAPI)                          │
│                          Render                                │
│                                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐      │
│  │ 텍스트   │ │ 시세     │ │ 건축물   │ │ 전세사기     │      │
│  │ 분석     │ │ 검증     │ │ 대장     │ │ 위험 분석    │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────────┘      │
└───────┼───────────┼───────────┼────────────┼─────────────────┘
        │           │           │            │
   ┌────▼───────────▼───┐  ┌───▼────┐  ┌────▼────────────┐
   │      LLM API        │  │ 실거래가│  │  카카오맵 API   │
   │ (OpenAI / Gemini)   │  │ 건축물  │  │ (Geocode/Map)  │
   └─────────────────────┘  │ 대장   │  └─────────────────┘
                            │  API   │
                            └────────┘
```

- **프론트엔드**: Next.js 16 App Router, `page.tsx` 단일 페이지에 탭(매물 분석 / 분석 결과 / 매물 비교) 구성. `next.config.ts`의 `rewrites`로 `/api/*`를 백엔드로 프록시.
- **백엔드**: FastAPI, lifespan으로 기동/종료 로깅, CORS는 `CORS_ORIGINS` 환경 변수(쉼표 구분)로 제어.

---

## 🛠️ 기술 스택

| 구분 | 기술 |
|------|------|
| **Frontend** | Next.js 16 · React 19 · TypeScript · Tailwind CSS v4 · Geist 폰트 |
| **Backend** | Python 3.11+ · FastAPI · Pydantic v2 · Uvicorn |
| **AI / LLM** | OpenAI GPT-4o (기본) · Google Gemini 2.5 Flash (선택, API 키 로테이션 지원) |
| **외부 API** | 국토교통부 실거래가·건축물대장(동일 Decoding 키) · 카카오맵 REST(주소/역지오코딩) |
| **배포** | Vercel (Frontend) · Render (Backend) |

---

## 📐 전세사기 위험도 산출 기준

### 점수 산출 규칙 (참고: 국토연구원·HUG·금융위 기준)

| 항목 | 조건 | 점수 |
|------|------|:----:|
| **전세가율** | 60% 이하 | +0~5 |
| | 70~80% | +15 |
| | 80~90% | +25 |
| | 90% 이상 | +35 |
| **총 부담률** | 70% 이하 | +0~5 |
| | 80~90% | +15 |
| | 90~100% | +25 |
| | 100% 초과 (깡통전세) | +35 |
| **경매안전율** | 100% 초과 | +10 |
| **시세 편차** | 전세 시세 대비 저가 의심 | +5~10 |
| **압류/가압류** | 있음 | +25 |
| **신탁등기** | 있음 | +15 |
| **매물 텍스트** | 과장/의심 | +5~10 |
| **건축물대장** | 위반건축물·비주거용·노후 | 위험 요소로 반영 |

- **총 부담률** = (추정실채무액 + 보증금) / 매매시세 × 100. 채권최고액은 실대출의 약 120%로 가정하여 ×0.83 보정.
- **경매안전율** = (추정실채무액 + 보증금) / (매매시세 × 물건별 낙찰가율). 100% 초과 시 경매에서 보증금 전액 회수 불가.

### 위험 등급

| 점수 | 등급 | 설명 |
|:----:|:----:|------|
| 0~20 | 🟢 **안전** | 특별한 위험 요소 없음 |
| 21~40 | 🟡 **주의** | 일부 확인 필요 |
| 41~60 | 🟠 **경고** | 전문가 상담 권장 |
| 61~100 | 🔴 **위험** | 전세사기 가능성 높음, 거래 재고 권장 |

---

## 📡 API 명세

| Method | Endpoint | 설명 | 요청/비고 |
|:------:|----------|------|-----------|
| `GET` | `/api/health` | 서버 상태 확인 | - |
| `POST` | `/api/analyze` | 매물 종합 분석 | Body: `ListingAnalysisRequest` → `AnalysisReport` |
| `POST` | `/api/analyze/text` | 매물 텍스트만 분석 (허위·과장 + 정보 추출) | Body: `{ "listing_text": "..." }` → `TextAnalysisResult` |
| `POST` | `/api/analyze/registry` | 등기부등본 텍스트 분석 | Body: `{ "registry_text", "deposit" }` → `JeonseRisk` |
| `POST` | `/api/analyze/registry/file` | 등기부등본 파일(이미지/PDF) 분석 | `multipart/form-data`, `file` 필드 → `RegistryFileResponse` |
| `POST` | `/api/scrape-listing` | URL에서 매물 정보 스크래핑 | Body: `{ "url": "..." }` → `ScrapeListingResponse`. 주소 불완전 시 카카오 역지오코딩으로 보강 |
| `GET` | `/api/market-price` | 실거래가 시세 조회 | Query: `address`, `area_sqm`, `listing_price`, `listing_type`, `property_type`, `building_name` → `MarketComparison` |
| `GET` | `/api/geocode` | 주소 → 좌표·법정동코드 변환 | Query: `address` → `GeocodingResponse` |

- **ListingAnalysisRequest**: `listing_text`, `listing_type`, `property_type`, `address`, `building_name`, `deposit`, `monthly_rent`(선택), `area_sqm`, `registry`(선택).
- **AnalysisReport**: `reliability_score`, `reliability_grade`, `evaluation`, `ai_report`, `input_summary`, `text_analysis`, `extracted_info`, `market_comparison`, `location_verification`, `nearby_facilities`, `building_info`, `jeonse_risk`.

---

## 📁 프로젝트 구조

```
project/
├── README.md
├── requirements.txt              # Python 의존성 (fastapi, uvicorn, openai, pydantic, httpx 등)
├── render.yaml                   # Render Web Service Blueprint (safehome-api)
├── .env.example                  # 백엔드 환경변수 템플릿
├── .gitignore
│
├── app/                          # FastAPI 백엔드
│   ├── main.py                   # FastAPI 앱, CORS, 라우트: /api/health, /api/analyze, /api/analyze/text,
│   │                             # /api/analyze/registry, /api/analyze/registry/file, /api/scrape-listing,
│   │                             # /api/market-price, /api/geocode
│   ├── config.py                 # Pydantic Settings: LLM_PROVIDER, Gemini/OpenAI 키·모델, REAL_ESTATE_API_KEY,
│   │                             # KAKAO_API_KEY, APP_HOST/PORT/DEBUG. get_gemini_keys() 로테이션
│   ├── models/
│   │   └── schemas.py            # Pydantic 모델: Enums(ListingType, PropertyType, RiskGrade 등), Request/Response
│   │                             # (ListingAnalysisRequest, AnalysisReport, JeonseRisk, MarketComparison,
│   │                             # ScrapeListingResponse, BuildingRegisterInfo, LocationVerification 등)
│   ├── modules/
│   │   ├── text_analyzer.py       # 허위·과장 표현 탐지 + 핵심 정보 추출 (LLM 1회 호출)
│   │   ├── info_extractor.py      # 매물 텍스트에서 가격·면적·층수·위치주장·시설 추출 (LLM)
│   │   ├── market_comparator.py   # 실거래가 시세 비교, 편차·적정성·전세가율·월별 추이 산출
│   │   ├── jeonse_analyzer.py     # 전세 위험도: 등기부 분석, 총 부담률, 경매안전율, 보험 가입 가능 여부
│   │   └── report_generator.py    # 종합 리포트: 텍스트/시세/위치/건축물대장/전세위험 조합, AI 평가·섹션 생성
│   ├── services/
│   │   ├── llm_service.py         # LLM API (OpenAI / Gemini), chat, chat_json, extract_from_image
│   │   ├── real_estate_api.py     # 국토교통부 실거래가·건축물대장 API (동일 키)
│   │   ├── building_register.py   # 건축물대장 조회 서비스
│   │   ├── kakao_map_service.py   # 카카오 주소 검색·역지오코딩
│   │   ├── listing_scraper.py     # 네이버 부동산·다방(직방) URL 스크래핑
│   │   └── location_verifier.py   # 매물 위치 주장 검증 (공원·은행·학교 등 실제 시설만)
│   └── utils/
│       └── scoring.py             # 전세 위험 점수, 신뢰도 점수, score_to_grade, 경매 낙찰가율 등
│
├── frontend/                     # Next.js 프론트엔드
│   ├── next.config.ts            # rewrites: /api/* → NEXT_PUBLIC_API_URL/api/*
│   ├── vercel.json               # framework: nextjs
│   ├── .env.local.example        # NEXT_PUBLIC_API_URL, NEXT_PUBLIC_KAKAO_MAP_KEY, (선택) NEXT_PUBLIC_BACKEND_URL
│   ├── package.json              # next 16, react 19, tailwindcss 4, typescript
│   └── src/
│       ├── app/
│       │   ├── layout.tsx        # 루트 레이아웃, Geist 폰트, 메타데이터, 헤더/푸터
│       │   ├── page.tsx          # 메인 페이지: 탭(매물 분석/분석 결과/매물 비교), 로딩 오버레이, 분석 요청·저장·삭제
│       │   └── globals.css       # Tailwind, CSS 변수, 로딩 바 애니메이션
│       ├── components/
│       │   ├── listing-form.tsx  # 매물 입력 폼: URL 스크래핑, 주소·가격·면적(㎡/평), 등기부(폼/원문/파일), 분석 제출
│       │   ├── analysis-report.tsx# 분석 결과 렌더: ScoreRing, RiskBadge, 시세·전세위험·건축물대장·위치검증·AI 리포트
│       │   ├── comparison-view.tsx# 비교함: getReports/saveReport/removeReport(localStorage), 목록·삭제·보기
│       │   ├── score-ring.tsx     # 신뢰도 점수 링 UI
│       │   └── risk-badge.tsx    # 위험 등급 뱃지 UI
│       └── lib/
│           ├── api.ts            # analyzeListing, scrapeListing, analyzeRegistryFile, healthCheck. API_BASE로 요청,
│           │                     # 등기부 파일은 BACKEND_DIRECT(NEXT_PUBLIC_BACKEND_URL)로 직접 호출
│           └── types.ts          # 백엔드 스키마에 대응하는 TypeScript 타입 정의
│
└── tests/
    └── test_modules.py           # pytest: 전세 위험 점수, score_to_grade, 신뢰도 점수 테스트
```

---

## 🔐 환경 변수

### 백엔드 (루트 `.env`)

| 변수 | 필수 | 설명 |
|------|:----:|------|
| `LLM_PROVIDER` | ✅ | `openai` 또는 `gemini` |
| `OPENAI_API_KEY` | OpenAI 사용 시 | [OpenAI](https://platform.openai.com) API 키 |
| `OPENAI_MODEL` | - | 기본 `gpt-4o` |
| `GEMINI_API_KEYS` | Gemini 사용 시 | 쉼표 구분 복수 키 (로테이션) |
| `GEMINI_MODEL` | - | 기본 `gemini-2.5-flash` |
| `REAL_ESTATE_API_KEY` | ✅ | 공공데이터포털 **Decoding** 키 (실거래가·건축물대장 공용) |
| `KAKAO_API_KEY` | ✅ | [카카오 개발자](https://developers.kakao.com) REST API 키 |
| `APP_HOST` | - | 기본 `0.0.0.0` |
| `APP_PORT` | - | 기본 `8000` |
| `APP_DEBUG` | - | 개발 시 `true` |
| `CORS_ORIGINS` | - | 쉼표 구분 허용 오리진, 기본 `*` (배포 시 Vercel 도메인 권장) |

### 프론트엔드 (`frontend/.env.local`)

| 변수 | 필수 | 설명 |
|------|:----:|------|
| `NEXT_PUBLIC_API_URL` | ✅ | 백엔드 URL (로컬: `http://localhost:8000`, 프로덕션: Render URL). rewrites 프록시에 사용 |
| `NEXT_PUBLIC_KAKAO_MAP_KEY` | 지도 사용 시 | 카카오맵 JavaScript 키 (지도 표시용) |
| `NEXT_PUBLIC_BACKEND_URL` | - | 등기부 파일 업로드 등 직접 백엔드 호출이 필요할 때 (미설정 시 `NEXT_PUBLIC_API_URL` 사용) |

---

## 🚀 시작하기

### 사전 요구사항

- **Python 3.11+**
- **Node.js 18+**
- **API 키**: OpenAI 또는 Gemini, 공공데이터포털 실거래가·건축물대장 Decoding 키, 카카오 REST API 키

### 설치 및 실행

```bash
# 1. 리포지토리 클론
git clone <repository-url>
cd project

# 2. 환경변수 설정
cp .env.example .env                    # 백엔드 키 입력
cp frontend/.env.local.example frontend/.env.local   # 프론트엔드 API URL 등

# 3. 백엔드 실행
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 4. 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
```

- 프론트: [http://localhost:3000](http://localhost:3000)
- 백엔드: [http://localhost:8000](http://localhost:8000). API 문서: `http://localhost:8000/docs`
- 프론트엔드는 `NEXT_PUBLIC_API_URL`로 백엔드를 호출합니다. 로컬에서는 `http://localhost:8000`으로 설정하면 Next의 rewrites를 통해 `/api/*` 요청이 백엔드로 프록시됩니다.

---

## 🧪 테스트

백엔드 점수 로직 단위 테스트:

```bash
# 프로젝트 루트에서
pip install pytest
pytest tests/ -v
```

- `tests/test_modules.py`: `calculate_jeonse_risk_score`, `score_to_grade`, `calculate_reliability_score` 경계값 및 조합 테스트.

---

## ☁️ 배포 가이드

### 1단계: 백엔드 → Render

1. [Render](https://render.com) → **New Web Service** → GitHub 리포 연결.
2. 설정:
   | 항목 | 값 |
   |------|-----|
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Environment | Python 3 |
3. 환경 변수 추가 (`.env.example` 참고): `LLM_PROVIDER`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `GEMINI_API_KEYS`, `GEMINI_MODEL`, `REAL_ESTATE_API_KEY`, `KAKAO_API_KEY`.
4. `CORS_ORIGINS`에 Vercel 프론트 도메인 입력 (예: `https://your-app.vercel.app`).

또는 리포 루트의 `render.yaml` Blueprint로 서비스 정의 후 Render 대시보드에서 동일하게 환경 변수만 설정.

### 2단계: 프론트엔드 → Vercel

1. [Vercel](https://vercel.com) → **New Project** → GitHub 리포 연결.
2. 설정:
   | 항목 | 값 |
   |------|-----|
   | Framework | Next.js |
   | Root Directory | `frontend` |
3. 환경 변수:
   - `NEXT_PUBLIC_API_URL` → Render 백엔드 URL (예: `https://safehome-api.onrender.com`)
   - `NEXT_PUBLIC_BACKEND_URL` → 동일 (파일 업로드 직접 호출용, 선택)
   - `NEXT_PUBLIC_KAKAO_MAP_KEY` → 카카오맵 JS 키

배포 후 프론트 도메인을 백엔드 `CORS_ORIGINS`에 반드시 추가하세요.

---

<div align="center">

**SafeHome** — 안전한 부동산 거래의 시작

Made with ❤️ for safer real estate transactions

</div>
