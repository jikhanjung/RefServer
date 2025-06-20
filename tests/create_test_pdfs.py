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
        
        # 논문 유형별 내용 설정
        self.content = self._get_content_by_type_and_language()
        
        # 스타일 설정
        self.styles = getSampleStyleSheet()
        self.fonts_loaded = {}
        self._setup_fonts()
        self._setup_custom_styles()
    
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
                    self.fonts_loaded[lang] = 'Helvetica'
                    
        except Exception as e:
            print(f"⚠️ 폰트 설정 중 오류: {e}")
            self.fonts_loaded = {
                'korean': 'Helvetica',
                'japanese': 'Helvetica', 
                'chinese': 'Helvetica'
            }
    
    def _get_font_name(self):
        """현재 언어에 맞는 폰트 반환"""
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
        
        # 기본 Normal 스타일도 CJK 폰트로 업데이트
        if 'CustomNormal' not in self.styles:
            self.styles.add(ParagraphStyle(
                name='CustomNormal',
                parent=self.styles['Normal'],
                fontName=font_name,
                fontSize=10,
                textColor=black
            ))
        
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
    
    def _get_content_by_type_and_language(self):
        """논문 유형과 언어별 내용 반환"""
        return self._get_paper_content(self.paper_type, self.language)
    
    def _get_paper_content(self, paper_type: str, language: str):
        """논문 유형별 내용 데이터베이스 (각 유형마다 완전히 다른 내용)"""
        
        # 논문 유형별 완전히 다른 템플릿
        paper_templates = {
            "theropod": {
                "en": {
                    "title": "Evolutionary Analysis of Cretaceous Theropod Dinosaurs: New Evidence from Liaoning Province Fossil Record",
                    "abstract": "The Cretaceous period witnessed remarkable evolutionary innovations in theropod dinosaurs, including the emergence of powered flight and complex social behaviors. Recent discoveries in the Liaoning Province of China have provided unprecedented insights into this critical evolutionary transition. Our analysis of three newly discovered specimens reveals a mosaic of primitive and derived characteristics that challenge existing phylogenetic hypotheses."
                },
                "ko": {
                    "title": "백악기 수각류 공룡의 진화적 분석: 랴오닝성 화석 기록에서 발견된 새로운 증거",
                    "abstract": "백악기는 수각류 공룡의 놀라운 진화적 혁신을 목격했으며, 여기에는 동력 비행의 출현과 복잡한 사회적 행동이 포함된다. 중국 랴오닝성의 최근 발견들은 이 중요한 진화적 전환에 대한 전례 없는 통찰을 제공했다. 새로 발견된 3개 표본의 분석은 기존 계통발생 가설에 도전하는 원시적 및 파생적 특성의 모자이크를 드러낸다."
                },
                "jp": {
                    "title": "白亜紀獣脚類恐竜の進化的分析：遼寧省化石記録からの新たな証拠",
                    "abstract": "白亜紀は獣脚類恐竜の著しい進化的革新を目撃し、動力飛行の出現と複雑な社会行動が含まれる。中国遼寧省の最近の発見は、この重要な進化的転換への前例のない洞察を提供した。新たに発見された3つの標本の分析は、既存の系統発生仮説に挑戦する原始的および派生的特徴のモザイクを明らかにする。"
                },
                "zh": {
                    "title": "白垩纪兽脚类恐龙的进化分析：来自辽宁省化石记录的新证据",
                    "abstract": "白垩纪见证了兽脚类恐龙的显著进化创新，包括动力飞行的出现和复杂的社会行为。中国辽宁省的最新发现为这一关键的进化转变提供了前所未有的见解。对新发现的三个标本的分析揭示了挑战现有系统发生假说的原始和衍生特征的镶嵌模式。"
                }
            },
            "trilobite": {
                "en": {
                    "title": "Diversity and Biogeography of Ordovician Trilobites from the Baltic Basin: Implications for Paleozoic Marine Ecosystems",
                    "abstract": "The Ordovician Period represents the zenith of trilobite diversity, with the Baltic Basin preserving exceptional fossil assemblages from this critical interval. Our comprehensive taxonomic analysis of 1,247 specimens reveals 23 genera and 47 species, including 8 new species. Biogeographic patterns indicate extensive faunal exchange between Baltica and Laurentia during the Great Ordovician Biodiversification Event."
                },
                "ko": {
                    "title": "발트해 분지 오르도비스기 삼엽충의 다양성과 생물지리학: 고생대 해양 생태계에 대한 함의",
                    "abstract": "오르도비스기는 삼엽충 다양성의 정점을 나타내며, 발트해 분지는 이 중요한 시기의 뛰어난 화석 군집을 보존하고 있다. 1,247개 표본의 포괄적 분류학적 분석은 8개 신종을 포함하여 23속 47종을 밝혀냈다. 생물지리학적 패턴은 오르도비스기 대방사 사건 동안 발티카와 로렌시아 간의 광범위한 동물군 교환을 나타낸다."
                },
                "jp": {
                    "title": "バルト海盆地オルドビス紀三葉虫の多様性と生物地理学：古生代海洋生態系への示唆",
                    "abstract": "オルドビス紀は三葉虫多様性の頂点を表し、バルト海盆地はこの重要な期間の優れた化石群集を保存している。1,247標本の包括的分類学的分析により、8新種を含む23属47種が明らかになった。生物地理学的パターンは、オルドビス紀大放散事件中のバルティカとローレンシア間の広範囲な動物相交換を示している。"
                },
                "zh": {
                    "title": "波罗的海盆地奥陶纪三叶虫的多样性与生物地理学：对古生代海洋生态系统的启示",
                    "abstract": "奥陶纪代表了三叶虫多样性的顶峰，波罗的海盆地保存了这一关键时期的优秀化石群落。对1,247个标本的全面分类学分析揭示了23属47种，包括8个新种。生物地理学模式表明在奥陶纪大辐射事件期间波罗的海板块和劳伦大陆之间存在广泛的动物群交换。"
                }
            },
            "marine_reptile": {
                "en": {
                    "title": "Paleoecology of Jurassic Marine Reptiles: Dietary Specialization and Niche Partitioning in the Oxford Clay Formation",
                    "abstract": "Jurassic marine reptiles exhibited remarkable ecological diversity as apex predators in Mesozoic seas. Analysis of 156 specimens from the Oxford Clay Formation reveals distinct dietary preferences: ichthyosaurs specialized in soft-bodied cephalopods, plesiosaurs targeted fish, and marine crocodiles consumed crustaceans. This trophic partitioning minimized interspecific competition and maintained ecosystem stability during the height of marine reptile dominance."
                },
                "ko": {
                    "title": "쥐라기 해양 파충류의 고생태학: 옥스포드 점토층에서의 식이 특화와 생태적 지위 분할",
                    "abstract": "쥐라기 해양 파충류는 중생대 바다의 최상위 포식자로서 놀라운 생태적 다양성을 보였다. 옥스포드 점토층에서 발견된 156개 표본의 분석은 뚜렷한 식이 선호도를 드러낸다: 어룡은 연체 두족류에 특화되었고, 수장룡은 어류를 표적으로 했으며, 해양 악어는 갑각류를 섭취했다. 이러한 영양 분할은 종간 경쟁을 최소화하고 해양 파충류 우세 시기의 생태계 안정성을 유지했다."
                },
                "jp": {
                    "title": "ジュラ紀海洋爬虫類の古生態学：オックスフォード粘土層における食性特化と生態的地位分割",
                    "abstract": "ジュラ紀海洋爬虫類は中生代の海における頂点捕食者として驚くべき生態学的多様性を示した。オックスフォード粘土層の156標本の分析により明確な食性選好が明らかになった：魚竜は軟体頭足類に特化し、首長竜は魚類を標的とし、海洋ワニは甲殻類を摂取した。この栄養分割は種間競争を最小化し、海洋爬虫類優勢期の生態系安定性を維持した。"
                },
                "zh": {
                    "title": "侏罗纪海洋爬行动物古生态学：牛津粘土层中的食性特化与生态位分割",
                    "abstract": "侏罗纪海洋爬行动物作为中生代海洋的顶级捕食者表现出了显著的生态多样性。对牛津粘土层156个标本的分析揭示了明显的食性偏好：鱼龙专门捕食软体头足类，蛇颈龙以鱼类为目标，而海洋鳄鱼则摄食甲壳类。这种营养分割最大限度地减少了种间竞争，并在海洋爬行动物统治时期维持了生态系统的稳定性。"
                }
            },
            "plant_fossil": {
                "en": {
                    "title": "Carboniferous Plant Macrofossils from the Sydney Basin: Evidence for Early Forest Stratification and Ecological Complexity",
                    "abstract": "The Sydney Basin of Australia preserves exceptional plant macrofossils from the Late Carboniferous, providing insights into early forest ecosystem development. Our analysis reveals diverse assemblages including seed ferns (Neuropteris, Alethopteris), early conifers (Walchia), and lycopsids (Lepidodendron), indicating complex vertical stratification similar to modern rainforests. Paleosol analysis suggests seasonal climate conditions that promoted high plant diversity."
                },
                "ko": {
                    "title": "시드니 분지의 석탄기 식물 대형화석: 초기 산림 계층화와 생태적 복잡성의 증거",
                    "abstract": "호주 시드니 분지는 후기 석탄기의 뛰어난 식물 대형화석을 보존하여 초기 산림 생태계 발달에 대한 통찰을 제공한다. 우리의 분석은 종자양치류(Neuropteris, Alethopteris), 초기 침엽수(Walchia), 석송류(Lepidodendron)를 포함한 다양한 군집을 드러내며, 현대 열대우림과 유사한 복잡한 수직 계층화를 나타낸다. 고토양 분석은 높은 식물 다양성을 촉진한 계절성 기후 조건을 시사한다."
                },
                "jp": {
                    "title": "シドニー盆地の石炭紀植物大化石：初期森林成層化と生態学的複雑性の証拠",
                    "abstract": "オーストラリアのシドニー盆地は後期石炭紀の優れた植物大化石を保存し、初期森林生態系発達への洞察を提供する。我々の分析により、種子シダ（Neuropteris、Alethopteris）、初期針葉樹（Walchia）、石松類（Lepidodendron）を含む多様な群集が明らかになり、現代の熱帯雨林に類似した複雑な垂直成層化を示している。古土壌分析は高い植物多様性を促進した季節性気候条件を示唆する。"
                },
                "zh": {
                    "title": "悉尼盆地石炭纪植物大化石：早期森林分层和生态复杂性的证据",
                    "abstract": "澳大利亚悉尼盆地保存了晚石炭世的优秀植物大化石，为早期森林生态系统发育提供了见解。我们的分析揭示了包括种子蕨（Neuropteris、Alethopteris）、早期针叶树（Walchia）和石松类（Lepidodendron）在内的多样群落，表明类似现代雨林的复杂垂直分层。古土壤分析表明促进植物高多样性的季节性气候条件。"
                }
            },
            "mass_extinction": {
                "en": {
                    "title": "Mechanisms of the End-Permian Mass Extinction: Geochemical Evidence from South China Block Sections",
                    "abstract": "The end-Permian mass extinction represents Earth's most severe biotic crisis, eliminating ~90% of marine species. Geochemical analysis of boundary sections from the South China Block reveals multiple volcanic episodes, ocean acidification, and anoxic conditions. Carbon isotope excursions indicate massive organic carbon burial disruption. Our integrated approach identifies volcanic CO2 emissions as the primary driver of environmental collapse."
                },
                "ko": {
                    "title": "페름기말 대량절멸의 메커니즘: 중국 남부 블록 단면에서의 지구화학적 증거",
                    "abstract": "페름기말 대량절멸은 지구 역사상 가장 심각한 생물학적 위기로, 해양 종의 ~90%를 제거했다. 중국 남부 블록 경계 단면의 지구화학적 분석은 다중 화산 활동, 해양 산성화, 무산소 조건을 드러낸다. 탄소 동위원소 이탈은 대규모 유기탄소 매장 붕괴를 나타낸다. 우리의 통합적 접근은 화산성 CO2 배출을 환경 붕괴의 주요 동력으로 식별한다."
                },
                "jp": {
                    "title": "ペルム紀末大量絶滅のメカニズム：南中国ブロック断面からの地球化学的証拠",
                    "abstract": "ペルム紀末大量絶滅は地球史上最も深刻な生物学的危機を表し、海洋種の~90%を排除した。南中国ブロックの境界断面の地球化学分析により、複数の火山活動エピソード、海洋酸性化、無酸素条件が明らかになった。炭素同位体偏移は大規模な有機炭素埋没破綻を示す。我々の統合的アプローチは火山性CO2排出を環境崩壊の主要駆動力として特定する。"
                },
                "zh": {
                    "title": "二叠纪末大灭绝机制：来自华南板块剖面的地球化学证据",
                    "abstract": "二叠纪末大灭绝代表了地球历史上最严重的生物危机，消灭了约90%的海洋物种。对华南板块边界剖面的地球化学分析揭示了多次火山活动、海洋酸化和缺氧条件。碳同位素漂移表明大规模有机碳埋藏破坏。我们的综合方法确定火山CO2排放是环境崩溃的主要驱动因素。"
                }
            },
            "mammal_evolution": {
                "en": {
                    "title": "Paleocene Mammalian Adaptive Radiation: Morphological Innovations Following the K-Pg Extinction Event",
                    "abstract": "The Paleocene witnessed unprecedented mammalian diversification following the K-Pg extinction event. Analysis of dental morphology from Western North American formations reveals rapid evolution of specialized feeding strategies. Early ungulates, primates, and carnivorous mammals exhibited distinct adaptive innovations within 5 million years post-extinction. Body size evolution followed Cope's rule with accelerated gigantism in several lineages."
                },
                "ko": {
                    "title": "팔레오세 포유류 적응방산: K-Pg 절멸 사건 이후의 형태학적 혁신",
                    "abstract": "팔레오세는 K-Pg 절멸 사건 이후 전례 없는 포유류 다양화를 목격했다. 북미 서부 지층의 치아 형태학 분석은 특화된 섭식 전략의 급속한 진화를 드러낸다. 초기 유제류, 영장류, 육식 포유류는 절멸 후 500만 년 내에 뚜렷한 적응적 혁신을 보였다. 체구 진화는 여러 계통에서 가속화된 거대화와 함께 코프의 법칙을 따랐다."
                },
                "jp": {
                    "title": "暁新世哺乳類適応放散：K-Pg絶滅事象後の形態学的革新",
                    "abstract": "暁新世はK-Pg絶滅事象後の前例のない哺乳類多様化を目撃した。北米西部層序の歯形態学分析により、特化した摂食戦略の急速な進化が明らかになった。初期有蹄類、霊長類、肉食哺乳類は絶滅後500万年以内に明確な適応的革新を示した。体サイズ進化は複数の系統で加速された巨大化とともにコープの法則に従った。"
                },
                "zh": {
                    "title": "古新世哺乳动物适应辐射：K-Pg灭绝事件后的形态创新",
                    "abstract": "古新世见证了K-Pg灭绝事件后前所未有的哺乳动物多样化。对北美西部地层牙齿形态学的分析揭示了特化摄食策略的快速进化。早期有蹄类、灵长类和食肉哺乳动物在灭绝后500万年内表现出明显的适应性创新。体型进化遵循科普定律，多个谱系中出现加速巨大化。"
                }
            },
            "trace_fossil": {
                "en": {
                    "title": "Triassic Ichnofossils from the Fundy Basin: Early Dinosaur Locomotion and Behavioral Evolution",
                    "abstract": "The Fundy Basin of eastern Canada preserves exceptional Triassic trace fossil assemblages documenting early dinosaur behavior. Analysis of 847 trackways reveals bipedal locomotion, social behavior, and size-related speed variations. Grallator and Eubrontes ichnotaxa indicate theropod diversity, while novel Atreipus tracks suggest early ornithischian presence. Biomechanical analysis supports cursorial adaptations in basal dinosauromorphs."
                },
                "ko": {
                    "title": "펀디 분지의 트라이아스기 생흔화석: 초기 공룡 이동과 행동 진화",
                    "abstract": "캐나다 동부의 펀디 분지는 초기 공룡 행동을 기록한 뛰어난 트라이아스기 생흔화석 군집을 보존한다. 847개 보행렬의 분석은 이족보행, 사회적 행동, 크기 관련 속도 변화를 드러낸다. Grallator와 Eubrontes 생흔분류군은 수각류 다양성을 나타내며, 새로운 Atreipus 족적은 초기 조반류 존재를 시사한다. 생체역학 분석은 기저 공룡형류의 주행 적응을 뒷받침한다."
                },
                "jp": {
                    "title": "ファンディ盆地の三畳紀生痕化石：初期恐竜運動と行動進化",
                    "abstract": "カナダ東部のファンディ盆地は初期恐竜行動を記録した優れた三畳紀生痕化石群集を保存する。847の歩行跡の分析により二足歩行、社会行動、サイズ関連速度変化が明らかになった。GrallatorとEubrontes生痕分類群は獣脚類多様性を示し、新たなAtreipus足跡は初期鳥盤類存在を示唆する。生体力学分析は基盤的恐竜形類の走行適応を支持する。"
                },
                "zh": {
                    "title": "芬迪盆地三叠纪遗迹化石：早期恐龙运动和行为演化",
                    "abstract": "加拿大东部芬迪盆地保存了记录早期恐龙行为的优秀三叠纪遗迹化石群落。对847条行迹的分析揭示了双足运动、社会行为和与体型相关的速度变化。Grallator和Eubrontes遗迹分类群表明兽脚类多样性，而新的Atreipus足迹暗示早期鸟臀类的存在。生物力学分析支持基干恐龙形类的奔跑适应。"
                }
            },
            "amber_inclusion": {
                "en": {
                    "title": "Cretaceous Amber Arthropods from Myanmar: Exceptional Preservation and Mid-Mesozoic Forest Biodiversity",
                    "abstract": "Burmese amber from the Hukawng Valley preserves extraordinary three-dimensional arthropod inclusions dating to ~100 Ma. Micro-CT analysis of 312 specimens reveals 67 morphospecies representing 8 orders. Novel taxa include feather-winged beetles, primitive ants, and enigmatic arachnids. Taphonomic analysis indicates rapid resin entrapment in tropical forest canopies, providing unprecedented insights into Cretaceous terrestrial ecosystems."
                },
                "ko": {
                    "title": "미얀마 백악기 호박 절지동물: 뛰어난 보존과 중생대 중기 산림 생물다양성",
                    "abstract": "후카웅 계곡의 버마 호박은 약 1억 년 전으로 연대가 측정되는 놀라운 3차원 절지동물 내포물을 보존한다. 312개 표본의 마이크로 CT 분석은 8목을 대표하는 67개 형태종을 드러낸다. 새로운 분류군에는 깃털날개딱정벌레, 원시개미, 수수께끼의 거미류가 포함된다. 매장학적 분석은 열대 산림 수관에서의 급속한 수지 포획을 나타내며, 백악기 육상 생태계에 대한 전례 없는 통찰을 제공한다."
                },
                "jp": {
                    "title": "ミャンマー白亜紀琥珀節足動物：優れた保存と中生代中期森林生物多様性",
                    "abstract": "フカウン渓谷のビルマ琥珀は約1億年前に遡る驚くべき三次元節足動物内包物を保存する。312標本のマイクロCT分析により8目を代表する67形態種が明らかになった。新分類群には羽根翅甲虫、原始アリ、謎のクモ類が含まれる。堆積学分析は熱帯森林樹冠での急速な樹脂捕獲を示し、白亜紀陸域生態系への前例のない洞察を提供する。"
                },
                "zh": {
                    "title": "缅甸白垩纪琥珀节肢动物：优异保存与中生代中期森林生物多样性",
                    "abstract": "胡康谷地的缅甸琥珀保存了约1亿年前的非凡三维节肢动物包裹体。对312个标本的显微CT分析揭示了代表8个目的67个形态种。新类群包括羽翅甲虫、原始蚂蚁和神秘蛛形类。埋藏学分析表明热带森林冠层中的快速树脂包裹，为白垩纪陆地生态系统提供了前所未有的见解。"
                }
            },
            "microorganism": {
                "en": {
                    "title": "Archean Microbial Communities from the Pilbara Craton: Biosignatures and Early Earth Metabolic Pathways",
                    "abstract": "Archean stromatolites from the Pilbara Craton preserve Earth's earliest unambiguous evidence of life at 3.48 Ga. Micro-analytical techniques reveal organic biosignatures within layered structures. Carbon isotope ratios (δ13C = -27‰) indicate biological fractionation consistent with cyanobacterial photosynthesis. Sulfur isotope systematics suggest contemporaneous sulfate reduction, documenting complex microbial ecosystems in early Archean shallow marine environments."
                },
                "ko": {
                    "title": "필바라 크라톤의 시생대 미생물 군집: 생체신호와 초기 지구 대사 경로",
                    "abstract": "필바라 크라톤의 시생대 스트로마톨라이트는 34억 8천만 년 전의 지구 최초 명확한 생명체 증거를 보존한다. 미세분석 기법은 층상 구조 내 유기 생체신호를 드러낸다. 탄소 동위원소 비율(δ13C = -27‰)은 시아노박테리아 광합성과 일치하는 생물학적 분별을 나타낸다. 황 동위원소 체계는 동시대 황산염 환원을 시사하여 초기 시생대 천해 환경의 복잡한 미생물 생태계를 기록한다."
                },
                "jp": {
                    "title": "ピルバラクラトンの太古代微生物群集：生体シグナルと初期地球代謝経路",
                    "abstract": "ピルバラクラトンの太古代ストロマトライトは34億8000万年前の地球最古の明確な生命証拠を保存する。微細分析技術により層状構造内の有機生体シグナルが明らかになった。炭素同位体比（δ13C = -27‰）はシアノバクテリア光合成と一致する生物学的分別を示す。硫黄同位体系統学は同時代の硫酸塩還元を示唆し、初期太古代浅海環境の複雑な微生物生態系を記録する。"
                },
                "zh": {
                    "title": "皮尔巴拉克拉通太古代微生物群落：生物标志和早期地球代谢途径",
                    "abstract": "皮尔巴拉克拉通的太古代叠层石保存了34.8亿年前地球最早明确的生命证据。微分析技术揭示了层状结构内的有机生物标志。碳同位素比值（δ13C = -27‰）表明与蓝藻光合作用一致的生物分馏。硫同位素系统学暗示同期硫酸盐还原，记录了早太古代浅海环境中复杂的微生物生态系统。"
                }
            },
            "taphonomy": {
                "en": {
                    "title": "Experimental Taphonomy of Burgess Shale-type Preservation: Factors Controlling Soft Tissue Fossilization",
                    "abstract": "Exceptional fossil preservation in Burgess Shale-type deposits results from specific physicochemical conditions during early diagenesis. Controlled decay experiments using modern arthropods under varying pH, salinity, and oxygen levels reveal critical taphonomic windows. Rapid pyritization and clay mineral authigenesis facilitate soft tissue preservation. Our results identify optimal conditions (pH 6.5-7.2, anoxic, high sulfide) for exceptional preservation."
                },
                "ko": {
                    "title": "버지스 셰일형 보존의 실험적 매장학: 연조직 화석화를 조절하는 요인들",
                    "abstract": "버지스 셰일형 퇴적물의 뛰어난 화석 보존은 초기 속성작용 동안의 특정 물리화학적 조건에서 비롯된다. 다양한 pH, 염도, 산소 수준 하에서 현생 절지동물을 사용한 조절된 부패 실험이 중요한 매장학적 창을 드러낸다. 급속한 황철석화와 점토광물 자생작용이 연조직 보존을 촉진한다. 우리의 결과는 뛰어난 보존을 위한 최적 조건(pH 6.5-7.2, 무산소, 고황화물)을 식별한다."
                },
                "jp": {
                    "title": "バージェス頁岩型保存の実験的埋没学：軟組織化石化を制御する要因",
                    "abstract": "バージェス頁岩型堆積物の優れた化石保存は初期続成作用中の特定物理化学条件に起因する。様々なpH、塩分、酸素レベル下での現生節足動物を用いた制御された腐敗実験により重要な埋没学的窓が明らかになった。急速な黄鉄鉱化と粘土鉱物自生作用が軟組織保存を促進する。我々の結果は優れた保存のための最適条件（pH 6.5-7.2、無酸素、高硫化物）を特定する。"
                },
                "zh": {
                    "title": "布尔吉斯页岩型保存的实验埋藏学：控制软组织化石化的因素",
                    "abstract": "布尔吉斯页岩型沉积物中的异常化石保存源于早期成岩作用期间的特定物理化学条件。在不同pH、盐度和氧气水平下使用现代节肢动物进行的受控腐败实验揭示了关键的埋藏学窗口。快速黄铁矿化和粘土矿物自生作用促进软组织保存。我们的结果确定了异常保存的最佳条件（pH 6.5-7.2，缺氧，高硫化物）。"
                }
            }
        }
        
        # 기본 템플릿 가져오기
        template_data = paper_templates.get(paper_type, paper_templates["theropod"]).get(language, paper_templates.get(paper_type, paper_templates["theropod"])["en"])
        
        # 저자 정보 생성 (논문 유형별로 완전히 다름)
        authors_data = self._generate_authors(paper_type, language)
        
        # 저널 정보 생성
        journal_info = self._generate_journal_info(paper_type, language)
        
        # 영어 제목도 함께 생성 (다국어 논문용)
        english_title = template_data["title"]
        if language != "en" and paper_type in paper_templates:
            english_title = paper_templates[paper_type].get("en", {}).get("title", template_data["title"])
        
        content_data = {
            "title": template_data["title"],
            "english_title": english_title if language != "en" else None,
            "authors": authors_data["authors"],
            "journal": f"Journal of Paleontological Research, Vol. {journal_info['volume']}, No. {journal_info['issue']} ({journal_info['year']})",
            "volume": f"pp. {journal_info['start_page']}-{journal_info['end_page']}",
            "doi": f"10.1016/j.jpr.2024.{journal_info['doi_suffix']}",
            "abstract": template_data.get("abstract", "This study presents new findings in paleontological research."),
            "keywords": self._get_keywords_by_type(paper_type, language),
            "received": f"Received: {journal_info['year']}-{journal_info['volume']:02d}-15",
            "accepted": f"Accepted: {journal_info['year']}-{journal_info['volume']+1:02d}-28"
        }
        
        return content_data
    
    def _get_keywords_by_type(self, paper_type, language):
        """논문 유형별 키워드 생성"""
        keywords_by_type = {
            "theropod": ["theropod dinosaurs", "Cretaceous", "evolution", "phylogeny", "Liaoning", "feathered dinosaurs"],
            "trilobite": ["trilobites", "Ordovician", "biodiversity", "biogeography", "Baltic Basin", "marine ecosystems"],
            "marine_reptile": ["marine reptiles", "Jurassic", "paleoecology", "dietary specialization", "ichthyosaurs", "plesiosaurs"],
            "plant_fossil": ["plant fossils", "Carboniferous", "forest ecosystems", "paleobotany", "seed ferns", "coal measures"],
            "mass_extinction": ["mass extinction", "Permian-Triassic", "environmental crisis", "volcanic activity", "ocean acidification"],
            "mammal_evolution": ["mammalian evolution", "Paleocene", "adaptive radiation", "dental morphology", "K-Pg extinction"],
            "trace_fossil": ["trace fossils", "ichnology", "dinosaur tracks", "Triassic", "locomotion", "behavior"],
            "amber_inclusion": ["amber fossils", "arthropods", "Cretaceous", "forest ecosystems", "Myanmar", "Burmese amber"],
            "microorganism": ["microbial fossils", "Archean", "stromatolites", "biosignatures", "early life", "Pilbara"],
            "taphonomy": ["taphonomy", "experimental paleontology", "soft tissue preservation", "Burgess Shale", "fossilization"]
        }
        return keywords_by_type.get(paper_type, ["paleontology", "evolution", "fossil record"])
    
    def _generate_authors(self, paper_type, language):
        """논문 유형별로 완전히 다른 저자 정보 생성"""
        
        # 논문 유형별 완전히 다른 저자 세트
        author_sets = {
            "theropod": {
                "en": ["Dr. Sarah Chen", "Department of Paleontology, Harvard University",
                       "Prof. Michael Thompson", "Institute for Geological Sciences, MIT",
                       "Dr. Yuki Tanaka", "Natural History Museum, Tokyo"],
                "ko": ["첸 사라 박사", "하버드대학교 고생물학과",
                       "마이클 톰슨 교수", "MIT 지질과학연구소",
                       "다나카 유키 박사", "도쿄자연사박물관"],
                "jp": ["チェン・サラ博士", "ハーバード大学古生物学科",
                       "マイケル・トンプソン教授", "MIT地質科学研究所",
                       "田中雪博士", "東京自然史博物館"],
                "zh": ["陈莎拉博士", "哈佛大学古生物学系",
                       "迈克尔·汤普森教授", "麻省理工学院地质科学研究所",
                       "田中雪博士", "东京自然历史博物馆"]
            },
            "trilobite": {
                "en": ["Dr. Anna Lindström", "Department of Earth Sciences, Uppsala University",
                       "Prof. James McKenna", "Institute of Paleobiology, University of Cambridge",
                       "Dr. Erik Bergmann", "Museum of Natural History, Stockholm"],
                "ko": ["안나 린드스트롬 박사", "웁살라대학교 지구과학과",
                       "제임스 맥케나 교수", "케임브리지대학교 고생물학연구소",
                       "에릭 베르크만 박사", "스톡홀름자연사박물관"],
                "jp": ["アンナ・リンドストローム博士", "ウプサラ大学地球科学科",
                       "ジェームズ・マッケナ教授", "ケンブリッジ大学古生物学研究所",
                       "エリック・ベルクマン博士", "ストックホルム自然史博物館"],
                "zh": ["安娜·林德斯特伦博士", "乌普萨拉大学地球科学系",
                       "詹姆斯·麦肯纳教授", "剑桥大学古生物学研究所",
                       "埃里克·伯格曼博士", "斯德哥尔摩自然历史博物馆"]
            },
            "marine_reptile": {
                "en": ["Dr. Benjamin Clarke", "Department of Paleontology, Oxford University",
                       "Prof. Rebecca Williams", "School of Earth Sciences, University of Bristol",
                       "Dr. Thomas Mueller", "Natural History Museum, London"],
                "ko": ["벤자민 클라크 박사", "옥스포드대학교 고생물학과",
                       "레베카 윌리엄스 교수", "브리스톨대학교 지구과학대학",
                       "토마스 뮐러 박사", "런던자연사박물관"],
                "jp": ["ベンジャミン・クラーク博士", "オックスフォード大学古生物学科",
                       "レベッカ・ウィリアムズ教授", "ブリストル大学地球科学大学",
                       "トーマス・ミュラー博士", "ロンドン自然史博物館"],
                "zh": ["本杰明·克拉克博士", "牛津大学古生物学系",
                       "丽贝卡·威廉姆斯教授", "布里斯托大学地球科学学院",
                       "托马斯·穆勒博士", "伦敦自然历史博物馆"]
            },
            "plant_fossil": {
                "en": ["Dr. Emma Richardson", "School of Biological Sciences, University of Sydney",
                       "Prof. David Martinez", "Department of Paleobotany, Yale University",
                       "Dr. Lisa Anderson", "Australian Museum, Sydney"],
                "ko": ["엠마 리처드슨 박사", "시드니대학교 생물과학대학",
                       "데이비드 마르티네스 교수", "예일대학교 고식물학과",
                       "리사 앤더슨 박사", "시드니 호주박물관"],
                "jp": ["エマ・リチャードソン博士", "シドニー大学生物科学大学",
                       "デイビッド・マルティネス教授", "イェール大学古植物学科",
                       "リサ・アンダーソン博士", "シドニー・オーストラリア博物館"],
                "zh": ["艾玛·理查德森博士", "悉尼大学生物科学学院",
                       "大卫·马丁内斯教授", "耶鲁大学古植物学系",
                       "丽莎·安德森博士", "悉尼澳大利亚博物馆"]
            },
            "mass_extinction": {
                "en": ["Dr. Zhong Wei", "Institute of Geology, Chinese Academy of Sciences",
                       "Prof. Maria Rodriguez", "Department of Geosciences, Princeton University",
                       "Dr. Klaus Weber", "Institute of Earth Sciences, ETH Zurich"],
                "ko": ["중웨이 박사", "중국과학원 지질연구소",
                       "마리아 로드리게스 교수", "프린스턴대학교 지구과학과",
                       "클라우스 베버 박사", "취리히연방공과대학 지구과학연구소"],
                "jp": ["ジョン・ウェイ博士", "中国科学院地質研究所",
                       "マリア・ロドリゲス教授", "プリンストン大学地球科学科",
                       "クラウス・ウェーバー博士", "チューリッヒ工科大学地球科学研究所"],
                "zh": ["钟伟博士", "中国科学院地质研究所",
                       "玛丽亚·罗德里格斯教授", "普林斯顿大学地球科学系",
                       "克劳斯·韦伯博士", "苏黎世联邦理工学院地球科学研究所"]
            },
            "mammal_evolution": {
                "en": ["Dr. Katherine Foster", "Department of Vertebrate Paleontology, University of California Berkeley",
                       "Prof. Robert Johnson", "Museum of Paleontology, University of Michigan",
                       "Dr. Jean-Pierre Dubois", "Institut de Paléontologie, Sorbonne Université"],
                "ko": ["캐서린 포스터 박사", "UC버클리 척추동물고생물학과",
                       "로버트 존슨 교수", "미시간대학교 고생물학박물관",
                       "장-피에르 뒤부아 박사", "소르본대학교 고생물학연구소"],
                "jp": ["キャサリン・フォスター博士", "カリフォルニア大学バークレー校脊椎動物古生物学科",
                       "ロバート・ジョンソン教授", "ミシガン大学古生物学博物館",
                       "ジャン=ピエール・デュボワ博士", "ソルボンヌ大学古生物学研究所"],
                "zh": ["凯瑟琳·福斯特博士", "加州大学伯克利分校脊椎动物古生物学系",
                       "罗伯特·约翰逊教授", "密歇根大学古生物学博物馆",
                       "让-皮埃尔·杜布瓦博士", "索邦大学古生物学研究所"]
            },
            "trace_fossil": {
                "en": ["Dr. Nicole Patterson", "Department of Geology, Dalhousie University",
                       "Prof. Mark Stevens", "Institute of Ichnology, University of Alberta",
                       "Dr. Andrew MacLeod", "Royal Ontario Museum, Toronto"],
                "ko": ["니콜 패터슨 박사", "달하우지대학교 지질학과",
                       "마크 스티븐스 교수", "앨버타대학교 생흔학연구소",
                       "앤드류 맥레오드 박사", "토론토 왕립온타리오박물관"],
                "jp": ["ニコル・パターソン博士", "ダルハウジー大学地質学科",
                       "マーク・スティーブンス教授", "アルバータ大学生痕学研究所",
                       "アンドリュー・マクレオド博士", "トロント王立オンタリオ博物館"],
                "zh": ["妮可·帕特森博士", "达尔豪西大学地质学系",
                       "马克·史蒂文斯教授", "阿尔伯塔大学遗迹学研究所",
                       "安德鲁·麦克劳德博士", "多伦多皇家安大略博物馆"]
            },
            "amber_inclusion": {
                "en": ["Dr. Lin Zhao", "Key Laboratory of Insect Evolution, Capital Normal University",
                       "Prof. Alexander Grimaldi", "Division of Invertebrate Zoology, AMNH, New York",
                       "Dr. Mateus Santos", "Museu de Ciências da Terra, Brasília"],
                "ko": ["린자오 박사", "수도사범대학교 곤충진화연구소",
                       "알렉산더 그리말디 교수", "뉴욕자연사박물관 무척추동물학과",
                       "마테우스 산토스 박사", "브라질리아 지구과학박물관"],
                "jp": ["リン・ジャオ博士", "首都師範大学昆虫進化研究所",
                       "アレクサンダー・グリマルディ教授", "ニューヨーク自然史博物館無脊椎動物学科",
                       "マテウス・サントス博士", "ブラジリア地球科学博物館"],
                "zh": ["林昭博士", "首都师范大学昆虫进化重点实验室",
                       "亚历山大·格里马尔迪教授", "纽约美国自然历史博物馆无脊椎动物学部",
                       "马泰乌斯·桑托斯博士", "巴西利亚地球科学博物馆"]
            },
            "microorganism": {
                "en": ["Prof. Sherry L. Cady", "Department of Geology, Pacific Lutheran University",
                       "Dr. Kenichiro Sugitani", "Graduate School of Environmental Studies, Nagoya University",
                       "Dr. Frances Westall", "CNRS Centre de Biophysique Moléculaire, Orléans"],
                "ko": ["셰리 케이디 교수", "퍼시픽루터란대학교 지질학과",
                       "스기타니 겐이치로 박사", "나고야대학교 환경학연구과",
                       "프랜시스 웨스톨 박사", "오를레앙 분자생물물리학센터"],
                "jp": ["シェリー・ケイディ教授", "パシフィック・ルーテル大学地質学科",
                       "杉谷健一郎博士", "名古屋大学環境学研究科",
                       "フランシス・ウェストール博士", "オルレアン分子生物物理学センター"],
                "zh": ["雪莉·凯迪教授", "太平洋路德大学地质学系",
                       "杉谷健一郎博士", "名古屋大学环境学研究科",
                       "弗朗西斯·韦斯托尔博士", "奥尔良分子生物物理学中心"]
            },
            "taphonomy": {
                "en": ["Dr. Mark A. Wilson", "Department of Earth Sciences, The College of Wooster",
                       "Prof. Susan Kidwell", "Department of Geophysical Sciences, University of Chicago",
                       "Dr. Martin Brasier", "Department of Earth Sciences, University of Oxford"],
                "ko": ["마크 윌슨 박사", "우스터대학교 지구과학과",
                       "수잔 키드웰 교수", "시카고대학교 지구물리학과",
                       "마틴 브레이지어 박사", "옥스포드대학교 지구과학과"],
                "jp": ["マーク・ウィルソン博士", "ウースター大学地球科学科",
                       "スーザン・キドウェル教授", "シカゴ大学地球物理学科",
                       "マーティン・ブレイジャー博士", "オックスフォード大学地球科学科"],
                "zh": ["马克·威尔逊博士", "伍斯特学院地球科学系",
                       "苏珊·基德韦尔教授", "芝加哥大学地球物理学系",
                       "马丁·布雷西尔博士", "牛津大学地球科学系"]
            }
        }
        
        # 기본값으로 theropod 사용
        authors = author_sets.get(paper_type, author_sets["theropod"]).get(language, author_sets[paper_type]["en"])
        return {"authors": authors}
    
    def _generate_journal_info(self, paper_type, language):
        """논문 유형별 저널 정보 생성 (다양한 variation)"""
        
        # 논문 유형별 저널 데이터베이스
        journal_sets = {
            "theropod": {"volume": random.randint(40, 50), "issue": random.randint(1, 4), "year": random.choice([2023, 2024])},
            "trilobite": {"volume": random.randint(25, 35), "issue": random.randint(1, 3), "year": random.choice([2023, 2024])},
            "marine_reptile": {"volume": random.randint(55, 65), "issue": random.randint(2, 5), "year": random.choice([2023, 2024])},
            "plant_fossil": {"volume": random.randint(30, 40), "issue": random.randint(1, 4), "year": random.choice([2022, 2023])},
            "mass_extinction": {"volume": random.randint(70, 80), "issue": random.randint(3, 6), "year": random.choice([2023, 2024])},
            "mammal_evolution": {"volume": random.randint(45, 55), "issue": random.randint(1, 3), "year": random.choice([2023, 2024])},
            "trace_fossil": {"volume": random.randint(35, 45), "issue": random.randint(2, 4), "year": random.choice([2022, 2023])},
            "amber_inclusion": {"volume": random.randint(60, 70), "issue": random.randint(1, 4), "year": random.choice([2023, 2024])},
            "microorganism": {"volume": random.randint(85, 95), "issue": random.randint(2, 5), "year": random.choice([2023, 2024])},
            "taphonomy": {"volume": random.randint(50, 60), "issue": random.randint(1, 3), "year": random.choice([2022, 2023])}
        }
        
        # 기본값으로 theropod 사용
        journal_info = journal_sets.get(paper_type, journal_sets["theropod"])
        start_page = random.randint(150, 300)
        end_page = start_page + random.randint(15, 35)
        
        return {
            "volume": journal_info["volume"],
            "issue": journal_info["issue"],
            "year": journal_info["year"],
            "start_page": start_page,
            "end_page": end_page,
            "doi_suffix": f"{random.randint(1, 12):02d}.{random.randint(100, 500):03d}"
        }
    
    def _create_first_page_template(self):
        """첫 페이지 복합 템플릿 생성 (상단: 단일컬럼, 하단: 2컬럼)"""
        page_width, page_height = A4
        
        # 상단: 제목, 저자, 초록용 단일 컬럼 프레임
        title_frame = Frame(
            x1=2*cm, y1=15*cm, width=17*cm, height=12*cm,
            leftPadding=6, bottomPadding=6, rightPadding=6, topPadding=6,
            id='title_frame'
        )
        
        # 하단 왼쪽: 본문 시작용 컬럼
        lower_left_frame = Frame(
            x1=2*cm, y1=2*cm, width=8.25*cm, height=12.5*cm,
            leftPadding=6, bottomPadding=6, rightPadding=3, topPadding=6,
            id='lower_left'
        )
        
        # 하단 오른쪽: 본문 계속용 컬럼  
        lower_right_frame = Frame(
            x1=10.75*cm, y1=2*cm, width=8.25*cm, height=12.5*cm,
            leftPadding=3, bottomPadding=6, rightPadding=6, topPadding=6,
            id='lower_right'
        )
        
        return PageTemplate(id='first_page', frames=[title_frame, lower_left_frame, lower_right_frame])
    
    def _create_two_column_template(self):
        """2컬럼 페이지 템플릿 생성 (2페이지 이후)"""
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
        
        # 첫 페이지 복합 템플릿과 일반 2단 템플릿 추가
        first_page_template = self._create_first_page_template()
        two_column_template = self._create_two_column_template()
        
        doc.addPageTemplates([first_page_template, two_column_template])
        
        story = []
        
        # 첫 페이지: 제목 페이지 내용 (단일 컬럼 프레임에 배치)
        story.extend(self._create_title_page())
        
        # 첫 페이지 하단에서 본문 시작 (2단 프레임으로 자동 이동)
        story.extend(self._create_body_content())
        
        # 2페이지부터는 일반 2단 템플릿 사용
        story.append(NextPageTemplate('two_column'))
        story.append(PageBreak())
        
        # 2페이지 이후 추가 내용
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
        """PDF를 이미지로 변환하여 텍스트 레이어 제거"""
        try:
            # pdf2image를 사용하여 PDF를 이미지로 변환
            from pdf2image import convert_from_path
            from PIL import Image
            import io
            
            print(f"   📝 텍스트 레이어 제거 중...")
            
            # PDF를 이미지로 변환 (150 DPI)
            images = convert_from_path(str(filepath), dpi=150)
            
            # 새로운 PDF 생성 (이미지만 포함)
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            
            temp_filepath = filepath.with_suffix('.temp.pdf')
            c = canvas.Canvas(str(temp_filepath), pagesize=A4)
            
            for i, image in enumerate(images):
                # 이미지를 바이트 스트림으로 변환
                img_buffer = io.BytesIO()
                image.save(img_buffer, format='JPEG', quality=85)
                img_buffer.seek(0)
                
                # PDF 페이지에 이미지 추가
                page_width, page_height = A4
                c.drawImage(img_buffer, 0, 0, width=page_width, height=page_height)
                
                if i < len(images) - 1:
                    c.showPage()
            
            c.save()
            
            # 원본 파일을 새 파일로 교체
            filepath.unlink()
            temp_filepath.rename(filepath)
            
            print(f"   ✅ 텍스트 레이어 제거 완료")
            
        except ImportError:
            print(f"   ⚠️ pdf2image가 설치되지 않음. 시뮬레이션으로 처리됨")
            print(f"   💡 실제 텍스트 레이어 제거를 위해서는 'pip install pdf2image pillow' 실행")
        except Exception as e:
            print(f"   ⚠️ 텍스트 레이어 제거 실패: {e}")
    
    def _create_title_page(self):
        """제목 페이지 생성 (단일 컬럼)"""
        content = []
        
        # 저널 정보 (CJK 폰트 적용)
        content.append(Paragraph(self.content["journal"], self.styles['CustomNormal']))
        content.append(Paragraph(self.content["volume"], self.styles['CustomNormal']))
        content.append(Paragraph(f"DOI: {self.content['doi']}", self.styles['CustomNormal']))
        content.append(Spacer(1, 20))
        
        # 제목 (다국어의 경우 원어 + 영어)
        content.append(Paragraph(self.content["title"], self.styles['CustomTitle']))
        
        # 영어 제목 추가 (다국어 논문의 경우)
        if self.content.get("english_title") and self.language != "en":
            content.append(Spacer(1, 5))
            content.append(Paragraph(f"<i>{self.content['english_title']}</i>", self.styles['Authors']))
        
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
        
        # 접수/승인 날짜 (간소화, CJK 폰트 적용)
        dates_text = f"{self.content['received']} | {self.content['accepted']}"
        content.append(Paragraph(dates_text, self.styles['CustomNormal']))
        
        return content
    
    def _create_body_content(self):
        """논문 유형별 본문 내용 생성 (2단 레이아웃)"""
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
    
    def _get_paper_texts(self, paper_type):
        """논문 유형별 언어별 텍스트 (각 유형마다 완전히 다른 내용)"""
        
        texts_database = {
            "theropod": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "The Cretaceous period (145-66 million years ago) witnessed remarkable evolutionary innovations in theropod dinosaurs, including the emergence of powered flight and complex social behaviors. Recent discoveries in the Liaoning Province of China have provided unprecedented insights into this critical evolutionary transition. The Yixian Formation, dated to approximately 125 million years ago, has yielded exceptional preservation of theropod specimens with soft tissue details, feather impressions, and complete skeletal remains.\n\nThe evolutionary relationship between non-avian dinosaurs and birds has been a subject of intense scientific debate for over a century. Since Huxley's (1868) initial proposal of a dinosaurian origin for birds, accumulating fossil evidence has strengthened this hypothesis. The discovery of Archaeopteryx in 1861 provided the first compelling evidence of a transitional form, but it was not until the remarkable discoveries from China beginning in the 1990s that the full picture of theropod-bird evolution began to emerge.\n\nThe Jehol Biota of northeastern China, particularly from the Yixian and Jiufotang formations, has revolutionized our understanding of theropod evolution. These deposits have produced hundreds of exceptionally preserved specimens, many with intact feathers and other soft tissues. The preservation quality is attributed to rapid burial in volcanic ash and anoxic lake environments, which prevented decay and scavenging.\n\nThis study presents three new theropod specimens that display a unique combination of primitive and derived characteristics, providing crucial information about the stepwise acquisition of avian features. Our analysis focuses on morphological innovations related to flight capability, including modifications of the forelimb, shoulder girdle, and tail structure. These specimens offer new insights into the timing and sequence of character acquisition during the theropod-bird transition.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Specimen Collection and Preparation\nThree nearly complete theropod specimens (IVPP V23456, IVPP V23457, IVPP V23458) were collected from the Jianshangou beds of the lower Yixian Formation, Beipiao, western Liaoning Province, China. Field excavation was conducted using standard paleontological techniques, with specimens jacketed in plaster for transport. GPS coordinates and stratigraphic data were recorded for all collection sites.\n\nSpecimens were prepared at the Institute of Vertebrate Paleontology and Paleoanthropology (IVPP) using pneumatic air scribes and pin vices under binocular microscopes. Matrix removal employed dilute acetic acid (5%) for carbonate-rich sections. Consolidation was achieved using Paraloid B-72 dissolved in acetone.\n\n2.2 Morphological Analysis\nDetailed morphological measurements were taken using digital calipers (Mitutoyo 500-196-30, ±0.01 mm precision) and documented following standard osteological protocols. All measurements were repeated three times to ensure accuracy. Photographic documentation utilized a Nikon D850 with macro lens under controlled lighting conditions. CT scanning was performed on selected elements using a GE Phoenix v|tome|x industrial scanner at 180 kV and 180 μA.\n\n2.3 Phylogenetic Analysis\nPhylogenetic analysis employed a modified version of the Theropod Working Group (TWiG) matrix, incorporating 247 morphological characters scored for 156 operational taxonomic units (OTUs). Character coding followed established protocols with multistate characters treated as unordered. Maximum parsimony analysis was conducted using TNT v1.5 with 10,000 random addition sequences and tree bisection reconnection (TBR) branch swapping. Bootstrap support values were calculated from 1,000 replicates.\n\n2.4 Statistical Methods\nPrincipal component analysis (PCA) was performed on limb proportion data to assess morphospace occupation. All statistical analyses were conducted in R v4.1.0 using standard packages. Significance was assessed at α = 0.05.",
                    "results_title": "3. Results",
                    "results_text": "Morphological analysis reveals a mosaic of primitive and derived characteristics. All specimens exhibit elongated arms with well-developed flight feathers, suggesting powered flight capabilities. However, retention of primitive features such as unfused vertebrae and presence of gastralia indicates these taxa represent transitional forms between non-avian theropods and modern birds.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "These findings challenge previous hypotheses regarding theropod evolution during the Cretaceous. The presence of flight-capable theropods with primitive skeletal features suggests that powered flight evolved multiple times independently within Theropoda. The phylogenetic position of these taxa supports a complex pattern of character evolution during the theropod-bird transition.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Three new theropod species from the Yixian Formation represent transitional forms between primitive theropods and modern birds. Flight capabilities evolved independently multiple times within Theropoda. Morphological diversity during the Early Cretaceous was greater than previously recognized, supporting rapid evolutionary innovation during this critical period."
                },
                "ko": {
                    "intro_title": "1. 서론",
                    "intro_text": "백악기(1억 4천 5백만-6천 6백만 년 전)는 수각류 공룡의 놀라운 진화적 혁신을 목격했으며, 여기에는 동력 비행의 출현과 복잡한 사회적 행동이 포함된다. 중국 랴오닝성의 최근 발견들은 이 중요한 진화적 전환에 대한 전례 없는 통찰을 제공했다. 이셴층은 연조직 세부사항, 깃털 인상, 완전한 골격 유해를 가진 수각류 표본의 탁월한 보존을 산출했다.",
                    "methods_title": "2. 재료 및 방법",
                    "methods_text": "이셴층의 지안샹구 층에서 거의 완전한 수각류 표본 3점(IVPP V23456, IVPP V23457, IVPP V23458)을 수집했다. 표본들은 표준 기계적 및 화학적 기법을 사용하여 준비되었다. 형태학적 측정은 디지털 캘리퍼(±0.01 mm 정밀도)를 사용하여 수행되었다. 계통분류학적 분석은 TNT v1.5에서 최대절약법을 사용하여 156개 분류군의 247개 형태학적 특성을 사용했다.",
                    "results_title": "3. 결과",
                    "results_text": "형태학적 분석은 원시적 특성과 파생적 특성의 모자이크를 드러낸다. 모든 표본은 잘 발달된 비행깃털을 가진 긴 팔을 보여주며, 이는 동력 비행 능력을 시사한다. 그러나 융합되지 않은 척추와 복늑골의 존재와 같은 원시적 특징의 유지는 이러한 분류군이 비조류 수각류와 현생 조류 사이의 전이형을 나타낸다는 것을 보여준다.",
                    "discussion_title": "4. 토론",
                    "discussion_text": "이러한 발견들은 백악기 동안의 수각류 진화에 대한 이전 가설들에 도전한다. 원시적 골격 특징을 가진 비행 가능한 수각류의 존재는 동력 비행이 수각류 내에서 여러 번 독립적으로 진화했음을 시사한다. 이러한 분류군의 계통발생학적 위치는 수각류-조류 전환 동안의 복잡한 특성 진화 패턴을 뒷받침한다.",
                    "conclusions_title": "5. 결론",
                    "conclusions_text": "이셴층의 새로운 수각류 3종은 원시 수각류와 현생 조류 사이의 전이형을 나타낸다. 비행 능력은 수각류 내에서 여러 번 독립적으로 진화했다. 전기 백악기의 형태학적 다양성은 이전에 인식되었던 것보다 더 컸으며, 이 중요한 시기 동안의 급속한 진화적 혁신을 뒷받침한다."
                },
                "jp": {
                    "intro_title": "1. はじめに",
                    "intro_text": "白亜紀（1億4500万年前～6600万年前）は獣脚類恐竜の著しい進化的革新を目撃し、動力飛行の出現と複雑な社会行動が含まれる。中国遼寧省の最近の発見は、この重要な進化的転換への前例のない洞察を提供した。義県層は軟組織の詳細、羽毛の印象、完全な骨格遺体を持つ獣脚類標本の卓越した保存を産出した。",
                    "methods_title": "2. 材料と方法",
                    "methods_text": "義県層の尖山溝層からほぼ完全な獣脚類標本3点（IVPP V23456、IVPP V23457、IVPP V23458）を収集した。標本は標準的な機械的および化学的技法を使用して準備された。形態学的測定はデジタルキャリパー（±0.01 mm精度）を使用して行われた。系統分類学的分析はTNT v1.5で最大節約法を使用して156分類群の247形態学的特性を使用した。",
                    "results_title": "3. 結果",
                    "results_text": "形態学的分析は原始的特徴と派生的特徴のモザイクを明らかにする。すべての標本はよく発達した飛翔羽を持つ長い腕を示し、動力飛行能力を示唆する。しかし、融合していない椎骨と腹肋骨の存在などの原始的特徴の保持は、これらの分類群が非鳥類獣脚類と現生鳥類の間の移行型を表すことを示している。",
                    "discussion_title": "4. 考察",
                    "discussion_text": "これらの発見は白亜紀における獣脚類進化についての以前の仮説に挑戦する。原始的骨格特徴を持つ飛行可能な獣脚類の存在は、動力飛行が獣脚類内で複数回独立して進化したことを示唆する。これらの分類群の系統発生学的位置は、獣脚類-鳥類移行期における複雑な特徴進化パターンを支持する。",
                    "conclusions_title": "5. 結論",
                    "conclusions_text": "義県層の新しい獣脚類3種は原始獣脚類と現生鳥類の間の移行型を表す。飛行能力は獣脚類内で複数回独立して進化した。前期白亜紀の形態学的多様性は以前に認識されていたよりも大きく、この重要な時期における急速な進化的革新を支持する。"
                },
                "zh": {
                    "intro_title": "1. 引言",
                    "intro_text": "白垩纪（1.45-0.66亿年前）见证了兽脚类恐龙的显著进化创新，包括动力飞行的出现和复杂的社会行为。中国辽宁省的最新发现为这一关键的进化转变提供了前所未有的见解。义县组产出了具有软组织细节、羽毛印痕和完整骨骼遗骸的兽脚类标本的卓越保存。",
                    "methods_title": "2. 材料与方法",
                    "methods_text": "从义县组尖山沟层收集了三个近乎完整的兽脚类标本（IVPP V23456、IVPP V23457、IVPP V23458）。使用标准机械和化学技术准备标本。使用数字卡尺（±0.01毫米精度）进行形态学测量。系统发育分析在TNT v1.5中使用最大简约法，采用156个类群的247个形态学特征。",
                    "results_title": "3. 结果",
                    "results_text": "形态学分析揭示了原始和衍生特征的镶嵌模式。所有标本都显示出具有发达飞羽的长臂，表明具有动力飞行能力。然而，保留的原始特征如未融合的脊椎和腹肋的存在表明这些类群代表非鸟类兽脚类和现生鸟类之间的过渡形式。",
                    "discussion_title": "4. 讨论",
                    "discussion_text": "这些发现挑战了关于白垩纪兽脚类进化的先前假设。具有原始骨骼特征的飞行兽脚类的存在表明动力飞行在兽脚类内多次独立进化。这些类群的系统发育位置支持兽脚类-鸟类转换期间复杂的特征进化模式。",
                    "conclusions_title": "5. 结论",
                    "conclusions_text": "义县组的三个新兽脚类物种代表了原始兽脚类和现生鸟类之间的过渡形式。飞行能力在兽脚类内多次独立进化。早白垩世的形态学多样性比以前认识的更大，支持这一关键时期的快速进化创新。"
                }
            },
            "trilobite": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "The Ordovician Period (485-444 Ma) represents the zenith of trilobite diversity, coinciding with the Great Ordovician Biodiversification Event (GOBE). This remarkable interval witnessed an unprecedented expansion of marine biodiversity, with trilobites playing a central role as dominant arthropods in Paleozoic seas. The Baltic Basin preserves exceptional fossil assemblages from this critical interval, offering unique insights into marine ecosystem dynamics during peak Paleozoic biodiversity.\n\nTrilobites, as one of the most successful arthropod groups in Earth's history, exhibited remarkable morphological and ecological diversity throughout their 270-million-year evolutionary history. The Ordovician radiation of trilobites was particularly spectacular, with new body plans, feeding strategies, and ecological niches rapidly evolving in response to changing environmental conditions and the proliferation of new marine habitats.\n\nThe Baltic Basin, comprising present-day Estonia, Latvia, Lithuania, and adjacent areas, represents one of the most completely preserved Ordovician marine sequences in the world. The basin's carbonate platform deposits provide exceptional windows into ancient marine ecosystems, with trilobite assemblages preserved in exquisite detail. These assemblages document not only taxonomic diversity but also complex ecological interactions, including predator-prey relationships, ontogenetic changes, and behavioral patterns.\n\nPrevious studies of Baltic Ordovician trilobites have focused primarily on systematic descriptions and biostratigraphic applications. However, comprehensive biogeographic and paleoecological analyses have been limited by the scattered nature of existing collections and the lack of quantitative analytical frameworks. This study presents the first comprehensive analysis of trilobite diversity patterns across the entire Baltic Basin, employing modern statistical methods to unravel the complex relationships between environmental change, biogeography, and evolutionary innovation during this critical interval in Earth's history.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Specimen Collection and Repository\nWe analyzed 1,247 trilobite specimens collected from 47 Ordovician limestone formations across Estonia, Latvia, and southern Sweden. Collections span the complete Ordovician sequence from Tremadocian to Hirnantian stages. Specimens are housed in the Institute of Geology, Tallinn University of Technology (GIT), Natural History Museum of Latvia (NHML), and Swedish Museum of Natural History (NRM). All specimens are catalogued with precise stratigraphic and geographic data.\n\n2.2 Specimen Preparation and Photography\nAll specimens were processed using standard acid preparation techniques. Carbonate matrix was removed using 10% acetic acid (buffered to pH 4.5) over periods of 6-48 hours depending on matrix composition. Specimens were neutralized in sodium bicarbonate solution and air-dried. Photographic documentation employed low-angle lighting to enhance morphological details, with images captured using a Canon EOS 5D Mark IV with 100mm macro lens.\n\n2.3 Systematic Identification and Measurement\nSystematic identification followed established taxonomic protocols of Fortey (1980), Adrain & Westrop (2003), and regional monographs. Morphological measurements included cephalic length and width, glabellar dimensions, eye parameters, and thoracic/pygidial proportions. All measurements were taken using digital calipers (±0.1 mm precision) and recorded in a standardized database.\n\n2.4 Biogeographic and Statistical Analysis\nBiogeographic patterns were analyzed using multivariate statistical methods including cluster analysis (UPGMA) and non-metric multidimensional scaling (NMDS). Taxonomic diversity was calculated using rarefaction analysis to account for sampling differences. Faunal similarity between localities was assessed using Jaccard and Sørensen coefficients. All analyses were performed in R v4.1.0 using packages vegan, cluster, and fossil.\n\n2.5 Paleogeographic Reconstruction\nPaleogeographic positions were reconstructed using published plate tectonic models calibrated to Ordovician magnetic reference frames. Sea-level curves and environmental interpretations were based on lithofacies analysis and integration with regional stratigraphic frameworks.",
                    "results_title": "3. Results",
                    "results_text": "Our analysis identified 23 genera and 47 species, including 8 new species awaiting formal description. Diversity peaks in the Darriwilian stage with 32 co-occurring species. Biogeographic analysis reveals distinct provincial assemblages with evidence for episodic faunal exchange between Baltica and Laurentia during transgressive episodes.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "High trilobite diversity reflects optimal environmental conditions during Ordovician greenhouse climates. Sea-level fluctuations controlled dispersal corridors, facilitating intermittent faunal exchange between paleocontinents. Endemic radiations occurred during periods of geographic isolation, contributing to overall global diversity.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Baltic trilobite assemblages document peak Ordovician marine diversity. Biogeographic patterns reflect complex interactions between sea-level change, climate, and continental configuration. These findings provide crucial calibration points for understanding Paleozoic biodiversity dynamics and the evolutionary consequences of major environmental transitions."
                },
                "ko": {
                    "intro_title": "1. 서론",
                    "intro_text": "오르도비스기(4억 8천 5백만-4억 4천 4백만 년 전)는 오르도비스기 대방사 사건과 동시에 삼엽충 다양성의 정점을 나타낸다. 발트해 분지는 이 중요한 시기의 뛰어난 화석 군집을 보존하여 고생대 생물다양성 최고조 시기의 해양 생태계 역학에 대한 통찰을 제공한다. 이 지역의 삼엽충 군집은 복잡한 생물지리학적 패턴과 진화적 방산을 기록한다.",
                    "methods_title": "2. 재료 및 방법",
                    "methods_text": "에스토니아, 라트비아, 남부 스웨덴의 오르도비스기 석회암층에서 수집된 1,247개의 삼엽충 표본을 분석했다. 모든 표본은 10% 아세트산으로 처리하여 탄산염 기질에서 분리했다. 체계적 동정은 확립된 분류학적 규약을 따랐다. 생물지리학적 패턴의 통계 분석은 군집 분석과 배열법을 사용했다.",
                    "results_title": "3. 결과",
                    "results_text": "우리의 분석은 공식 기재를 기다리는 8개 신종을 포함하여 23속 47종을 확인했다. 다양성은 32종이 공존하는 다리윌리안 단계에서 최고조에 달한다. 생물지리학적 분석은 해침 에피소드 동안 발티카와 로렌시아 간의 간헐적 동물군 교환 증거와 함께 뚜렷한 지역적 군집을 드러낸다.",
                    "discussion_title": "4. 토론",
                    "discussion_text": "높은 삼엽충 다양성은 오르도비스기 온실 기후 동안의 최적 환경 조건을 반영한다. 해수면 변동은 분산 회랑을 조절하여 고대륙 간의 간헐적 동물군 교환을 촉진했다. 지리적 격리 기간 동안 고유 방산이 일어나 전체 지구적 다양성에 기여했다.",
                    "conclusions_title": "5. 결론",
                    "conclusions_text": "발트해 삼엽충 군집은 오르도비스기 해양 다양성의 정점을 기록한다. 생물지리학적 패턴은 해수면 변화, 기후, 대륙 배치 간의 복잡한 상호작용을 반영한다. 이러한 발견들은 고생대 생물다양성 역학과 주요 환경 전환의 진화적 결과를 이해하기 위한 중요한 보정점을 제공한다."
                }
            },
            "marine_reptile": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "Jurassic marine reptiles dominated oceanic ecosystems during the Mesozoic Era, representing one of the most successful adaptive radiations in vertebrate history. These apex predators exhibited remarkable ecological diversity, including long-necked plesiosaurs, short-necked pliosaurs, dolphin-like ichthyosaurs, and marine crocodilians. The evolutionary transition from terrestrial to fully aquatic lifestyles required extensive morphological modifications affecting locomotion, feeding, reproduction, and sensory systems.\n\nThe Jurassic period (201-145 Ma) witnessed peak diversity of marine reptiles, particularly during the Middle to Late Jurassic interval. Major depositional basins across Europe, including the Oxford Clay, Kimmeridge Clay, and equivalent formations, preserve exceptional assemblages of marine reptile remains. These deposits provide crucial insights into the paleoecology, trophic structure, and evolutionary dynamics of Mesozoic marine ecosystems.\n\nRecent discoveries from the Oxford Clay Formation of England have yielded remarkably complete marine reptile skeletons, including specimens with preserved soft tissues and stomach contents. These finds offer unprecedented opportunities to reconstruct feeding ecology, reproductive biology, and social behavior of extinct marine reptiles. The exceptional preservation is attributed to rapid burial in dysoxic marine environments with low bioturbation rates.\n\nThis study presents a comprehensive analysis of marine reptile assemblages from newly discovered localities in the Oxford Clay Formation. Our research integrates morphological, geochemical, and taphonomic data to reconstruct marine ecosystem dynamics during the Late Jurassic greenhouse interval. Special attention is given to niche partitioning, predator-prey relationships, and the factors controlling marine reptile diversity.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Geological Setting and Specimen Collection\nSpecimens were collected from three quarries in the Oxford Clay Formation (Callovian-Oxfordian) near Peterborough, England. The Oxford Clay represents a marine mudstone sequence deposited in a shallow epicontinental sea. Detailed stratigraphic sections were measured and specimens were collected with precise horizon control. All specimens are housed in the Natural History Museum, London (NHMUK).\n\n2.2 Specimen Preparation and Documentation\nSpecimens were prepared using standard mechanical techniques including pneumatic preparation tools and fine needles. Larger specimens required plaster jacketing for safe transport. Complete photographic documentation was carried out before, during, and after preparation. Selected specimens were subjected to micro-CT scanning using a Nikon Metrology HMX ST 225 system at various resolutions (15-50 μm voxel size).\n\n2.3 Morphological Analysis\nMorphometric analysis included standard measurements of skull, vertebral column, and appendicular elements. Functional morphology was assessed through biomechanical modeling of feeding apparatus and locomotory structures. Swimming performance was estimated using body mass reconstruction and hydrodynamic modeling based on extant analogues.\n\n2.4 Geochemical Analysis\nStable isotope analysis (δ¹³C, δ¹⁸O) was performed on carbonate components of bones and teeth using a Thermo Fisher Scientific MAT 253 mass spectrometer. Sample preparation involved mechanical cleaning, acid treatment, and roasting to remove organic contaminants. Isotopic compositions were used to infer paleotemperature, salinity, and trophic positioning.\n\n2.5 Taphonomic Assessment\nTaphonomic analysis evaluated completeness, articulation, and preservation quality of specimens. Bone surface modifications were documented using scanning electron microscopy. Statistical analysis of specimen distribution patterns employed spatial autocorrelation methods to identify potential mass mortality events.",
                    "results_title": "3. Results",
                    "results_text": "Systematic analysis identified four major marine reptile groups: plesiosaurs (12 species), ichthyosaurs (8 species), marine crocodilians (3 species), and marine turtles (2 species). Size distributions reveal clear niche partitioning with small piscivorous forms (1-3 m), medium-sized generalist predators (4-8 m), and large apex predators (10-15 m). Isotopic analysis indicates distinct trophic levels and habitat preferences among different taxa.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Marine reptile diversity patterns reflect complex ecological interactions within Jurassic marine ecosystems. Large body size evolution occurred independently in multiple lineages, suggesting strong selective pressures for increased predatory efficiency. Isotopic evidence indicates resource partitioning reduced interspecific competition, facilitating coexistence of multiple large predators.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Oxford Clay marine reptile assemblages represent peak Mesozoic marine reptile diversity. Ecological niche partitioning enabled coexistence of multiple apex predators through resource specialization. These findings provide crucial insights into the structure and dynamics of ancient marine ecosystems during greenhouse climate intervals."
                }
            },
            "plant_fossil": {
                "en": {
                    "intro_title": "1. Introduction", 
                    "intro_text": "The Carboniferous Period (359-299 Ma) witnessed the emergence and radiation of the first extensive terrestrial forest ecosystems. This interval, often termed the 'Coal Age,' was characterized by vast lowland swamps dominated by lycopsid trees, early conifers, and seed ferns. These ancient forests played crucial roles in global carbon cycling, atmospheric evolution, and the establishment of terrestrial food webs. Plant macrofossils from Carboniferous deposits provide exceptional insights into early forest ecosystem development and terrestrial biodiversity patterns.\n\nThe transition from early terrestrial plant communities to complex forest ecosystems represents one of the most significant ecological innovations in Earth's history. During the Carboniferous, plants evolved numerous adaptive strategies including extensive root systems, specialized reproductive structures, and sophisticated vascular architectures. These innovations enabled the colonization of diverse terrestrial environments and the construction of multi-tiered forest canopies reaching heights exceeding 40 meters.\n\nCarboniferous plant assemblages are preserved in various depositional environments including coal swamps, alluvial plains, and lacustrine settings. The exceptional preservation often includes cellular details, reproductive structures, and even three-dimensional permineralized specimens. These fossils provide unparalleled opportunities to reconstruct plant anatomy, physiology, and ecological relationships.\n\nThis study examines plant macrofossil assemblages from the Westphalian (Late Carboniferous) coal measures of the Ruhr Basin, Germany. Our analysis integrates taxonomic, ecological, and taphonomic data to reconstruct forest community structure and environmental controls on plant diversity. Special emphasis is placed on understanding the ecological drivers of early forest succession and the factors controlling plant community composition in ancient wetland environments.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Sample Collection and Stratigraphy\nPlant macrofossils were collected from 15 coal seam roof shales and associated clastic units within the Westphalian C sequence of the Ruhr Basin. Stratigraphic sections were measured at centimeter resolution with detailed lithofacies analysis. All specimens are curated at the Geological Survey of North Rhine-Westphalia (GD NRW) with complete stratigraphic and geographic provenance data.\n\n2.2 Specimen Preparation and Photography\nFossils preserved as compressions were exposed using fine needles and soft brushes. Matrix was removed using dilute hydrofluoric acid (5%) where appropriate. Permineralized specimens were sectioned using diamond-wire saws and polished for microscopic examination. Photography employed low-angle lighting and polarizing filters to enhance morphological details.\n\n2.3 Taxonomic Identification and Measurement\nTaxonomic identification followed established systems of Boureau (1964-1975) and modern revisions. Morphological measurements included laminar dimensions, venation patterns, reproductive structure parameters, and anatomical features. All measurements were digitized and incorporated into a comprehensive morphometric database.\n\n2.4 Paleoecological Analysis\nCommunity structure was analyzed using abundance data from systematic collections. Diversity indices (Shannon-Weaver, Simpson) were calculated for individual horizons and compared statistically. Ordination analysis (DCA, CCA) was employed to identify environmental gradients controlling plant community composition.\n\n2.5 Taphonomic and Depositional Analysis\nPreservation quality was assessed using standardized taphonomic protocols. Completeness ratios, fragmentation patterns, and transport indicators were quantified. Paleoenvironmental reconstruction integrated sedimentological data with plant assemblage characteristics and geochemical proxies.",
                    "results_title": "3. Results",
                    "results_text": "Systematic analysis identified 67 plant taxa representing major Carboniferous groups including lycopsids (23 species), sphenopsids (12 species), seed ferns (18 species), and early conifers (14 species). Community analysis reveals distinct ecological zones corresponding to different moisture regimes and substrate types. Lycopsid-dominated swamp communities show highest diversity (H' = 2.8), while upland conifer assemblages exhibit lower diversity but higher endemism.",
                    "discussion_title": "4. Discussion", 
                    "discussion_text": "Carboniferous forest communities exhibit clear ecological zonation related to hydrological gradients and substrate stability. Lycopsid dominance in permanently waterlogged environments reflects specialized adaptations to anaerobic root conditions. Seed fern diversity in seasonally flooded areas suggests sophisticated drought tolerance mechanisms. These patterns provide insights into early terrestrial ecosystem assembly rules.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Westphalian plant assemblages document complex forest ecosystem organization with clear environmental controls on community structure. Moisture regime represents the primary ecological gradient determining plant community composition. These findings enhance understanding of early terrestrial ecosystem dynamics and provide important calibration data for Carboniferous climate models."
                }
            },
            "mass_extinction": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "The end-Permian mass extinction (EPME), occurring approximately 252 million years ago, represents Earth's most severe biotic crisis, eliminating an estimated 81% of marine species and 70% of terrestrial vertebrate species. This catastrophic event fundamentally restructured global ecosystems and marks the boundary between the Paleozoic and Mesozoic eras. Understanding the mechanisms, timing, and ecological consequences of the EPME is crucial for assessing modern biodiversity loss and ecosystem resilience.\n\nThe EPME coincided with the eruption of the Siberian Traps Large Igneous Province, one of the largest volcanic events in Earth's history. This volcanism released massive quantities of greenhouse gases, toxic compounds, and particulates into the atmosphere and oceans, triggering a cascade of environmental perturbations including global warming, ocean acidification, and marine anoxia. The precise causal relationships between volcanism and extinction, however, remain subjects of intense scientific debate.\n\nRecent advances in geochronology, geochemistry, and paleobiology have provided new insights into EPME dynamics. High-resolution uranium-lead dating has refined the timing of extinction relative to volcanic activity, while mercury anomalies provide direct evidence for volcanic impacts on marine ecosystems. Paleobiological analyses reveal complex patterns of selective extinction, with some groups showing gradual decline while others experienced rapid collapse.\n\nThis study presents an integrated analysis of end-Permian extinction patterns and environmental changes recorded in marine carbonate sections from South China. Our research combines high-resolution biostratigraphic, geochemical, and sedimentological data to reconstruct the sequence of environmental deterioration and its relationship to biotic turnover. We focus on understanding the relative importance of different kill mechanisms and the factors controlling survival selectivity.",
                    "methods_title": "2. Materials and Methods", 
                    "methods_text": "2.1 Stratigraphic Sections and Sampling\nThree well-exposed Permian-Triassic boundary sections were studied in detail: Meishan (Zhejiang Province), Shangsi (Sichuan Province), and Daijiagou (Chongqing Municipality). These sections represent different depositional environments from shallow platform (Meishan) to basinal settings (Daijiagou). Samples were collected at 10-20 cm intervals through the critical boundary interval.\n\n2.2 Biostratigraphic Analysis\nFossil abundance and diversity were quantified through systematic sampling of conodont, foraminifer, brachiopod, and ammonoid assemblages. Taxonomic identification followed established protocols with special attention to boundary taxa. Range data were compiled for statistical analysis of extinction patterns and timing.\n\n2.3 Geochemical Analysis\nCarbon and oxygen isotope analysis was performed on both bulk carbonate and conodont apatite. Samples were analyzed using a Thermo Fisher Scientific MAT 253 mass spectrometer with precision better than 0.1‰. Mercury concentrations were determined by atomic absorption spectroscopy following acid digestion. Trace element analysis employed ICP-MS techniques.\n\n2.4 Sedimentological and Petrographic Analysis\nDetailed petrographic analysis was conducted on thin sections to identify microfacies changes and diagenetic alterations. Cathodoluminescence microscopy was used to assess carbonate diagenesis. Scanning electron microscopy documented microbial structures and pyrite framboid morphology as indicators of redox conditions.\n\n2.5 Statistical Analysis\nExtinction selectivity was analyzed using logistic regression models incorporating multiple ecological and morphological variables. Confidence intervals for extinction timing were calculated using biostratigraphic range data. Time series analysis of geochemical data employed spectral methods to identify cyclical patterns.",
                    "results_title": "3. Results",
                    "results_text": "Biostratigraphic analysis documents two-phase extinction pattern with initial diversity loss in latest Changhsingian followed by catastrophic collapse at the Permian-Triassic boundary. Carbon isotope values show dramatic negative excursion (δ¹³C = -8‰) coincident with main extinction pulse. Mercury concentration spikes provide direct evidence for volcanic input. Microfacies analysis reveals rapid transition from normal marine to dysoxic/anoxic conditions.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Extinction patterns indicate complex interplay between volcanic forcing and environmental deterioration. Initial warming and acidification weakened marine ecosystems, making them vulnerable to subsequent anoxic events. Selective extinction favored small, simple organisms with broad environmental tolerances. Recovery patterns suggest fundamental restructuring of marine ecosystem architecture.",
                    "conclusions_title": "5. Conclusions", 
                    "conclusions_text": "End-Permian extinction represents a cascade of environmental perturbations triggered by Siberian Traps volcanism. Multi-phase extinction pattern reflects threshold responses to cumulative environmental stress. These findings provide crucial insights into ecosystem vulnerability and resilience during extreme environmental change."
                }
            },
            "mammal_evolution": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "The Paleocene-Eocene Thermal Maximum (PETM) at approximately 56 million years ago represents one of the most significant rapid warming events in Earth's history, providing crucial insights into mammalian evolutionary responses to climate change. This hyperthermal event, characterized by a ~5-8°C global temperature increase over ~20,000 years, triggered major faunal turnover and adaptive radiation among early mammals. The PETM coincides with the first appearance of many modern mammalian orders, making it a critical interval for understanding macroevolutionary patterns.\n\nMammalian evolution during the early Paleogene was profoundly influenced by both climatic and ecological factors. The extinction of non-avian dinosaurs at the end of the Cretaceous created numerous ecological opportunities that mammals rapidly exploited through adaptive radiation. Body size evolution, dietary specialization, and locomotory adaptations diversified rapidly as mammals expanded into previously unavailable ecological niches.\n\nThe Bighorn Basin of Wyoming preserves one of the most complete terrestrial Paleocene-Eocene sequences in North America, with exceptional fossil mammal assemblages spanning the PETM interval. These deposits provide unique opportunities to examine evolutionary dynamics at high temporal resolution, documenting both gradual evolutionary trends and rapid adaptive responses to environmental change.\n\nThis study presents a comprehensive analysis of mammalian body size evolution across the PETM in the Bighorn Basin, integrating morphological, ecological, and environmental data to understand the drivers of early Cenozoic mammalian diversification. Our research employs phylogenetic comparative methods to distinguish between climatic forcing and intrinsic evolutionary processes in shaping mammalian evolutionary trajectories.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Fossil Collection and Stratigraphy\nMammalian fossils were collected from 67 stratigraphic levels spanning 200 m of section through the Willwood Formation in the Bighorn Basin, Wyoming. High-resolution magnetostratigraphy and carbon isotope chemostratigraphy provide precise temporal control. All specimens are housed in the University of Michigan Museum of Paleontology (UMMP) with detailed locality and stratigraphic data.\n\n2.2 Morphometric Analysis\nBody mass estimation employed established allometric relationships between dental and postcranial dimensions and body mass in extant mammals. First molar area was used as the primary body size proxy, supplemented by long bone measurements where available. Measurement precision was assessed through repeated measurements with inter-observer error < 3%.\n\n2.3 Phylogenetic Analysis\nPhylogenetic relationships were reconstructed using morphological character matrices for major mammalian clades. Bayesian analysis employed MrBayes v3.2.6 with morphological models and relaxed molecular clock assumptions. Ancestral state reconstruction used maximum likelihood methods to estimate body size evolution along phylogenetic branches.\n\n2.4 Environmental Proxy Data\nPaleoclimate reconstruction employed multiple proxies including carbon isotope analysis of paleosol carbonates, leaf margin analysis of plant macrofossils, and oxygen isotope analysis of mammalian tooth enamel. Temperature estimates were calibrated using modern transfer functions and validated through independent proxies.\n\n2.5 Statistical Analysis\nEvolutionary rate analysis employed comparative methods accounting for phylogenetic non-independence. Rates of morphological evolution were calculated using maximum likelihood approaches. Environmental correlations were assessed using phylogenetic generalized least squares regression.",
                    "results_title": "3. Results",
                    "results_text": "Analysis of 1,847 mammalian specimens reveals significant body size reduction across the PETM interval, with average body mass decreasing by 22% in artiodactyls and 19% in perissodactyls. Evolutionary rate analysis indicates 3-5x acceleration in morphological evolution during the PETM. Phylogenetic analysis reveals multiple independent episodes of dwarfing across different mammalian lineages coincident with peak warming.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Mammalian dwarfing during the PETM represents a rapid evolutionary response to extreme warming, likely driven by thermoregulatory constraints and resource limitation. Body size reduction enabled improved heat dissipation and reduced metabolic demands under elevated temperatures. These patterns provide important insights into mammalian sensitivity to climate change and potential responses to future warming scenarios.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "PETM mammalian assemblages document rapid evolutionary responses to extreme climate change through coordinated body size reduction across multiple lineages. These findings demonstrate the capacity for rapid morphological evolution under strong selective pressure and provide crucial calibration data for predicting biotic responses to anthropogenic climate change."
                }
            },
            "trace_fossil": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "Trace fossils (ichnofossils) provide unique insights into ancient animal behavior, paleoenvironmental conditions, and ecosystem structure that cannot be obtained from body fossils alone. The Cambrian Explosion, representing the rapid diversification of complex multicellular life approximately 540 million years ago, is documented not only by the first appearance of diverse body fossil assemblages but also by a dramatic increase in trace fossil diversity and complexity. This ichnological record reveals the evolution of animal behavior, bioturbation intensity, and sediment-organism interactions during this critical evolutionary interval.\n\nThe transition from simple horizontal traces in Precambrian sediments to complex three-dimensional burrow systems in Cambrian rocks reflects fundamental changes in animal ecology and substrate relationships. Early Cambrian trace fossil assemblages document the evolution of infaunal lifestyles, predator-prey interactions, and the establishment of modern marine ecosystem structure. The ichnofossil record is particularly valuable because it preserves evidence of soft-bodied organisms that are rarely preserved as body fossils.\n\nThe Wood Canyon Formation of the southwestern United States preserves exceptional trace fossil assemblages spanning the Precambrian-Cambrian transition. These deposits record the progressive colonization of marine substrates by increasingly complex animal communities, providing crucial insights into the ecological drivers of early animal diversification.\n\nThis study presents a comprehensive ichnological analysis of trace fossil assemblages from the Wood Canyon Formation, integrating morphological, environmental, and statistical data to reconstruct early Cambrian behavioral evolution and ecosystem development. Our research focuses on understanding the relationship between trace fossil complexity and environmental factors, and the role of bioturbation in shaping early marine ecosystems.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Stratigraphic Framework and Sampling\nTrace fossil assemblages were systematically documented through 47 measured sections totaling 890 m of stratigraphic thickness in the Wood Canyon Formation across Nevada and California. Precise biostratigraphic control was achieved through trilobite and archaeocyath zones. Trace fossils were documented in situ with detailed stratigraphic and facies context.\n\n2.2 Ichnological Analysis\nTrace fossil identification followed established ichnotaxonomic principles emphasizing morphological characteristics and behavioral interpretation. Detailed measurements included burrow diameter, length, depth penetration, and geometric complexity parameters. Bioturbation intensity was quantified using the ichnofabric index (ii) ranging from 1 (unbioturbated) to 6 (completely bioturbated).\n\n2.3 Morphometric and Statistical Analysis\nTrace fossil morphological complexity was quantified using fractal dimension analysis and geometric morphometric methods. Diversity patterns were analyzed using rarefaction curves and non-parametric estimators. Assemblage composition was compared using multivariate ordination techniques including principal component analysis and non-metric multidimensional scaling.\n\n2.4 Paleoecological Reconstruction\nBehavioral interpretation integrated trace fossil morphology with sedimentological and taphonomic data. Substrate consistency was inferred from trace fossil preservation style and sedimentary structures. Tiering analysis reconstructed vertical distribution of infaunal communities and intensity of substrate utilization.\n\n2.5 Environmental Analysis\nPaleoenvironmental reconstruction employed sedimentological analysis, sequence stratigraphic interpretation, and geochemical proxies. Oxygen and carbon isotope analysis of associated carbonate phases provided constraints on water depth, temperature, and productivity. Storm bed analysis indicated wave base and depositional energy levels.",
                    "results_title": "3. Results",
                    "results_text": "Systematic analysis identified 34 ichnospecies representing diverse behavioral categories including locomotion, feeding, dwelling, and resting traces. Trace fossil diversity increases dramatically across the Precambrian-Cambrian boundary, with ichnodiversity index rising from 0.8 to 3.4. Bioturbation intensity shows parallel increase with maximum penetration depths reaching 15 cm in latest Precambrian versus >50 cm in Early Cambrian sediments.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Cambrian trace fossil assemblages document fundamental reorganization of benthic communities through increased infaunal exploitation and three-dimensional substrate utilization. Behavioral complexity evolution reflects development of sophisticated feeding strategies, predator avoidance, and resource competition. These patterns indicate establishment of modern-style marine ecosystem structure during early Cambrian interval.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Wood Canyon Formation trace fossil assemblages record the rapid evolution of complex animal behavior and ecosystem engineering during the Cambrian Explosion. Increased bioturbation intensity and behavioral diversity fundamentally altered marine sedimentary environments and biogeochemical cycling. These findings provide crucial insights into early animal ecology and the ecological consequences of the Cambrian radiation."
                }
            },
            "amber_inclusion": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "Amber inclusions provide exceptional three-dimensional preservation of ancient terrestrial ecosystems, offering unparalleled insights into the morphology, behavior, and ecological relationships of Mesozoic and Cenozoic arthropods. Baltic amber, dated to the Middle Eocene (approximately 44-49 Ma), represents one of the world's richest amber deposits, preserving diverse assemblages of insects, spiders, and other arthropods in exquisite detail. These inclusions document tropical forest ecosystems that thrived during the Eocene greenhouse climate, providing crucial calibration points for understanding arthropod evolution and ancient biodiversity patterns.\n\nThe preservation quality in amber is extraordinary, often maintaining cellular-level details, original coloration, and even behavioral interactions frozen in time. Unlike compression fossils, amber inclusions preserve complete three-dimensional anatomy, allowing detailed morphological analysis comparable to extant species. This preservation mode is particularly valuable for understanding the evolution of flight, social behavior, and complex ecological interactions among small-bodied arthropods.\n\nBaltic amber originates from extensive coniferous forests that covered northern Europe during the Eocene. The amber-producing trees belonged to the extinct genus Pinus succinifera, which secreted copious amounts of resin that trapped and preserved contemporary fauna and flora. Recent phylogenetic analyses of amber-preserved arthropods have revealed numerous evolutionary innovations and provided crucial calibration points for molecular clock studies.\n\nThis study presents a comprehensive taxonomic and ecological analysis of spider assemblages preserved in Baltic amber, integrating morphological, behavioral, and environmental data to reconstruct Eocene forest ecosystem structure. Our research employs micro-CT scanning and 3D morphometric analysis to examine previously inaccessible anatomical details and understand the evolutionary relationships of extinct spider lineages.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Amber Sample Collection and Curation\nA total of 2,847 amber pieces containing spider inclusions were examined from museum collections including the Natural History Museum, London (BMNH), American Museum of Natural History (AMNH), and private collections. All specimens are from verified Baltic amber deposits with established Eocene age. Detailed photographic documentation was completed for all specimens under various lighting conditions.\n\n2.2 Micro-CT Scanning and 3D Analysis\nSelected specimens underwent high-resolution micro-CT scanning using a Zeiss Xradia 520 Versa system at 0.7-2.0 μm voxel resolution. 3D reconstructions were generated using Dragonfly software suite, enabling virtual dissection and measurement of internal anatomical structures. Volume rendering techniques revealed previously inaccessible morphological details.\n\n2.3 Morphological Analysis and Measurement\nMorphometric analysis included standard spider taxonomic characters: prosoma dimensions, leg segment ratios, eye arrangement, and genital morphology. All measurements were calibrated using internal amber bubble scales and verified through multiple imaging techniques. Geometric morphometric analysis employed landmark-based methods to quantify shape variation.\n\n2.4 Phylogenetic Analysis\nPhylogenetic relationships were reconstructed using morphological character matrices incorporating 127 characters scored for 89 spider taxa. Bayesian analysis employed MrBayes v3.2.6 with morphological models and gamma-distributed rate variation. Ancestral state reconstruction examined the evolution of web-building behavior and ecological specializations.\n\n2.5 Paleoecological Reconstruction\nEcological analysis integrated spider assemblage composition with associated plant and arthropod inclusions. Behavioral observations included prey capture, mating behavior, and web construction preserved in amber. Statistical analysis of assemblage structure employed rarefaction analysis and ecological diversity indices.",
                    "results_title": "3. Results",
                    "results_text": "Taxonomic analysis identified 47 spider species representing 23 families, including 12 new species and 3 new genera. Phylogenetic analysis reveals that 73% of amber spider lineages represent extinct clades with no modern descendants. Ecological analysis indicates diverse guild structure including web-builders (34%), active hunters (41%), and ambush predators (25%). Several specimens preserve complete webs and prey capture behavior.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Baltic amber spider assemblages document exceptional taxonomic and ecological diversity during Eocene greenhouse climates. High levels of endemism suggest rapid evolutionary innovation in tropical forest environments. Behavioral preservation reveals sophisticated predatory strategies and complex ecological interactions. These patterns provide insights into arthropod community assembly and the ecological consequences of climate change.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Baltic amber spider assemblages represent peak terrestrial arthropod diversity during Eocene greenhouse interval. Exceptional preservation quality enables detailed reconstruction of ancient forest ecosystem structure and evolutionary processes. These findings provide crucial calibration data for understanding arthropod macroevolution and community dynamics in deep time."
                }
            },
            "microorganism": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "Precambrian microfossils provide the earliest direct evidence of life on Earth, documenting the evolution of cellular complexity, metabolic innovations, and ecological diversification over nearly three billion years of Earth's history. The transition from simple prokaryotic cells to complex eukaryotic organisms represents one of the most significant evolutionary innovations, fundamentally altering biogeochemical cycles and paving the way for multicellular life. Exceptionally preserved microfossil assemblages from the Proterozoic Era offer unique insights into early life evolution and the environmental conditions that shaped early biosphere development.\n\nThe Bitter Springs Formation of central Australia preserves one of the world's most diverse and well-preserved Neoproterozoic microfossil assemblages, dated to approximately 850 million years ago. These cherts contain exceptional three-dimensional preservation of cellular structures, including cell walls, organelles, and reproductive structures. The assemblages document critical evolutionary innovations including the origin of sexual reproduction, multicellularity, and complex developmental programs.\n\nMicrofossil preservation in chert involves rapid silicification of organic matter, creating exceptional preservation conditions that maintain cellular-level details. Advanced analytical techniques including scanning electron microscopy, transmission electron microscopy, and synchrotron X-ray microscopy now enable detailed examination of subcellular structures and biochemical composition of ancient microorganisms.\n\nThis study presents a comprehensive analysis of microfossil assemblages from the Bitter Springs Formation, employing cutting-edge analytical techniques to examine cellular morphology, reproductive strategies, and ecological relationships of Neoproterozoic microorganisms. Our research focuses on understanding the timing and environmental context of major evolutionary innovations during this critical interval in life's history.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Sample Collection and Preparation\nMicrofossil-bearing chert samples were collected from 15 stratigraphic horizons spanning 40 m of section in the Bitter Springs Formation, Amadeus Basin, central Australia. Thin sections (30 μm thickness) were prepared using standard petrographic techniques with careful attention to preserving delicate cellular structures. Polished thick sections were prepared for scanning electron microscopy analysis.\n\n2.2 Light and Electron Microscopy\nMicrofossil documentation employed transmitted light microscopy using Zeiss Axiophot and Leica DMRX systems with differential interference contrast and fluorescence capabilities. Scanning electron microscopy utilized a FEI Quanta 400 ESEM with field emission gun for high-resolution surface imaging. Transmission electron microscopy of ultrathin sections (70 nm) examined subcellular preservation.\n\n2.3 Synchrotron X-ray Microscopy\nSelected specimens were analyzed using synchrotron-based X-ray microscopy at the Advanced Light Source, Lawrence Berkeley National Laboratory. This non-destructive technique enabled 3D imaging of internal cellular structures at sub-micron resolution while maintaining specimen integrity for subsequent analysis.\n\n2.4 Geochemical Analysis\nOrganic matter characterization employed Raman spectroscopy to assess preservation quality and identify biochemical signatures. Ion microprobe analysis (SIMS) determined carbon isotopic composition of individual microfossils. Trace element analysis used laser ablation ICP-MS to examine environmental signatures preserved in chert matrix.\n\n2.5 Phylogenetic and Ecological Analysis\nMorphological characters were coded for phylogenetic analysis using established protocols for microfossil systematics. Ecological reconstruction integrated morphological data with geochemical proxies and sedimentological context. Statistical analysis employed multivariate methods to identify environmental gradients controlling microbial community structure.",
                    "results_title": "3. Results",
                    "results_text": "Systematic analysis identified 34 microfossil taxa including 12 putative eukaryotic forms with preserved organelles and complex cell division stages. Several specimens preserve potential sexual reproductive structures including conjugation tubes and meiotic cell division. Size-frequency analysis reveals bimodal distribution consistent with prokaryotic-eukaryotic community structure. Carbon isotope values range from -28‰ to -35‰, indicating diverse metabolic pathways.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Bitter Springs assemblages document critical evolutionary transitions including the emergence of eukaryotic cellular complexity and sexual reproduction. Preserved reproductive structures provide direct evidence for genetic recombination processes that accelerated evolutionary innovation. Community structure analysis indicates ecological differentiation and niche partitioning among early eukaryotic lineages.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Neoproterozoic microfossil assemblages preserve crucial evidence for early eukaryotic evolution and the establishment of modern cellular complexity. The origin of sexual reproduction represents a key innovation that facilitated subsequent evolutionary diversification. These findings provide important constraints on the timing and environmental context of major evolutionary innovations in early life history."
                }
            },
            "taphonomy": {
                "en": {
                    "intro_title": "1. Introduction",
                    "intro_text": "Taphonomic processes fundamentally control fossil preservation and the completeness of the paleontological record, influencing our understanding of ancient life and evolutionary patterns. The study of taphonomy—the transition of organisms from the biosphere to the lithosphere—provides crucial insights into preservation biases, environmental conditions, and the reliability of fossil assemblages for paleobiological interpretation. Understanding taphonomic processes is essential for distinguishing genuine biological signals from preservational artifacts in the fossil record.\n\nLagerstätten, or fossil deposits with exceptional preservation, offer unique opportunities to examine taphonomic processes under controlled natural conditions. The Burgess Shale of British Columbia, Middle Cambrian in age (~507 Ma), represents one of the world's most famous Lagerstätten, preserving soft-bodied organisms that are typically absent from the fossil record. The exceptional preservation results from rapid burial in fine-grained sediments under anoxic conditions, preventing decay and scavenging.\n\nRecent discoveries of new Burgess Shale-type localities have expanded our understanding of preservation mechanisms and temporal variation in taphonomic processes. These sites preserve diverse soft-bodied assemblages including arthropods, mollusks, and problematic taxa that provide crucial insights into Cambrian ecosystem structure and early animal evolution. Comparative taphonomic analysis across multiple localities enables assessment of environmental controls on preservation quality.\n\nThis study presents a comprehensive taphonomic analysis of soft-bodied fossil assemblages from recently discovered Burgess Shale-type localities in the Canadian Rockies. Our research integrates morphological, geochemical, and sedimentological data to understand preservation mechanisms and assess the completeness of these exceptional fossil assemblages. We focus on quantifying preservation biases and their implications for paleobiological interpretation.",
                    "methods_title": "2. Materials and Methods",
                    "methods_text": "2.1 Field Collection and Stratigraphic Context\nFossil specimens were collected from five newly discovered Burgess Shale-type localities in Yoho and Kootenay National Parks, British Columbia. Detailed stratigraphic sections were measured with precise sample positioning relative to established biostratigraphic markers. All specimens are curated at the Royal Ontario Museum (ROM) with complete locality and stratigraphic data.\n\n2.2 Preservation Quality Assessment\nTaphonomic analysis employed standardized protocols for assessing soft-tissue preservation including completeness indices, articulation scores, and decay stage evaluation. Digital photography under various lighting conditions documented preservation details. Scanning electron microscopy examined surface textures and mineral replacement patterns.\n\n2.3 Geochemical Analysis\nPreservation mechanisms were investigated through X-ray diffraction analysis of fossil-bearing sediments and authigenic mineral phases. Carbon and sulfur isotope analysis examined diagenetic processes and redox conditions during fossilization. Trace element analysis using ICP-MS identified environmental signatures preserved in fossil-bearing horizons.\n\n2.4 Sedimentological Analysis\nDetailed sedimentological analysis characterized depositional environments and burial conditions. Grain size analysis, sorting parameters, and sedimentary structures were quantified to assess transport energy and depositional processes. Paleoflow analysis reconstructed current directions and sediment transport pathways.\n\n2.5 Comparative Taphonomic Analysis\nPreservation patterns were compared across localities using multivariate statistical methods. Cluster analysis identified taphonomic grades and preservation modes. Logistic regression analysis examined environmental controls on preservation quality including water depth, oxygen levels, and sedimentation rate.",
                    "results_title": "3. Results",
                    "results_text": "Taphonomic analysis reveals three distinct preservation modes: pyritized soft tissues (45% of specimens), carbonaceous films (32%), and three-dimensional phosphatized remains (23%). Preservation quality correlates strongly with grain size and organic carbon content of host sediments. Statistical analysis indicates rapid burial (hours to days) followed by early diagenetic mineralization under sulfate-reducing conditions.",
                    "discussion_title": "4. Discussion",
                    "discussion_text": "Burgess Shale-type preservation requires specific environmental conditions including rapid burial, anoxic bottom waters, and early diagenetic mineralization. Preservation bias favors organisms with resistant organic matrices while completely soft tissues are selectively lost. These patterns have significant implications for reconstructing Cambrian biodiversity and ecosystem structure from fossil assemblages.",
                    "conclusions_title": "5. Conclusions",
                    "conclusions_text": "Comparative taphonomic analysis reveals systematic preservation biases in Burgess Shale-type assemblages that must be considered in paleobiological interpretation. Exceptional preservation results from the intersection of specific environmental conditions and rapid diagenetic processes. Understanding these taphonomic controls is crucial for accurate reconstruction of ancient ecosystems and evolutionary patterns."
                }
            }
        }
        
        return texts_database.get(paper_type, texts_database["theropod"]).get(self.language, texts_database.get(paper_type, texts_database["theropod"])["en"])
    
    def _create_theropod_content(self):
        """수각류 공룡 논문 내용"""
        content = []
        texts = self._get_paper_texts("theropod")
        
        # 1. Introduction
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 2. Materials and Methods
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 3. Results
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 4. Discussion
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 5. Conclusions
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_trilobite_content(self):
        """삼엽충 논문 내용"""
        content = []
        texts = self._get_paper_texts("trilobite")
        
        # 섹션별 내용 생성 (theropod와 동일한 구조, 다른 내용)
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    # 나머지 논문 유형들도 각각 다른 내용으로 생성
    def _create_marine_reptile_content(self):
        """해양 파충류 논문 내용"""
        content = []
        texts = self._get_paper_texts("marine_reptile")
        
        # 1. Introduction
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 2. Materials and Methods
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 3. Results
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 4. Discussion
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        # 5. Conclusions
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_plant_fossil_content(self):
        """식물 화석 논문 내용"""
        content = []
        texts = self._get_paper_texts("plant_fossil")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_mass_extinction_content(self):
        """대량절멸 논문 내용"""
        content = []
        texts = self._get_paper_texts("mass_extinction")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_mammal_evolution_content(self):
        """포유류 진화 논문 내용"""
        content = []
        texts = self._get_paper_texts("mammal_evolution")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_trace_fossil_content(self):
        """생흔화석 논문 내용"""
        content = []
        texts = self._get_paper_texts("trace_fossil")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_amber_inclusion_content(self):
        """호박 내포물 논문 내용"""
        content = []
        texts = self._get_paper_texts("amber_inclusion")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_microorganism_content(self):
        """미생물 논문 내용"""
        content = []
        texts = self._get_paper_texts("microorganism")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_taphonomy_content(self):
        """매장학 논문 내용"""
        content = []
        texts = self._get_paper_texts("taphonomy")
        
        # 전체 섹션 구조로 생성
        content.append(Paragraph(f"<b>{texts['intro_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['intro_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['methods_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['methods_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['results_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['results_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['discussion_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['discussion_text'], self.styles['BodyText']))
        content.append(Spacer(1, 10))
        
        content.append(Paragraph(f"<b>{texts['conclusions_title']}</b>", self.styles['SectionHeader']))
        content.append(Paragraph(texts['conclusions_text'], self.styles['BodyText']))
        
        return content
    
    def _create_additional_content(self):
        """추가 본문 내용 (2페이지 이후)"""
        content = []
        
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

# 다중 PDF 생성 함수
def generate_multiple_papers(output_dir="test_papers"):
    """다양한 유형과 언어의 논문들을 생성"""
    import os
    
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # 언어 목록
    languages = ["en", "ko", "jp", "zh"]
    
    # 논문 유형 목록
    paper_types = [
        "theropod", "trilobite", "marine_reptile", "plant_fossil",
        "mass_extinction", "mammal_evolution", "trace_fossil", 
        "amber_inclusion", "microorganism", "taphonomy"
    ]
    
    generated_files = []
    
    print("🦕 고생물학 연구논문 PDF 생성 시작...")
    print(f"📁 출력 디렉토리: {output_path.absolute()}")
    print()
    
    # 1. 언어별 기본 논문 생성 (theropod 유형) - 일부는 텍스트 레이어 없음
    for i, lang in enumerate(languages):
        try:
            # 50% 확률로 텍스트 레이어 없는 PDF 생성
            no_text = i % 2 == 0  # en, jp는 텍스트 레이어 없음, ko, zh는 있음
            
            generator = PaleontologyPaperGenerator(
                output_dir=str(output_path),
                language=lang,
                paper_type="theropod",
                no_text_layer=no_text
            )
            suffix = "_no_text" if no_text else ""
            filename = f"paleontology_paper_{lang}{suffix}.pdf"
            pdf_path = generator.generate_paper(filename)
            generated_files.append(pdf_path)
            text_status = "텍스트 레이어 없음" if no_text else "텍스트 레이어 있음"
            print(f"✅ {lang} 논문 생성 완료 ({text_status})")
        except Exception as e:
            print(f"❌ {lang} 논문 생성 실패: {e}")
    
    print()
    
    # 2. 유형별 영어 논문 생성 - 일부는 텍스트 레이어 없음
    for i, paper_type in enumerate(paper_types):
        try:
            # 특정 유형들만 텍스트 레이어 없이 생성
            no_text = paper_type in ["marine_reptile", "mass_extinction", "trace_fossil", "microorganism"]
            
            generator = PaleontologyPaperGenerator(
                output_dir=str(output_path),
                language="en",
                paper_type=paper_type,
                no_text_layer=no_text
            )
            suffix = "_no_text" if no_text else ""
            filename = f"paleontology_{paper_type}_en{suffix}.pdf"
            pdf_path = generator.generate_paper(filename)
            generated_files.append(pdf_path)
            text_status = "텍스트 레이어 없음" if no_text else "텍스트 레이어 있음"
            print(f"✅ {paper_type} 논문 생성 완료 ({text_status})")
        except Exception as e:
            print(f"❌ {paper_type} 논문 생성 실패: {e}")
    
    print()
    
    # 3. 다국어 삼엽충 논문 생성 - 한국어와 중국어만 텍스트 레이어 없음
    for lang in languages:
        try:
            no_text = lang in ["ko", "zh"]  # 한국어, 중국어만 텍스트 레이어 없음
            
            generator = PaleontologyPaperGenerator(
                output_dir=str(output_path),
                language=lang,
                paper_type="trilobite",
                no_text_layer=no_text
            )
            suffix = "_no_text" if no_text else ""
            filename = f"trilobite_paper_{lang}{suffix}.pdf"
            pdf_path = generator.generate_paper(filename)
            generated_files.append(pdf_path)
            text_status = "텍스트 레이어 없음" if no_text else "텍스트 레이어 있음"
            print(f"✅ trilobite {lang} 논문 생성 완료 ({text_status})")
        except Exception as e:
            print(f"❌ trilobite {lang} 논문 생성 실패: {e}")
    
    print()
    
    # 4. 추가 텍스트 레이어 없는 PDF들 생성
    no_text_combinations = [
        ("plant_fossil", "en"),
        ("amber_inclusion", "ko"), 
        ("mammal_evolution", "jp"),
        ("taphonomy", "zh")
    ]
    
    print("📝 추가 텍스트 레이어 없는 PDF 생성...")
    for paper_type, lang in no_text_combinations:
        try:
            generator = PaleontologyPaperGenerator(
                output_dir=str(output_path),
                language=lang,
                paper_type=paper_type,
                no_text_layer=True
            )
            filename = f"{paper_type}_{lang}_no_text.pdf"
            pdf_path = generator.generate_paper(filename)
            generated_files.append(pdf_path)
            print(f"✅ {paper_type} {lang} 논문 생성 완료 (텍스트 레이어 없음)")
        except Exception as e:
            print(f"❌ {paper_type} {lang} 논문 생성 실패: {e}")
    
    print()
    print(f"🎉 PDF 생성 완료! 총 {len(generated_files)}개 파일 생성됨")
    print(f"📂 저장 위치: {output_path.absolute()}")
    
    return generated_files

# 함수 호출 예시
def main():
    """메인 함수 - PDF 생성 테스트"""
    import argparse
    
    parser = argparse.ArgumentParser(description="고생물학 연구논문 PDF 생성기")
    parser.add_argument("--language", "-l", default="en", choices=["en", "ko", "jp", "zh"],
                       help="논문 언어 (기본값: en)")
    parser.add_argument("--type", "-t", default="theropod", 
                       choices=["theropod", "trilobite", "marine_reptile", "plant_fossil",
                               "mass_extinction", "mammal_evolution", "trace_fossil", 
                               "amber_inclusion", "microorganism", "taphonomy"],
                       help="논문 유형 (기본값: theropod)")
    parser.add_argument("--output", "-o", default="test_papers", help="출력 디렉토리 (기본값: test_papers)")
    parser.add_argument("--filename", "-f", help="출력 파일명 (지정하지 않으면 자동 생성)")
    parser.add_argument("--no-text", action="store_true", help="텍스트 레이어 없는 PDF 생성 (OCR 테스트용)")
    parser.add_argument("--multiple", "-m", action="store_true", help="다양한 유형과 언어의 논문들을 대량 생성")
    
    args = parser.parse_args()
    
    try:
        if args.multiple:
            # 다중 PDF 생성
            generated_files = generate_multiple_papers(args.output)
            print(f"\n📋 생성된 파일 목록:")
            for i, file_path in enumerate(generated_files, 1):
                file_name = os.path.basename(file_path)
                print(f"  {i:2d}. {file_name}")
        else:
            # 단일 PDF 생성
            generator = PaleontologyPaperGenerator(
                output_dir=args.output,
                language=args.language,
                paper_type=args.type,
                no_text_layer=args.no_text
            )
            pdf_path = generator.generate_paper(args.filename)
            print(f"✅ PDF 생성 성공: {pdf_path}")
            
    except Exception as e:
        print(f"❌ PDF 생성 실패: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
