<div align="center">

# 🏠 SafeHome

**AI 기반 부동산 매물 신뢰도 분석 및 전세사기 위험 탐지 시스템**

[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-412991?logo=openai&logoColor=white)](https://openai.com/)
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
- [시작하기](#-시작하기)
- [배포 가이드](#-배포-가이드)

---

## 🎯 프로젝트 개요

### 배경

> 2023년 전세사기 피해자 수 약 **1만 5천명**, 피해 금액 약 **1조원 이상**  
> 허위·과장 매물 비율이 전체 온라인 매물의 약 **15~20%** 로 추정

등기부등본 등 전문 지식 부족으로 일반인의 사기 판별이 어려운 구조적 문제를 해결하기 위해,  
부동산 매물 텍스트의 **허위·과장 표현을 AI로 자동 탐지**하고 **전세사기 위험도를 분석**하여 종합 리포트를 제공합니다.

### 기대 효과

| | 효과 | 설명 |
|:---:|------|------|
| 🔍 | **정보 비대칭 해소** | 비전문가도 매물의 위험 요소를 쉽게 파악 |
| 🛡️ | **전세사기 사전 예방** | 깡통전세, 다중 임대 등 사기 패턴 사전 경고 |
| ✅ | **거래 안전성 향상** | 등기부등본 자동 해석 및 체크리스트 제공 |

---

## ✨ 주요 기능

### 🔎 매물 검색 (직방 API)
- 지역/주소 키워드 검색
- 원룸, 오피스텔, 빌라 매물 실시간 조회
- 전세/월세/매매 필터링

### 📝 매물 분석
- **URL 스크래핑** — 네이버 부동산, 직방, 다방 링크에서 매물 정보 자동 추출
- **도로명주소 검색** — 카카오 주소 API 연동
- **면적 자동 변환** — ㎡ ↔ 평 실시간 변환
- **가격 단위 표시** — 30000 → 3억 자동 표시

### 🤖 AI 종합 분석
- **허위·과장 표현 탐지** — 과장, 오해 유발, 미끼 가격, 정보 누락 탐지
- **실거래가 시세 비교** — 국토교통부 API 기반, 최근 1년 실거래 내역
- **전세사기 위험도 산출** — 전세가율 + 등기부등본 + 시세 분석 결합
- **주변 시설 거리 검증** — "도보 5분 지하철역" 등 실제 거리 확인
- **종합 신뢰도 리포트** — 0~100점 점수 + 위험 등급 + 체크리스트

### 📊 매물 비교
- 분석된 매물 비교함 저장
- 항목별 나란히 비교

---

## 🏗️ 시스템 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│               Frontend (Next.js + Tailwind CSS)              │
│                                                              │
│    [ 매물 검색 ]  [ 매물 분석 ]  [ 분석 결과 ]  [ 매물 비교 ] │
│                         Vercel                               │
└─────────┬───────────────▲────────────────────▲───────────────┘
          │  API Proxy    │   (rewrites)       │
┌─────────▼───────────────┴────────────────────┴───────────────┐
│                     Backend (FastAPI)                         │
│                          Render                              │
│                                                              │
│    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│    │ 텍스트   │ │ 정보     │ │ 시세     │ │ 전세사기     │  │
│    │ 분석     │ │ 추출     │ │ 검증     │ │ 위험 분석    │  │
│    └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────────┘  │
└─────────┼────────────┼────────────┼────────────┼─────────────┘
          │            │            │            │
   ┌──────▼────────────▼──┐  ┌─────▼────┐  ┌───▼────────────┐
   │      LLM API         │  │ 실거래가 │  │  카카오맵 API  │
   │ (OpenAI / Gemini)    │  │   API    │  │ (Geocode/Map)  │
   └──────────────────────┘  └──────────┘  └────────────────┘
```

---

## 🛠️ 기술 스택

| 구분 | 기술 |
|------|------|
| **Frontend** | Next.js 16 · TypeScript · Tailwind CSS v4 |
| **Backend** | Python 3.11+ · FastAPI · Pydantic v2 |
| **AI / LLM** | OpenAI GPT-4o-mini (기본) · Google Gemini 2.5 Flash |
| **외부 API** | 국토교통부 실거래가 · 카카오맵 REST · 직방 비공식 API |
| **배포** | Vercel (Frontend) · Render (Backend) |

---

## 📐 전세사기 위험도 산출 기준

### 점수 산출 규칙

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
| **압류/가압류** | 없음 / 있음 | +0 / +30 |
| **신탁등기** | 없음 / 있음 | +0 / +20 |
| **매물 텍스트** | 정상 / 과장 / 허위 의심 | +0 / +10 / +20 |

### 위험 등급

| 점수 | 등급 | 설명 |
|:----:|:----:|------|
| 0~20 | 🟢 **안전** | 특별한 위험 요소 없음 |
| 21~40 | 🟡 **주의** | 일부 확인 필요 |
| 41~60 | 🟠 **경고** | 전문가 상담 권장 |
| 61~100 | 🔴 **위험** | 전세사기 가능성 높음, 거래 재고 권장 |

---

## 📡 API 명세

| Method | Endpoint | 설명 |
|:------:|----------|------|
| `POST` | `/api/analyze` | 매물 종합 분석 |
| `POST` | `/api/analyze/text` | 매물 텍스트만 분석 |
| `POST` | `/api/analyze/registry` | 등기부등본 분석 |
| `POST` | `/api/analyze/registry/file` | 등기부등본 파일(이미지/PDF) 분석 |
| `POST` | `/api/scrape-listing` | URL에서 매물 정보 스크래핑 |
| `GET` | `/api/market-price` | 실거래가 시세 조회 |
| `GET` | `/api/geocode` | 주소 → 좌표 변환 |
| `GET` | `/api/zigbang/search` | 직방 지역 키워드 검색 |
| `GET` | `/api/zigbang/listings` | 직방 매물 목록 조회 |
| `GET` | `/api/zigbang/detail/:id` | 직방 매물 상세 |
| `GET` | `/api/health` | 서버 상태 확인 |

---

## 📁 프로젝트 구조

```
safehome/
├── 📄 README.md
├── 📄 requirements.txt              # Python 의존성
├── 📄 render.yaml                   # Render 배포 Blueprint
├── 📄 .env.example                  # 백엔드 환경변수 템플릿
│
├── 🐍 app/                          # FastAPI 백엔드
│   ├── main.py                      # 진입점 + 라우터
│   ├── config.py                    # 환경변수 설정
│   ├── models/
│   │   └── schemas.py               # Pydantic 스키마
│   ├── modules/
│   │   ├── text_analyzer.py         # 허위·과장 표현 탐지
│   │   ├── info_extractor.py        # 핵심 정보 추출
│   │   ├── market_comparator.py     # 시세 교차 검증
│   │   ├── jeonse_analyzer.py       # 전세사기 위험 분석
│   │   └── report_generator.py      # 종합 리포트 생성
│   ├── services/
│   │   ├── llm_service.py           # LLM API (OpenAI / Gemini)
│   │   ├── real_estate_api.py       # 국토교통부 실거래가
│   │   ├── kakao_map_service.py     # 카카오맵 REST API
│   │   ├── listing_scraper.py       # URL 매물 스크래핑
│   │   ├── zigbang_api.py           # 직방 비공식 API
│   │   └── location_verifier.py     # 주변 시설 거리 검증
│   └── utils/
│       └── scoring.py               # 점수 계산 로직
│
├── ⚛️ frontend/                      # Next.js 프론트엔드
│   ├── next.config.ts               # API 프록시 rewrites
│   ├── vercel.json                  # Vercel 설정
│   ├── .env.local.example           # 프론트 환경변수 템플릿
│   └── src/
│       ├── app/
│       │   ├── layout.tsx           # 루트 레이아웃
│       │   ├── page.tsx             # 메인 페이지 (탭 구조)
│       │   └── globals.css
│       ├── components/
│       │   ├── listing-form.tsx     # 매물 입력 폼 + URL 스크래핑
│       │   ├── analysis-report.tsx  # AI 분석 결과 표시
│       │   ├── zigbang-search.tsx   # 직방 매물 검색
│       │   ├── comparison-view.tsx  # 매물 비교함
│       │   ├── score-ring.tsx       # 신뢰도 점수 링
│       │   └── risk-badge.tsx       # 위험 등급 뱃지
│       └── lib/
│           ├── api.ts               # FastAPI 연동 클라이언트
│           └── types.ts             # TypeScript 타입 정의
│
└── 🧪 tests/
    └── test_modules.py              # 테스트
```

---

## 🚀 시작하기

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- API 키: OpenAI (또는 Gemini), 국토교통부 실거래가, 카카오맵

### 설치 및 실행

```bash
# 1. 리포지토리 클론
git clone https://github.com/wrtn-edu-sch-bootcamp/20233506-Personal-Project.git
cd 20233506-Personal-Project

# 2. 환경변수 설정
cp .env.example .env                              # 백엔드 키 입력
cp frontend/.env.local.example frontend/.env.local # 프론트 키 입력

# 3. 백엔드 실행
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# 4. 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
```

> 또는 동시 실행: `npm install && npm run dev` (루트에서)

---

## ☁️ 배포 가이드

### 1단계: 백엔드 → Render

1. [Render](https://render.com) → **New Web Service** → GitHub 리포 연결
2. 설정:
   | 항목 | 값 |
   |------|-----|
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Environment | Python 3 |
3. 환경변수 추가 (`.env.example` 참조)
4. `CORS_ORIGINS` → Vercel 도메인 입력

### 2단계: 프론트엔드 → Vercel

1. [Vercel](https://vercel.com) → **New Project** → GitHub 리포 연결
2. 설정:
   | 항목 | 값 |
   |------|-----|
   | Framework | Next.js |
   | Root Directory | `frontend` |
3. 환경변수 추가:
   - `NEXT_PUBLIC_API_URL` → Render 백엔드 URL
   - `NEXT_PUBLIC_KAKAO_MAP_KEY` → 카카오맵 JS 키

---

<div align="center">

**SafeHome** — 안전한 부동산 거래의 시작

Made with ❤️ for safer real estate transactions

</div>
