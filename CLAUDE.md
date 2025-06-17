# 📄 RefServer – Unified PDF Intelligence Pipeline

## 🎯 목적
RefServer는 과학 논문 PDF 파일을 입력받아 다음의 작업을 자동으로 수행하는 통합 처리 시스템입니다:
- OCR 및 품질 평가 (LLaVA via Ollama)
- 텍스트 추출 및 임베딩 생성 (bge-m3)
- 서지정보 추출 (GPT 또는 llama 기반)
- PDF 레이아웃 분석 (via Huridocs)
- SQLite 기반 저장 및 API 제공

---

## 🗂️ 디렉토리 구조

```
RefServer/
├── docker-compose.yml
├── requirements.txt         # (루트로 이동)
├── app/
│   ├── main.py             # FastAPI 진입점
│   ├── pipeline.py         # 전체 처리 흐름
│   ├── ocr.py              # ocrmypdf 및 이미지 추출
│   ├── ocr_quality.py      # llava를 이용한 OCR 품질 판단
│   ├── embedding.py        # bge-m3 임베딩 처리
│   ├── metadata.py         # LLM을 이용한 서지정보 추출
│   ├── layout.py           # huridocs layout API 호출 처리
│   ├── db.py               # SQLite 저장 및 질의
│   └── __init__.py
├── data/                   # PDF, 이미지, DB 등 저장소
└── README.md
```

---

## 🔁 전체 처리 흐름 (`pipeline.py`)
1. 업로드된 PDF 저장
2. OCR 수행 (필요시) – `ocrmypdf` 사용
3. OCR 품질 평가 – LLaVA (Ollama)
4. 텍스트 추출
5. 임베딩 생성 – bge-m3
6. 레이아웃 분석 – Huridocs API 호출
7. 메타데이터 추출 – GPT or llama
8. SQLite에 저장
9. 처리 요약 반환

---

## 🔧 API 구조 (`main.py`)

| Method | Endpoint         | 설명 |
|--------|------------------|------|
| POST   | `/process`       | PDF 업로드 및 자동 처리 수행 |
| GET    | `/metadata/{id}` | 서지정보 및 OCR 품질 조회 |
| GET    | `/embedding/{id}`| 벡터 반환 (list of float) |
| GET    | `/layout/{id}`   | layout 결과 JSON 반환 |
| GET    | `/preview/{id}`  | 첫 페이지 이미지 반환 |

---

## 🧩 사용 기술

- **FastAPI**: REST API 서버
- **ocrmypdf**: OCR 처리
- **Tesseract**: 다국어 OCR backend
- **PyMuPDF/pdf2image**: PDF → 텍스트/이미지
- **Ollama + LLaVA**: OCR 품질 평가 및 LLM 기반 메타데이터 추출
- **Huridocs layout server**: PDF 구조 분석
- **bge-m3**: 임베딩 모델
- **SQLite**: 경량 DB
- **Docker + Compose**: 컨테이너화 및 실행
- **requirements.txt**: 프로젝트 루트로 이동 (의존성 관리는 루트에서 일괄)

---

## ✅ 구현 완료 상태 (v1.0.0)

### 📁 구조 및 환경 - ✅ 완료
- [x] 프로젝트 디렉토리 및 기본 파일 구성
- [x] Dockerfile 작성 (FastAPI + ocrmypdf + bge-m3 + 다국어 Tesseract)
- [x] docker-compose.yml 작성 (FastAPI + Huridocs + 외부 Ollama 연동)
- [x] requirements.txt 및 requirements-test.txt 구성

### ⚙️ 기능 모듈 - ✅ 완료 (9개 모듈)
- [x] `models.py`: Peewee ORM 모델 (Paper, Embedding, Metadata, LayoutAnalysis)
- [x] `db.py`: 완전한 CRUD 인터페이스 + 자동 마이그레이션
- [x] `ocr.py`: ocrmypdf + 10개 언어 자동 감지 + 스마트 OCR
- [x] `ocr_quality.py`: LLaVA 기반 OCR 품질 평가 (via Ollama)
- [x] `embedding.py`: BGE-M3 임베딩 생성 + 로컬 모델 지원
- [x] `layout.py`: Huridocs layout API 연동 + 구조 분석
- [x] `metadata.py`: 3단계 LLM 서지정보 추출 (구조화→단순→규칙 기반)

