# RefServer 종합 테스트 가이드 (v0.1.12)

RefServer의 모든 기능을 자동으로 테스트하고 검증하는 종합 가이드입니다.
**API + 백업 시스템 + 일관성 검증 + 관리자 시스템** - GPU/CPU 환경 자동 감지 + v0.1.12 엔터프라이즈 기능 전체 지원

## 📋 목차

- [개요](#개요)
- [자동화 테스트](#자동화-테스트)
- [수동 테스트 방법](#수동-테스트-방법)
- [성공 기준](#성공-기준)
- [예상 결과](#예상-결과)
- [고급 테스트 시나리오](#고급-테스트-시나리오)
- [트러블슈팅](#트러블슈팅)

---

## 개요

`test_api.py`는 RefServer의 모든 API 엔드포인트를 체계적으로 테스트하는 자동화 스크립트입니다.

### 🎯 테스트 범위
- **27개 API 엔드포인트** 전체 테스트 (비동기 처리 + 관리자 인터페이스 포함)
- **비동기 PDF 처리 워크플로우** - 업로드 즉시 응답 + 실시간 상태 추적
- **레거시 동기 처리** - 하위 호환성 검증
- **서비스 상태** 실시간 모니터링
- **오류 처리** 및 예외 상황 검증 (job 상태, 업로드 오류 포함)
- **성능 측정** 및 응답 시간 분석

### ✅ 테스트되는 엔드포인트

#### 🔄 비동기 처리 API (NEW in v0.1.6)
1. `POST /upload` - PDF 업로드 (즉시 job_id 반환)
2. `GET /job/{job_id}` - 처리 상태 및 진행률 실시간 조회

#### 📄 핵심 API 엔드포인트
3. `GET /health` - 헬스체크
4. `GET /status` - 서비스 상태
5. `POST /process` - PDF 처리 (레거시, deprecated)
6. `GET /paper/{doc_id}` - 논문 정보
7. `GET /metadata/{doc_id}` - 서지정보
8. `GET /embedding/{doc_id}` - 벡터 임베딩
9. `GET /layout/{doc_id}` - 레이아웃 분석
10. `GET /preview/{doc_id}` - 미리보기 이미지
11. `GET /text/{doc_id}` - 텍스트 내용
12. `GET /search` - 논문 검색
13. `GET /stats` - 시스템 통계

#### ⚠️ 오류 처리 테스트
14. **Invalid endpoints** - 404 오류 (job, paper, metadata 등)
15. **Upload errors** - 파일 없음, 잘못된 파일 타입 등

---

## 자동화 테스트

RefServer는 5개의 전문화된 테스트 스크립트를 제공합니다. 기본 설치 및 실행 방법은 [README.md](./README.md)를 참조하세요.

### 테스트 스크립트 개요
- **test_api_core.py**: 핵심 PDF 처리 (업로드, OCR, 임베딩, 메타데이터)
- **test_backup_system.py**: 백업, 일관성 검증, 재해 복구 (v0.1.12)
- **test_admin_system.py**: 관리자 인터페이스 및 권한 관리 (v0.1.12)
- **test_api.py**: 전체 API 엔드포인트 통합 테스트
- **test_ocr_language_detection.py**: 하이브리드 언어 감지 OCR

### 고급 테스트 옵션
```bash
# 특정 PDF 파일로 테스트
python test_api_core.py --pdf /path/to/complex_paper.pdf

# 원격 서버 테스트
python test_backup_system.py --url http://production-server:8060

# 상세 로그 모드
python test_admin_system.py --username admin --password secret --verbose

---

## 고급 테스트 시나리오

### 🧪 시나리오 1: GPU 환경 전체 기능 테스트
**목적**: GPU 가속 기능을 포함한 모든 기능 검증
```bash
# GPU 환경에서 실행 (docker-compose.yml)
python test_api.py
```
**검증 항목**:
- **🎮 GPU 기능**: LLaVA 품질 평가, Huridocs 레이아웃 분석
- **비동기 업로드**: 즉시 job_id 반환 (< 1초)
- **실시간 상태 추적**: 2초 간격 폴링으로 진행률 확인
- **LLM 기반 메타데이터**: 고품질 서지정보 추출
- **완전한 처리 파이프라인**: 7단계 모든 처리 수행
- 전체 API 엔드포인트 정상 동작 (17개 테스트)

**예상 결과**: 90-100% 성공률

### 🧪 시나리오 2: CPU 환경 핵심 기능 테스트
**목적**: GPU 없는 환경에서 핵심 기능 검증
```bash
# CPU 환경에서 실행 (docker-compose.cpu.yml)
python test_api.py
```
**검증 항목**:
- **🖥️ CPU 기능**: OCR, 임베딩, rule-based 메타데이터
- **비동기 업로드**: GPU와 동일한 업로드 성능
- **백그라운드 처리**: CPU 기반 처리 파이프라인
- **Fallback 처리**: GPU 기능 대신 대체 처리 수행
- **핵심 API**: 업로드, 상태 추적, 텍스트/임베딩 조회

**예상 결과**: 70-85% 성공률 (GPU 기능 제외)

### 🧪 시나리오 3: 실제 논문 처리 테스트
**목적**: 실제 학술 논문 처리 성능 확인
```bash
python test_api.py --pdf /path/to/real_paper.pdf
```
**검증 항목**:
- 복잡한 PDF 처리 능력
- OCR 품질
- 메타데이터 추출 정확도
- 레이아웃 분석 성능

### 🧪 시나리오 4: 서비스 부분 장애 시뮬레이션
**목적**: 외부 서비스 장애 시 동작 확인
```bash
# Ollama 서비스를 중단한 상태에서 테스트
python test_api.py
```
**검증 항목**:
- 기본 OCR 기능 유지
- 적절한 오류 메시지
- 부분 성공 시나리오

### 🧪 시나리오 5: 비동기 처리 성능 테스트
**목적**: 비동기 시스템의 성능 및 다중 처리 능력 확인
```bash
# 큰 PDF 파일로 비동기 처리 성능 테스트
python test_api.py --pdf large_document.pdf --timeout 300
```
**검증 항목**:
- **업로드 응답 시간**: 파일 크기와 무관하게 즉시 응답
- **처리 진행률 정확성**: 실제 처리 단계와 progress % 일치
- **백그라운드 처리 시간**: 전체 파이프라인 처리 시간 측정
- **오류 복구**: 처리 중 실패 시 적절한 오류 상태 반환

### 🧪 시나리오 6: 오류 처리 및 예외 상황
**목적**: 다양한 오류 상황에서의 시스템 안정성 확인
```bash
python test_api.py
```
**검증 항목**:
- **잘못된 job_id 조회**: 404 오류 적절히 반환
- **파일 없는 업로드**: 422 validation 오류
- **비PDF 파일 업로드**: 파일 타입 검증
- **타임아웃 상황**: 장시간 처리 중 상태 추적

---

## 예상 결과

### ✅ 정상 동작 시나리오

#### 🎮 GPU 환경 - 모든 서비스 정상 (최적 상태)
```
📊 Test Summary
   Total tests: 17
   Passed: 17 ✅
   Failed: 0 ❌
   Success rate: 100.0%
   Total time: 45.23s
   Deployment mode: GPU
   🎮 GPU Features: Quality assessment ✅, Layout analysis ✅, LLM metadata ✅
   🎉 Test PASSED for GPU mode
```
**특징**: 모든 GPU 가속 기능 + 비동기 처리 완벽 동작

#### 🖥️ CPU 환경 - 핵심 기능 정상 (예상 동작)
```
📊 Test Summary
   Total tests: 17
   Passed: 13 ✅     # 핵심 기능 정상
   Failed: 4 ❌      # GPU 전용 기능 제외
   Success rate: 76.5%
   Total time: 35.12s    # fallback 처리로 빠른 완료
   Deployment mode: CPU
   🖥️ CPU Features: Core processing ✅, Rule-based metadata ✅
   ⚠️ GPU Features: Quality assessment ❌, Layout analysis ❌
   🎉 Test PASSED for CPU mode
```
**특징**: 비동기 업로드 정상, GPU 기능 대신 fallback 처리 수행

#### ⚠️ 부분 장애 - 외부 서비스 일부 실패
```
📊 Test Summary
   Total tests: 17
   Passed: 11 ✅     # 기본 기능만 동작
   Failed: 6 ❌      # 외부 서비스 의존 기능 실패
   Success rate: 64.7%
   Total time: 25.15s    # 빠른 실패로 더 빠른 완료
```
**특징**: OCR, 임베딩 등 핵심 기능은 정상, LLM/GPU 서비스 장애

### 🔍 테스트 결과 분석

#### 환경별 성공률 해석 기준

##### 🎮 GPU 환경 기준
- **90-100%**: 🟢 우수 - 모든 GPU 기능 + 비동기 처리 정상
- **80-89%**: 🟡 양호 - 핵심 기능 정상, 일부 GPU 기능 제한
- **70-79%**: 🟠 주의 - 기본 처리는 가능하나 GPU 서비스 점검 필요
- **70% 미만**: 🔴 문제 - 시스템 전체 점검 필요

##### 🖥️ CPU 환경 기준
- **70-85%**: 🟢 우수 - CPU 모드 정상 동작 (GPU 기능 제외는 정상)
- **60-69%**: 🟡 양호 - 핵심 기능 동작, 일부 서비스 제한
- **50-59%**: 🟠 주의 - 기본 처리만 가능, 외부 서비스 점검 필요
- **50% 미만**: 🔴 문제 - 핵심 시스템 점검 필요

##### 📊 기능별 성공률 분석
| 기능 | GPU 환경 | CPU 환경 | 최소 환경 |
|------|---------|---------|-----------|
| **비동기 업로드** | ✅ | ✅ | ✅ |
| **OCR & 임베딩** | ✅ | ✅ | ✅ |
| **품질 평가** | ✅ | ❌ | ❌ |
| **레이아웃 분석** | ✅ | ❌ | ❌ |
| **LLM 메타데이터** | ✅ | ⚠️ | ❌ |
| **Rule-based 메타데이터** | ✅ | ✅ | ✅ |

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
❌ Cannot connect to http://localhost:8060
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
curl http://localhost:8060/health

# 서비스 상태만 확인
curl http://localhost:8060/status

# 수동 PDF 업로드 테스트
curl -X POST "http://localhost:8060/process" \
  -F "file=@test.pdf"
```

#### 네트워크 문제 진단
```bash
# 포트 사용 상태 확인
netstat -tlnp | grep 8060

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

### 🚀 처리 속도 개선 (비동기 처리 시스템)
1. **업로드 최적화**: 
   - **즉시 응답**: 파일 크기와 무관하게 < 1초 업로드 완료
   - **백그라운드 처리**: CPU 집약적 작업을 별도 스레드에서 실행
2. **하드웨어 최적화**:
   - **SSD 사용**: 디스크 I/O 성능 향상 (PDF 읽기/쓰기)
   - **메모리 증설**: BGE-M3 모델 로딩 속도 향상
   - **GPU 사용**: CUDA 지원 시 임베딩 생성 가속화
3. **다중 처리 능력**:
   - **동시 업로드**: 여러 PDF 파일 동시 처리 지원
   - **진행률 추적**: 실시간 상태 모니터링으로 사용자 경험 향상

### 🎯 정확도 향상
1. **고품질 PDF**: 스캔 품질이 좋은 문서 사용
2. **올바른 언어 설정**: Tesseract 언어 팩 확인
3. **외부 서비스 연동**: LLaVA, LLM 서비스 안정성 확보

### 📊 모니터링 지표 (비동기 처리 중심)
- **업로드 응답 시간**: PDF 업로드 API 응답 시간 (목표: < 1초)
- **처리 완료 시간**: 백그라운드 처리 전체 소요 시간
- **진행률 정확도**: 실제 처리 단계와 보고된 진행률의 일치도
- **동시 처리 능력**: 동시 처리 가능한 PDF 수량
- **Job 상태 정확성**: 처리 상태 전환의 정확성 (uploaded → processing → completed)
- **성공률**: 각 처리 단계별 성공률
- **리소스 사용량**: CPU, 메모리, 디스크 사용률
- **오류율**: 시간대별 오류 발생 패턴

---

## 🔧 수동 테스트 방법

### 1. 백업 시스템 API 테스트 (v0.1.12)

#### a) 백업 상태 확인
```bash
curl http://localhost:8060/admin/backup/status
```

#### b) 수동 백업 트리거
```bash
# SQLite 백업
curl -X POST -d "backup_type=snapshot&compress=true" \
     http://localhost:8060/admin/backup/trigger

# 통합 백업 (SQLite + ChromaDB)
curl -X POST -d "backup_type=snapshot&unified=true" \
     http://localhost:8060/admin/backup/trigger
```

#### c) 백업 검증
```bash
curl -X POST http://localhost:8060/admin/backup/verify/BACKUP_ID
```

### 2. 일관성 검증 API 테스트

#### a) 일관성 요약 확인
```bash
curl http://localhost:8060/admin/consistency/summary
```

#### b) 전체 일관성 검사
```bash
curl http://localhost:8060/admin/consistency/check
```

#### c) 자동 수정 (superuser 권한 필요)
```bash
curl -X POST http://localhost:8060/admin/consistency/fix
```

### 3. 재해 복구 시스템 테스트

#### a) 재해 복구 준비도 확인
```bash
curl http://localhost:8060/admin/disaster-recovery/status
```

### 4. 벡터 검색 API 테스트 (v0.1.10+)

#### a) 유사 문서 검색
```bash
curl http://localhost:8060/similar/PAPER_ID
```

#### b) 벡터 데이터베이스 통계
```bash
curl http://localhost:8060/vector/stats
```

### 5. 에러 핸들링 테스트

#### a) 잘못된 파일 업로드
```bash
# PDF가 아닌 파일 업로드 시도
curl -X POST -F "file=@not_a_pdf.txt" \
     http://localhost:8060/upload
# 예상 결과: 422 Unprocessable Entity
```

#### b) 대용량 파일 업로드 (크기 제한 확인)
```bash
# 100MB 이상의 대용량 파일 생성 및 업로드
dd if=/dev/zero of=large_test.pdf bs=1M count=101
curl -X POST -F "file=@large_test.pdf" \
     http://localhost:8060/upload
# 예상 결과: 413 Payload Too Large
```

---

## 📈 성공 기준

### 1. 테스트 통과 기준

#### GPU 모드 (전체 기능)
- **전체 테스트 성공률**: 90% 이상
- **핵심 기능**: OCR, 품질 평가, 레이아웃 분석, 메타데이터 추출 모두 정상
- **백업 시스템**: SQLite, ChromaDB, 통합 백업 모두 성공
- **일관성 검증**: 7가지 문제 유형 감지 및 수정 정상

#### CPU 모드 (핵심 기능)
- **전체 테스트 성공률**: 75% 이상
- **제한된 서비스**: 기본 OCR, 규칙 기반 메타데이터만 활성화
- **백업 시스템**: SQLite 백업 정상 (ChromaDB 제외)

#### 백업 시스템 (v0.1.12)
- **백업 생성**: SQLite, ChromaDB, 통합 백업 모두 성공
- **백업 검증**: 무결성 검사 통과
- **일관성 검사**: 7가지 문제 유형 정확 감지
- **재해 복구**: 준비도 점수 8/10 이상

### 2. 성능 기준

#### API 응답 시간
- **업로드 API**: 1초 미만 (즉시 job_id 반환)
- **상태 조회**: 100ms 미만
- **백업 트리거**: 5초 미만 (백그라운드 실행)

#### 처리 성능
- **PDF 처리**: 중간 크기 문서(10페이지) 3분 이내
- **백업 생성**: SQLite 30초, ChromaDB 60초 이내
- **일관성 검사**: 1000개 논문 기준 30초 이내

### 3. 안정성 기준

#### 에러 핸들링
- **잘못된 입력**: 적절한 4xx 에러 응답
- **서버 오류**: 5xx 에러 시 상세 로그 기록
- **백업 실패**: 실패 시 안전한 롤백

#### 자동 복구
- **일시적 문제**: 네트워크 오류 시 자동 재시도
- **일관성 문제**: 안전한 범위 내 자동 수정
- **백업 스케줄**: 자동 백업 스케줄링 정상 작동

### 4. 데이터 무결성 기준 (v0.1.12)

#### 백업 무결성
- **백업 검증**: SHA-256 체크섬 일치 100%
- **압축 무결성**: gzip 압축/해제 오류 없음
- **메타데이터**: 백업 메타정보 정확성

#### 일관성 검증
- **SQLite ↔ ChromaDB**: 논문 수 일치
- **임베딩 무결성**: 벡터 데이터 정합성
- **중복 감지**: 4층 중복 방지 시스템 정상

---

**RefServer 종합 테스트 가이드 v0.1.12** - 환경 적응형 테스트 + 백업 시스템 + 일관성 검증 + 관리자 시스템 포함 완전한 테스트 및 검증 가이드 ✅