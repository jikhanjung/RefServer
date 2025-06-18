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
│   ├── embedding.py        # bge-m3 임베딩 처리 (페이지별)
│   ├── metadata.py         # LLM을 이용한 서지정보 추출
│   ├── layout.py           # huridocs layout API 호출 처리
│   ├── db.py               # SQLite 저장 및 질의
│   ├── admin.py            # Jinja2 기반 관리자 인터페이스
│   ├── auth.py             # 사용자 인증 및 보안
│   ├── models.py           # Peewee ORM 모델 정의
│   ├── init_db.py          # 데이터베이스 초기화 스크립트
│   ├── templates/          # Jinja2 HTML 템플릿
│   │   ├── base.html       # 기본 레이아웃
│   │   ├── login.html      # 관리자 로그인
│   │   ├── dashboard.html  # 관리자 대시보드
│   │   ├── papers.html     # 논문 관리 페이지
│   │   └── paper_detail.html # 논문 상세보기
│   ├── static/             # 정적 파일 (CSS, JS)
│   │   ├── css/admin.css   # 관리자 인터페이스 스타일
│   │   └── js/admin.js     # 관리자 인터페이스 스크립트
│   └── __init__.py
├── scripts/                # 유틸리티 스크립트
│   ├── detect_gpu.py       # GPU 감지 및 배포 모드 결정
│   └── start_refserver.py  # 자동 환경 감지 및 시작
├── data/                   # PDF, 이미지, DB 등 저장소
├── docker-compose.yml      # GPU 환경용 Docker Compose
├── docker-compose.cpu.yml  # CPU 전용 환경 Docker Compose
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

### 📄 비동기 처리 API (v0.1.6)
| Method | Endpoint         | 설명 |
|--------|------------------|------|
| POST   | `/upload`        | PDF 업로드 (즉시 job_id 반환) |
| GET    | `/job/{job_id}`  | 처리 상태 및 진행률 조회 |

### 📄 Core API Endpoints (하위 호환성)
| Method | Endpoint         | 설명 |
|--------|------------------|------|
| POST   | `/process`       | PDF 업로드 및 자동 처리 수행 (deprecated) |
| GET    | `/metadata/{id}` | 서지정보 및 OCR 품질 조회 |
| GET    | `/embedding/{id}`| 벡터 반환 (list of float) |
| GET    | `/layout/{id}`   | layout 결과 JSON 반환 |
| GET    | `/preview/{id}`  | 첫 페이지 이미지 반환 |
| GET    | `/paper/{id}`    | 논문 기본 정보 조회 |
| GET    | `/text/{id}`     | 추출된 텍스트 내용 반환 |
| GET    | `/download/{id}` | PDF 파일 다운로드 |
| GET    | `/search`        | 논문 검색 (제목, 저자 등) |
| GET    | `/stats`         | 시스템 통계 정보 |
| GET    | `/status`        | 서비스 상태 확인 |
| GET    | `/health`        | 헬스체크 엔드포인트 |

### 🔐 Admin Interface (`admin.py`)
| Method | Endpoint                    | 설명 |
|--------|-----------------------------|------|
| GET    | `/admin/login`              | 관리자 로그인 페이지 |
| POST   | `/admin/login`              | 관리자 로그인 처리 |
| GET    | `/admin/logout`             | 관리자 로그아웃 |
| GET    | `/admin/dashboard`          | 관리자 대시보드 |
| GET    | `/admin/papers`             | 논문 목록 및 관리 |
| GET    | `/admin/papers/{id}`        | 논문 상세 정보 |
| POST   | `/admin/papers/{id}/delete` | 논문 삭제 |
| GET    | `/admin/upload`             | PDF 업로드 폼 |
| GET    | `/admin/change-password`    | 패스워드 변경 페이지 |
| POST   | `/admin/change-password`    | 패스워드 변경 처리 |
| GET    | `/admin/page-embeddings`    | 페이지 임베딩 목록 |
| GET    | `/admin/page-embeddings/{id}` | 페이지 임베딩 상세 |

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

