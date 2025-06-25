# 📋 RefServer 테스트용 PDF 파일 요구사항

RefServer의 세밀한 기능 테스트를 위한 체계적인 PDF 파일 분류 및 요구사항입니다.

## 🎯 테스트 목적

RefServer v0.1.12의 모든 핵심 기능을 검증하기 위해 다양한 특성을 가진 PDF 파일이 필요합니다:

- **하이브리드 언어 감지 OCR** (v0.1.11)
- **LLaVA 품질 평가 시스템**
- **Huridocs 레이아웃 분석**
- **BGE-M3 임베딩 생성**
- **LLM 메타데이터 추출**
- **4층 중복 방지 시스템**
- **ChromaDB 벡터 검색**

---

## 📂 테스트 PDF 파일 카테고리

### 🌍 1. 언어별 테스트 PDF

> **목적**: 하이브리드 언어 감지 OCR 시스템 (v0.1.11) 검증

#### 주요 언어 (우선순위 높음)
- **영어 (eng)**: 표준 학술논문 (Nature, Science, IEEE 등)
- **한국어 (kor)**: 한국 학술지 논문, KCI 논문
- **일본어 (jpn)**: 일본 학술지 논문, J-STAGE 논문
- **중국어 간체 (chi_sim)**: 중국 학술지 논문
- **프랑스어 (fra)**: 프랑스/벨기에 학술지 논문
- **독일어 (deu)**: 독일/오스트리아 학술지 논문
- **스페인어 (spa)**: 스페인/남미 학술지 논문

#### 혼합 언어 (고급 테스트)
- **영어+한국어**: 한국 대학 영문 논문 (저자명/소속 한글)
- **영어+일본어**: 일본 대학 영문 논문 (저자명 일본어)
- **영어+중국어**: 중국 대학 영문 논문 (저자명 중국어)

### 📄 2. 텍스트 레이어 유무별

> **목적**: OCR 처리 및 품질 평가 시스템 검증

#### 텍스트 레이어 있음 (Searchable PDF)
- **고품질 텍스트**: 최신 LaTeX 생성 PDF (완벽한 텍스트 레이어)
- **중품질 텍스트**: Word → PDF 변환 (일반적인 품질)
- **저품질 텍스트**: 이미지 + 부정확한 OCR 레이어

#### 텍스트 레이어 없음 (Image-only PDF)
- **고해상도 스캔**: 300+ DPI 스캔본 (선명한 텍스트)
- **중해상도 스캔**: 150-300 DPI 스캔본 (표준 품질)
- **저해상도 스캔**: 150 DPI 미만 스캔본 (흐린 텍스트)
- **복사기 스캔**: 복사기로 여러 번 복사된 문서

### 🖼️ 3. 이미지 품질별

> **목적**: LLaVA 품질 평가 시스템 테스트

#### 선명도별
- **매우 선명**: 원본 디지털 문서 (최고 품질)
- **선명**: 1세대 스캔 (양호한 품질)
- **흐림**: 여러 세대 복사본 (중간 품질)
- **매우 흐림**: 팩스 전송 품질 (저품질)

#### 배경 상태별
- **깨끗한 배경**: 흰 배경, 노이즈 없음
- **약간 지저분**: 미세한 점, 얼룩
- **지저분한 배경**: 명확한 노이즈, 얼룩
- **매우 지저분**: 심한 노이즈, 접힘 자국, 찢어짐

### 📐 4. 레이아웃 복잡도별

> **목적**: Huridocs 레이아웃 분석 시스템 검증

#### 단순 레이아웃
- **단일 컬럼**: 일반 텍스트 문서
- **제목+본문**: 기본적인 학술논문 구조

#### 표준 레이아웃
- **2컬럼**: 표준 IEEE/ACM 논문 형식
- **제목+초록+본문+참고문헌**: 일반적인 구조

#### 복잡 레이아웃
- **다중 컬럼**: 3컬럼 이상 신문/잡지 형식
- **표+그래프 포함**: 대량의 시각적 요소
- **수식 포함**: LaTeX 수학 공식 다수
- **특수 형식**: 포스터, 프레젠테이션 슬라이드

### 📊 5. 콘텐츠 유형별

> **목적**: 메타데이터 추출 및 임베딩 생성 테스트

#### 학술논문 분야별
- **컴퓨터과학**: CS 논문 (CVPR, NIPS, ICML 등)
- **의학**: 의학 논문 (Nature Medicine, NEJM 등)
- **물리학**: 물리학 논문 (Physical Review 등)
- **화학**: 화학 논문 (Journal of Chemistry 등)
- **사회과학**: 사회과학 논문 (다양한 연구 방법론)

