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

## ✅ TODO (작업 우선순위 기준)

### 📁 구조 및 환경
- [x] 프로젝트 디렉토리 및 기본 파일 구성
- [x] Dockerfile 작성 (FastAPI + ocrmypdf + bge-m3)
- [x] docker-compose.yml 작성 (FastAPI + Huridocs + 외부 Ollama 연동)

### ⚙️ 기능 모듈
- [ ] `ocr.py`: ocrmypdf 및 언어 자동 감지 처리
- [ ] `ocr_quality.py`: 첫 페이지 이미지 → LLaVA 호출 → 품질 판단
- [ ] `embedding.py`: 텍스트 → 벡터 임베딩 (bge-m3)
- [ ] `layout.py`: Huridocs layout API 호출 및 결과 파싱
- [ ] `metadata.py`: 텍스트 → LLM 서지 추출 (via Ollama)
- [ ] `db.py`: SQLite 테이블 생성 및 CRUD

### 🔁 파이프라인
- [ ] `pipeline.py`: 위 단계들을 연결하여 하나의 process_pdf(doc_id, file) 구성
- [ ] 예외 처리, 로깅, 임시 파일 정리 등 추가

### 🧪 API
- [ ] `main.py`: FastAPI 서버 및 `/process` endpoint 구현
- [ ] `/metadata/{doc_id}` 등 조회 API 구현
- [ ] `/layout/{doc_id}` layout 구조 JSON 반환

### 📄 기타
- [x] README 작성
- [x] CLAUDE.md 정리 완료 ✅

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

## 📌 주의 및 팁

- 모든 임시/출력 파일은 `data/` 하위에 저장
- Doc ID는 `uuid4()`를 사용하여 생성
- Ollama는 Docker 외부에서 미리 실행되어 있어야 함 (`llava` 모델 미리 다운로드)
- Huridocs layout 서버는 별도 Docker 컨테이너로 사전 실행 필요
- 추후 PostgreSQL + pgvector로 전환 가능성을 염두에 두고 구조 설계

---

## 📅 Changelog

- **2024-06-17**
    - 프로젝트 디렉토리(app/, data/) 및 주요 파일(main.py 등) 생성
    - requirements.txt를 루트로 이동 및 의존성 명시
    - docker-compose.yml, README.md, 각 모듈의 기본 파일/주석 추가
    - CLAUDE.md에 changelog 섹션 신설 및 최신 작업 내역 반영
    - **구조 및 환경 설정 완료**: Dockerfile 작성 (다국어 Tesseract, bge-m3 포함), docker-compose.yml에 Huridocs와 Ollama 연동 설정 추가
