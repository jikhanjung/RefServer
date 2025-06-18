# RefServer API 테스트 가이드

RefServer API의 모든 엔드포인트를 자동으로 테스트하고 검증하는 종합 가이드입니다.

## 📋 목차

- [개요](#개요)
- [테스트 스크립트 설치](#테스트-스크립트-설치)
- [기본 사용법](#기본-사용법)
- [고급 사용법](#고급-사용법)
- [테스트 시나리오](#테스트-시나리오)
- [예상 결과](#예상-결과)
- [트러블슈팅](#트러블슈팅)

---

## 개요

`test_api.py`는 RefServer의 모든 API 엔드포인트를 체계적으로 테스트하는 자동화 스크립트입니다.

### 🎯 테스트 범위
- **12개 API 엔드포인트** 전체 테스트
- **PDF 처리 파이프라인** 전체 플로우 검증
- **서비스 상태** 실시간 모니터링
- **오류 처리** 및 예외 상황 검증
- **성능 측정** 및 응답 시간 분석

### ✅ 테스트되는 엔드포인트
1. `GET /health` - 헬스체크
2. `GET /status` - 서비스 상태
3. `POST /process` - PDF 처리 (핵심 기능)
4. `GET /paper/{doc_id}` - 논문 정보
5. `GET /metadata/{doc_id}` - 서지정보
6. `GET /embedding/{doc_id}` - 벡터 임베딩
7. `GET /layout/{doc_id}` - 레이아웃 분석
8. `GET /preview/{doc_id}` - 미리보기 이미지
9. `GET /text/{doc_id}` - 텍스트 내용
10. `GET /search` - 논문 검색
11. `GET /stats` - 시스템 통계
12. **오류 처리** - 404, 500 등 예외 상황

---

## 테스트 스크립트 설치

### 1. 의존성 설치
```bash
# 테스트 전용 의존성 설치
pip install -r requirements-test.txt

# 또는 개별 설치
pip install requests reportlab
```

### 2. 실행 권한 부여
```bash
chmod +x test_api.py
```

### 3. RefServer 실행 확인
```bash
# Docker Compose로 RefServer 실행
docker-compose up -d

# 서버 상태 확인 (수동)
curl http://localhost:8000/health
```

---

## 기본 사용법

### 🚀 빠른 테스트
```bash
# 기본 테스트 실행 (localhost:8000)
python test_api.py
```

### 📊 실행 결과 예시
```
[12:34:56] INFO: 🚀 Starting RefServer API Tests
[12:34:56] INFO: ==================================================
[12:34:56] INFO: Testing health check endpoint...
[12:34:56] PASS: ✅ Health Check - PASSED (200)
[12:34:56] INFO:    Service status: healthy

[12:34:57] INFO: Testing service status endpoint...
[12:34:57] PASS: ✅ Service Status - PASSED (200)
[12:34:57] INFO:    Database: ✅
[12:34:57] INFO:    Quality Assessment: ❌  
[12:34:57] INFO:    Layout Analysis: ✅
[12:34:57] INFO:    Metadata Extraction: ❌

[12:34:57] INFO: Testing PDF processing endpoint...
[12:34:57] INFO:    Created test PDF: /tmp/test_paper.pdf
[12:34:57] INFO:    Uploading PDF: test_paper.pdf
[12:35:42] PASS: ✅ PDF Processing - PASSED (200)
[12:35:42] INFO:    Document ID: 550e8400-e29b-41d4-a716-446655440000
[12:35:42] INFO:    Success: True
[12:35:42] INFO:    Processing time: 45.23s
[12:35:42] INFO:    Steps completed: 6
[12:35:42] INFO:    Steps failed: 0
[12:35:42] INFO:    Using doc_id 550e8400-e29b-41d4-a716-446655440000 for subsequent tests

[12:35:43] INFO: Testing paper info endpoint...
[12:35:43] PASS: ✅ Paper Info - PASSED (200)
[12:35:43] INFO:    Filename: test.pdf
[12:35:43] INFO:    OCR Quality: good|score:75|confidence:85
[12:35:43] INFO:    Text length: 156

[12:35:44] INFO: Testing metadata endpoint...
[12:35:44] PASS: ✅ Metadata - PASSED (200)
[12:35:44] INFO:    Title: Test Academic Paper
[12:35:44] INFO:    Authors: 2 found
[12:35:44] INFO:    Year: 2024
[12:35:44] INFO:    Journal: Test Journal of Computer Science

[12:36:15] INFO: ==================================================
[12:36:15] INFO: 📊 Test Summary
[12:36:15] INFO:    Total tests: 12
[12:36:15] INFO:    Passed: 11 ✅
[12:36:15] INFO:    Failed: 1 ❌
[12:36:15] INFO:    Success rate: 91.7%
[12:36:15] INFO:    Total time: 78.45s
[12:36:15] INFO:    Test document ID: 550e8400-e29b-41d4-a716-446655440000
```

---

## 고급 사용법

### 🔧 커스텀 서버 URL
```bash
# 다른 서버에서 실행 중인 RefServer 테스트
python test_api.py --url http://192.168.1.100:8000

# 포트가 다른 경우
python test_api.py --url http://localhost:9000
```

### 📄 특정 PDF 파일 사용
```bash
# 실제 학술 논문으로 테스트
python test_api.py --pdf /path/to/research_paper.pdf

# 복잡한 PDF로 성능 테스트
python test_api.py --pdf /path/to/complex_document.pdf
```

### ⏱️ 타임아웃 설정
```bash
# 큰 PDF 파일을 위한 긴 타임아웃 (120초)
python test_api.py --timeout 120

# 빠른 테스트를 위한 짧은 타임아웃 (10초)
python test_api.py --timeout 10
```

### 🔄 조합 사용 예시
```bash
# 원격 서버의 실제 PDF로 종합 테스트
python test_api.py \
  --url http://production-server:8000 \
  --pdf /data/papers/nature_2024.pdf \
  --timeout 180
```

---

## 테스트 시나리오

### 🧪 시나리오 1: 기본 시스템 검증
**목적**: RefServer의 기본 동작 확인
```bash
python test_api.py
```
**검증 항목**:
- 서버 응답성
- 기본 PDF 처리 기능
- 데이터베이스 연동
- API 엔드포인트 정상 동작

### 🧪 시나리오 2: 실제 논문 처리 테스트
**목적**: 실제 학술 논문 처리 성능 확인
```bash
python test_api.py --pdf /path/to/real_paper.pdf
```
**검증 항목**:
- 복잡한 PDF 처리 능력
- OCR 품질
- 메타데이터 추출 정확도
- 레이아웃 분석 성능

### 🧪 시나리오 3: 서비스 부분 장애 시뮬레이션
**목적**: 외부 서비스 장애 시 동작 확인
```bash
# Ollama 서비스를 중단한 상태에서 테스트
python test_api.py
```
**검증 항목**:
- 기본 OCR 기능 유지
- 적절한 오류 메시지
- 부분 성공 시나리오

### 🧪 시나리오 4: 성능 벤치마크
**목적**: 시스템 성능 한계 확인
```bash
# 큰 PDF 파일로 성능 테스트
python test_api.py --pdf large_document.pdf --timeout 300
```
**검증 항목**:
- 처리 시간 측정
- 메모리 사용량
- 응답 시간 분석

---

## 예상 결과

### ✅ 정상 동작 시나리오

#### 모든 서비스 정상 (최적 상태)
```
📊 Test Summary
   Total tests: 12
   Passed: 12 ✅
   Failed: 0 ❌
   Success rate: 100.0%
   Total time: 65.23s
```

#### 외부 서비스 일부 장애 (정상 대응)
```
📊 Test Summary
   Total tests: 12
   Passed: 9 ✅     # 핵심 기능은 동작
   Failed: 3 ❌     # LLaVA, LLM 관련 기능만 실패
   Success rate: 75.0%
   Total time: 45.12s
```

### 🔍 테스트 결과 분석

#### 성공률별 상태 해석
- **90-100%**: 🟢 우수 - 모든 기능 정상 동작
- **70-89%**: 🟡 양호 - 핵심 기능 정상, 일부 고급 기능 제한
- **50-69%**: 🟠 주의 - 기본 기능은 동작하나 점검 필요
- **50% 미만**: 🔴 문제 - 시스템 점검 필요

#### 처리 시간 기준
- **< 60초**: 🟢 빠름 - 최적 성능
- **60-120초**: 🟡 보통 - 정상 범위
- **120-300초**: 🟠 느림 - 성능 최적화 고려
- **> 300초**: 🔴 매우 느림 - 시스템 점검 필요

### 📋 상세 결과 예시

#### PDF 처리 결과 분석
```json
{
  "doc_id": "550e8400-e29b-41d4-a716-446655440000",
  "success": true,
  "processing_time": 45.23,
  "steps_completed": ["save_paper", "ocr", "embedding", "layout"],
  "steps_failed": ["quality_assessment", "metadata"],
  "warnings": [
    "Quality assessment service unavailable",
    "Metadata extraction service unavailable"
  ],
  "data": {
    "ocr": {
      "text_length": 15420,
      "language": "en",
      "page_count": 8,
      "ocr_performed": true
    },
    "embedding": {
      "dimension": 1024,
      "content_id": "a7b9c3d2e1f4..."
    },
    "layout": {
      "page_count": 8,
      "total_elements": 245,
      "element_types": {
        "text": 189,
        "figure": 4,
        "table": 2
      }
    }
  }
}
```

---

## 트러블슈팅

### ❌ 일반적인 오류 및 해결책

#### 1. 연결 오류
```
❌ Cannot connect to http://localhost:8000
   Make sure RefServer is running with: docker-compose up
```
**해결책**:
```bash
# RefServer 실행 상태 확인
docker-compose ps

# 서비스 재시작
docker-compose down && docker-compose up -d

# 로그 확인
docker-compose logs refserver
```

#### 2. PDF 처리 타임아웃
```
❌ PDF processing timed out (5 minutes)
```
**해결책**:
```bash
# 타임아웃 늘리기
python test_api.py --timeout 300

# 더 작은 PDF로 테스트
python test_api.py --pdf small_document.pdf
```

#### 3. 외부 서비스 오류
```
❌ Quality Assessment: Unavailable
❌ Metadata Extraction: Unavailable
```
**해결책**:
```bash
# Ollama 서비스 확인
ollama list
ollama run llava
ollama run llama3.2

# 서비스 상태 직접 확인
curl http://localhost:11434/api/tags
```

#### 4. 메모리 부족
```
❌ BGE-M3 model loading failed: Out of memory
```
**해결책**:
```bash
# Docker 메모리 한계 증가
# docker-compose.yml에서 메모리 설정 조정

# 시스템 메모리 확인
free -h
docker stats
```

### 🔧 디버깅 팁

#### 상세 로그 확인
```bash
# RefServer 로그 실시간 모니터링
docker-compose logs -f refserver

# 특정 시간 범위 로그
docker-compose logs --since="10m" refserver
```

#### 개별 API 테스트
```bash
# 헬스체크만 테스트
curl http://localhost:8000/health

# 서비스 상태만 확인
curl http://localhost:8000/status

# 수동 PDF 업로드 테스트
curl -X POST "http://localhost:8000/process" \
  -F "file=@test.pdf"
```

#### 네트워크 문제 진단
```bash
# 포트 사용 상태 확인
netstat -tlnp | grep 8000

# Docker 네트워크 확인
docker network ls
docker network inspect refserver_default
```

### 📞 지원 및 보고

테스트 관련 문제가 지속되면:

1. **로그 수집**: `docker-compose logs refserver > refserver.log`
2. **시스템 정보**: `docker-compose ps`, `docker stats`
3. **테스트 결과**: `test_api.py` 전체 출력
4. **환경 정보**: OS, Docker 버전, 메모리 용량

---

## 📈 성능 최적화 가이드

### 🚀 처리 속도 개선
1. **SSD 사용**: 디스크 I/O 성능 향상
2. **메모리 증설**: BGE-M3 모델 로딩 속도 향상
3. **GPU 사용**: CUDA 지원 시 임베딩 생성 가속화

### 🎯 정확도 향상
1. **고품질 PDF**: 스캔 품질이 좋은 문서 사용
2. **올바른 언어 설정**: Tesseract 언어 팩 확인
3. **외부 서비스 연동**: LLaVA, LLM 서비스 안정성 확보

### 📊 모니터링 지표
- **응답 시간**: API 엔드포인트별 평균 응답 시간
- **성공률**: 각 처리 단계별 성공률
- **리소스 사용량**: CPU, 메모리, 디스크 사용률
- **오류율**: 시간대별 오류 발생 패턴

---

**RefServer API Testing Guide v0.1.0** - 완전한 API 테스트 및 검증 가이드 ✅