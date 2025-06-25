# RefServer Batch Testing Guide

이 가이드는 RefServer의 배치 업로드 테스트 방법을 설명합니다.

## 🚀 빠른 시작

### 1. 전체 테스트 실행 (권장)
```bash
cd tests
./run_full_test.sh
```

### 2. 특정 포트로 테스트
```bash
./run_full_test.sh --url http://localhost:8060
```

### 3. 테스트 후 자동 정리
```bash
./run_full_test.sh --cleanup
```

## 📋 테스트 종류

### A. PDF 생성 및 배치 업로드 테스트
```bash
# Python 스크립트 직접 실행
python3 test_batch_upload.py

# 다른 서버 URL 사용
python3 test_batch_upload.py --url http://localhost:8060

# 테스트 후 파일 정리
python3 test_batch_upload.py --cleanup
```

**테스트 내용:**
- 22개의 다양한 테스트 PDF 생성 (언어별, 유형별)
- 모든 PDF를 서버에 업로드
- 처리 상태 모니터링
- API 엔드포인트 테스트
- 성공률 및 상세 결과 리포트

### B. 개별 테스트 스크립트

#### 1. 핵심 API 테스트
```bash
python3 test_api_core.py
```

#### 2. 백업 시스템 테스트
```bash
python3 test_backup_system.py
```

#### 3. 관리자 시스템 테스트
```bash
python3 test_admin_system.py
```

#### 4. OCR 언어 감지 테스트
```bash
python3 test_ocr_language_detection.py
```

#### 5. 전체 API 테스트
```bash
python3 test_api.py
```

## 📁 테스트 파일 구조

### 생성되는 테스트 PDF
```
tests/test_papers/
├── paleontology_paper_en.pdf         # 영어 일반 논문
├── paleontology_paper_ko.pdf         # 한국어 논문
├── paleontology_paper_jp.pdf         # 일본어 논문
├── paleontology_paper_zh.pdf         # 중국어 논문
├── paleontology_theropod_en.pdf      # 특정 유형 논문들
├── paleontology_trilobite_en.pdf
├── ...
├── paleontology_paper_en_no_text.pdf # OCR 테스트용 (텍스트 레이어 없음)
└── ...
```

### 테스트 결과 파일
```
tests/
├── test_results_20250623_142530.json # 상세 테스트 결과
├── test_results_20250623_143012.json
└── ...
```

## 🔧 테스트 환경 설정

### 전제 조건
1. **RefServer 실행 중**:
   ```bash
   # GPU 모드
   docker-compose up
   
   # CPU 모드
   docker-compose -f docker-compose.cpu.yml up
   ```

2. **Python 의존성 설치**:
   ```bash
   pip install requests
   ```

3. **Ollama 모델 준비** (메타데이터 추출용):
   ```bash
   ollama run llama3.2
   ```

### 선택적 서비스
- **LLaVA** (OCR 품질 평가): `ollama run llava`
- **Huridocs** (레이아웃 분석): Docker Compose에 포함됨

## 📊 테스트 결과 해석

### 성공률 기준
- **90% 이상**: 모든 시스템이 정상 작동 ✅
- **70-89%**: 대부분 정상, 일부 문제 있음 ⚠️
- **70% 미만**: 심각한 문제 발생 ❌

### 일반적인 실패 원인
1. **업로드 실패**: 서버 연결 문제
2. **처리 실패**: OCR, 임베딩, 또는 메타데이터 추출 오류
3. **API 테스트 실패**: 엔드포인트 응답 문제

## 🎉 성공적인 테스트 예시

```
╔════════════════════════════════════════════════════════════╗
║                     Test Suite Complete!                   ║
╚════════════════════════════════════════════════════════════╝

Duration: 245.67 seconds

PDF Generation:
  - Files created: 22

Upload Results:
  - Successful: 22
  - Failed: 0

Processing Results:
  - Completed: 22
  - Failed: 0

API Tests:
  - Passed: 18
  - Failed: 0

Overall Success Rate: 100.0%

✓ All tests completed successfully! 🎉
```