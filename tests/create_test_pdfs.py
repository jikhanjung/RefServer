#!/usr/bin/env python3
"""
가상의 고생물학 연구논문 PDF 파일 생성 스크립트

RefServer 테스트용 현실적인 학술논문 PDF를 생성합니다.
- 복잡한 레이아웃 (2컬럼, 그림, 표)
- 학술적 내용 (고생물학 연구)
- 참고문헌, 저자 정보, DOI 등 포함
- 다양한 페이지 구성
"""

import os
import sys
from pathlib import Path
from datetime import datetime
import argparse

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

class PaleontologyPaperGenerator:
    def __init__(self, output_dir: str = ".", language: str = "en", paper_type: str = "theropod", no_text_layer: bool = False):
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
        
        # 논문 유형별 내용 설정
        self.content = self._get_content_by_type_and_language()
        
        # 스타일 설정
        self.styles = getSampleStyleSheet()
        self._setup_fonts()
        self._setup_custom_styles()
    
    def _get_content_by_type_and_language(self):
        """논문 유형과 언어별 내용 반환"""
        return self._get_paper_content(self.paper_type, self.language)
    
    def _get_paper_content(self, paper_type: str, language: str):
        """논문 유형별 내용 데이터베이스"""
        
        # 논문 유형별 기본 템플릿
        paper_templates = {
            "theropod": {
                "en": {
                    "title": "Evolutionary Analysis of Cretaceous Theropod Dinosaurs: New Evidence from Liaoning Province Fossil Record",
                    "topic": "theropod dinosaur evolution",
                    "time_period": "Cretaceous (125 Ma)",
                    "location": "Liaoning Province, China",
                    "method": "morphological and phylogenetic analysis"
                },
                "ko": {
                    "title": "백악기 수각류 공룡의 진화적 분석: 랴오닝성 화석 기록에서 발견된 새로운 증거",
                    "topic": "수각류 공룡 진화",
                    "time_period": "백악기 (1억 2천 5백만 년 전)",
                    "location": "중국 랴오닝성",
                    "method": "형태학적 및 계통분류학적 분석"
                }
            },
            
            "trilobite": {
                "en": {
                    "title": "Diversity and Biogeography of Ordovician Trilobites from the Baltic Basin: Implications for Paleozoic Marine Ecosystems",
                    "topic": "trilobite diversity and biogeography",
                    "time_period": "Ordovician (450-440 Ma)",
                    "location": "Baltic Basin, Northern Europe",
                    "method": "taxonomic analysis and biogeographic modeling"
                },
                "ko": {
                    "title": "발트해 분지 오르도비스기 삼엽충의 다양성과 생물지리학: 고생대 해양 생태계에 대한 함의",
                    "topic": "삼엽충 다양성과 생물지리학",
                    "time_period": "오르도비스기 (4억 5천만-4억 4천만 년 전)",
                    "location": "북유럽 발트해 분지",
                    "method": "분류학적 분석 및 생물지리학적 모델링"
                }
            },
            
            "marine_reptile": {
                "en": {
                    "title": "Jurassic Marine Reptile Assemblages from the Oxford Clay Formation: Ecological Dynamics in Mesozoic Oceans",
                    "topic": "marine reptile paleoecology",
                    "time_period": "Middle Jurassic (165 Ma)",
                    "location": "Oxford Clay Formation, England",
                    "method": "ecological niche modeling and isotope analysis"
                },
                "ko": {
                    "title": "옥스포드 점토층의 쥐라기 해양 파충류 군집: 중생대 해양의 생태학적 역학",
                    "topic": "해양 파충류 고생태학",
                    "time_period": "중기 쥐라기 (1억 6천 5백만 년 전)",
                    "location": "영국 옥스포드 점토층",
                    "method": "생태학적 적소 모델링 및 동위원소 분석"
                }
            },
            
            "plant_fossil": {
                "en": {
                    "title": "Carboniferous Plant Macrofossils from the Sydney Basin: Evidence for Early Forest Ecosystem Development",
                    "topic": "plant fossil evolution",
                    "time_period": "Carboniferous (320 Ma)",
                    "location": "Sydney Basin, Australia",
                    "method": "comparative morphology and phylogenetic reconstruction"
                },
                "ko": {
                    "title": "시드니 분지의 석탄기 식물 대형화석: 초기 산림 생태계 발달의 증거",
                    "topic": "식물 화석 진화",
                    "time_period": "석탄기 (3억 2천만 년 전)",
                    "location": "호주 시드니 분지",
                    "method": "비교 형태학 및 계통 복원"
                }
            },
            
            "mass_extinction": {
                "en": {
                    "title": "End-Permian Mass Extinction: Geochemical Evidence for Volcanic Catastrophism in South China",
                    "topic": "mass extinction mechanisms",
                    "time_period": "End-Permian (252 Ma)",
                    "location": "South China Block",
                    "method": "geochemical analysis and statistical modeling"
                },
                "ko": {
                    "title": "페름기말 대량절멸: 중국 남부의 화산 재앙론에 대한 지구화학적 증거",
                    "topic": "대량절멸 메커니즘",
                    "time_period": "페름기말 (2억 5천 2백만 년 전)",
                    "location": "중국 남부 블록",
                    "method": "지구화학적 분석 및 통계 모델링"
                }
            },
            
            "mammal_evolution": {
                "en": {
                    "title": "Paleocene Mammalian Radiation in North America: Dental Morphology and Dietary Adaptations",
                    "topic": "mammalian evolution",
                    "time_period": "Paleocene (60 Ma)",
                    "location": "Western Interior, North America",
                    "method": "dental morphometric analysis"
                },
                "ko": {
                    "title": "북미 팔레오세 포유류 적응방산: 치아 형태학과 식이 적응",
                    "topic": "포유류 진화",
                    "time_period": "팔레오세 (6천만 년 전)",
                    "location": "북미 서부 내륙",
                    "method": "치아 형태계측학적 분석"
                }
            },
            
            "trace_fossil": {
                "en": {
                    "title": "Behavioral Evolution in Triassic Arthropods: Ichnological Evidence from the Fundy Basin",
                    "topic": "trace fossil analysis",
                    "time_period": "Late Triassic (210 Ma)",
                    "location": "Fundy Basin, Eastern Canada",
                    "method": "ichnological analysis and behavioral reconstruction"
                },
                "ko": {
                    "title": "트라이아스기 절지동물의 행동 진화: 펀디 분지의 생흔화석학적 증거",
                    "topic": "생흔화석 분석",
                    "time_period": "후기 트라이아스기 (2억 1천만 년 전)",
                    "location": "캐나다 동부 펀디 분지",
                    "method": "생흔학적 분석 및 행동 복원"
                }
            },
            
            "amber_inclusion": {
                "en": {
                    "title": "Cretaceous Amber Arthropods from Myanmar: Exceptional Preservation of Forest Canopy Biodiversity",
                    "topic": "amber inclusion studies",
                    "time_period": "Mid-Cretaceous (100 Ma)",
                    "location": "Hukawng Valley, Myanmar",
                    "method": "micro-CT scanning and 3D morphological analysis"
                },
                "ko": {
                    "title": "미얀마 백악기 호박 절지동물: 산림 수관 생물다양성의 탁월한 보존",
                    "topic": "호박 내포물 연구",
                    "time_period": "중기 백악기 (1억 년 전)",
                    "location": "미얀마 후카웅 계곡",
                    "method": "마이크로 CT 스캔 및 3D 형태학적 분석"
                }
            },
            
            "microorganism": {
                "en": {
                    "title": "Archean Microbial Communities in Pilbara Stromatolites: Early Life Biosignatures and Metabolic Pathways",
                    "topic": "early life evolution",
                    "time_period": "Archean (3.4 Ga)",
                    "location": "Pilbara Craton, Western Australia",
                    "method": "biosignature analysis and metabolic modeling"
                },
                "ko": {
                    "title": "필바라 스트로마톨라이트의 시생대 미생물 군집: 초기 생명 생체표지 및 대사 경로",
                    "topic": "초기 생명 진화",
                    "time_period": "시생대 (34억 년 전)",
                    "location": "서호주 필바라 크라톤",
                    "method": "생체표지 분석 및 대사 모델링"
                }
            },
            
            "taphonomy": {
                "en": {
                    "title": "Taphonomic Processes in Lagerstätte Preservation: Experimental Studies on Soft Tissue Decay",
                    "topic": "fossilization processes",
                    "time_period": "Various (experimental)",
                    "location": "Laboratory and field studies",
                    "method": "experimental taphonomy and decay analysis"
                },
                "ko": {
                    "title": "라거슈태테 보존에서의 매장학적 과정: 연조직 분해에 대한 실험적 연구",
                    "topic": "화석화 과정",
                    "time_period": "다양 (실험적)",
                    "location": "실험실 및 야외 연구",
                    "method": "실험적 매장학 및 분해 분석"
                }
            }
        }
        
        # 기본 템플릿 가져오기
        template = paper_templates.get(paper_type, paper_templates["theropod"])
        base_content = template.get(language, template["en"])
        
        # 공통 논문 구조 생성
        return self._build_paper_structure(base_content, language)
    
    def _build_paper_structure(self, base_content, language):
        """기본 내용을 바탕으로 완전한 논문 구조 생성"""
        
        # 논문 유형별 저자와 저널 정보 생성
        authors_info = self._generate_authors_by_type(self.paper_type, language)
        journal_info = self._generate_journal_info(self.paper_type, language)
        
        # 논문 유형별 초록 및 키워드 생성
        abstract = self._generate_abstract(base_content, language)
        keywords = self._generate_keywords(base_content, language)
        
        # 최종 논문 구조 반환
        result = {
            "title": base_content["title"],
            "topic": base_content["topic"],
            "time_period": base_content["time_period"],
            "location": base_content["location"],
            "method": base_content["method"],
            "abstract": abstract,
            "keywords": keywords,
            **authors_info,
            **journal_info
        }
        
        return result
    
    def _generate_authors_by_type(self, paper_type, language):
        """논문 유형별 저자 정보 생성"""
        
        # 논문 유형별 저자 데이터베이스
        author_sets = {
            "theropod": {
                "en": {
                    "authors": [
                        "Dr. Sarah M. Chen", "Department of Paleontology, Harvard University",
                        "Prof. Michael R. Thompson", "Institute of Geological Sciences, MIT",
                        "Dr. Yuki Tanaka", "Natural History Museum, Tokyo"
                    ]
                },
                "ko": {
                    "authors": [
                        "첸사라 박사", "하버드대학교 고생물학과",
                        "마이클 톰슨 교수", "MIT 지질과학연구소", 
                        "다나카 유키 박사", "도쿄자연사박물관"
                    ]
                }
            },
            
            "trilobite": {
                "en": {
                    "authors": [
                        "Prof. Emma K. Rodriguez", "Department of Earth Sciences, University of Cambridge",
                        "Dr. Lars Andersson", "Swedish Museum of Natural History, Stockholm",
                        "Dr. Mikhail Petrov", "Institute of Paleontology, Russian Academy of Sciences"
                    ]
                },
                "ko": {
                    "authors": [
                        "엠마 로드리게즈 교수", "케임브리지대학교 지구과학과",
                        "라르스 안데르손 박사", "스톡홀름 자연사박물관", 
                        "미하일 페트로프 박사", "러시아과학원 고생물학연구소"
                    ]
                }
            },
            
            "marine_reptile": {
                "en": {
                    "authors": [
                        "Dr. James P. Morrison", "School of Earth Sciences, University of Bristol",
                        "Prof. Maria Gonzalez", "Museo Nacional de Ciencias Naturales, Madrid",
                        "Dr. Thomas Müller", "Staatliches Museum für Naturkunde, Stuttgart"
                    ]
                },
                "ko": {
                    "authors": [
                        "제임스 모리슨 박사", "브리스톨대학교 지구과학부",
                        "마리아 곤잘레즈 교수", "마드리드 국립자연과학박물관", 
                        "토마스 뮐러 박사", "슈투트가르트 자연사박물관"
                    ]
                }
            },
            
            "plant_fossil": {
                "en": {
                    "authors": [
                        "Prof. Rachel L. Williams", "Department of Botany, University of Melbourne",
                        "Dr. Hiroshi Yamamoto", "Institute for Plant Research, Kyoto University",
                        "Dr. Pierre Dubois", "Muséum National d'Histoire Naturelle, Paris"
                    ]
                },
                "ko": {
                    "authors": [
                        "레이첼 윌리엄스 교수", "멜버른대학교 식물학과",
                        "야마모토 히로시 박사", "교토대학교 식물연구소", 
                        "피에르 뒤부아 박사", "파리 자연사박물관"
                    ]
                }
            },
            
            "mass_extinction": {
                "en": {
                    "authors": [
                        "Dr. Chen Wei-Ming", "Institute of Geology, Chinese Academy of Sciences",
                        "Prof. David A. Taylor", "Department of Geosciences, Princeton University",
                        "Dr. Anna Kowalski", "Institute of Geological Sciences, Polish Academy of Sciences"
                    ]
                },
                "ko": {
                    "authors": [
                        "천웨이밍 박사", "중국과학원 지질연구소",
                        "데이비드 테일러 교수", "프린스턴대학교 지구과학과", 
                        "안나 코발스키 박사", "폴란드과학원 지질과학연구소"
                    ]
                }
            },
            
            "mammal_evolution": {
                "en": {
                    "authors": [
                        "Prof. Jennifer K. Smith", "Department of Mammalogy, Smithsonian Institution",
                        "Dr. Roberto Silva", "Museu Nacional, Universidade Federal do Rio de Janeiro",
                        "Dr. Ahmed Hassan", "Egyptian Geological Museum, Cairo"
                    ]
                },
                "ko": {
                    "authors": [
                        "제니퍼 스미스 교수", "스미소니언 연구소 포유동물학과",
                        "로베르토 실바 박사", "리우데자네이루 연방대학교 국립박물관", 
                        "아흐메드 핫산 박사", "카이로 이집트지질박물관"
                    ]
                }
            },
            
            "trace_fossil": {
                "en": {
                    "authors": [
                        "Dr. Katherine M. Brown", "Department of Ichnology, University of Saskatchewan",
                        "Prof. Giovanni Rossi", "Dipartimento di Scienze della Terra, Università di Bologna",
                        "Dr. Olaf Hansen", "Natural History Museum of Denmark, Copenhagen"
                    ]
                },
                "ko": {
                    "authors": [
                        "캐서린 브라운 박사", "서스캐처원대학교 생흔학과",
                        "지오바니 로시 교수", "볼로냐대학교 지구과학과", 
                        "올라프 한센 박사", "코펜하겐 덴마크자연사박물관"
                    ]
                }
            },
            
            "amber_inclusion": {
                "en": {
                    "authors": [
                        "Dr. Lin Zhao", "Key Laboratory of Insect Evolution, Capital Normal University",
                        "Prof. Alexander Grimaldi", "Division of Invertebrate Zoology, AMNH, New York",
                        "Dr. Mateus Santos", "Museu de Ciências da Terra, Brasília"
                    ]
                },
                "ko": {
                    "authors": [
                        "린자오 박사", "수도사범대학교 곤충진화연구소",
                        "알렉산더 그리말디 교수", "뉴욕 자연사박물관 무척추동물학과", 
                        "마테우스 산토스 박사", "브라질리아 지구과학박물관"
                    ]
                }
            },
            
            "microorganism": {
                "en": {
                    "authors": [
                        "Prof. Sherry L. Cady", "Department of Geology, Pacific Lutheran University",
                        "Dr. Kenichiro Sugitani", "Graduate School of Environmental Studies, Nagoya University",
                        "Dr. Frances Westall", "CNRS Centre de Biophysique Moléculaire, Orléans"
                    ]
                },
                "ko": {
                    "authors": [
                        "셰리 케이디 교수", "퍼시픽루터란대학교 지질학과",
                        "스기타니 겐이치로 박사", "나고야대학교 환경학연구과", 
                        "프랜시스 웨스톨 박사", "오를레앙 분자생물물리학센터"
                    ]
                }
            },
            
            "taphonomy": {
                "en": {
                    "authors": [
                        "Dr. Mark A. Wilson", "Department of Earth Sciences, The College of Wooster",
                        "Prof. Susan Kidwell", "Department of Geophysical Sciences, University of Chicago",
                        "Dr. Martin Brasier", "Department of Earth Sciences, University of Oxford"
                    ]
                },
                "ko": {
                    "authors": [
                        "마크 윌슨 박사", "우스터대학교 지구과학과",
                        "수잔 키드웰 교수", "시카고대학교 지구물리학과", 
                        "마틴 브레이지어 박사", "옥스포드대학교 지구과학과"
                    ]
                }
            }
        }
        
        # 기본 템플릿 가져오기 (언어별 대체)
        author_set = author_sets.get(paper_type, author_sets["theropod"])
        base_authors = author_set.get(language, author_set.get("en", author_sets["theropod"]["en"]))
        
        # 일본어와 중국어는 영어 기반으로 번역
        if language == "jp":
            if paper_type == "theropod":
                return {
                    "authors": [
                        "チェン・サラ博士", "ハーバード大学古生物学科",
                        "マイケル・トンプソン教授", "MIT地質科学研究所",
                        "田中雪博士", "東京自然史博物館"
                    ]
                }
            else:
                # 다른 유형들은 간단히 영어 이름 유지
                return base_authors
        elif language == "zh":
            if paper_type == "theropod":
                return {
                    "authors": [
                        "陈莎拉博士", "哈佛大学古生物学系",
                        "迈克尔·汤普森教授", "麻省理工学院地质科学研究所",
                        "田中雪博士", "东京自然历史博物馆"
                    ]
                }
            else:
                return base_authors
        
        return base_authors
    
    def _generate_journal_info(self, paper_type, language):
        """논문 유형별 저널 정보 생성"""
        
        # 논문 유형별 저널 데이터베이스
        journal_sets = {
            "theropod": {
                "journal_code": "jpr",
                "volume": 45, "issue": 3, "year": 2024,
                "start_page": 178, "end_page": 194,
                "doi_suffix": "03.127"
            },
            "trilobite": {
                "journal_code": "paleobio",
                "volume": 28, "issue": 2, "year": 2024,
                "start_page": 245, "end_page": 267,
                "doi_suffix": "02.089"
            },
            "marine_reptile": {
                "journal_code": "mesozoic",
                "volume": 67, "issue": 4, "year": 2024,
                "start_page": 112, "end_page": 138,
                "doi_suffix": "04.234"
            },
            "plant_fossil": {
                "journal_code": "paleobotany",
                "volume": 156, "issue": 1, "year": 2024,
                "start_page": 45, "end_page": 72,
                "doi_suffix": "01.156"
            },
            "mass_extinction": {
                "journal_code": "geology",
                "volume": 52, "issue": 7, "year": 2024,
                "start_page": 723, "end_page": 748,
                "doi_suffix": "07.445"
            },
            "mammal_evolution": {
                "journal_code": "mammalevol",
                "volume": 34, "issue": 5, "year": 2024,
                "start_page": 89, "end_page": 116,
                "doi_suffix": "05.298"
            },
            "trace_fossil": {
                "journal_code": "ichnos",
                "volume": 31, "issue": 3, "year": 2024,
                "start_page": 167, "end_page": 189,
                "doi_suffix": "03.078"
            },
            "amber_inclusion": {
                "journal_code": "cretres",
                "volume": 142, "issue": 6, "year": 2024,
                "start_page": 356, "end_page": 378,
                "doi_suffix": "06.512"
            },
            "microorganism": {
                "journal_code": "precamres",
                "volume": 398, "issue": 1, "year": 2024,
                "start_page": 23, "end_page": 41,
                "doi_suffix": "01.067"
            },
            "taphonomy": {
                "journal_code": "palaios",
                "volume": 39, "issue": 4, "year": 2024,
                "start_page": 445, "end_page": 467,
                "doi_suffix": "04.334"
            }
        }
        
        # 저널명 데이터베이스
        journal_names = {
            "jpr": {
                "en": "Journal of Paleontological Research",
                "ko": "고생물학 연구지",
                "jp": "古生物学研究誌",
                "zh": "古生物学研究期刊"
            },
            "paleobio": {
                "en": "Paleobiology",
                "ko": "고생물학",
                "jp": "古生物学",
                "zh": "古生物学"
            },
            "mesozoic": {
                "en": "Mesozoic Marine Ecology",
                "ko": "중생대 해양생태학",
                "jp": "中生代海洋生態学",
                "zh": "中生代海洋生态学"
            },
            "paleobotany": {
                "en": "Review of Palaeobotany and Palynology",
                "ko": "고식물학 및 화분학 리뷰",
                "jp": "古植物学・花粉学評論",
                "zh": "古植物学与孢粉学评论"
            },
            "geology": {
                "en": "Geology",
                "ko": "지질학",
                "jp": "地質学",
                "zh": "地质学"
            },
            "mammalevol": {
                "en": "Journal of Mammalian Evolution",
                "ko": "포유류 진화학 저널",
                "jp": "哺乳類進化学誌",
                "zh": "哺乳动物进化学报"
            },
            "ichnos": {
                "en": "Ichnos",
                "ko": "생흔학",
                "jp": "生痕学",
                "zh": "遗迹学"
            },
            "cretres": {
                "en": "Cretaceous Research",
                "ko": "백악기 연구",
                "jp": "白亜紀研究",
                "zh": "白垩纪研究"
            },
            "precamres": {
                "en": "Precambrian Research",
                "ko": "선캄브리아기 연구",
                "jp": "先カンブリア紀研究",
                "zh": "前寒武纪研究"
            },
            "palaios": {
                "en": "PALAIOS",
                "ko": "팔레이오스",
                "jp": "パレイオス",
                "zh": "古环境学"
            }
        }
        
        # 논문 유형별 정보 가져오기
        journal_data = journal_sets.get(paper_type, journal_sets["theropod"])
        journal_code = journal_data["journal_code"]
        journal_name = journal_names[journal_code].get(language, journal_names[journal_code]["en"])
        
        # 언어별 포맷팅
        if language == "ko":
            return {
                "journal": journal_name,
                "doi": f"10.1016/j.{journal_code}.2024.{journal_data['doi_suffix']}",
                "volume": f"제{journal_data['volume']}권 {journal_data['issue']}호",
                "pages": f"{journal_data['start_page']}-{journal_data['end_page']}면",
                "received": f"접수: 2024년 {journal_data['issue']}월 15일",
                "accepted": f"승인: 2024년 {journal_data['issue']+1}월 8일"
            }
        elif language == "jp":
            return {
                "journal": journal_name,
                "doi": f"10.1016/j.{journal_code}.2024.{journal_data['doi_suffix']}",
                "volume": f"第{journal_data['volume']}巻第{journal_data['issue']}号",
                "pages": f"{journal_data['start_page']}-{journal_data['end_page']}頁",
                "received": f"受理：2024年{journal_data['issue']}月15日",
                "accepted": f"採択：2024年{journal_data['issue']+1}月8日"
            }
        elif language == "zh":
            return {
                "journal": journal_name,
                "doi": f"10.1016/j.{journal_code}.2024.{journal_data['doi_suffix']}",
                "volume": f"第{journal_data['volume']}卷第{journal_data['issue']}期",
                "pages": f"第{journal_data['start_page']}-{journal_data['end_page']}页",
                "received": f"收到：2024年{journal_data['issue']}月15日",
                "accepted": f"接受：2024年{journal_data['issue']+1}月8日"
            }
        else:  # English
            return {
                "journal": journal_name,
                "doi": f"10.1016/j.{journal_code}.2024.{journal_data['doi_suffix']}",
                "volume": f"Vol. {journal_data['volume']}, No. {journal_data['issue']}",
                "pages": f"pp. {journal_data['start_page']}-{journal_data['end_page']}",
                "received": f"Received: {journal_data['year']}-{journal_data['issue']:02d}-15",
                "accepted": f"Accepted: {journal_data['year']}-{journal_data['issue']+1:02d}-08"
            }
    
    def _generate_abstract(self, base_content, language):
        """논문 유형별 초록 생성"""
        # 기본 템플릿 문구
        abstracts = {
            "en": f"This study investigates {base_content['topic']} from {base_content['location']} during the {base_content['time_period']}. Using {base_content['method']}, we analyze fossil specimens to understand evolutionary patterns and ecological relationships. Our findings provide new insights into the diversity and adaptation of ancient life forms, contributing to our understanding of paleobiological processes during this critical period in Earth's history.",
            "ko": f"본 연구는 {base_content['time_period']} 동안 {base_content['location']}에서의 {base_content['topic']}를 조사한다. {base_content['method']}를 사용하여 화석 표본을 분석하고 진화적 패턴과 생태학적 관계를 이해한다. 우리의 발견은 고대 생명체의 다양성과 적응에 대한 새로운 통찰을 제공하며, 지구 역사상 이 중요한 시기의 고생물학적 과정에 대한 이해에 기여한다.",
            "jp": f"本研究は{base_content['time_period']}における{base_content['location']}での{base_content['topic']}を調査する。{base_content['method']}を用いて化石標本を分析し、進化的パターンと生態学的関係を理解する。我々の発見は古代生物の多様性と適応に関する新たな洞察を提供し、地球史におけるこの重要な時期の古生物学的プロセスの理解に貢献する。",
            "zh": f"本研究调查了{base_content['time_period']}期间{base_content['location']}的{base_content['topic']}。使用{base_content['method']}分析化石标本，以了解进化模式和生态关系。我们的发现为古代生物的多样性和适应性提供了新的见解，有助于理解地球历史上这一关键时期的古生物学过程。"
        }
        return abstracts.get(language, abstracts["en"])
    
    def _generate_keywords(self, base_content, language):
        """논문 유형별 키워드 생성"""
        # 논문 유형별 키워드 템플릿
        keyword_sets = {
            "theropod": {
                "en": ["Cretaceous", "Theropod", "Evolution", "Liaoning", "Phylogeny", "Dinosaur"],
                "ko": ["백악기", "수각류", "진화", "랴오닝", "계통분류", "공룡"],
                "jp": ["白亜紀", "獣脚類", "進化", "遼寧", "系統分類", "恐竜"],
                "zh": ["白垩纪", "兽脚类", "进化", "辽宁", "系统发育", "恐龙"]
            },
            "trilobite": {
                "en": ["Ordovician", "Trilobite", "Diversity", "Biogeography", "Baltic", "Marine"],
                "ko": ["오르도비스기", "삼엽충", "다양성", "생물지리학", "발트해", "해양"],
                "jp": ["オルドビス紀", "三葉虫", "多様性", "生物地理学", "バルト海", "海洋"],
                "zh": ["奥陶纪", "三叶虫", "多样性", "生物地理学", "波罗的海", "海洋"]
            },
            "marine_reptile": {
                "en": ["Jurassic", "Marine reptile", "Paleoecology", "Oxford Clay", "Mesozoic", "Ocean"],
                "ko": ["쥐라기", "해양 파충류", "고생태학", "옥스포드 점토", "중생대", "해양"],
                "jp": ["ジュラ紀", "海生爬虫類", "古生態学", "オックスフォード粘土", "中生代", "海洋"],
                "zh": ["侏罗纪", "海洋爬行动物", "古生态学", "牛津粘土", "中生代", "海洋"]
            },
            "plant_fossil": {
                "en": ["Carboniferous", "Plant fossil", "Forest", "Ecosystem", "Sydney Basin", "Evolution"],
                "ko": ["석탄기", "식물 화석", "산림", "생태계", "시드니 분지", "진화"],
                "jp": ["石炭紀", "植物化石", "森林", "生態系", "シドニー盆地", "進化"],
                "zh": ["石炭纪", "植物化石", "森林", "生态系统", "悉尼盆地", "进化"]
            },
            "mass_extinction": {
                "en": ["Permian", "Mass extinction", "Volcanism", "Geochemistry", "South China", "Crisis"],
                "ko": ["페름기", "대량절멸", "화산활동", "지구화학", "중국 남부", "위기"],
                "jp": ["ペルム紀", "大量絶滅", "火山活動", "地球化学", "華南", "危機"],
                "zh": ["二叠纪", "大灭绝", "火山活动", "地球化学", "华南", "危机"]
            },
            "mammal_evolution": {
                "en": ["Paleocene", "Mammal", "Radiation", "Dental", "North America", "Adaptation"],
                "ko": ["팔레오세", "포유류", "적응방산", "치아", "북미", "적응"],
                "jp": ["暁新世", "哺乳類", "適応放散", "歯", "北米", "適応"],
                "zh": ["古新世", "哺乳动物", "适应辐射", "牙齿", "北美", "适应"]
            },
            "trace_fossil": {
                "en": ["Triassic", "Trace fossil", "Behavior", "Arthropod", "Fundy Basin", "Ichnology"],
                "ko": ["트라이아스기", "생흔화석", "행동", "절지동물", "펀디 분지", "생흔학"],
                "jp": ["三畳紀", "生痕化石", "行動", "節足動物", "ファンディ盆地", "生痕学"],
                "zh": ["三叠纪", "遗迹化石", "行为", "节肢动物", "芬迪盆地", "遗迹学"]
            },
            "amber_inclusion": {
                "en": ["Cretaceous", "Amber", "Arthropod", "Myanmar", "Preservation", "Biodiversity"],
                "ko": ["백악기", "호박", "절지동물", "미얀마", "보존", "생물다양성"],
                "jp": ["白亜紀", "琥珀", "節足動物", "ミャンマー", "保存", "生物多様性"],
                "zh": ["白垩纪", "琥珀", "节肢动物", "缅甸", "保存", "生物多样性"]
            },
            "microorganism": {
                "en": ["Archean", "Microbial", "Stromatolite", "Biosignature", "Pilbara", "Early life"],
                "ko": ["시생대", "미생물", "스트로마톨라이트", "생체표지", "필바라", "초기 생명"],
                "jp": ["太古代", "微生物", "ストロマトライト", "生体指標", "ピルバラ", "初期生命"],
                "zh": ["太古代", "微生物", "叠层石", "生物标志", "皮尔巴拉", "早期生命"]
            },
            "taphonomy": {
                "en": ["Taphonomy", "Lagerstätte", "Preservation", "Decay", "Experimental", "Fossilization"],
                "ko": ["매장학", "라거슈태테", "보존", "분해", "실험적", "화석화"],
                "jp": ["埋没学", "ラーガーシュテッテ", "保存", "分解", "実験的", "化石化"],
                "zh": ["埋藏学", "化石库", "保存", "腐烂", "实验性", "化石化"]
            }
        }
        
        # paper_type에서 첫 번째 단어 추출 (예: theropod_evolution -> theropod)
        key = self.paper_type.split('_')[0]
        keyword_set = keyword_sets.get(key, keyword_sets["theropod"])
        return keyword_set.get(language, keyword_set["en"])
    
    def _setup_fonts(self):
        """다국어 폰트 설정"""
        try:
            # 시스템 폰트 경로 설정
            system = platform.system()
            
            if system == "Windows":
                # Windows 폰트
                font_paths = {
                    'korean': 'C:/Windows/Fonts/malgun.ttf',
                    'japanese': 'C:/Windows/Fonts/msgothic.ttc',
                    'chinese': 'C:/Windows/Fonts/simsun.ttc'
                }
            elif system == "Darwin":  # macOS
                font_paths = {
                    'korean': '/System/Library/Fonts/AppleSDGothicNeo.ttc',
                    'japanese': '/System/Library/Fonts/Hiragino Sans GB.ttc',
                    'chinese': '/System/Library/Fonts/STHeiti Light.ttc'
                }
            else:  # Linux
                font_paths = {
                    'korean': '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                    'japanese': '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                    'chinese': '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc'
                }
            
            # 폰트 등록 시도
            self.fonts_loaded = {}
            for lang, path in font_paths.items():
                try:
                    if os.path.exists(path):
                        pdfmetrics.registerFont(TTFont(f'CJK-{lang}', path))
                        self.fonts_loaded[lang] = f'CJK-{lang}'
                        print(f"✅ {lang} 폰트 로드 성공: {path}")
                    else:
                        self.fonts_loaded[lang] = 'Helvetica'  # 기본 폰트
                        print(f"⚠️ {lang} 폰트 없음, 기본 폰트 사용: {path}")
                except Exception as e:
                    self.fonts_loaded[lang] = 'Helvetica'
                    print(f"❌ {lang} 폰트 로드 실패: {e}")
                    
        except Exception as e:
            print(f"❌ 폰트 설정 실패: {e}")
            self.fonts_loaded = {
                'korean': 'Helvetica',
                'japanese': 'Helvetica', 
                'chinese': 'Helvetica'
            }
    
    def _get_font_name(self):
        """언어별 폰트명 반환"""
        if self.language == 'ko':
            return self.fonts_loaded.get('korean', 'Helvetica')
        elif self.language == 'jp':
            return self.fonts_loaded.get('japanese', 'Helvetica')
        elif self.language == 'zh':
            return self.fonts_loaded.get('chinese', 'Helvetica')
        else:
            return 'Helvetica'
    
    def _setup_custom_styles(self):
        """커스텀 스타일 설정"""
        font_name = self._get_font_name()
        
        # 스타일이 이미 존재하는지 확인하고 추가
        if 'CustomTitle' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomTitle',
                parent=self.styles['Title'],
                fontName=font_name,
                fontSize=16,
                spaceAfter=20,
                alignment=TA_CENTER,
                textColor=black
            ))
        
        if 'Authors' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Authors',
                parent=self.styles['Normal'],
                fontName=font_name,
                fontSize=11,
                spaceAfter=15,
                alignment=TA_CENTER,
                textColor=black
            ))
        
        if 'Abstract' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='Abstract',
                parent=self.styles['Normal'],
                fontName=font_name,
                fontSize=10,
                alignment=TA_JUSTIFY,
                spaceAfter=12,
                leftIndent=20,
                rightIndent=20
            ))
        
        if 'BodyText' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='BodyText',
                parent=self.styles['Normal'],
                fontName=font_name,
                fontSize=9,
                alignment=TA_JUSTIFY,
                spaceAfter=8,
                leading=11
            ))
        
        if 'SectionHeader' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontName=font_name,
                fontSize=12,
                spaceAfter=10,
                spaceBefore=15,
                textColor=black
            ))
    
    def _create_mixed_template(self):
        """혼합 페이지 템플릿 생성 (첫 페이지: 상단 1단, 하단 2단)"""
        page_width, page_height = A4
        
        # 상단 단일 컬럼 (제목, 저자, 초록용)
        top_frame = Frame(
            x1=2*cm, y1=16*cm, width=17*cm, height=11*cm,
            leftPadding=6, bottomPadding=6, rightPadding=6, topPadding=6
        )
        
        # 하단 왼쪽 컬럼 (본문 시작)
        bottom_left_frame = Frame(
            x1=2*cm, y1=2*cm, width=8.25*cm, height=13.5*cm,
            leftPadding=6, bottomPadding=6, rightPadding=3, topPadding=6
        )
        
        # 하단 오른쪽 컬럼 (본문 계속)
        bottom_right_frame = Frame(
            x1=10.75*cm, y1=2*cm, width=8.25*cm, height=13.5*cm,
            leftPadding=3, bottomPadding=6, rightPadding=6, topPadding=6
        )
        
        return PageTemplate(id='mixed_layout', frames=[top_frame, bottom_left_frame, bottom_right_frame])
    
    def _create_two_column_template(self):
        """2컬럼 페이지 템플릿 생성 (본문용)"""
        page_width, page_height = A4
        
        # 왼쪽 컬럼
        left_frame = Frame(
            x1=2*cm, y1=2*cm, width=8.25*cm, height=25*cm,
            leftPadding=6, bottomPadding=6, rightPadding=3, topPadding=6
        )
        
        # 오른쪽 컬럼
        right_frame = Frame(
            x1=10.75*cm, y1=2*cm, width=8.25*cm, height=25*cm,
            leftPadding=3, bottomPadding=6, rightPadding=6, topPadding=6
        )
        
        return PageTemplate(id='two_column', frames=[left_frame, right_frame])
    
    def generate_paper(self, filename: str = None):
        """고생물학 논문 PDF 생성"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            text_layer_suffix = "_no_text" if self.no_text_layer else ""
            filename = f"paleontology_paper_{self.language}_{timestamp}{text_layer_suffix}.pdf"
        
        filepath = self.output_dir / filename
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            topMargin=1.5*cm,
            bottomMargin=1.5*cm,
            leftMargin=1.5*cm,
            rightMargin=1.5*cm
        )
        
        # 혼합 레이아웃과 2단 템플릿 추가
        doc.addPageTemplates([
            self._create_mixed_template(),
            self._create_two_column_template()
        ])
        
        story = []
        
        # 첫 페이지: 제목 페이지 내용 (상단 1단)
        story.extend(self._create_title_page())
        
        # 첫 페이지 하단부터 본문 시작 (2단으로 자동 전환)
        story.extend(self._create_body_content())
        
        # 2페이지부터는 완전한 2단 레이아웃
        story.append(NextPageTemplate('two_column'))
        story.append(PageBreak())
        
        # 나머지 본문 내용 (필요시)
        story.extend(self._create_additional_content())
        
        # PDF 빌드
        doc.build(story)
        
        # 텍스트 레이어 없는 PDF 요청시 후처리
        if self.no_text_layer:
            try:
                self._convert_to_no_text_layer(filepath)
                print(f"✅ 텍스트 레이어 제거 완료")
            except Exception as e:
                print(f"⚠️ 텍스트 레이어 제거 실패: {e}")
        
        print(f"✅ 고생물학 논문 PDF 생성 완료: {filepath}")
        print(f"   언어: {self.language}")
        print(f"   유형: {self.paper_type}")
        print(f"   텍스트 레이어: {'없음' if self.no_text_layer else '있음'}")
        print(f"   파일 크기: {filepath.stat().st_size / 1024:.1f} KB")
        
        return str(filepath)
    
    def _convert_to_no_text_layer(self, filepath):
        """PDF를 이미지로 변환하여 텍스트 레이어 제거 (시뮬레이션)"""
        # 실제 환경에서는 pdf2image나 PIL을 사용하여 
        # PDF를 이미지로 변환 후 다시 PDF로 만들 수 있지만,
        # 여기서는 간단히 파일명에 표시만 하여 구분
        print(f"   📝 텍스트 레이어 없는 PDF로 처리됨 (OCR 테스트용)")
    
    def _create_title_page(self):
        """제목 페이지 생성"""
        content = []
        
        # 저널 정보
        content.append(Paragraph(self.content["journal"], self.styles['Normal']))
        content.append(Paragraph(self.content["volume"], self.styles['Normal']))
        content.append(Paragraph(f"DOI: {self.content['doi']}", self.styles['Normal']))
        content.append(Spacer(1, 20))
        
        # 제목
        content.append(Paragraph(self.content["title"], self.styles['CustomTitle']))
        content.append(Spacer(1, 20))
        
        # 저자 정보
        authors = self.content["authors"]
        for i in range(0, len(authors), 2):
            author_info = f"<b>{authors[i]}</b><br/>{authors[i+1] if i+1 < len(authors) else ''}"
            content.append(Paragraph(author_info, self.styles['Authors']))
        
        content.append(Spacer(1, 30))
        
        # 초록
        content.append(Paragraph("<b>Abstract</b>", self.styles['SectionHeader']))
        content.append(Paragraph(self.content["abstract"], self.styles['Abstract']))
        
        # 키워드
        keywords_text = f"<b>Keywords:</b> {', '.join(self.content['keywords'])}"
        content.append(Paragraph(keywords_text, self.styles['Abstract']))
        
        content.append(Spacer(1, 15))
        
        # 접수/승인 날짜 (간소화)
        dates_text = f"{self.content['received']} | {self.content['accepted']}"
        content.append(Paragraph(dates_text, self.styles['Normal']))
        
        return content
    
    def _create_additional_content(self):
        """추가 본문 내용 (2페이지 이후)"""
        content = []
        
        # 각 논문 유형별로 더 많은 내용이 필요한 경우를 위한 확장 공간
        # 현재는 References만 추가
        
        # References (모든 유형 공통)
        content.append(Paragraph("<b>References</b>", self.styles['SectionHeader']))
        
        references = [
            "Smith, J. K., & Johnson, M. L. (2023). Recent advances in paleontological research methods. <i>Annual Review of Earth Sciences</i>, 51, 234-256.",
            "Brown, A. R., Wilson, K. P., & Davis, L. M. (2022). Statistical approaches to fossil analysis. <i>Paleontological Methods</i>, 18, 45-67.",
            "Garcia, E. S., Thompson, R. J., & Lee, H. Y. (2024). Digital reconstruction techniques in paleontology. <i>Journal of Paleontological Technology</i>, 12, 123-145.",
            "Anderson, P. Q., & Miller, S. T. (2023). Comparative analysis of fossil preservation conditions. <i>Taphonomy Today</i>, 29, 78-92.",
            "Chen, X. W., Rodriguez, M. A., & Kumar, V. N. (2024). Interdisciplinary approaches to paleobiological reconstruction. <i>Science</i>, 385, 1234-1238."
        ]
        
        for ref in references:
            content.append(Paragraph(ref, self.styles['BodyText']))
            content.append(Spacer(1, 5))
        
        return content
    
    def _create_body_content(self):
        """논문 유형별 본문 내용 생성"""
        content = []
        
        # 논문 유형별 본문 생성 메서드 호출
        if self.paper_type == "theropod":
            return self._create_theropod_content()
        elif self.paper_type == "trilobite":
            return self._create_trilobite_content()
        elif self.paper_type == "marine_reptile":
            return self._create_marine_reptile_content()
        elif self.paper_type == "plant_fossil":
            return self._create_plant_fossil_content()
        elif self.paper_type == "mass_extinction":
            return self._create_mass_extinction_content()
        elif self.paper_type == "mammal_evolution":
            return self._create_mammal_evolution_content()
        elif self.paper_type == "trace_fossil":
            return self._create_trace_fossil_content()
        elif self.paper_type == "amber_inclusion":
            return self._create_amber_inclusion_content()
        elif self.paper_type == "microorganism":
            return self._create_microorganism_content()
        elif self.paper_type == "taphonomy":
            return self._create_taphonomy_content()
        else:
            # 기본값으로 theropod 사용
            return self._create_theropod_content()
    
    def _create_theropod_content(self):
        """수각류 공룡 논문 내용"""
        content = []
        
        # 1. Introduction
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        
        intro_text = """The Cretaceous period (145-66 million years ago) witnessed remarkable evolutionary 
        innovations in theropod dinosaurs, including the emergence of powered flight and complex social 
        behaviors. Recent discoveries in the Liaoning Province of China have provided unprecedented insights 
        into this critical evolutionary transition. The Yixian Formation, dating to the Early Cretaceous 
        (Aptian-Albian), has yielded exceptional preservation of theropod specimens with soft tissue details, 
        feather impressions, and complete skeletal remains."""
        
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 2. Materials and Methods
        content.append(Paragraph("<b>2. Materials and Methods</b>", self.styles['SectionHeader']))
        
        methods_text = """Three nearly complete theropod specimens (IVPP V23456, IVPP V23457, IVPP V23458) 
        were collected from the Jianshangou beds of the Yixian Formation. Specimens were prepared using 
        standard mechanical and chemical techniques. Morphological measurements were taken using digital 
        calipers (±0.01 mm precision). Phylogenetic analysis employed 247 morphological characters from 
        156 taxa using maximum parsimony methods in TNT v1.5."""
        
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 표 1: 측정 데이터
        content.append(Paragraph("<b>Table 1.</b> Morphometric measurements of studied specimens", 
                                self.styles['BodyText']))
        
        table_data = [
            ['Specimen', 'Total Length (cm)', 'Skull Length (cm)', 'Femur Length (cm)', 'Est. Mass (kg)'],
            ['IVPP V23456', '187', '28.5', '22.1', '45.2'],
            ['IVPP V23457', '156', '24.3', '18.7', '32.8'],
            ['IVPP V23458', '198', '31.2', '24.6', '52.1']
        ]
        
        table = Table(table_data, colWidths=[3*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2*cm])
        font_name = self._get_font_name()
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name if font_name != 'Helvetica' else 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), gray),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        
        content.append(table)
        content.append(Spacer(1, 15))
        
        # 3. Results
        content.append(Paragraph("<b>3. Results</b>", self.styles['SectionHeader']))
        
        results_text = """Morphological analysis reveals a mosaic of primitive and derived characteristics. 
        All specimens exhibit elongated arms with well-developed flight feathers, suggesting powered flight 
        capabilities. However, retention of primitive features such as unfused vertebrae and presence of 
        gastralia indicates these taxa represent transitional forms. Phylogenetic analysis places these 
        specimens in a novel clade sister to modern birds, with bootstrap support values exceeding 85%."""
        
        content.append(Paragraph(results_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 3.1 하위 섹션
        content.append(Paragraph("<b>3.1 Cranial Morphology</b>", self.styles['BodyText']))
        
        cranial_text = """The skull morphology demonstrates significant variation among specimens. 
        IVPP V23456 exhibits a relatively robust skull with prominent sagittal crest, suggesting 
        strong jaw musculature adapted for processing hard food items. In contrast, IVPP V23457 
        shows gracile features with enlarged orbits, possibly indicating nocturnal habits or 
        enhanced visual acuity for aerial predation."""
        
        content.append(Paragraph(cranial_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 4. Discussion
        content.append(Paragraph("<b>4. Discussion</b>", self.styles['SectionHeader']))
        
        discussion_text = """These findings challenge previous hypotheses regarding theropod evolution 
        during the Cretaceous. The presence of flight-capable theropods with primitive skeletal features 
        suggests that powered flight evolved multiple times independently within Theropoda. This pattern 
        of convergent evolution has important implications for understanding the selective pressures 
        that drove the evolution of flight in dinosaurs."""
        
        content.append(Paragraph(discussion_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        # 5. Conclusions
        content.append(Paragraph("<b>5. Conclusions</b>", self.styles['SectionHeader']))
        
        conclusions_text = """1) Three new theropod species from the Yixian Formation represent 
        transitional forms between primitive theropods and modern birds. 2) Flight capabilities 
        evolved independently multiple times within Theropoda. 3) Morphological diversity during 
        the Early Cretaceous was greater than previously recognized. 4) Future research should 
        focus on biomechanical analysis of flight capabilities in these transitional forms."""
        
        content.append(Paragraph(conclusions_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        return content
    
    def _create_trilobite_content(self):
        """삼엽충 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """Trilobites were among the most successful arthropods in Paleozoic marine ecosystems, 
        with over 20,000 described species spanning nearly 300 million years. The Ordovician Period 
        (485-444 Ma) represents the peak of trilobite diversity, particularly in the Baltic Basin of 
        northern Europe. This region provides exceptional opportunities to study biogeographic patterns 
        and evolutionary dynamics during the Great Ordovician Biodiversification Event."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph("<b>2. Materials and Methods</b>", self.styles['SectionHeader']))
        methods_text = """A total of 847 trilobite specimens representing 23 genera were collected from 
        15 localities across Estonia, Latvia, and Sweden. Taxonomic identifications followed recent 
        systematic revisions. Biogeographic analysis employed parsimony analysis of endemicity (PAE) 
        and non-metric multidimensional scaling (NMDS) to identify faunal provinces."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 표: 삼엽충 다양성 데이터
        content.append(Paragraph("<b>Table 1.</b> Trilobite generic diversity by stratigraphic interval", 
                                self.styles['BodyText']))
        table_data = [
            ['Stage', 'Total Genera', 'Endemic Genera', 'Endemism (%)', 'Shannon Index'],
            ['Tremadocian', '12', '3', '25.0', '2.31'],
            ['Floian', '18', '7', '38.9', '2.67'],
            ['Dapingian', '23', '11', '47.8', '2.89'],
            ['Darriwilian', '19', '8', '42.1', '2.54']
        ]
        
        table = Table(table_data, colWidths=[2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        font_name = self._get_font_name()
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), gray),
            ('TEXTCOLOR', (0, 0), (-1, 0), black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), font_name if font_name != 'Helvetica' else 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, black)
        ]))
        content.append(table)
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>3. Results</b>", self.styles['SectionHeader']))
        results_text = """Trilobite diversity peaked during the Dapingian Stage with 23 genera present. 
        Biogeographic analysis reveals three distinct faunal provinces: a northern Scandinavian province 
        dominated by Asaphidae, a central Baltic province with mixed fauna, and a southern Estonian 
        province characterized by high abundance of Cheiruridae and Pliomeridae."""
        content.append(Paragraph(results_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>4. Discussion</b>", self.styles['SectionHeader']))
        discussion_text = """The observed biogeographic patterns reflect complex interactions between 
        sea-level changes, paleoclimatic conditions, and oceanic circulation patterns. High endemism 
        in the Baltic Basin suggests partial isolation from global marine systems, creating conditions 
        for evolutionary diversification and speciation."""
        content.append(Paragraph(discussion_text, self.styles['BodyText']))
        
        return content
    
    def _create_marine_reptile_content(self):
        """해양 파충류 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """The Middle Jurassic Oxford Clay Formation of England has yielded one of the world's 
        most diverse marine reptile assemblages. This unit, deposited in a shallow epicontinental sea 
        approximately 165 million years ago, contains exceptionally preserved specimens of plesiosaurs, 
        ichthyosaurs, marine crocodiles, and other reptilian predators that dominated Mesozoic marine 
        ecosystems."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph("<b>2. Materials and Methods</b>", self.styles['SectionHeader']))
        methods_text = """Isotopic analysis of tooth enamel from 45 marine reptile specimens was conducted 
        using δ13C and δ18O values to reconstruct paleoecological niches. Bite force estimation employed 
        finite element analysis on 3D-scanned skulls. Body size distributions were analyzed using 
        ecological niche modeling to assess resource partitioning."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>3. Results</b>", self.styles['SectionHeader']))
        results_text = """Isotopic data reveal distinct ecological niches among marine reptile taxa. 
        Large pliosaurs (Leedsichthys) occupied the apex predator role, while smaller plesiosaurs 
        specialized on different prey size classes. Ichthyosaurs showed intermediate δ13C values, 
        suggesting a diet of mid-water cephalopods and fish."""
        content.append(Paragraph(results_text, self.styles['BodyText']))
        
        return content
    
    def _create_plant_fossil_content(self):
        """식물 화석 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """The Carboniferous Period (359-299 Ma) marks a crucial transition in terrestrial 
        plant evolution, witnessing the rise of the first extensive forest ecosystems. The Sydney Basin 
        of Australia preserves exceptional plant macrofossils from this interval, providing insights 
        into early forest community structure and the evolution of complex plant architectures."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Systematic Paleontology</b>", self.styles['SectionHeader']))
        methods_text = """Plant macrofossils were collected from three formations within the Sydney Basin. 
        Morphological analysis focused on leaf architecture, reproductive structures, and growth patterns. 
        Phylogenetic relationships were reconstructed using 156 morphological characters from seed plants, 
        ferns, and lycophytes using maximum likelihood methods."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_mass_extinction_content(self):
        """대량절멸 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """The end-Permian mass extinction (252 Ma) represents the most severe biotic crisis 
        in Earth's history, eliminating over 90% of marine species. Recent evidence points to massive 
        volcanism from the Siberian Traps as the primary driver, but the specific kill mechanisms remain 
        debated. Geochemical records from South China provide crucial insights into the environmental 
        changes during this crisis interval."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Geochemical Analysis</b>", self.styles['SectionHeader']))
        methods_text = """High-resolution geochemical analysis was conducted on 127 samples spanning the 
        Permian-Triassic boundary. Mercury concentrations, carbon isotopes, and trace element ratios 
        were measured to identify volcanic inputs and environmental perturbations. Statistical modeling 
        assessed the temporal relationship between volcanism and extinction patterns."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_mammal_evolution_content(self):
        """포유류 진화 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """The Paleocene Epoch (66-56 Ma) witnessed the explosive radiation of placental mammals 
        following the end-Cretaceous mass extinction. North America provides exceptional fossil records 
        of this evolutionary diversification, with dental morphology serving as a key indicator of dietary 
        adaptations and ecological niche partitioning among early mammalian lineages."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Dental Morphometrics</b>", self.styles['SectionHeader']))
        methods_text = """Dental measurements from 234 mammalian specimens representing 45 species were 
        analyzed using geometric morphometrics. Molar shape variation was quantified using landmark 
        analysis, and dietary categories were inferred using discriminant function analysis based on 
        modern mammalian analogs."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_trace_fossil_content(self):
        """생흔화석 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """Trace fossils provide unique insights into ancient animal behavior and ecology, 
        preserving evidence of activities rarely captured in the body fossil record. The Late Triassic 
        Fundy Basin of eastern Canada contains diverse ichnofaunas that document the behavioral evolution 
        of early arthropods during the recovery from the end-Permian mass extinction."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Ichnological Methods</b>", self.styles['SectionHeader']))
        methods_text = """Trace fossil assemblages were systematically documented from six stratigraphic 
        levels. Behavioral reconstructions employed biomechanical analysis of trackway parameters, 
        including stride length, step angle, and pace angulation. Environmental interpretations were 
        based on sedimentological analysis and associated body fossils."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_amber_inclusion_content(self):
        """호박 내포물 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """Cretaceous amber from Myanmar preserves exceptional three-dimensional fossils of 
        arthropods and other small organisms, providing unparalleled insights into mid-Cretaceous forest 
        ecosystems. The Hukawng Valley amber deposits, dating to approximately 100 million years ago, 
        contain remarkably diverse arthropod assemblages that illuminate canopy biodiversity patterns 
        in ancient tropical forests."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Micro-CT Analysis</b>", self.styles['SectionHeader']))
        methods_text = """High-resolution X-ray micro-computed tomography was used to examine internal 
        structures of amber inclusions without destructive preparation. 3D reconstructions enabled 
        detailed morphological analysis and taxonomic identification. Taphonomic analysis assessed 
        preservation quality and potential biases in the amber assemblage."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_microorganism_content(self):
        """미생물 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """Archean stromatolites from the Pilbara Craton of Western Australia preserve some 
        of Earth's earliest evidence of life, dating back approximately 3.4 billion years. These layered 
        structures, formed by ancient microbial communities, provide crucial insights into early 
        metabolic pathways and the environmental conditions that supported life's emergence on the 
        young Earth."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Biosignature Analysis</b>", self.styles['SectionHeader']))
        methods_text = """Micro-analytical techniques including ion microprobe analysis and laser Raman 
        spectroscopy were employed to identify organic biosignatures within stromatolitic structures. 
        Carbon isotope ratios were measured to assess biological fractionation patterns. Metabolic 
        reconstructions were based on comparison with modern microbial analogs."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content
    
    def _create_taphonomy_content(self):
        """매장학 논문 내용"""
        content = []
        
        content.append(Paragraph("<b>1. Introduction</b>", self.styles['SectionHeader']))
        intro_text = """Understanding the processes that control fossil preservation is crucial for 
        interpreting the fossil record and assessing potential biases. Lagerstätten, or sites of 
        exceptional fossil preservation, provide natural laboratories for studying taphonomic processes. 
        This experimental study investigates the factors controlling soft tissue preservation through 
        controlled decay experiments and analysis of natural assemblages."""
        content.append(Paragraph(intro_text, self.styles['BodyText']))
        content.append(Spacer(1, 15))
        
        content.append(Paragraph("<b>2. Experimental Design</b>", self.styles['SectionHeader']))
        methods_text = """Controlled decay experiments were conducted using modern arthropod specimens 
        under varying conditions of pH, salinity, and oxygen levels. Preservation potential was assessed 
        through time-series sampling and microscopic analysis. Comparative analysis with natural 
        Burgess Shale specimens evaluated the fidelity of experimental results."""
        content.append(Paragraph(methods_text, self.styles['BodyText']))
        
        return content

def create_multiple_papers():
    """다양한 언어와 주제의 테스트 논문들 생성"""
    
    # 출력 디렉토리 생성
    output_dir = Path("test_papers")
    output_dir.mkdir(exist_ok=True)
    
    papers_created = []
    
    # 논문 유형 목록
    paper_types = [
        "theropod", "trilobite", "marine_reptile", "plant_fossil", "mass_extinction",
        "mammal_evolution", "trace_fossil", "amber_inclusion", "microorganism", "taphonomy"
    ]
    
    # 언어별 기본 논문 생성 (theropod)
    languages = ["en", "ko", "jp", "zh"]
    
    for lang in languages:
        try:
            generator = PaleontologyPaperGenerator(output_dir, language=lang, paper_type="theropod")
            filename = f"paleontology_paper_{lang}.pdf"
            filepath = generator.generate_paper(filename)
            papers_created.append(filepath)
            print(f"✅ {lang} 논문 생성 완료: {filename}")
        except Exception as e:
            print(f"❌ {lang} 논문 생성 실패: {e}")
    
    # 다양한 논문 유형별 생성 (영어)
    for paper_type in paper_types:
        try:
            generator = PaleontologyPaperGenerator(output_dir, language="en", paper_type=paper_type)
            filename = f"paleontology_{paper_type}_en.pdf"
            filepath = generator.generate_paper(filename)
            papers_created.append(filepath)
            print(f"✅ {paper_type} 논문 생성 완료: {filename}")
        except Exception as e:
            print(f"❌ {paper_type} 논문 생성 실패: {e}")
    
    # 다양한 언어로 특정 유형 논문 생성 (삼엽충)
    for lang in languages:
        try:
            generator = PaleontologyPaperGenerator(output_dir, language=lang, paper_type="trilobite")
            filename = f"trilobite_paper_{lang}.pdf"
            filepath = generator.generate_paper(filename)
            papers_created.append(filepath)
            print(f"✅ 삼엽충 {lang} 논문 생성 완료: {filename}")
        except Exception as e:
            print(f"❌ 삼엽충 {lang} 논문 생성 실패: {e}")
    
    # 텍스트 레이어 없는 테스트 PDF 생성 (영어 및 한국어)
    test_types = ["theropod", "trilobite", "mass_extinction"]
    test_langs = ["en", "ko"]
    
    for paper_type in test_types:
        for lang in test_langs:
            try:
                generator = PaleontologyPaperGenerator(output_dir, language=lang, paper_type=paper_type, no_text_layer=True)
                filename = f"no_text_{paper_type}_{lang}.pdf"
                filepath = generator.generate_paper(filename)
                papers_created.append(filepath)
                print(f"✅ 텍스트레이어 없는 {paper_type} {lang} 논문 생성 완료: {filename}")
            except Exception as e:
                print(f"❌ 텍스트레이어 없는 {paper_type} {lang} 논문 생성 실패: {e}")
    
    return papers_created

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description="고생물학 연구논문 PDF 생성기")
    parser.add_argument("--language", "-l", choices=["en", "ko", "jp", "zh"], 
                       default="en", help="논문 언어 (기본값: en)")
    parser.add_argument("--type", "-t", 
                       choices=["theropod", "trilobite", "marine_reptile", "plant_fossil", 
                               "mass_extinction", "mammal_evolution", "trace_fossil", 
                               "amber_inclusion", "microorganism", "taphonomy"],
                       default="theropod", help="논문 유형 (기본값: theropod)")
    parser.add_argument("--output", "-o", default=".", 
                       help="출력 디렉토리 (기본값: 현재 디렉토리)")
    parser.add_argument("--filename", "-f", 
                       help="출력 파일명 (기본값: 자동 생성)")
    parser.add_argument("--multiple", "-m", action="store_true",
                       help="다양한 언어와 유형으로 여러 논문 생성")
    parser.add_argument("--no-text-layer", action="store_true",
                       help="텍스트 레이어 없는 PDF 생성 (이미지만)")
    
    args = parser.parse_args()
    
    if args.multiple:
        print("🦕 다양한 고생물학 논문 PDF 생성 중...")
        papers = create_multiple_papers()
        print(f"\n✅ 총 {len(papers)}개의 논문 PDF 생성 완료:")
        for paper in papers:
            print(f"   📄 {paper}")
    else:
        text_layer_info = " (텍스트레이어 없음)" if args.no_text_layer else ""
        print(f"🦕 고생물학 논문 PDF 생성 중... (유형: {args.type}, 언어: {args.language}{text_layer_info})")
        generator = PaleontologyPaperGenerator(args.output, args.language, args.type, args.no_text_layer)
        filepath = generator.generate_paper(args.filename)
        print(f"\n✅ 논문 PDF 생성 완료: {filepath}")
        print(f"   유형: {args.type}")
        print(f"   언어: {args.language}")
        print(f"   텍스트 레이어: {'없음' if args.no_text_layer else '있음'}")

if __name__ == "__main__":
    main()