#### 문서 유형별
- **저널 논문**: 피어리뷰 학술지 논문
- **컨퍼런스 논문**: 학회 발표 논문 (짧은 형식)
- **학위논문**: 석사/박사 학위논문 (긴 형식)
- **기술보고서**: 연구소/기업 기술보고서
- **리뷰논문**: 서베이/리뷰 논문 (참고문헌 다수)

### 📏 6. 문서 크기별

> **목적**: 성능 및 메모리 사용량 테스트

#### 페이지 수별
- **짧은 문서**: 1-5페이지 (컨퍼런스 논문)
- **중간 문서**: 6-20페이지 (일반 저널 논문)
- **긴 문서**: 21-50페이지 (리뷰 논문)
- **매우 긴 문서**: 50+ 페이지 (학위논문, 기술보고서)

#### 파일 크기별
- **소형**: 1MB 미만 (텍스트 위주)
- **중형**: 1-10MB (일반적인 논문)
- **대형**: 10-50MB (고해상도 이미지 포함)
- **초대형**: 50MB+ (대량 이미지/그래프)

### 🔧 7. 특수 케이스

> **목적**: 엣지 케이스 및 오류 처리 테스트

#### 문제가 있는 PDF
- **손상된 PDF**: 부분적으로 깨진 파일
- **암호화된 PDF**: 패스워드 보호 문서
- **빈 페이지**: 완전히 빈 페이지 포함
- **매우 큰 페이지**: A3 이상 큰 페이지 크기
- **회전된 페이지**: 90도/180도 회전된 페이지

#### 특수 포맷
- **스캔된 책**: 책 스캔본 (굽은 텍스트, 그림자)
- **손글씨 포함**: 일부 손으로 쓴 내용
- **다양한 폰트**: 특수 폰트, 기호 다수 사용
- **컬러 문서**: 컬러 배경, 하이라이트, 워터마크

### 🧪 8. 중복 감지 테스트용

> **목적**: 4층 중복 방지 시스템 검증

#### 동일한 내용, 다른 포맷
- **원본 + 스캔본**: 같은 논문의 원본과 스캔 버전
- **다른 해상도**: 같은 내용, 다른 DPI
- **다른 압축**: 같은 내용, 다른 압축률
- **다른 페이지 순서**: 페이지 순서가 바뀐 버전

#### 유사한 내용
- **버전 차이**: 같은 논문의 초고/최종본
- **언어 차이**: 같은 논문의 영어/한국어 버전
- **요약본**: 원본 논문 + 확장 요약본
- **발표자료**: 논문 + 관련 프레젠테이션

---

## 📁 추천 테스트 파일 구조