### 🔁 파이프라인 - ✅ 완료
- [x] `pipeline.py`: 7단계 통합 처리 파이프라인
- [x] 내용 기반 중복 감지 (임베딩 벡터 해시)
- [x] 부분 실패 지원 + 상세 진행 상황 추적
- [x] 예외 처리, 로깅, 임시 파일 정리 완료

### 🧪 API - ✅ 완료 (12개 엔드포인트)
- [x] `main.py`: FastAPI 서버 + Pydantic 모델 + CORS
- [x] `POST /process`: PDF 업로드 및 전체 파이프라인 처리
- [x] `GET /health`, `/status`: 헬스체크 및 서비스 상태
- [x] `GET /paper/{id}`, `/metadata/{id}`, `/embedding/{id}`: 데이터 조회
- [x] `GET /layout/{id}`, `/text/{id}`, `/preview/{id}`: 구조 및 콘텐츠
- [x] `GET /download/{id}`: PDF 파일 다운로드
- [x] `GET /search`, `/stats`: 검색 및 시스템 통계

### 🧪 테스트 및 배포 도구 - ✅ 완료
- [x] `test_api.py`: 전체 API 자동 테스트 스크립트
- [x] `download_model.py`: BGE-M3 모델 로컬 다운로드
- [x] `migrate.py`: 데이터베이스 마이그레이션 유틸리티

### 📄 문서화 - ✅ 완료
- [x] README.md: 완전한 프로젝트 문서
- [x] CLAUDE.md: 프로젝트 가이드 및 변경 로그
- [x] API_TESTING_GUIDE.md: API 테스트 가이드

---

## 🔐 Unique Paper ID (내용 기반 고유 식별자)

논문 PDF는 동일한 제목과 저자를 갖더라도 포맷이 다를 수 있으므로, 단순한 해시나 DOI만으로는 고유성을 보장하기 어렵습니다.  
이에 따라, Paper Alchemist는 **OCR 또는 본문에서 생성된 임베딩 벡터의 평균값을 이용하여 SHA-256 해시**를 계산하고, 이를 해당 논문의 **내용 기반 고유 ID (content_id)**로 사용합니다.

```python
import hashlib
import numpy as np

def compute_sha256_from_vector(vec: list[float]) -> str:
    byte_vec = np.array(vec, dtype=np.float32).tobytes()
    return hashlib.sha256(byte_vec).hexdigest()
```

이 `content_id`는 SQLite의 `papers` 테이블에 저장되어, **논문의 실질적인 중복 여부**를 판단하는 기준으로 활용됩니다.

---

---

## 🚀 시작하기

### 전제 조건
- Docker & Docker Compose
- Ollama (외부 실행 필요, `llava` 및 `llama3.2` 모델 설치)

### 설치 및 실행

1. **모델 다운로드**
```bash
# BGE-M3 임베딩 모델 다운로드
python download_model.py
```

2. **Ollama 모델 준비**
```bash
# 별도 터미널에서 Ollama 실행
ollama run llava        # OCR 품질 평가용
ollama run llama3.2     # 메타데이터 추출용
```

3. **RefServer 실행**
```bash
docker-compose up --build
```

4. **API 테스트**
```bash
# 모든 API 엔드포인트 테스트
python test_api.py

# 특정 PDF 파일로 테스트
python test_api.py --pdf /path/to/paper.pdf
```

5. **API 문서 확인**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📌 주의 사항

### 서비스 의존성
- **데이터베이스**: SQLite (자동 초기화)
- **Ollama**: 외부 실행 필요 (`host.docker.internal:11434`)
- **Huridocs**: Docker 컨테이너로 자동 실행
- **BGE-M3**: 로컬 모델 사용 (컨테이너 내 포함)

