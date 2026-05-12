# 🏠 AI 전세계약 가이드 시스템

## 📌 프로젝트 소개

<p align="center">
    <img width="749" height="497" alt="Image" src="https://github.com/user-attachments/assets/d2d31ccf-a941-4229-b584-0b9038bc80f8" />
    <img width="749" height="497" alt="Image" src="https://github.com/user-attachments/assets/b640ac3e-ee30-4e11-972a-042fc0b4d1a3" />
</p>

<br>

 전세 계약 경험이 부족한 전세입문자를 위해 안전하고 신뢰할 수 있는 전세 계약 환경을 제공하는 AI 기반 전세계약 가이드 시스템입니다.
공공데이터와 LLM 기반 문서 분석 기술을 활용하여 계약 과정에서 발생할 수 있는 전세사기, 허위 매물, 문서 간 불일치 위험 요소를 사전에 탐지하고, 사용자에게 계약 절차와 위험 정보를 직관적으로 제공합니다.

---

## 🎯 프로젝트 목표

* 전세 계약 과정의 복잡한 절차를 단계별로 안내
* 공공 문서 간 의미 불일치 자동 탐지
* 실거래가 및 전세가율 기반 위험도 분석 제공
* AI 챗봇 기반 전세 계약 정보 제공
* 전세사기 예방 및 사용자 의사결정 지원

---

# ⚙️ 시스템 아키텍처

<p align="center">
  <img width="1672" height="941" alt="Image" src="https://github.com/user-attachments/assets/20920fdf-b80c-4462-8498-724d6430b7d5" />
</p>

---

# 💻 기술 스택

## Frontend

* Flutter (Dart)

## Backend

* Python
* FastAPI
* Uvicorn

## AI / LLM

* LangChain
* GPT-4
* KoAlpaca (초기 실험 모델)

## Database

* PostgreSQL
* Chroma VectorDB

## Crawling / Data Processing

* Selenium
* Regex (정규표현식)

## API

* CODEF API
* 공공데이터포털 API
* 도로명주소 API

## Collaboration

* GitHub
* JCloud

---

# 🛠 주요 기능

## 1. 의미 불일치 탐지 및 위험 분석 시스템

등기부등본과 건축물대장 간 의미적 불일치를 자동 탐지하고, 이를 기반으로 전세사기 위험도를 분석하는 기능입니다.

<p align="center">
  <img width="1000" alt="Image" src="https://github.com/user-attachments/assets/217dccad-7806-44df-a8e9-7af561c9eb52" />
</p>

### ✔ 주요 기능

* CODEF API 기반 공공 문서 수집
* 정규표현식을 활용한 주요 계약 정보 추출
* LangChain 기반 Prompt Chain 구성
* GPT-4 기반 의미 불일치 탐지
* 위험도 분석 및 리포트 생성

### ✔ 분석 프로세스

| Chain            | 역할              |
| ---------------- | --------------- |
| extract_metadata | 계약 문서 주요 항목 추출  |
| compare_document | 문서 간 의미 불일치 탐지  |
| predict_risk     | 위험도 판단 및 리포트 생성 |

### ✔ 분석 대상 항목

* 소유자명
* 건물 용도
* 전용 면적
* 근저당 설정 여부
* 구조 유형

---

## 2. 실거래가 분석 시스템

사용자가 입력한 주소를 기반으로 실제 전세 거래 데이터를 수집·분석하여 현실적인 보증금 수준과 위험도를 제공합니다.

### ✔ 주요 기능

* 도로명주소 API 기반 법정동 코드 조회
* 공공데이터포털 전세 실거래가 API 연동
* 동일 단지 거래 데이터 자동 수집
* 최신 거래 데이터 우선 조회
* 거래 데이터 정제 및 통계 분석

### ✔ 제공 정보

* 평균 보증금
* 최저 / 최고 보증금
* 최다 거래 단지명
* 최다 거래 면적대
* 면적당 평균 보증금

---

## 3. 전세가율 기반 위험도 분석

전세가율 데이터를 기반으로 깡통전세 위험성을 분석하는 기능입니다.

### ✔ 주요 기능

* Selenium 기반 전세가율 데이터 크롤링
* 지역별 최근 3개월 / 1년 평균 전세가율 분석
* 사용자 입력 주소 기반 위험도 매칭
* 위험도 시각화 제공

### ✔ 위험도 기준

| 전세가율      | 위험도           |
| --------- | ------------- |
| 60% 이하    | 낮음            |
| 60% ~ 80% | 주의 필요         |
| 80% 이상    | 위험 (깡통전세 가능성) |

---

## 4. AI 챗봇 기반 전세 계약 가이드

전세 계약 초심자도 쉽게 계약 절차를 이해할 수 있도록 단계별 정보를 제공하는 챗봇 기능입니다.

### ✔ 주요 기능

* Flutter 기반 버튼 선택형 UI
* 단계별 계약 정보 제공
* 키워드 기반 FAQ 응답
* 자유 질문 입력 기능
* 말풍선 기반 채팅 UI 제공

### ✔ 챗봇 동작 방식

1. 사용자가 계약 단계 선택
2. 관련 키워드 목록 출력
3. 키워드 선택 시 설명 제공
4. 자유 질문 입력 가능

### ✔ 데이터 관리

* PostgreSQL 기반 keywords 테이블 관리
* JSON 기반 키워드 데이터 저장
* 중복 방지 로직 적용
* migrate_keywords.py 기반 데이터 마이그레이션

---


---

# 🚀 기대 효과

* 전세 계약 초심자의 정보 비대칭 문제 완화
* 공공 문서 기반 위험 탐지 자동화
* 전세사기 및 깡통전세 예방 지원
* AI 기반 계약 의사결정 보조 시스템 제공
* 실생활 문제 해결형 AI 서비스 구현

---

# 👨‍💻 담당 역할

* FastAPI 기반 백엔드 개발
* GPT-4 + LangChain 기반 의미 불일치 탐지 시스템 구현
* 공공데이터 API 연동
* 실거래가 분석 로직 구현
* 전세가율 기반 위험도 분석 기능 구현
* PostgreSQL 및 ChromaDB 데이터 관리
* JCloud 기반 협업 인프라 구축
* Flutter 연동 API 설계 및 JSON 응답 처리