```
test_pdfs/
├── 01_languages/
│   ├── eng_nature_2024_high_quality.pdf      # 영어 고품질 논문
│   ├── kor_kci_journal_scan.pdf              # 한국어 스캔 논문
│   ├── jpn_jstage_paper.pdf                  # 일본어 논문
│   ├── chi_sim_academic.pdf                  # 중국어 간체 논문
│   ├── fra_academic_paper.pdf                # 프랑스어 논문
│   ├── deu_academic_paper.pdf                # 독일어 논문
│   ├── spa_academic_paper.pdf                # 스페인어 논문
│   └── mixed_eng_kor_authors.pdf             # 영어+한국어 혼합
│
├── 02_text_layers/
│   ├── searchable_latex_high_quality.pdf     # LaTeX 생성 고품질
│   ├── searchable_word_medium_quality.pdf    # Word 변환 중품질
│   ├── searchable_ocr_low_quality.pdf        # 부정확한 OCR 레이어
│   ├── image_only_300dpi_clear.pdf           # 고해상도 이미지만
│   ├── image_only_200dpi_medium.pdf          # 중해상도 이미지만
│   ├── image_only_150dpi_low.pdf             # 저해상도 이미지만
│   └── image_only_photocopy.pdf              # 복사기 스캔
│
├── 03_image_quality/
│   ├── crystal_clear_digital.pdf             # 매우 선명한 디지털
│   ├── clear_first_scan.pdf                  # 선명한 1세대 스캔
│   ├── blurry_multiple_copies.pdf            # 흐린 다중 복사
│   ├── very_blurry_fax_quality.pdf           # 매우 흐린 팩스 품질
│   ├── clean_white_background.pdf            # 깨끗한 배경
│   ├── slightly_dirty_minor_spots.pdf        # 약간 지저분한 배경
│   ├── dirty_clear_noise.pdf                 # 명확한 노이즈
│   └── very_dirty_heavy_damage.pdf           # 심하게 손상된 문서
│
├── 04_layouts/
│   ├── simple_single_column.pdf              # 단순 단일 컬럼
│   ├── basic_title_abstract_body.pdf         # 기본 논문 구조
│   ├── standard_two_column_ieee.pdf          # 표준 2컬럼 IEEE
│   ├── standard_acm_format.pdf               # 표준 ACM 형식
│   ├── complex_three_column.pdf              # 복잡한 3컬럼
│   ├── heavy_tables_graphs.pdf               # 대량 표/그래프
│   ├── math_formulas_latex.pdf               # 수식 다수 포함
│   ├── poster_presentation.pdf               # 포스터 형식
│   └── slides_presentation.pdf               # 프레젠테이션 슬라이드
│
├── 05_content_types/
│   ├── computer_science_cvpr.pdf             # 컴퓨터과학 논문
│   ├── medicine_nature_med.pdf               # 의학 논문
│   ├── physics_physical_review.pdf           # 물리학 논문
│   ├── chemistry_jacs.pdf                    # 화학 논문
│   ├── social_science_survey.pdf             # 사회과학 논문
│   ├── journal_paper_peer_reviewed.pdf       # 저널 논문
│   ├── conference_paper_short.pdf            # 컨퍼런스 논문
│   ├── master_thesis_long.pdf                # 석사 학위논문
│   ├── phd_dissertation_very_long.pdf        # 박사 학위논문
│   ├── technical_report_industry.pdf         # 기술보고서
│   └── review_paper_survey.pdf               # 리뷰 논문
│
├── 06_document_sizes/
│   ├── tiny_1_page.pdf                       # 1페이지 (요약)
│   ├── short_4_pages.pdf                     # 4페이지 (컨퍼런스)
│   ├── medium_15_pages.pdf                   # 15페이지 (일반 논문)
│   ├── long_35_pages.pdf                     # 35페이지 (리뷰)
│   ├── very_long_80_pages.pdf                # 80페이지 (학위논문)
│   ├── small_file_1mb.pdf                    # 1MB 미만
│   ├── medium_file_5mb.pdf                   # 5MB 중간
│   ├── large_file_25mb.pdf                   # 25MB 대형
│   └── huge_file_60mb.pdf                    # 60MB 초대형
│
├── 07_special_cases/
│   ├── corrupted_partial_damage.pdf          # 부분 손상
│   ├── password_protected.pdf                # 암호화된 PDF
│   ├── with_blank_pages.pdf                  # 빈 페이지 포함
│   ├── a3_large_page_size.pdf                # A3 큰 페이지
│   ├── rotated_pages_mixed.pdf               # 회전된 페이지 혼합
│   ├── scanned_book_curved_text.pdf          # 스캔된 책 (굽은 텍스트)
│   ├── handwritten_annotations.pdf           # 손글씨 주석 포함
│   ├── special_fonts_symbols.pdf             # 특수 폰트/기호
│   ├── color_background_highlights.pdf       # 컬러 배경/하이라이트
│   └── watermarked_document.pdf              # 워터마크 포함
│
└── 08_duplicates/
    ├── original_digital_paper.pdf            # 원본 디지털
    ├── scanned_version_same_content.pdf      # 같은 내용 스캔본
    ├── different_resolution_same.pdf         # 다른 해상도 같은 내용
    ├── different_compression_same.pdf        # 다른 압축 같은 내용
    ├── reordered_pages_same.pdf              # 페이지 순서 다름
    ├── draft_version_paper.pdf               # 초고 버전
    ├── final_version_paper.pdf               # 최종 버전
    ├── english_version.pdf                   # 영어 버전
    ├── korean_translation.pdf                # 한국어 번역
    ├── paper_full_text.pdf                   # 전체 논문
    ├── paper_extended_abstract.pdf           # 확장 요약
    └── related_presentation.pdf              # 관련 발표자료
```

---

## 🎯 테스트 우선순위

### 🔥 Phase 1: 필수 기본 테스트 (10개 파일)

| 우선순위 | 파일명 | 테스트 목적 |
|---------|--------|-------------|
| 1 | `eng_nature_2024_high_quality.pdf` | 영어 고품질 표준 테스트 |
| 2 | `kor_kci_journal_scan.pdf` | 한국어 언어 감지 + OCR 테스트 |
| 3 | `image_only_300dpi_clear.pdf` | 텍스트 레이어 없는 고품질 OCR |
| 4 | `jpn_jstage_paper.pdf` | 일본어 언어 감지 테스트 |
| 5 | `very_long_80_pages.pdf` | 대용량 문서 성능 테스트 |
| 6 | `short_4_pages.pdf` | 짧은 문서 처리 테스트 |
| 7 | `very_blurry_fax_quality.pdf` | 저품질 이미지 처리 테스트 |
| 8 | `math_formulas_latex.pdf` | 복잡한 수식 레이아웃 테스트 |
| 9 | `heavy_tables_graphs.pdf` | 대량 시각적 요소 테스트 |
| 10 | `corrupted_partial_damage.pdf` | 오류 처리 테스트 |

