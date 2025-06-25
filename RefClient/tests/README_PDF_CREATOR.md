# 🦕 고생물학 연구논문 PDF 생성기

RefServer 테스트용 현실적인 학술논문 PDF를 생성하는 스크립트입니다.

## 🎯 특징

### 📄 현실적인 학술논문 구조
- **복잡한 레이아웃**: 2컬럼 본문, 표, 그림 배치
- **완전한 메타데이터**: 제목, 저자, 초록, 키워드, DOI, 저널 정보
- **학술적 내용**: 10가지 고생물학 분야별 특화 내용
- **참고문헌**: 현실적인 인용 목록
- **다양한 섹션**: Introduction, Methods, Results, Discussion, Conclusions

### 🦴 다양한 고생물학 논문 유형 (10종)
- **theropod**: 백악기 수각류 공룡 진화 연구
- **trilobite**: 오르도비스기 삼엽충 다양성과 생물지리학
- **marine_reptile**: 쥐라기 해양 파충류 고생태학
- **plant_fossil**: 석탄기 식물 화석과 초기 산림 생태계
- **mass_extinction**: 페름기말 대량절멸 메커니즘
- **mammal_evolution**: 팔레오세 포유류 적응방산
- **trace_fossil**: 트라이아스기 생흔화석과 행동 진화
- **amber_inclusion**: 백악기 호박 내포물과 생물다양성
- **microorganism**: 시생대 미생물 군집과 초기 생명
- **taphonomy**: 화석화 과정의 실험적 매장학 연구

### 🌍 다국어 지원
- **영어 (en)**: 표준 국제 학술지 형식
- **한국어 (ko)**: 한국 학술지 형식
- **일본어 (jp)**: 일본 학술지 형식  
- **중국어 (zh)**: 중국 학술지 형식

### 🧪 RefServer 테스트 최적화
- **OCR 테스트**: 다양한 언어별 텍스트 인식
- **메타데이터 추출**: LLM 기반 서지정보 추출 테스트
- **레이아웃 분석**: Huridocs 복잡한 구조 분석
- **임베딩 생성**: BGE-M3 다국어 임베딩 테스트
- **언어 감지**: 하이브리드 언어 감지 OCR 테스트

## 🚀 사용법

### 1. 의존성 설치
```bash
pip install reportlab
```

### 2. 단일 논문 생성
```bash
# 영어 수각류 논문 생성 (기본)
python create_test_pdfs.py

# 한국어 논문 생성
python create_test_pdfs.py --language ko

# 일본어 삼엽충 논문 생성
python create_test_pdfs.py --language jp --type trilobite

# 중국어 대량절멸 논문 생성  
python create_test_pdfs.py --language zh --type mass_extinction

# 특정 유형의 영어 논문들
python create_test_pdfs.py --type marine_reptile
python create_test_pdfs.py --type amber_inclusion
python create_test_pdfs.py --type taphonomy

# 사용자 정의 파일명
python create_test_pdfs.py --language en --type plant_fossil --filename my_plant_paper.pdf

# 특정 디렉토리에 저장
python create_test_pdfs.py --output /path/to/output --language ko --type microorganism
```

### 3. 다중 논문 생성 (권장)
```bash
# 모든 언어와 유형으로 테스트 논문 생성
python create_test_pdfs.py --multiple

# 결과: test_papers/ 디렉토리에 18개 PDF 생성
# 언어별 기본 논문 (4개):
# - paleontology_paper_en.pdf, paleontology_paper_ko.pdf, paleontology_paper_jp.pdf, paleontology_paper_zh.pdf
# 
# 유형별 영어 논문 (10개):
# - paleontology_theropod_en.pdf, paleontology_trilobite_en.pdf, paleontology_marine_reptile_en.pdf
# - paleontology_plant_fossil_en.pdf, paleontology_mass_extinction_en.pdf, paleontology_mammal_evolution_en.pdf
# - paleontology_trace_fossil_en.pdf, paleontology_amber_inclusion_en.pdf, paleontology_microorganism_en.pdf
# - paleontology_taphonomy_en.pdf
#
# 다국어 삼엽충 논문 (4개):
# - trilobite_paper_en.pdf, trilobite_paper_ko.pdf, trilobite_paper_jp.pdf, trilobite_paper_zh.pdf
```

## 📊 생성되는 PDF 특성

