# RefServer 프로덕션 배포 가이드

## 🚀 리눅스 서버 배포 (Docker Hub 이미지 사용)

### 전제 조건
- Docker 및 Docker Compose 설치
- Ollama 설치 및 모델 준비 (별도 서버 또는 로컬)

### 1. 필요한 파일
```bash
# 이 파일만 서버에 복사하면 됩니다
docker-compose.prod.yml
```

### 2. 서버 설정

```bash
# 1. 작업 디렉토리 생성
mkdir refserver && cd refserver

# 2. docker-compose 파일 복사
# docker-compose.prod.yml을 현재 디렉토리에 복사

# 3. 데이터 디렉토리 생성
mkdir -p data

# 4. Ollama 모델 준비 (별도 서버에서)
ollama run llava        # OCR 품질 평가용
ollama run llama3.2     # 메타데이터 추출용
```

### 3. 환경 설정

**Ollama가 다른 서버에 있는 경우:**
```bash
# docker-compose.prod.yml에서 OLLAMA_HOST 수정
# - OLLAMA_HOST=your-ollama-server:11434
```

**로컬에 Ollama가 있는 경우:**
```bash
# 기본 설정 사용 (host.docker.internal:11434)
```

### 4. 서비스 시작
```bash
# 이미지 다운로드 및 서비스 시작
docker-compose -f docker-compose.prod.yml up -d

# 로그 확인
docker-compose -f docker-compose.prod.yml logs -f
```

### 5. 서비스 확인
```bash
# API 상태 확인
curl http://localhost:8000/health
curl http://localhost:8000/status

# 웹 브라우저에서 API 문서 확인
# http://your-server:8000/docs
```

## 🗂️ 사용되는 Docker 이미지

### RefServer 이미지
- **이미지**: `honestjung/refserver:latest`
- **크기**: ~21GB (BGE-M3 모델 포함)
- **포함 내용**:
  - FastAPI 서버
  - BGE-M3 임베딩 모델
  - OCR 도구 (ocrmypdf, Tesseract)
  - 모든 Python 의존성

### Layout Analysis 이미지  
- **이미지**: `honestjung/pdf-layout-custom:latest`
- **크기**: ~36GB (ML 모델 포함)
- **포함 내용**:
  - Huridocs Layout Analysis
  - LayoutLM 모델
  - 필요한 ML 의존성

## 🔧 서비스 관리

```bash
# 서비스 중지
docker-compose -f docker-compose.prod.yml down

# 서비스 재시작
docker-compose -f docker-compose.prod.yml restart

# 이미지 업데이트
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# 볼륨 및 데이터 백업
tar -czf refserver-backup.tar.gz data/
```

## 📊 필요한 서버 사양

### 최소 사양
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 100GB (이미지 + 데이터)

### 권장 사양  
- **CPU**: 8 cores
- **RAM**: 16GB
- **Storage**: 200GB SSD

## 🔐 보안 고려사항

```bash
# 방화벽 설정 (필요한 포트만 개방)
ufw allow 8000/tcp  # RefServer API
ufw allow 5000/tcp  # Layout Analysis (선택사항)

# SSL/TLS 설정은 별도 reverse proxy 사용 권장
# (Nginx, Traefik 등)
```

## 🚨 문제 해결

### Ollama 연결 문제
```bash
# Ollama 서버 확인
curl http://ollama-server:11434/api/tags

# RefServer 컨테이너에서 연결 테스트
docker exec refserver curl http://host.docker.internal:11434/api/tags
```

### Layout Analysis 연결 문제
```bash
# Layout 서비스 확인
curl http://localhost:5000/
docker logs huridocs-layout
```

### 데이터 손실 방지
```bash
# 정기 백업 스크립트 설정
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf "/backup/refserver_$DATE.tar.gz" data/
```