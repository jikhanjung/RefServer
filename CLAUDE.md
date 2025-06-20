# 📄 RefServer – Unified PDF Intelligence Pipeline

## 🎯 목적
RefServer는 과학 논문 PDF 파일을 입력받아 다음의 작업을 자동으로 수행하는 통합 처리 시스템입니다:
- **하이브리드 언어 감지 OCR** (텍스트 → LLaVA → 다중 OCR 샘플링)
- OCR 품질 평가 (LLaVA via Ollama)
- 텍스트 추출 및 임베딩 생성 (bge-m3)
- 서지정보 추출 (GPT 또는 llama 기반)
- PDF 레이아웃 분석 (via Huridocs)
- **ChromaDB 벡터 데이터베이스** 및 **4층 중복 방지**
- SQLite + ChromaDB 하이브리드 저장 및 API 제공

---

## 🗂️ 디렉토리 구조

```
RefServer/
├── docker-compose.yml
├── requirements.txt         # (루트로 이동)
├── app/
│   ├── main.py             # FastAPI 진입점
│   ├── pipeline.py         # 전체 처리 흐름
│   ├── ocr.py              # 하이브리드 언어감지 OCR (텍스트/LLaVA/다중OCR)
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

### 📄 비동기 처리 API (v0.1.6-0.1.7)
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

### 🛡️ Backup & Recovery (v0.1.12)
| Method | Endpoint                    | 설명 |
|--------|-----------------------------|------|
| GET    | `/admin/backup`             | 백업 관리 대시보드 |
| POST   | `/admin/backup/trigger`     | 수동 백업 실행 (full/incremental/snapshot/unified) |
| GET    | `/admin/backup/status`      | 백업 시스템 상태 조회 |
| GET    | `/admin/backup/history`     | 백업 이력 조회 |
| POST   | `/admin/backup/restore/{id}` | 백업 복구 (superuser 전용) |
| POST   | `/admin/backup/health-check` | 백업 건강 상태 체크 |
| POST   | `/admin/backup/verify/{id}` | 백업 무결성 검증 |

### ⚖️ Data Consistency (v0.1.12)
| Method | Endpoint                    | 설명 |
|--------|-----------------------------|------|
| GET    | `/admin/consistency`        | 일관성 관리 대시보드 |
| GET    | `/admin/consistency/check`  | 전체 일관성 검증 실행 |
| GET    | `/admin/consistency/summary` | 빠른 일관성 상태 조회 |
| POST   | `/admin/consistency/fix`    | 자동 일관성 문제 수정 (superuser 전용) |

### 🚨 Disaster Recovery (v0.1.12)
| Method | Endpoint                    | 설명 |
|--------|-----------------------------|------|
| GET    | `/admin/disaster-recovery/status` | 재해 복구 준비도 평가 |

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
- **ChromaDB**: 벡터 데이터베이스
- **APScheduler**: 백업 스케줄링 (v0.1.12)
- **Docker + Compose**: 컨테이너화 및 실행
- **requirements.txt**: 프로젝트 루트로 이동 (의존성 관리는 루트에서 일괄)

---

## ✅ 구현 완료 상태 (v0.1.12)

### 📁 구조 및 환경 - ✅ 완료
- [x] 프로젝트 디렉토리 및 기본 파일 구성
- [x] Dockerfile 작성 (FastAPI + ocrmypdf + bge-m3 + 다국어 Tesseract)
- [x] docker-compose.yml 작성 (FastAPI + Huridocs + 외부 Ollama 연동)
- [x] requirements.txt 및 requirements-test.txt 구성

### ⚙️ 기능 모듈 - ✅ 완료 (14개 모듈)
- [x] `models.py`: Peewee ORM 모델 (Paper, PageEmbedding, Embedding, Metadata, LayoutAnalysis, AdminUser)
- [x] `db.py`: 완전한 CRUD 인터페이스 + 자동 마이그레이션
- [x] `ocr.py`: ocrmypdf + 10개 언어 자동 감지 + 스마트 OCR
- [x] `ocr_quality.py`: LLaVA 기반 OCR 품질 평가 (via Ollama)
- [x] `embedding.py`: BGE-M3 페이지별 임베딩 생성 + 로컬 모델 지원
- [x] `layout.py`: Huridocs layout API 연동 + 구조 분석
- [x] `metadata.py`: 3단계 LLM 서지정보 추출 (구조화→단순→규칙 기반)
- [x] `admin.py`: Jinja2 기반 관리자 인터페이스 (로그인, 대시보드, 논문 관리)
- [x] `auth.py`: JWT 기반 사용자 인증 + bcrypt 비밀번호 해싱
- [x] `backup.py`: SQLite/ChromaDB 통합 백업 시스템 + APScheduler (v0.1.12)
- [x] `consistency_check.py`: 데이터베이스 일관성 검증 + 자동 복구 (v0.1.12)
- [x] `vector_db.py`: ChromaDB 벡터 데이터베이스 클라이언트 (v0.1.10+)

### 🔁 파이프라인 - ✅ 완료
- [x] `pipeline.py`: 7단계 통합 처리 파이프라인
- [x] 내용 기반 중복 감지 (임베딩 벡터 해시)
- [x] 부분 실패 지원 + 상세 진행 상황 추적
- [x] 예외 처리, 로깅, 임시 파일 정리 완료

### 🧪 API - ✅ 완료 (25개+ 엔드포인트)
- [x] `main.py`: FastAPI 서버 + Pydantic 모델 + CORS
- [x] `POST /process`: PDF 업로드 및 전체 파이프라인 처리
- [x] `GET /health`, `/status`: 헬스체크 및 서비스 상태
- [x] `GET /paper/{id}`, `/metadata/{id}`, `/embedding/{id}`: 데이터 조회
- [x] `GET /layout/{id}`, `/text/{id}`, `/preview/{id}`: 구조 및 콘텐츠
- [x] `GET /download/{id}`: PDF 파일 다운로드
- [x] `GET /search`, `/stats`: 검색 및 시스템 통계
- [x] **백업 관리 API (v0.1.12)**: 7개 엔드포인트 (트리거, 상태, 이력, 복구, 검증)
- [x] **일관성 검증 API (v0.1.12)**: 4개 엔드포인트 (체크, 요약, 수정)
- [x] **재해 복구 API (v0.1.12)**: 준비도 평가 엔드포인트

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
이에 따라, RefServer는 **OCR 또는 본문에서 생성된 임베딩 벡터의 평균값을 이용하여 SHA-256 해시**를 계산하고, 이를 해당 논문의 **내용 기반 고유 ID (content_id)**로 사용합니다.

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

3. **관리자 계정 설정**
```bash
# 기본 관리자 계정 생성 (admin/admin123)
docker exec -it refserver python manage_admin.py ensure-default

# 새 관리자 계정 생성
docker exec -it refserver python manage_admin.py create myadmin --email admin@example.com --superuser

# 관리자 계정 목록 확인
docker exec -it refserver python manage_admin.py list

# 비밀번호 변경
docker exec -it refserver python manage_admin.py passwd myadmin
```

4. **관리자 인터페이스 접속**
- 관리자 로그인: http://localhost:8060/admin
- 기본 계정: admin / admin123

5. **API 테스트**
```bash
# 모든 API 엔드포인트 테스트
python test_api.py

# 특정 PDF 파일로 테스트
python test_api.py --pdf /path/to/paper.pdf
```

6. **API 문서 확인**
- Swagger UI: http://localhost:8060/docs
- ReDoc: http://localhost:8060/redoc

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

## 📄 문서화

프로젝트의 상세한 변경 내역과 향후 개발 계획은 별도 문서로 관리됩니다:

- **[CHANGELOG.md](./CHANGELOG.md)**: 모든 버전별 상세 변경 내역
- **[ROADMAP.md](./ROADMAP.md)**: 향후 개발 계획 및 로드맵

현재 상태: **v0.1.12** - 엔터프라이즈급 백업 시스템, 재해 복구, 데이터베이스 일관성 검증 완비
