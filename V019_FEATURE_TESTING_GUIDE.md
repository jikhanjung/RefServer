# RefServer v0.1.9 기능 테스트 가이드

## 🎯 개요

RefServer v0.1.9에서 새로 추가된 기능들을 검증하고 테스트하는 방법을 안내합니다.

### 🆕 새로운 기능
1. **비동기 처리 에러 핸들링 강화** - 네트워크 타임아웃, 재시도 메커니즘, 복구 로직
2. **성능 모니터링 시스템** - Job 처리 시간 메트릭, 리소스 사용량 모니터링  
3. **동시 처리 제한 및 큐 관리** - 최대 동시 Job 수 제한, 우선순위 시스템
4. **관리자 인터페이스 모니터링** - 성능, 큐, 시스템 모니터링 대시보드
5. **파일 업로드 보안 강화** - 파일 검증, 크기 제한, 악성 파일 차단, 속도 제한

---

## 🧪 자동 테스트 실행

### 1. 종합 기능 테스트
```bash
# RefServer 서버가 실행 중인 상태에서
python test_v019_features.py

# 상세 로그와 함께 실행
python test_v019_features.py --verbose

# 결과를 JSON 파일로 저장
python test_v019_features.py --output test_results.json

# 다른 서버 URL로 테스트
python test_v019_features.py --url http://your-server:8000
```

### 2. 테스트 결과 해석
```bash
# 성공 예시
📊 Tests: 8/8 passed
📈 Success Rate: 100.0%
🏆 Overall: PASS

🔧 Feature Status:
   ✅ Async Error Handling
   ✅ Performance Monitoring
   ✅ Queue Management
   ✅ Concurrent Processing
   ✅ Priority Queue
   ✅ System Metrics
   ✅ Export Functionality
   ✅ Security Validation

💡 Recommendations:
   • All v0.1.9 features are working correctly!
```

---

## 🔧 수동 테스트 방법

### 1. 성능 모니터링 API 테스트

#### a) 성능 통계 조회
```bash
curl http://localhost:8000/performance/stats
```

#### b) 시스템 메트릭 조회
```bash
curl http://localhost:8000/performance/system
```

#### c) Job 성능 메트릭 조회
```bash
curl http://localhost:8000/performance/jobs
```

#### d) 성능 데이터 내보내기
```bash
# JSON 형식으로 내보내기
curl http://localhost:8000/performance/export?format=json > performance.json

# CSV 형식으로 내보내기
curl http://localhost:8000/performance/export?format=csv > performance.csv
```

### 2. 큐 관리 시스템 테스트

#### a) 큐 상태 확인
```bash
curl http://localhost:8000/queue/status
```

#### b) 우선순위가 있는 PDF 업로드
```bash
# 높은 우선순위로 업로드
curl -X POST -F "file=@test.pdf" -F "priority=high" \
     http://localhost:8000/upload-priority

# 긴급 우선순위로 업로드  
curl -X POST -F "file=@test.pdf" -F "priority=urgent" \
     http://localhost:8000/upload-priority

# 일반 우선순위로 업로드
curl -X POST -F "file=@test.pdf" -F "priority=normal" \
     http://localhost:8000/upload-priority
```

#### c) 큐에서 Job 취소
```bash
curl -X POST http://localhost:8000/queue/cancel/JOB_ID
```

### 3. 에러 핸들링 테스트

#### a) 잘못된 파일 업로드 (에러 핸들링 확인)
```bash
# PDF가 아닌 파일 업로드 시도
curl -X POST -F "file=@not_a_pdf.txt" \
     http://localhost:8000/upload-priority
# 예상 결과: 400 Bad Request
```

#### b) 잘못된 우선순위 설정
```bash
curl -X POST -F "file=@test.pdf" -F "priority=invalid" \
     http://localhost:8000/upload-priority
# 예상 결과: 400 Bad Request
```

#### c) 존재하지 않는 Job 취소
```bash
curl -X POST http://localhost:8000/queue/cancel/non-existent-job
# 예상 결과: 400 또는 404
```

### 4. 파일 업로드 보안 테스트

#### a) 보안 시스템 상태 확인
```bash
curl http://localhost:8000/security/status
```

#### b) 유효한 PDF 업로드 (보안 통과 확인)
```bash
curl -X POST -F "file=@valid_test.pdf" \
     http://localhost:8000/upload
# 예상 결과: 200 OK (보안 검증 통과)
```

