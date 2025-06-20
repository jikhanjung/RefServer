# 🚨 RefServer 재해 복구 가이드

## 📋 목차
1. [재해 시나리오](#재해-시나리오)
2. [백업 전략](#백업-전략)
3. [복구 절차](#복구-절차)
4. [자동 복구 스크립트](#자동-복구-스크립트)
5. [예방 조치](#예방-조치)
6. [체크리스트](#체크리스트)

---

## 🎯 재해 시나리오

### 1. 데이터베이스 손상
- **SQLite 데이터베이스 손상**: 파일 시스템 오류, 디스크 장애
- **ChromaDB 인덱스 손상**: 벡터 데이터 불일치, 인덱스 깨짐
- **증상**: API 오류, 검색 실패, 데이터 조회 불가

### 2. 서비스 장애
- **Docker 컨테이너 크래시**: 메모리 부족, 프로세스 오류
- **의존 서비스 장애**: Ollama, Huridocs 연결 실패
- **증상**: 503 Service Unavailable, 처리 중단

### 3. 스토리지 장애
- **디스크 가득 참**: 백업 파일 누적, 로그 과다
- **파일 시스템 오류**: 권한 문제, 마운트 해제
- **증상**: 업로드 실패, 백업 실패

### 4. 완전 시스템 장애
- **서버 다운**: 하드웨어 장애, 전원 문제
- **데이터 센터 장애**: 네트워크 단절, 재해
- **증상**: 전체 서비스 중단

---

## 💾 백업 전략

### 현재 백업 구성
```
일별 백업: 매일 오전 3시 (7일 보관)
주별 백업: 일요일 오전 4시 (30일 보관)
시간별 증분: 매시간 (2일 보관)
```

### 백업 위치
```
/data/backups/
├── sqlite/
│   ├── daily/
│   ├── weekly/
│   └── incremental/
├── chromadb/
│   ├── daily/
│   ├── weekly/
│   └── snapshots/
└── metadata/
    └── backup_history.json
```

### 오프사이트 백업 (권장)
```bash
# 원격 서버로 백업 동기화
rsync -avz /data/backups/ user@backup-server:/backups/refserver/

# S3로 백업 업로드
aws s3 sync /data/backups/ s3://my-bucket/refserver-backups/
```

---

## 🔧 복구 절차

### 1. SQLite 데이터베이스 복구

#### 자동 복구 (API 사용)
```bash
# 최신 백업 확인
curl -X GET http://localhost:8060/admin/backup/history \
  -H "Authorization: Bearer YOUR_TOKEN"

# 특정 백업으로 복구
curl -X POST http://localhost:8060/admin/backup/restore/BACKUP_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 수동 복구
```bash
# 1. 서비스 중지
docker-compose down

# 2. 현재 DB 백업 (안전을 위해)
cp /data/refserver.db /data/refserver.db.corrupted

# 3. 백업 파일 찾기
ls -la /data/backups/sqlite/daily/

# 4. 백업 복구
gunzip -c /data/backups/sqlite/daily/refserver_2025-01-20_daily.db.gz > /data/refserver.db

# 5. 권한 설정
chmod 644 /data/refserver.db

# 6. 서비스 시작
docker-compose up -d
```

### 2. ChromaDB 복구

#### 수동 복구
```bash
# 1. 서비스 중지
docker-compose down

# 2. 현재 ChromaDB 백업
mv /data/chromadb /data/chromadb.corrupted

# 3. 백업 복구
tar -xzf /data/backups/chromadb/daily/chromadb_20250120_120000_full.tar.gz -C /data/

# 4. 권한 설정
chown -R 1000:1000 /data/chromadb

# 5. 서비스 시작
docker-compose up -d
```

### 3. 통합 복구 (SQLite + ChromaDB)

최신 통합 백업을 사용하여 두 데이터베이스를 동시에 복구:

```bash
# 자동 복구 스크립트 사용
./scripts/disaster_recovery.sh --unified --backup-id "unified_20250120_030000"
```

### 4. 부분 복구

#### PDF 파일만 복구
```bash
# PDF 파일은 별도 백업 필요
rsync -av /backup/pdfs/ /data/pdfs/
```

#### 특정 시점으로 복구 (Point-in-Time Recovery)
```bash
# 특정 날짜의 백업 찾기
./scripts/disaster_recovery.sh --list --date "2025-01-19"

# 해당 시점으로 복구
./scripts/disaster_recovery.sh --restore --point-in-time "2025-01-19 14:00:00"
```

---

## 🤖 자동 복구 스크립트

### 기본 사용법
```bash
# 도움말
./scripts/disaster_recovery.sh --help

# 상태 확인
./scripts/disaster_recovery.sh --check

# 최신 백업으로 복구
./scripts/disaster_recovery.sh --restore-latest

# 특정 백업으로 복구
./scripts/disaster_recovery.sh --restore --backup-id "BACKUP_ID"

# 건강 상태 확인 후 자동 복구
./scripts/disaster_recovery.sh --auto-recover
```

### 스크립트 기능
- 서비스 상태 확인
- 데이터베이스 무결성 검사
- 자동 백업 선택
- 복구 전 안전 백업
- 복구 후 검증

---

## 🛡️ 예방 조치

### 1. 모니터링
```bash
# 디스크 사용량 모니터링
df -h /data

# 데이터베이스 무결성 정기 검사
sqlite3 /data/refserver.db "PRAGMA integrity_check;"

# 서비스 상태 확인
curl http://localhost:8060/health
```

### 2. 정기 점검
- **일일**: 백업 상태 확인
- **주간**: 백업 복구 테스트
- **월간**: 전체 시스템 복구 훈련

### 3. 알림 설정
```bash
# 백업 실패 시 알림
# /etc/cron.d/refserver-monitoring
0 * * * * /scripts/check_backups.sh || mail -s "RefServer Backup Failed" admin@example.com
```

---

## ✅ 복구 체크리스트

### 사전 준비
- [ ] 최신 백업 위치 확인
- [ ] 백업 무결성 검증
- [ ] 복구 계획 수립
- [ ] 관련자 통보

### 복구 작업
- [ ] 서비스 중지
- [ ] 현재 상태 백업
- [ ] 백업 파일 복구
- [ ] 권한 및 소유권 설정
- [ ] 서비스 재시작

### 복구 후 검증
- [ ] API 헬스체크 (/health)
- [ ] 데이터 무결성 확인
- [ ] 주요 기능 테스트
- [ ] 성능 모니터링

### 사후 조치
- [ ] 복구 로그 작성
- [ ] 원인 분석
- [ ] 재발 방지 대책
- [ ] 문서 업데이트

---

## 📞 긴급 연락처

- **시스템 관리자**: admin@example.com
- **데이터베이스 관리자**: dba@example.com
- **24/7 지원**: +1-XXX-XXX-XXXX

---

## 🔄 복구 시간 목표 (RTO/RPO)

- **RTO (Recovery Time Objective)**: 2시간 이내
- **RPO (Recovery Point Objective)**: 1시간 이내
- **백업 보관 기간**: 최소 30일

---

## 📝 변경 이력

- v0.1.12 (2025-01-20): 초기 재해 복구 가이드 작성
- SQLite/ChromaDB 통합 복구 절차 추가
- 자동 복구 스크립트 문서화