### 파일 저장 구조
```
/data/
├── pdfs/           # 처리된 PDF 파일
├── images/         # 첫 페이지 미리보기 이미지
├── temp/           # 임시 처리 파일 (자동 정리)
└── refserver.db    # SQLite 데이터베이스
```

### 성능 고려사항
- PDF 처리 시간: 1-3분 (문서 크기에 따라)
- 메모리 사용량: ~2-4GB (BGE-M3 모델 포함)
- 디스크 공간: 처리된 PDF 및 이미지 저장

---

## 📅 Changelog

- **2025-06-17**
    - **🏗️ 프로젝트 초기 설정**
        - 프로젝트 디렉토리(app/, data/) 및 주요 파일 구조 생성
        - requirements.txt를 루트로 이동 및 의존성 명시
        - docker-compose.yml, README.md, 각 모듈의 기본 파일/주석 추가
        - CLAUDE.md에 changelog 섹션 신설
    
    - **🐳 Docker 환경 구축**
        - Dockerfile 작성 (FastAPI + ocrmypdf + BGE-M3 + 다국어 Tesseract)
        - docker-compose.yml에 Huridocs와 Ollama 연동 설정 추가
        - BGE-M3 모델 로컬 다운로드 및 Docker 이미지 포함
    
    - **🗄️ 데이터베이스 설계 및 구현**
        - Peewee ORM 선택 (PostgreSQL 마이그레이션 고려)
        - models.py: 4개 테이블 (Paper, Embedding, Metadata, LayoutAnalysis)
        - db.py: 완전한 CRUD 인터페이스 + 자동 마이그레이션
        - 내용 기반 고유 ID 시스템 (임베딩 벡터 해시)
    
    - **🔍 OCR 및 품질 평가 시스템**
        - ocr.py: ocrmypdf + 10개 언어 자동 감지 + 스마트 OCR
        - ocr_quality.py: LLaVA 기반 품질 평가 (via Ollama)
        - 첫 페이지 이미지 추출 및 품질 점수 생성
    
    - **🧠 임베딩 및 AI 처리**
        - embedding.py: BGE-M3 모델 + 로컬 모델 지원
        - 텍스트 청킹 및 배치 처리로 긴 문서 지원
        - 싱글톤 패턴으로 메모리 효율성 확보
    
    - **📐 레이아웃 분석 및 메타데이터 추출**
        - layout.py: Huridocs PDF 레이아웃 분석 API 연동
        - metadata.py: 3단계 추출 시스템 (구조화 LLM → 단순 LLM → 규칙 기반)
        - 견고한 검증 및 데이터 정리 메커니즘
    
    - **🔗 통합 파이프라인**
        - pipeline.py: 7단계 처리 파이프라인 구현
        - 내용 기반 중복 감지 시스템
        - 부분 실패 지원 + 상세 진행 상황 추적
        - 외부 서비스 장애에 대한 우아한 성능 저하
    
    - **🌐 FastAPI 서버 및 API**
        - main.py: 12개 엔드포인트 완전 구현
        - Pydantic 모델로 요청/응답 검증
        - 파일 업로드 처리 + 백그라운드 정리
        - CORS 지원 + 자동 API 문서
    
    - **🧪 테스트 및 도구**
        - test_api.py: 종합 API 테스트 스크립트
        - 자동 테스트 PDF 생성 (reportlab)
        - 성능 메트릭 및 상세 실패 리포팅
        - download_model.py: 오프라인 배포용 모델 다운로드
    
    - **📚 문서화 완료**
        - README.md: 완전한 프로젝트 가이드 (아키텍처, 설치, 사용법)
        - API_TESTING_GUIDE.md: 종합 API 테스트 가이드
        - CLAUDE.md: 최신 구현 상태 반영
    
    **🎉 RefServer v1.0.0 구현 완료!**
    - 9개 핵심 모듈 + 12개 API 엔드포인트
    - 완전한 Docker 배포 + 종합 테스트 스위트
    - 프로덕션 준비 완료된 PDF 지능형 처리 파이프라인