#### c) 잘못된 파일 형식 업로드 (보안 차단 확인)
```bash
# 텍스트 파일을 PDF로 위장하여 업로드
echo "This is not a PDF" > fake.pdf
curl -X POST -F "file=@fake.pdf" \
     http://localhost:8000/upload
# 예상 결과: 400 Bad Request (보안 차단)

# .txt 파일 직접 업로드
curl -X POST -F "file=@test.txt" \
     http://localhost:8000/upload
# 예상 결과: 400 Bad Request (확장자 차단)
```

#### d) 대용량 파일 업로드 (크기 제한 확인)
```bash
# 100MB 이상의 대용량 파일 생성 및 업로드
dd if=/dev/zero of=large_test.pdf bs=1M count=101
curl -X POST -F "file=@large_test.pdf" \
     http://localhost:8000/upload
# 예상 결과: 400 Bad Request 또는 413 Payload Too Large
```

#### e) 속도 제한 테스트 (Rate Limiting)
```bash
#!/bin/bash
# 빠른 연속 업로드로 속도 제한 확인
for i in {1..10}; do
    curl -X POST -F "file=@test.pdf" \
         http://localhost:8000/upload &
done
wait
# 예상 결과: 일부 요청은 성공(200), 일부는 속도 제한(429)
```

#### f) 악성 PDF 패턴 감지 테스트
```bash
# JavaScript가 포함된 PDF 업로드 (실제 악성 파일은 사용하지 않음)
# 이 테스트는 실제 운영 환경에서는 주의해서 수행
curl -X POST -F "file=@suspicious_test.pdf" \
     http://localhost:8000/upload
# 예상 결과: 400 Bad Request (의심스러운 내용 감지 시)
```

---

## 🎛️ 관리자 인터페이스 테스트

### 1. 로그인 및 접근
```bash
# 브라우저에서 접속
http://localhost:8000/admin/login

# 기본 계정: admin / admin123
```

### 2. 모니터링 페이지 확인

#### a) 성능 모니터링 대시보드
- URL: `http://localhost:8000/admin/performance`
- 확인 사항:
  - [ ] 시스템 상태 지표 표시
  - [ ] CPU, 메모리, 디스크 사용량 표시
  - [ ] 처리 단계별 성능 통계
  - [ ] 큐 상태 정보
  - [ ] 자동 새로고침 기능

#### b) Job 큐 관리 대시보드
- URL: `http://localhost:8000/admin/queue`
- 확인 사항:
  - [ ] 큐 크기 및 활성 Job 수 표시
  - [ ] 대기 중인 Job 목록 (우선순위별)
  - [ ] 최근 Job 처리 이력
  - [ ] Job 취소 기능
  - [ ] 처리 슬롯 시각화

#### c) 시스템 모니터링 대시보드
- URL: `http://localhost:8000/admin/system`
- 확인 사항:
  - [ ] CPU, 메모리, 디스크 게이지 차트
  - [ ] 시스템 상태 알림
  - [ ] 리소스 사용량 트렌드
  - [ ] 실시간 시스템 정보

#### d) 보안 모니터링 (향후 버전에서 제공 예정)
- URL: `http://localhost:8000/security/status` (API 엔드포인트)
- 확인 사항:
  - [ ] 보안 시스템 활성화 상태
  - [ ] 파일 크기 제한 설정
  - [ ] 허용된 확장자 목록
  - [ ] 속도 제한 설정
  - [ ] 격리 시스템 상태

---

## 🚀 동시 처리 테스트

### 1. 다중 PDF 동시 업로드 테스트
```bash
#!/bin/bash
# 여러 PDF를 동시에 업로드하여 큐 관리 테스트

for i in {1..5}; do
    curl -X POST -F "file=@test${i}.pdf" -F "priority=normal" \
         http://localhost:8000/upload-priority &
done
wait

# 큐 상태 확인
curl http://localhost:8000/queue/status
```

### 2. 우선순위 테스트
```bash
#!/bin/bash
# 다른 우선순위로 PDF 업로드하여 큐 순서 확인

# 낮은 우선순위 먼저 업로드
curl -X POST -F "file=@low_priority.pdf" -F "priority=low" \
     http://localhost:8000/upload-priority

# 높은 우선순위 나중에 업로드 (먼저 처리되어야 함)
curl -X POST -F "file=@high_priority.pdf" -F "priority=high" \
     http://localhost:8000/upload-priority

# 큐 순서 확인
curl http://localhost:8000/queue/status | jq '.queue_items'
```

