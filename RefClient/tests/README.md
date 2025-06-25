# 🧪 RefServer 테스트 스위트

RefServer v0.1.12 전체 기능 검증을 위한 종합 테스트 스크립트 모음입니다.

## 🚀 빠른 시작

### 1. 전제 조건
```bash
# RefServer 실행
docker-compose up -d

# 테스트 의존성 설치
pip install requests reportlab

# 관리자 계정 생성 (백업/관리자 테스트용)
docker exec -it refserver python manage_admin.py ensure-default
```

### 2. 기본 테스트 실행
```bash
# 핵심 API 테스트 (가장 중요)
python test_api_core.py

# 백업 시스템 테스트 (v0.1.12)
python test_backup_system.py

# 관리자 시스템 테스트 (v0.1.12)
python test_admin_system.py
```

## 📁 테스트 스크립트

| 스크립트 | 목적 | 실행 시간 |
|----------|------|-----------|
| `test_api_core.py` | 핵심 PDF 처리 API | ~3분 |
| `test_backup_system.py` | 백업/일관성/재해복구 | ~2분 |
| `test_admin_system.py` | 관리자 인터페이스 | ~1분 |
| `test_api.py` | 전체 API 통합 테스트 | ~5분 |
| `test_ocr_language_detection.py` | OCR 언어 감지 | ~2분 |

## 📊 성공 기준

- **GPU 모드**: 90% 이상 성공률
- **CPU 모드**: 75% 이상 성공률  
- **백업 시스템**: 85% 이상 성공률

## 💡 문제 해결

### 일반적인 오류
```bash
# 연결 오류
❌ Cannot connect to http://localhost:8060
→ docker-compose up 실행

# 인증 오류
❌ Admin authentication failed  
→ docker exec -it refserver python manage_admin.py ensure-default

# PDF 처리 시간 초과
⏰ Processing timeout after 300s
→ 더 작은 PDF 파일 사용
```

## 📚 상세 가이드

자세한 테스트 방법론, 수동 테스트, 성공 기준은 다음 문서를 참조:

- **[TESTING_GUIDE.md](./TESTING_GUIDE.md)**: 종합 테스트 가이드 (API, 백업, 수동 테스트 등)
- **[TEST_PDF_REQUIREMENTS.md](./TEST_PDF_REQUIREMENTS.md)**: PDF 테스트 파일 요구사항
- **[README_PDF_CREATOR.md](./README_PDF_CREATOR.md)**: 테스트용 PDF 생성기 가이드

---

**RefServer v0.1.12** - 엔터프라이즈급 PDF 지능형 처리 플랫폼 🚀