## ✅ 구현 완료 상태 (v0.1.0)

### 📁 구조 및 환경 - ✅ 완료
- [x] 프로젝트 디렉토리 및 기본 파일 구성
- [x] Dockerfile 작성 (FastAPI + ocrmypdf + bge-m3 + 다국어 Tesseract)
- [x] docker-compose.yml 작성 (FastAPI + Huridocs + 외부 Ollama 연동)
- [x] requirements.txt 및 requirements-test.txt 구성

### ⚙️ 기능 모듈 - ✅ 완료 (11개 모듈)
- [x] `models.py`: Peewee ORM 모델 (Paper, PageEmbedding, Embedding, Metadata, LayoutAnalysis, AdminUser)
- [x] `db.py`: 완전한 CRUD 인터페이스 + 자동 마이그레이션
- [x] `ocr.py`: ocrmypdf + 10개 언어 자동 감지 + 스마트 OCR
- [x] `ocr_quality.py`: LLaVA 기반 OCR 품질 평가 (via Ollama)
- [x] `embedding.py`: BGE-M3 페이지별 임베딩 생성 + 로컬 모델 지원
- [x] `layout.py`: Huridocs layout API 연동 + 구조 분석
- [x] `metadata.py`: 3단계 LLM 서지정보 추출 (구조화→단순→규칙 기반)
- [x] `admin.py`: Jinja2 기반 관리자 인터페이스 (로그인, 대시보드, 논문 관리)
- [x] `auth.py`: JWT 기반 사용자 인증 + bcrypt 비밀번호 해싱

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
- Ollama (외부 실행 필요)

### 자동 환경 감지 및 실행 (권장)

```bash
# GPU/CPU 환경 자동 감지 후 최적 모드로 실행
python scripts/start_refserver.py
```

### 수동 설치 및 실행

#### GPU 환경 (모든 기능 활성화)
1. **Ollama 모델 준비**
```bash
# 별도 터미널에서 Ollama 실행
ollama run llava        # OCR 품질 평가용 (GPU 필요)
ollama run llama3.2     # 메타데이터 추출용
```

2. **RefServer 실행**
```bash
docker-compose up --build
```

#### CPU 전용 환경 (핵심 기능만)
1. **Ollama 모델 준비**
```bash
# 메타데이터 추출용만 실행
ollama run llama3.2
```

