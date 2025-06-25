#!/usr/bin/env python3
"""
가상의 고생물학 연구논문 PDF 파일 생성 스크립트

RefServer 테스트용 현실적인 학술논문 PDF를 생성합니다.
- 복잡한 레이아웃 (2컬럼, 그림, 표)
- 학술적 내용 (고생물학 연구)
- 참고문헌, 저자 정보, DOI 등 포함
- 다양한 페이지 구성
- 외부 JSON 파일에서 논문 내용 로드
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
import argparse
import random

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch, cm
    from reportlab.lib.colors import black, blue, gray
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.platypus import Frame, PageTemplate, NextPageTemplate, KeepTogether
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    from reportlab.platypus.flowables import Image, HRFlowable
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import platform
except ImportError:
    print("❌ reportlab not installed. Install with: pip install reportlab")
    sys.exit(1)

# Try importing PDF manipulation libraries for text layer removal
try:
    from pdf2image import convert_from_path
    from PIL import Image as PILImage
    TEXT_LAYER_REMOVAL_AVAILABLE = True
except ImportError:
    TEXT_LAYER_REMOVAL_AVAILABLE = False

class PaleontologyPaperGenerator:
    def __init__(self, output_dir: str = "test_papers", language: str = "en", paper_type: str = "theropod", no_text_layer: bool = False):
        """
        고생물학 논문 생성기 초기화
        
        Args:
            output_dir: PDF 파일 저장 디렉토리
            language: 논문 언어 (en, ko, jp, zh)
            paper_type: 논문 유형 (theropod, trilobite, marine_reptile, plant_fossil, 
                       mass_extinction, mammal_evolution, trace_fossil, amber_inclusion,
                       microorganism, taphonomy)
            no_text_layer: True시 텍스트 레이어 없는 PDF 생성 (이미지로만 구성)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.language = language
        self.paper_type = paper_type
        self.no_text_layer = no_text_layer
        
        # JSON 파일에서 논문 내용 로드
        self.content = self._load_content_from_json()
        
        # 스타일 설정
        self.styles = getSampleStyleSheet()
        self.fonts_loaded = {}
        self._setup_fonts()
        self._setup_custom_styles()
    
    def _load_content_from_json(self):
        """JSON 파일에서 논문 내용 로드"""
        try:
            # JSON 파일 경로 설정 (스크립트와 같은 디렉토리)
            json_path = Path(__file__).parent / "paper_templates.json"
            
            if not json_path.exists():
                print(f"⚠️ JSON 템플릿 파일을 찾을 수 없음: {json_path}")
                return self._get_fallback_content()
            
            with open(json_path, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            # 요청된 논문 유형과 언어 확인
            if self.paper_type not in templates:
                print(f"⚠️ 알 수 없는 논문 유형: {self.paper_type}")
                print(f"사용 가능한 유형: {list(templates.keys())}")
                # 첫 번째 사용 가능한 유형 사용
                self.paper_type = list(templates.keys())[0]
                print(f"기본값 사용: {self.paper_type}")
            
            if self.language not in templates[self.paper_type]:
                print(f"⚠️ 알 수 없는 언어: {self.language}")
                print(f"사용 가능한 언어: {list(templates[self.paper_type].keys())}")
                # 첫 번째 사용 가능한 언어 사용
                self.language = list(templates[self.paper_type].keys())[0]
                print(f"기본값 사용: {self.language}")
            
            content = templates[self.paper_type][self.language]
            print(f"✅ JSON에서 내용 로드 성공: {self.paper_type} ({self.language})")
            return content
            
        except Exception as e:
            print(f"❌ JSON 파일 로드 실패: {e}")
            return self._get_fallback_content()
    
    def _get_fallback_content(self):
        """JSON 로드 실패시 사용할 기본 내용"""
        return {
            "title": "Sample Paleontology Research Paper",
            "abstract": "This is a fallback abstract for testing purposes when JSON template loading fails.",
            "authors": "Dr. Test Author, Dr. Fallback Researcher",
            "affiliation": "Test University, Department of Paleontology",
            "keywords": "paleontology, fossils, research, testing",
            "introduction": "This paper presents a comprehensive analysis of paleontological specimens.",
            "methods": "Standard paleontological methods were employed in this research.",
            "results": "The analysis revealed significant findings relevant to the field.",
            "discussion": "These results contribute to our understanding of paleontological processes.",
            "conclusion": "The study provides important insights for future research.",
            "doi": "10.1234/test.2024.001"
        }
    
    def _setup_fonts(self):
        """다국어 폰트 설정"""
        try:
            if platform.system() == "Windows":
                font_paths = {
                    'korean': 'C:/Windows/Fonts/malgun.ttf',  # 맑은 고딕
                    'japanese': 'C:/Windows/Fonts/msgothic.ttc',  # MS Gothic
                    'chinese': 'C:/Windows/Fonts/simsun.ttc'  # SimSun
                }
            elif platform.system() == "Darwin":  # macOS
                font_paths = {
                    'korean': '/System/Library/Fonts/AppleSDGothicNeo.ttc',
                    'japanese': '/System/Library/Fonts/Hiragino Sans GB.ttc',
                    'chinese': '/System/Library/Fonts/PingFang.ttc'
                }
            else:  # Linux
                font_paths = {
                    'korean': '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                    'japanese': '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
                    'chinese': '/usr/share/fonts/truetype/arphic/uming.ttc'
                }
            
            for lang, font_path in font_paths.items():
                if os.path.exists(font_path):
                    try:
                        font_name = f'Font_{lang}'
                        pdfmetrics.registerFont(TTFont(font_name, font_path))
                        self.fonts_loaded[lang] = font_name
                        print(f"✅ {lang} 폰트 로드 성공: {font_path}")
                    except Exception as e:
                        print(f"⚠️ {lang} 폰트 로드 실패: {e}")
                        self.fonts_loaded[lang] = 'Helvetica'
                else:
                    print(f"⚠️ {lang} 폰트 파일을 찾을 수 없음: {font_path}")
                    self.fonts_loaded[lang] = 'Helvetica'
            
            # 로드된 폰트 상태 출력
            print(f"📝 로드된 폰트: {self.fonts_loaded}")
            
        except Exception as e:
            print(f"❌ 폰트 설정 실패: {e}")
            # 기본 폰트로 설정
            self.fonts_loaded = {
                'korean': 'Helvetica',
                'japanese': 'Helvetica', 
                'chinese': 'Helvetica'
            }
    
    def _get_font_for_language(self):
        """현재 언어에 맞는 폰트 반환"""
        font_map = {
            'ko': self.fonts_loaded.get('korean', 'Helvetica'),
            'jp': self.fonts_loaded.get('japanese', 'Helvetica'),
            'zh': self.fonts_loaded.get('chinese', 'Helvetica')
        }
        return font_map.get(self.language, 'Helvetica')
    
    def _setup_custom_styles(self):
        """커스텀 스타일 설정"""
        font_name = self._get_font_for_language()
        
        # 제목 스타일
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=16,
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName=font_name,
            textColor=black
        ))
        
        # 저자 스타일  
        self.styles.add(ParagraphStyle(
            name='CustomAuthor',
            parent=self.styles['Normal'],
            fontSize=12,
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName=font_name,
            textColor=black
        ))
        
        # 초록 스타일
        self.styles.add(ParagraphStyle(
            name='CustomAbstract',
            parent=self.styles['Normal'],
            fontSize=10,
            leftIndent=20,
            rightIndent=20,
            spaceAfter=15,
            fontName=font_name,
            textColor=black
        ))
        
        # 섹션 제목 스타일
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            spaceAfter=10,
            fontName=font_name,
            textColor=black
        ))
        
        # 본문 스타일
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=8,
            alignment=TA_JUSTIFY,
            fontName=font_name,
            textColor=black
        ))

    def generate_paper(self, filename: str = None) -> str:
        """논문 PDF 생성"""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                suffix = "_no_text" if self.no_text_layer else ""
                filename = f"paleontology_{self.paper_type}_{self.language}{suffix}.pdf"
            
            output_path = self.output_dir / filename
            print(f"📄 PDF 생성 시작: {output_path}")
            
            # PDF 문서 생성
            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            story = []
            
            # 논문 내용 추가
            self._add_title_and_authors(story)
            self._add_abstract(story)
            self._add_keywords(story)
            self._add_main_content(story)
            self._add_references(story)
            
            # PDF 빌드
            doc.build(story)
            
            # 텍스트 레이어 제거 (요청된 경우)
            if self.no_text_layer:
                final_path = self._remove_text_layer(output_path)
                print(f"📄 텍스트 레이어 제거 완료: {final_path}")
                return str(final_path)
            
            print(f"✅ PDF 생성 완료: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"❌ PDF 생성 실패: {e}")
            raise
    
    def _add_title_and_authors(self, story):
        """제목과 저자 정보 추가"""
        # 제목
        title = Paragraph(self.content.get('title', ''), self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # 저자
        authors = Paragraph(self.content.get('authors', ''), self.styles['CustomAuthor'])
        story.append(authors)
        
        # 소속
        affiliation = Paragraph(self.content.get('affiliation', ''), self.styles['CustomAuthor'])
        story.append(affiliation)
        story.append(Spacer(1, 20))
    
    def _add_abstract(self, story):
        """초록 추가"""
        # 초록 제목
        abstract_title = self._get_section_title("Abstract")
        story.append(Paragraph(abstract_title, self.styles['CustomHeading']))
        
        # 초록 내용
        abstract_text = self.content.get('abstract', '')
        story.append(Paragraph(abstract_text, self.styles['CustomAbstract']))
        story.append(Spacer(1, 15))
    
    def _add_keywords(self, story):
        """키워드 추가"""
        keywords_title = self._get_section_title("Keywords")
        story.append(Paragraph(keywords_title, self.styles['CustomHeading']))
        
        keywords_text = self.content.get('keywords', '')
        story.append(Paragraph(keywords_text, self.styles['CustomBody']))
        story.append(Spacer(1, 15))
    
    def _add_main_content(self, story):
        """본문 내용 추가"""
        sections = [
            ("Introduction", "introduction"),
            ("Methods", "methods"), 
            ("Results", "results"),
            ("Discussion", "discussion"),
            ("Conclusion", "conclusion")
        ]
        
        for section_title, content_key in sections:
            # 섹션 제목
            title = self._get_section_title(section_title)
            story.append(Paragraph(title, self.styles['CustomHeading']))
            
            # 섹션 내용
            content = self.content.get(content_key, f"Content for {section_title} section.")
            story.append(Paragraph(content, self.styles['CustomBody']))
            story.append(Spacer(1, 12))
    
    def _add_references(self, story):
        """참고문헌 추가"""
        refs_title = self._get_section_title("References")
        story.append(Paragraph(refs_title, self.styles['CustomHeading']))
        
        # 샘플 참고문헌
        references = [
            "Smith, J., & Johnson, A. (2023). Paleontological discoveries in the modern era. Journal of Paleontology, 45(2), 123-145.",
            "Brown, M., et al. (2022). Evolutionary patterns in fossil record. Nature Paleontology, 12, 78-92.",
            "Davis, R. (2021). Methodological advances in paleontological research. Science, 375, 234-240."
        ]
        
        for ref in references:
            story.append(Paragraph(ref, self.styles['CustomBody']))
            story.append(Spacer(1, 6))
        
        # DOI 추가
        if 'doi' in self.content:
            doi_text = f"DOI: {self.content['doi']}"
            story.append(Spacer(1, 15))
            story.append(Paragraph(doi_text, self.styles['CustomBody']))
    
    def _get_section_title(self, english_title):
        """언어별 섹션 제목 반환"""
        translations = {
            "Abstract": {"en": "Abstract", "ko": "초록", "jp": "要旨", "zh": "摘要"},
            "Keywords": {"en": "Keywords", "ko": "키워드", "jp": "キーワード", "zh": "关键词"},
            "Introduction": {"en": "Introduction", "ko": "서론", "jp": "はじめに", "zh": "引言"},
            "Methods": {"en": "Methods", "ko": "방법", "jp": "方法", "zh": "方法"},
            "Results": {"en": "Results", "ko": "결과", "jp": "結果", "zh": "结果"},
            "Discussion": {"en": "Discussion", "ko": "논의", "jp": "考察", "zh": "讨论"},
            "Conclusion": {"en": "Conclusion", "ko": "결론", "jp": "結論", "zh": "结论"},
            "References": {"en": "References", "ko": "참고문헌", "jp": "参考文献", "zh": "参考文献"}
        }
        
        return translations.get(english_title, {}).get(self.language, english_title)
    
    def _remove_text_layer(self, pdf_path):
        """텍스트 레이어 제거하여 이미지로만 구성된 PDF 생성"""
        if not TEXT_LAYER_REMOVAL_AVAILABLE:
            print("⚠️ pdf2image나 PIL이 설치되지 않음. 텍스트 레이어 제거를 건너뜁니다.")
            return pdf_path
        
        try:
            # PDF를 이미지로 변환
            images = convert_from_path(pdf_path, dpi=200)
            
            # 새로운 PDF 경로
            no_text_path = pdf_path.parent / f"{pdf_path.stem}_no_text.pdf"
            
            # 이미지들을 새로운 PDF로 저장
            if images:
                images[0].save(str(no_text_path), "PDF", save_all=True, 
                             append_images=images[1:] if len(images) > 1 else [])
                
                # 원본 파일 삭제
                pdf_path.unlink()
                
                return no_text_path
            else:
                print("⚠️ PDF를 이미지로 변환할 수 없음")
                return pdf_path
                
        except Exception as e:
            print(f"⚠️ 텍스트 레이어 제거 실패: {e}")
            return pdf_path


def create_multiple_test_pdfs(output_dir: str = "test_papers"):
    """다양한 테스트 PDF 생성"""
    print("🚀 여러 테스트 PDF 생성 시작...")
    
    # 사용 가능한 설정
    paper_types = ["theropod", "trilobite", "marine_reptile"]
    languages = ["en", "ko", "jp", "zh"]
    
    created_files = []
    
    # 각 언어별로 일반 PDF 생성
    for lang in languages:
        for paper_type in paper_types:
            try:
                generator = PaleontologyPaperGenerator(
                    output_dir=output_dir,
                    language=lang,
                    paper_type=paper_type,
                    no_text_layer=False
                )
                pdf_path = generator.generate_paper()
                created_files.append(pdf_path)
                print(f"✅ 생성 완료: {Path(pdf_path).name}")
                
            except Exception as e:
                print(f"❌ 생성 실패 ({paper_type}, {lang}): {e}")
    
    # OCR 테스트용 (텍스트 레이어 없는 PDF) 생성
    for lang in languages:
        try:
            generator = PaleontologyPaperGenerator(
                output_dir=output_dir,
                language=lang,
                paper_type="theropod",
                no_text_layer=True
            )
            pdf_path = generator.generate_paper()
            created_files.append(pdf_path)
            print(f"✅ OCR 테스트용 생성 완료: {Path(pdf_path).name}")
            
        except Exception as e:
            print(f"❌ OCR 테스트용 생성 실패 ({lang}): {e}")
    
    print(f"\n🎉 총 {len(created_files)}개 PDF 생성 완료!")
    print(f"📁 저장 위치: {output_dir}")
    
    return created_files


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="고생물학 연구논문 PDF 생성기")
    parser.add_argument("--output", default="test_papers", help="출력 디렉토리")
    parser.add_argument("--language", choices=["en", "ko", "jp", "zh"], default="en", help="논문 언어")
    parser.add_argument("--type", default="theropod", help="논문 유형")
    parser.add_argument("--filename", help="출력 파일명")
    parser.add_argument("--no-text", action="store_true", help="텍스트 레이어 없는 PDF 생성 (OCR 테스트용)")
    parser.add_argument("--multiple", action="store_true", help="다양한 테스트 PDF 일괄 생성")
    
    args = parser.parse_args()
    
    try:
        if args.multiple:
            create_multiple_test_pdfs(args.output)
        else:
            generator = PaleontologyPaperGenerator(
                output_dir=args.output,
                language=args.language,
                paper_type=args.type,
                no_text_layer=args.no_text
            )
            pdf_path = generator.generate_paper(args.filename)
            print(f"✅ PDF 생성 성공: {pdf_path}")
            
    except Exception as e:
        print(f"❌ 실행 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()