### 📄 논문 내용 (유형별)
- **Theropod**: 백악기 수각류 공룡 진화 - 중국 랴오닝성 이셴층
- **Trilobite**: 오르도비스기 삼엽충 다양성 - 북유럽 발트해 분지
- **Marine Reptile**: 쥐라기 해양 파충류 고생태학 - 영국 옥스포드 점토층
- **Plant Fossil**: 석탄기 식물 대형화석 - 호주 시드니 분지
- **Mass Extinction**: 페름기말 대량절멸 - 중국 남부 블록
- **Mammal Evolution**: 팔레오세 포유류 적응방산 - 북미 서부 내륙
- **Trace Fossil**: 트라이아스기 생흔화석 - 캐나다 동부 펀디 분지
- **Amber Inclusion**: 백악기 호박 절지동물 - 미얀마 후카웅 계곡
- **Microorganism**: 시생대 미생물 군집 - 서호주 필바라 크라톤
- **Taphonomy**: 라거슈태테 보존 과정 - 실험실 및 야외 연구

### 👥 공통 요소
- **저자**: 다국적 연구진 (하버드, MIT, 도쿄자연사박물관)
- **분야**: 고생물학, 진화생물학, 지질학

### 🔬 학술적 요소
- **DOI**: 10.1016/j.jpr.2024.03.127
- **저널**: Journal of Paleontological Research  
- **초록**: 200단어 내외의 구조화된 요약
- **키워드**: 6개 전문 용어
- **참고문헌**: 5개 현실적인 인용
- **표**: 측정 데이터 표
- **그림**: 과학적 도표 (예정)

### 📐 레이아웃 복잡도
- **1페이지**: 단일 컬럼 (제목, 저자, 초록)
- **2페이지 이후**: 2컬럼 본문
- **표**: 격자 구조, 헤더 강조
- **섹션**: 계층적 구조 (1, 1.1, 1.1.1)
- **서식**: 다양한 폰트 크기, 스타일

## 🧪 RefServer 테스트에 활용

### 1. OCR 테스트
```bash
# 생성된 PDF로 OCR 정확도 테스트
python tests/test_api_core.py --pdf test_papers/paleontology_paper_ko.pdf
```

### 2. 언어 감지 테스트
```bash  
# 다국어 언어 감지 테스트
python tests/test_ocr_language_detection.py test_papers/paleontology_paper_jp.pdf
```

### 3. 메타데이터 추출 테스트
```bash
# LLM 기반 서지정보 추출 테스트
curl -X POST -F "file=@test_papers/paleontology_paper_en.pdf" \
     http://localhost:8060/upload
```

### 4. 레이아웃 분석 테스트
```bash
# Huridocs 복잡한 구조 분석
curl http://localhost:8060/layout/PAPER_ID
```

## 📈 테스트 시나리오

### 🎯 시나리오 1: 다국어 OCR 정확도
```bash
python create_test_pdfs.py --multiple
for pdf in test_papers/*.pdf; do
    python test_api_core.py --pdf "$pdf"
done
```

### 🎯 시나리오 2: 복잡한 레이아웃 처리
```bash
# 복잡한 구조의 논문으로 레이아웃 분석 한계 테스트
python test_api_core.py --pdf test_papers/complex_paleontology_paper.pdf
```

### 🎯 시나리오 3: 메타데이터 추출 비교
```bash
# 언어별 메타데이터 추출 정확도 비교
for lang in en ko jp zh; do
    echo "Testing $lang paper..."
    python test_api_core.py --pdf test_papers/paleontology_paper_$lang.pdf
done
```

## 🔧 커스터마이징

### 새로운 논문 주제 추가
`PaleontologyPaperGenerator` 클래스를 상속하여 다른 분야 논문 생성:

```python
class PhysicsPaperGenerator(PaleontologyPaperGenerator):
    def _get_content_by_language(self):
        # 물리학 논문 내용 정의
        pass
```

### 레이아웃 복잡도 조정
`_create_two_column_template()` 메서드 수정으로 3컬럼, 다양한 프레임 구조 생성 가능

### 언어 추가
`_get_content_by_language()` 메서드에 새로운 언어 추가:

```python
"fr": {  # 프랑스어
    "title": "Analyse évolutionnaire des dinosaures théropodes du Crétacé...",
    # ...
}
```

## 💡 활용 팁

### 🎨 다양한 테스트 케이스
- **언어별 차이**: 각 언어의 OCR 정확도 비교
- **구조 복잡도**: 단순/복잡한 레이아웃 처리 능력
- **분량별 테스트**: 짧은/긴 논문 처리 시간 비교
- **메타데이터 풍부도**: 완전한 vs 부분적 정보 추출

### 📊 성능 벤치마킹
- **처리 시간**: 언어별, 복잡도별 처리 시간 측정
- **정확도**: OCR, 메타데이터 추출 정확도 평가
- **품질 점수**: LLaVA 품질 평가 결과 비교

---

**RefServer v0.1.12** - 현실적인 테스트 데이터로 엔터프라이즈급 PDF 처리 성능 검증 🦕