2. **RefServer CPU 모드 실행**
```bash
docker-compose -f docker-compose.cpu.yml up --build
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
    
    **🎉 RefServer v0.1.0 구현 완료!**
    - 9개 핵심 모듈 + 12개 API 엔드포인트
    - 완전한 Docker 배포 + 종합 테스트 스위트
    - 프로덕션 준비 완료된 PDF 지능형 처리 파이프라인

    - **🔧 프로덕션 배포 최적화**
        - API 임포트 에러 수정 (상대 임포트 → 절대 임포트)
        - Docker 환경용 데이터베이스 경로 최적화 (/data/refserver.db)
        - 마이그레이션을 빌드 타임으로 이동하여 런타임 성능 향상
        - .gitignore 및 .dockerignore 최적화로 배포 파일 관리 개선
    
    - **🤖 BGE-M3 모델 통합**
        - Docker 빌드 시 BGE-M3 모델 자동 다운로드 (download_model.py)
        - 21GB 완전 자립형 Docker 이미지 생성
        - 런타임 모델 다운로드 제거로 초기 처리 시간 단축
        - 오프라인 환경 배포 지원
    
    - **🧪 테스트 환경 완성**
        - 크로스 플랫폼 PDF 생성 (Windows/Linux/macOS)
        - 테스트 검증 로직 개선 (다중 상태 코드 지원)
        - 100% 테스트 성공률 달성 (14/14 테스트 통과)
        - 중복 컨텐츠 감지 시스템 검증 완료
    
    - **🚀 Docker Hub 배포 준비**
        - `honestjung/refserver:latest` 태그 준비
        - 완전한 프로덕션 Docker 이미지
        - 모든 의존성 및 모델 포함된 standalone 배포

    **📊 최종 성능 메트릭:**
    - 테스트 성공률: 100% (14/14)
    - Docker 이미지 크기: 21GB (BGE-M3 포함)
    - 평균 PDF 처리 시간: 3-4분 (CPU 환경)
    - 지원 언어: 10개 (자동 감지)
    - API 엔드포인트: 12개 (완전 검증)

    - **🔧 Layout Analysis 서비스 수정**
        - Huridocs 포트 매핑 오류 발견 및 수정 (5000:5000 → 5000:5060)
        - Layout 서비스 내부 포트 5060 확인 및 환경변수 수정
        - Connection refused 에러 완전 해결
        - Layout Analysis 정상 작동 확인

- **2025-06-18**
    - **🔧 Docker 배포 구조 최적화**
        - DB 초기화 시점 변경: 빌드타임 → 런타임으로 이동
        - init_db.py를 루트에서 app/ 디렉토리로 재구성
        - 볼륨 마운트와 DB 초기화 순서 문제 해결
        - Dockerfile 간소화 (불필요한 COPY 제거)
        - Docker Compose 배포 시 호스트 /data 디렉토리에 정상 DB 생성 보장

    - **📄 페이지별 임베딩 시스템 구현**
        - **DB 스키마 확장**: PageEmbedding 모델 추가 (페이지별 임베딩 저장)
        - **텍스트 처리 개선**: extract_page_texts_from_pdf() - 페이지별 텍스트 추출
        - **임베딩 로직 재설계**: 
            - 기존: 텍스트 청킹 → 평균 임베딩
            - 신규: 페이지별 임베딩 → 문서 평균 임베딩
        - **배치 처리 최적화**: save_page_embeddings_batch() 페이지별 일괄 저장
        - **API 엔드포인트 확장**: 
            - GET /embedding/{doc_id}/pages - 모든 페이지 임베딩 조회
            - GET /embedding/{doc_id}/page/{page_num} - 특정 페이지 임베딩 조회
        - **파이프라인 통합**: Step 4를 "Page-level Embedding Generation"으로 변경
        - **마이그레이션 지원**: migrate.py에 PageEmbedding 모델 추가

    - **🔐 FastAPI Admin 관리자 시스템 구현**
        - **FastAPI Admin 통합**: 웹 기반 관리자 인터페이스 구축
        - **DB 기반 사용자 관리**: AdminUser 모델로 다중 관리자 계정 지원
        - **보안 강화**: 
            - bcrypt 해싱으로 안전한 비밀번호 저장
            - 세션 기반 인증 시스템
            - 계정 활성화/비활성화 관리
            - 슈퍼유저 권한 분리
        - **관리 기능**: 
            - Papers, Metadata, Embeddings, Layout Analysis 관리
            - 검색, 필터링, 페이지네이션 지원
            - CRUD 작업 (생성, 조회, 수정, 삭제)
        - **CLI 관리 도구**: manage_admin.py - 관리자 계정 생성/관리
        - **자동 초기화**: 기본 관리자 계정 자동 생성 (admin/admin123)
        - **접속 경로**: http://localhost:8000/admin

    - **🛠️ Jinja2 관리자 인터페이스 구현**
        - **FastAPI Admin 의존성 문제 해결**: aioredis TimeoutError 충돌로 FastAPI Admin 제거
        - **Jinja2 기반 관리자 시스템**: 
            - 경량화된 HTML 템플릿 기반 관리 인터페이스
            - Bootstrap 5 기반 반응형 디자인
            - JWT 인증 + 세션 쿠키 관리
        - **관리자 인터페이스 구성**: 
            - `/admin/login` - 관리자 로그인 페이지
            - `/admin/dashboard` - 통계 대시보드 (처리 현황, 서비스 상태)
            - `/admin/papers` - 논문 관리 (검색, CRUD, 상세보기)
            - `/admin/papers/{id}` - 논문 상세 정보 (메타데이터, 임베딩, 레이아웃)
        - **UI/UX 기능**: 
            - 실시간 처리 통계 (진행률 바, 상태 뱃지)
            - 논문 검색 및 필터링
            - 모달 기반 삭제 확인
            - 반응형 테이블 및 카드 레이아웃
        - **보안**: JWT 토큰 + HTTP-only 쿠키로 안전한 세션 관리
        - **정적 파일**: CSS/JS 최적화 및 CDN Bootstrap 활용
        - **접속 경로**: http://localhost:8000/admin

    **🎯 RefServer v0.1.3 Jinja2 관리자 인터페이스 완성!**
    - **의존성 최적화**: FastAPI Admin 제거로 aioredis 충돌 해결
    - **경량화**: Jinja2 템플릿으로 단순하고 빠른 관리 인터페이스
    - **사용자 친화적**: Bootstrap 기반 모던 UI/UX
    - **완전한 관리 기능**: 논문 CRUD + 통계 대시보드
    - **프로덕션 준비**: 보안 강화 및 최적화 완료

- **2025-06-18**
    - **🔒 관리자 인터페이스 보안 강화**
        - **패스워드 변경 기능**: `/admin/change-password` 페이지 추가
            - 현재 비밀번호 확인 및 새 비밀번호 검증
            - 클라이언트 사이드 비밀번호 강도 표시기
            - 보안을 위한 변경 후 자동 로그아웃
        - **세션 보안**: JWT 토큰 만료 시간 관리 및 안전한 쿠키 설정
        - **사용자 인증**: bcrypt 해시 기반 안전한 비밀번호 저장

    - **📊 페이지 임베딩 관리 시스템**
        - **페이지별 임베딩 지원**: BGE-M3 모델을 사용한 페이지 단위 벡터 생성
        - **PageEmbedding 모델**: 페이지별 텍스트, 벡터, 메타데이터 저장
        - **관리 인터페이스 확장**: 
            - `/admin/page-embeddings` - 페이지 임베딩 목록 및 통계
            - `/admin/page-embeddings/{id}` - 페이지별 상세 정보 및 텍스트 뷰어
        - **대시보드 통계**: 페이지 임베딩 진행률 및 전체 통계 표시
        - **데이터 시각화**: 텍스트 길이 분포, 처리 현황 등 상세 통계

    - **📤 PDF 업로드 인터페이스 개선**
        - **업로드 폼 페이지**: `/admin/upload` - 사용자 친화적인 PDF 업로드 인터페이스
            - 파일 검증 (PDF 전용, 50MB 크기 제한)
            - 처리 파이프라인 미리보기 (7단계 시각화)
            - 실시간 진행 상황 모달 (시뮬레이션)
        - **사용자 경험 개선**: 
            - 기존 원시 API 엔드포인트 대신 직관적인 웹 폼 제공
            - 파일 선택 시 동적 버튼 텍스트 변경
            - 업로드 진행 상황 및 단계별 상태 표시
        - **인터페이스 통합**: papers.html 내 업로드 링크를 새 폼으로 연결

    **🎯 RefServer v0.1.4 관리자 인터페이스 고도화!**
    - **보안 강화**: 패스워드 변경 및 세션 관리 개선
    - **페이지 임베딩**: 페이지별 벡터 생성 및 관리 시스템 완성
    - **사용자 경험**: 직관적인 PDF 업로드 인터페이스 제공
    - **완전한 관리 도구**: 논문 처리부터 분석까지 통합 관리 환경

    - **🖥️ GPU/CPU 적응형 배포 시스템**
        - **자동 GPU 감지**: `scripts/detect_gpu.py` - NVIDIA GPU 및 Docker 런타임 자동 감지
        - **조건부 서비스 활성화**: GPU 사용 불가 시 자동으로 CPU 전용 모드 전환
        - **서비스별 세분화 제어**:
            - **LLaVA (OCR 품질 평가)**: GPU 필요 - CPU 모드에서 비활성화
            - **Huridocs (레이아웃 분석)**: GPU 가속 권장 - CPU 모드에서 비활성화
            - **Llama 3.2 (메타데이터 추출)**: CPU 지원 - 모든 모드에서 활성화
            - **BGE-M3 (임베딩)**: CPU 지원 - 모든 모드에서 활성화
        - **CPU 전용 설정**: `docker-compose.cpu.yml` - GPU 없는 환경을 위한 최적화된 구성
        - **자동 시작 스크립트**: `scripts/start_refserver.py` - 환경 감지 후 적절한 모드로 자동 실행
        - **환경변수 기반 제어**: `LLAVA_ENABLED`, `HURIDOCS_LAYOUT_URL` 등으로 세밀한 제어

    - **🔧 Rule-based 메타데이터 추출 Fallback**
        - **패턴 기반 추출**: LLM 사용 불가 시 정규식 및 휴리스틱으로 기본 메타데이터 추출
        - **지원 필드**: 제목, 저자, 연도, DOI, 초록 등 핵심 서지정보
        - **견고한 처리**: 다양한 논문 형식에 대응하는 유연한 추출 로직

    **🎯 RefServer v0.1.5 GPU/CPU 적응형 배포 완성!**
    - **유연한 배포**: GPU 환경과 CPU 환경 모두 지원
    - **자동 최적화**: 환경에 따른 서비스 자동 조정
    - **견고한 Fallback**: 외부 서비스 장애 시에도 핵심 기능 유지
    - **개발자 친화적**: 환경 감지 및 배포 자동화로 설정 복잡성 제거

    - **🔄 비동기 PDF 처리 시스템 구현 (v0.1.6)**
        - **PDF 업로드와 처리 분리**: 업로드는 즉시 완료, 처리는 백그라운드에서 비동기 실행
        - **새로운 API 엔드포인트**:
            - `POST /upload` - PDF 업로드 및 즉시 job_id 반환
            - `GET /job/{job_id}` - 실시간 처리 상태 및 진행률 조회 (2초 간격 폴링)
        - **ProcessingJob 모델**: 비동기 작업 상태 추적용 새 데이터베이스 모델
            - job_id, status, progress_percentage, current_step 등 상세 추적
            - 처리 시작/완료 시간, 단계별 성공/실패 기록
        - **BackgroundProcessor 시스템**: FastAPI BackgroundTasks 기반 비동기 처리
            - 업로드 즉시 job 생성, 백그라운드에서 PDF 처리 파이프라인 실행
            - 단계별 진행률 업데이트 (0-100%) 및 실시간 상태 추적
        - **관리자 인터페이스 개선**: 
            - 업로드 폼을 새 비동기 API로 업데이트
            - 실시간 진행률 표시 및 2초 간격 상태 폴링
            - 처리 완료 후 자동으로 논문 상세 페이지로 리다이렉션
        - **하위 호환성 유지**: 기존 `/process` 엔드포인트 deprecated로 표시하되 정상 작동
        - **테스트 시스템 업데이트**: test_api.py에 비동기 워크플로우 테스트 추가
            - 새 API 엔드포인트 테스트 (`test_upload_pdf`, `test_job_status_polling`)
            - 기존 동기 API 호환성 테스트 (`test_process_pdf_legacy`)

    **🎯 RefServer v0.1.6 비동기 처리 시스템 완성!**
    - **사용자 경험 개선**: PDF 업로드 즉시 완료, 처리 과정 실시간 확인 가능
    - **성능 향상**: 업로드와 처리 분리로 응답성 대폭 개선
    - **확장성**: 백그라운드 처리로 다중 PDF 동시 처리 지원
    - **투명성**: 실시간 진행률 및 단계별 상태 추적으로 사용자 대기 시간 최소화