---

## 📊 성능 지표 확인

### 1. 처리 성능 메트릭
```json
{
  "jobs": {
    "currently_active": 2,
    "success_rate_today": 95.5,
    "completed_today": 42
  },
  "performance": {
    "average_duration_seconds": 157.3,
    "fastest_job_seconds": 89.2,
    "slowest_job_seconds": 245.1
  },
  "system": {
    "overall_score": 87.5,
    "status": "good"
  }
}
```

### 2. 큐 관리 지표
```json
{
  "queue_size": 3,
  "active_jobs": 2,
  "max_concurrent": 3,
  "total_queued": 156,
  "total_processed": 148,
  "total_failed": 8,
  "estimated_queue_time": 480
}
```

---

## 🔍 문제 해결

### 1. 테스트 실패 시 확인사항

#### a) 서버 연결 문제
```bash
# 서버 상태 확인
curl http://localhost:8000/health

# 로그 확인
docker logs refserver_app_1
```

#### b) 성능 모니터링 오류
```bash
# 성능 엔드포인트 개별 테스트
curl http://localhost:8000/performance/stats
curl http://localhost:8000/performance/system
curl http://localhost:8000/performance/jobs
```

#### c) 큐 관리 오류
```bash
# 큐 상태 확인
curl http://localhost:8000/queue/status

# 활성 Job 확인
curl http://localhost:8000/performance/jobs | jq '.active_jobs'
```

### 2. 일반적인 문제

#### a) psutil 모듈 오류
```bash
# Docker 컨테이너에서 psutil 설치 확인
docker exec -it refserver_app_1 python -c "import psutil; print('psutil OK')"
```

#### b) 메모리 부족
```bash
# 시스템 리소스 확인
curl http://localhost:8000/performance/system | jq '.memory'
```

#### c) 큐가 가득 참
```bash
# 큐 크기 및 제한 확인
curl http://localhost:8000/queue/status | jq '{queue_size, max_queue_size}'
```

---

## 📈 성공 기준

### 1. 테스트 통과 기준
- **전체 테스트 성공률**: 80% 이상
- **핵심 기능 테스트**: 모든 기능 정상 작동
- **성능 API**: 모든 엔드포인트 응답
- **큐 관리**: 우선순위 정렬 및 동시 처리 제한 동작
- **관리자 인터페이스**: 모든 모니터링 페이지 접근 가능
- **보안 시스템**: 파일 검증, 크기 제한, 속도 제한 정상 작동

### 2. 성능 기준
- **API 응답 시간**: 평균 1초 미만
- **큐 처리**: 우선순위에 따른 정확한 순서
- **동시 처리**: 설정된 제한(기본 3개) 준수
- **메모리 사용량**: 안정적인 메모리 관리

### 3. 안정성 기준
- **에러 핸들링**: 잘못된 입력에 적절한 에러 응답
- **재시도 메커니즘**: 네트워크 오류 시 자동 재시도
- **회로 차단기**: 연속 실패 시 서비스 보호
- **자동 복구**: 일시적 문제 해결 후 정상 작동

### 4. 보안 기준
- **파일 검증**: 잘못된 파일 형식 차단 (100% 성공률)
- **크기 제한**: 대용량 파일 업로드 차단
- **속도 제한**: 과도한 요청 차단 및 제한
- **악성 콘텐츠 감지**: 의심스러운 패턴 탐지 및 격리
- **보안 로깅**: 모든 보안 이벤트 적절한 로깅

---

## 🎯 실제 사용 시나리오

### 1. 일반적인 사용 흐름
1. **PDF 업로드**: 우선순위와 함께 업로드
2. **큐 확인**: 처리 순서 및 예상 시간 확인
3. **진행 모니터링**: 실시간 처리 상태 추적
4. **결과 확인**: 처리 완료 후 결과 다운로드
5. **성능 분석**: 처리 성능 및 시스템 상태 확인

### 2. 관리자 모니터링 흐름
1. **대시보드 확인**: 전체 시스템 상태 개요
2. **성능 모니터링**: 처리 성능 및 병목 지점 확인
3. **큐 관리**: 대기 중인 Job 관리 및 우선순위 조정
4. **시스템 모니터링**: 리소스 사용량 및 알림 확인
5. **문제 해결**: 성능 저하 또는 오류 발생 시 대응

이 가이드를 통해 RefServer v0.1.9의 새로운 기능들이 제대로 작동하는지 체계적으로 확인할 수 있습니다! 🚀