### 🔸 Phase 2: 고급 기능 테스트 (15개 파일)

| 우선순위 | 파일명 | 테스트 목적 |
|---------|--------|-------------|
| 11 | `chi_sim_academic.pdf` | 중국어 언어 감지 테스트 |
| 12 | `mixed_eng_kor_authors.pdf` | 혼합 언어 처리 테스트 |
| 13 | `searchable_ocr_low_quality.pdf` | 부정확한 텍스트 레이어 처리 |
| 14 | `complex_three_column.pdf` | 복잡한 레이아웃 분석 |
| 15 | `huge_file_60mb.pdf` | 대용량 파일 메모리 테스트 |
| 16 | `password_protected.pdf` | 암호화 문서 처리 테스트 |
| 17 | `scanned_book_curved_text.pdf` | 특수 스캔 문서 처리 |
| 18 | `original_digital_paper.pdf` + `scanned_version_same_content.pdf` | 중복 감지 테스트 |
| 19 | `draft_version_paper.pdf` + `final_version_paper.pdf` | 버전 차이 중복 감지 |
| 20 | `english_version.pdf` + `korean_translation.pdf` | 언어별 중복 감지 |
| 21 | `poster_presentation.pdf` | 특수 형식 문서 처리 |
| 22 | `color_background_highlights.pdf` | 컬러 문서 처리 테스트 |
| 23 | `fra_academic_paper.pdf` | 프랑스어 언어 감지 테스트 |
| 24 | `rotated_pages_mixed.pdf` | 회전된 페이지 처리 테스트 |
| 25 | `with_blank_pages.pdf` | 빈 페이지 포함 문서 테스트 |

### 🔹 Phase 3: 전체 검증 테스트 (전체 파일셋)

모든 카테고리의 파일을 사용하여 RefServer의 모든 기능을 종합적으로 검증

---

## 🧪 테스트 자동화 스크립트 예시

```python
# test_pdf_comprehensive.py
import os
import asyncio
from pathlib import Path

class ComprehensivePDFTester:
    def __init__(self, test_pdf_dir: str = "test_pdfs"):
        self.test_pdf_dir = Path(test_pdf_dir)
        self.results = {}
    
    async def test_language_detection(self):
        """언어별 PDF 테스트"""
        language_dir = self.test_pdf_dir / "01_languages"
        for pdf_file in language_dir.glob("*.pdf"):
            # 언어 감지 테스트 로직
            pass
    
    async def test_ocr_quality(self):
        """OCR 품질별 테스트"""
        quality_dir = self.test_pdf_dir / "02_text_layers"
        for pdf_file in quality_dir.glob("*.pdf"):
            # OCR 품질 평가 테스트 로직
            pass
    
    async def test_layout_analysis(self):
        """레이아웃 분석 테스트"""
        layout_dir = self.test_pdf_dir / "04_layouts"
        for pdf_file in layout_dir.glob("*.pdf"):
            # 레이아웃 분석 테스트 로직
            pass
    
    async def test_duplicate_detection(self):
        """중복 감지 테스트"""
        duplicate_dir = self.test_pdf_dir / "08_duplicates"
        # 중복 쌍별 테스트 로직
        pass
    
    async def run_comprehensive_test(self):
        """종합 테스트 실행"""
        await self.test_language_detection()
        await self.test_ocr_quality()
        await self.test_layout_analysis()
        await self.test_duplicate_detection()
        
        return self.generate_report()
    
    def generate_report(self):
        """테스트 결과 리포트 생성"""
        return {
            "total_files_tested": len(self.results),
            "success_rate": self.calculate_success_rate(),
            "failed_tests": self.get_failed_tests(),
            "performance_metrics": self.get_performance_metrics()
        }

if __name__ == "__main__":
    tester = ComprehensivePDFTester()
    results = asyncio.run(tester.run_comprehensive_test())
    print(f"Test Results: {results}")
```

---

## 📊 기대 효과

이런 체계적인 테스트 PDF 파일셋을 구축하면:

1. **🔍 철저한 기능 검증**: RefServer의 모든 핵심 기능을 체계적으로 테스트
2. **🌍 다국어 지원 확인**: 10개 언어의 OCR 정확도 검증
3. **⚡ 성능 최적화**: 다양한 크기의 문서로 성능 병목 지점 발견
4. **🛡️ 안정성 향상**: 엣지 케이스와 오류 상황에 대한 견고성 확보
5. **🎯 품질 보증**: 실제 사용 환경을 반영한 현실적인 테스트

RefServer v0.1.12의 엔터프라이즈급 안정성과 성능을 보장하는 종합적인 테스트 체계가 될 것입니다! 🚀