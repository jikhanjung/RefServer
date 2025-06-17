# RefServer

과학 논문 PDF를 자동 처리하는 통합 파이프라인 서버입니다.

## 기능

- **OCR 처리**: ocrmypdf + Tesseract 다국어 지원
- **품질 평가**: LLaVA를 통한 OCR 품질 판단
- **임베딩 생성**: bge-m3 모델 사용
- **레이아웃 분석**: Huridocs layout API
- **메타데이터 추출**: LLM 기반 서지정보 추출
- **통합 저장**: SQLite 기반 데이터 관리

## 빠른 시작

### 전제 조건
- Docker & Docker Compose
- Ollama (외부 실행 필요, llava 모델 설치)

### 실행

```bash
# Ollama 실행 (별도 터미널)
ollama run llava

# RefServer 실행
docker-compose up --build
```

서버는 `http://localhost:8000`에서 실행됩니다.

## 디렉토리 구조

```
RefServer/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── app/
│   ├── main.py
│   ├── pipeline.py
│   ├── ocr.py
│   ├── ocr_quality.py
│   ├── embedding.py
│   ├── metadata.py
│   ├── layout.py
│   └── db.py
├── data/                   # PDF, 이미지, DB 저장소
└── README.md
```

## API 엔드포인트

| Method | Endpoint         | 설명 |
|--------|------------------|------|
| POST   | `/process`       | PDF 업로드 및 자동 처리 |
| GET    | `/metadata/{id}` | 서지정보 및 OCR 품질 조회 |
| GET    | `/embedding/{id}`| 벡터 임베딩 반환 |
| GET    | `/layout/{id}`   | 레이아웃 분석 결과 |
| GET    | `/preview/{id}`  | 첫 페이지 이미지 |

## 개발 상태

✅ **환경 설정 완료**
- [x] Docker 컨테이너 구성
- [x] 외부 서비스 연동 (Huridocs, Ollama)
- [x] 기본 프로젝트 구조

🚧 **개발 중**
- [ ] 기능 모듈 구현
- [ ] API 엔드포인트 구현
- [ ] 통합 파이프라인 구성