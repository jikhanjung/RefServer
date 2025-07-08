# 문단 구분 감지 규칙 (Paragraph Detection Rules)

## 개요
텍스트에서 문단 구분을 자동으로 감지하기 위한 규칙들을 정의합니다. 이 규칙들은 OCR 결과의 좌표 정보와 텍스트 패턴을 분석하여 적용됩니다.

---

## 1. 물리적 레이아웃 기반 규칙 (Physical Layout Rules)

### 1.1 수직 간격 (Vertical Spacing)
- **큰 간격**: 줄 간격이 평상시보다 1.5배 이상 클 때
- **빈 줄**: 완전히 빈 줄이 있을 때
- **측정 기준**: 
  ```
  normal_line_spacing = avg_line_height * 1.2
  paragraph_spacing = avg_line_height * 2.0
  ```

### 1.2 수평 정렬 (Horizontal Alignment)
- **줄 끝 위치 (Line End Position)**:
  ```
  line_width = rightmost_x - leftmost_x
  page_width = estimated_page_width
  short_line_threshold = page_width * 0.7  # 페이지 폭의 70% 미만
  ```
- **들여쓰기 (Indentation)**:
  ```
  normal_indent = leftmost_x_of_paragraph
  paragraph_indent = normal_indent + (avg_char_width * 2~4)
  ```

### 1.3 줄 길이 패턴 (Line Length Patterns)
- **짧은 줄**: 일반 줄보다 30% 이상 짧은 경우
- **가득 찬 줄**: 페이지 폭의 90% 이상을 사용하는 경우

---

## 2. 텍스트 패턴 기반 규칙 (Text Pattern Rules)

### 2.1 문장 끝 표시 (Sentence Ending Indicators)
```python
sentence_endings = ['.', '!', '?', ':', ';']
strong_endings = ['.', '!', '?']  # 강한 문장 끝
weak_endings = [':', ';']         # 약한 문장 끝
```

### 2.2 문단 시작 표시 (Paragraph Starting Indicators)
```python
# 대문자로 시작
def starts_with_capital(text):
    return text[0].isupper() if text else False

# 숫자로 시작 (목록)
def starts_with_number(text):
    return re.match(r'^\d+\.?\s', text)

# 특수 기호로 시작
def starts_with_bullet(text):
    return re.match(r'^[-•*▪▫○●]\s', text)
```

### 2.3 특수 패턴 (Special Patterns)
```python
# 학술 논문 섹션 헤더
section_headers = [
    'abstract', 'introduction', 'method', 'methods', 'result', 'results',
    'discussion', 'conclusion', 'conclusions', 'references', 'bibliography',
    'resumen', 'kurzfassung', 'zusammenfassung'
]

# 저자 정보 패턴
author_patterns = [
    r'^\w+\s+\w+\s*[&,]',  # "John Smith &"
    r'^\w+,\s+\w+\.?\s*[&,]',  # "Smith, J. &"
    r'^\w+\s+et\s+al\.',  # "Smith et al."
]

# 인용 패턴
citation_patterns = [
    r'\(\d{4}\)',  # (2023)
    r'\[\d+\]',    # [1]
    r'\(\w+\s+\d{4}\)',  # (Smith 2023)
]
```

---

## 3. 복합 조건 규칙 (Compound Condition Rules)

### 3.1 강한 문단 구분 (Strong Paragraph Break)
```python
def is_strong_paragraph_break(current_line, next_line, spacing_info):
    conditions = []
    
    # 조건 1: 큰 수직 간격
    conditions.append(spacing_info['vertical_gap'] > spacing_info['paragraph_threshold'])
    
    # 조건 2: 현재 줄이 짧고 강한 끝맺음
    conditions.append(
        current_line['is_short'] and 
        any(current_line['text'].rstrip().endswith(end) for end in ['.', '!', '?'])
    )
    
    # 조건 3: 다음 줄이 대문자로 시작
    conditions.append(next_line['starts_with_capital'])
    
    # 조건 4: 들여쓰기 변화
    conditions.append(abs(current_line['x'] - next_line['x']) > spacing_info['indent_threshold'])
    
    return sum(conditions) >= 2  # 2개 이상 조건 만족시 강한 구분
```

### 3.2 중간 문단 구분 (Medium Paragraph Break)
```python
def is_medium_paragraph_break(current_line, next_line, spacing_info):
    conditions = []
    
    # 조건 1: 중간 수직 간격
    conditions.append(
        spacing_info['line_threshold'] < spacing_info['vertical_gap'] < spacing_info['paragraph_threshold']
    )
    
    # 조건 2: 섹션 헤더 패턴
    conditions.append(is_section_header(current_line['text']) or is_section_header(next_line['text']))
    
    # 조건 3: 목록 패턴
    conditions.append(starts_with_number(next_line['text']) or starts_with_bullet(next_line['text']))
    
    # 조건 4: 줄 길이 급변
    conditions.append(
        abs(current_line['width'] - next_line['width']) > (spacing_info['avg_width'] * 0.4)
    )
    
    return sum(conditions) >= 2
```

### 3.3 약한 문단 구분 (Weak Paragraph Break)
```python
def is_weak_paragraph_break(current_line, next_line, spacing_info):
    conditions = []
    
    # 조건 1: 최소한의 수직 간격
    conditions.append(spacing_info['vertical_gap'] > spacing_info['line_threshold'])
    
    # 조건 2: 약한 끝맺음 + 대문자 시작
    conditions.append(
        current_line['text'].rstrip().endswith((':',';')) and
        next_line['starts_with_capital']
    )
    
    # 조건 3: 인용구나 특수 형식
    conditions.append(
        re.search(r'["\'""]$', current_line['text']) or
        re.search(r'^["\'""]', next_line['text'])
    )
    
    return sum(conditions) >= 2
```

---

## 4. 학술 논문 특화 규칙 (Academic Paper Specific Rules)

### 4.1 Abstract 구분
```python
def detect_abstract_section(lines):
    for i, line in enumerate(lines):
        if 'abstract' in line['text'].lower():
            # Abstract 제목 다음부터 첫 빈 줄까지 또는 다음 섹션까지
            return mark_section_boundary(lines, i)
```

### 4.2 참고문헌 구분
```python
def detect_references_section(lines):
    reference_keywords = ['references', 'bibliography', 'works cited', 'literatura']
    for i, line in enumerate(lines):
        if any(keyword in line['text'].lower() for keyword in reference_keywords):
            # 각 참고문헌 항목을 별도 문단으로 처리
            return mark_reference_entries(lines, i)
```

### 4.3 수식 및 표 주변
```python
def detect_formula_table_breaks(lines):
    special_patterns = [
        r'^\s*\(\d+\)',  # 수식 번호 (1)
        r'^Table\s+\d+',  # Table 1
        r'^Figure\s+\d+', # Figure 1
        r'^Equation\s+\d+' # Equation 1
    ]
    # 이런 패턴 앞뒤로 문단 구분 추가
```

---

## 5. 언어별 특수 규칙 (Language-Specific Rules)

### 5.1 영어 (English)
```python
english_rules = {
    'sentence_endings': ['.', '!', '?'],
    'paragraph_starters': ['The', 'This', 'That', 'In', 'For', 'However', 'Therefore'],
    'transition_words': ['however', 'therefore', 'moreover', 'furthermore', 'nevertheless']
}
```

### 5.2 한국어 (Korean)
```python
korean_rules = {
    'sentence_endings': ['다.', '요.', '니다.', '습니다.', '?', '!'],
    'paragraph_starters': ['이는', '그러나', '따라서', '또한', '하지만'],
    'transition_markers': ['그런데', '그러므로', '즉', '예를 들어']
}
```

### 5.3 독일어 (German)
```python
german_rules = {
    'sentence_endings': ['.', '!', '?'],
    'paragraph_starters': ['Der', 'Die', 'Das', 'In', 'Für', 'Jedoch', 'Daher'],
    'compound_indicators': ['außerdem', 'jedoch', 'daher', 'deshalb']
}
```

---

## 6. 📊 중요도별 규칙 분류 및 우선순위

### 6.1 🎯 Tier 1: 매우 확실한 규칙 (신뢰도 95%+)

#### 1. 큰 수직 간격 (Large Vertical Gap)
- **확실성**: ⭐⭐⭐⭐⭐
- **조건**: `vertical_gap > avg_font_height * 2.5`
- **이유**: 물리적으로 명확한 구분, 거의 틀릴 수 없음
- **적용**: 즉시 적용 권장

#### 2. 섹션 헤더 (Section Headers)
- **확실성**: ⭐⭐⭐⭐⭐
- **조건**: "Abstract", "Introduction", "References" 등
- **이유**: 학술논문에서 100% 확실한 문단 구분
- **적용**: 즉시 적용 권장

#### 3. 번호 목록 (Numbered Lists)
- **확실성**: ⭐⭐⭐⭐⭐
- **조건**: `"1. ", "2. ", "(1)", "(a)"` 등으로 시작
- **이유**: 각 항목이 별도 문단임이 명확
- **적용**: 즉시 적용 권장

### 6.2 🎯 Tier 2: 높은 확실성 (신뢰도 80-90%)

#### 4. 들여쓰기 변화 (Indentation Change)
- **확실성**: ⭐⭐⭐⭐
- **조건**: `abs(current_x - next_x) > avg_char_width * 3`
- **이유**: 의도적인 레이아웃 변화, 높은 신뢰도
- **적용**: 테스트 후 적용

#### 5. 짧은 줄 + 마침표 + 대문자 시작
- **확실성**: ⭐⭐⭐⭐
- **조건**: `short_line & ends_with_period & next_starts_capital`
- **이유**: 3개 조건 모두 만족시 거의 확실
- **적용**: 테스트 후 적용

### 6.3 🎯 Tier 3: 중간 확실성 (신뢰도 60-80%)

#### 6. 중간 수직 간격 + 텍스트 패턴
- **확실성**: ⭐⭐⭐
- **조건**: `1.5 * font_height < gap < 2.5 * font_height` + 텍스트 단서
- **이유**: 간격만으로는 애매하지만 텍스트 단서와 조합시 유용
- **적용**: 신중하게 적용

#### 7. 줄 길이 급변
- **확실성**: ⭐⭐⭐
- **조건**: 연속된 줄의 길이가 급격히 변화
- **이유**: 레이아웃 변화 감지하지만 false positive 가능
- **적용**: 사용자 설정 옵션으로

---

## 📐 폰트 크기 고려 개선 임계값

### 6.4 폰트 인식 기반 적응적 임계값
```python
def calculate_font_aware_thresholds(data):
    # 1. 문자 높이 분석 (개선)
    heights = []
    confidences = []
    
    for i in range(len(data['text'])):
        if data['text'][i].strip() and data['conf'][i] > 50:  # 신뢰도 50% 이상만
            heights.append(data['height'][i])
            confidences.append(data['conf'][i])
    
    if not heights:
        return default_thresholds()
    
    # 2. 가중 평균 (신뢰도 기반)
    weighted_heights = [h * c for h, c in zip(heights, confidences)]
    avg_font_height = sum(weighted_heights) / sum(confidences)
    
    # 3. 이상치 제거
    height_std = np.std(heights)
    filtered_heights = [h for h in heights if abs(h - avg_font_height) < 2 * height_std]
    avg_font_height = np.mean(filtered_heights) if filtered_heights else avg_font_height
    
    # 4. 계층적 임계값 설정
    thresholds = {
        'tiny_gap': avg_font_height * 0.3,      # 줄 내 단어 간격
        'line_gap': avg_font_height * 0.8,      # 일반 줄바꿈
        'small_para_gap': avg_font_height * 1.5, # 약한 문단 구분
        'medium_para_gap': avg_font_height * 2.0, # 중간 문단 구분
        'large_para_gap': avg_font_height * 3.0,  # 강한 문단 구분
        'section_gap': avg_font_height * 4.0,    # 섹션 구분
        'avg_char_width': avg_font_height * 0.6,  # 평균 문자 폭 추정
        'avg_font_height': avg_font_height        # 기준 폰트 높이
    }
    
    return thresholds, avg_font_height
```

### 6.5 규칙 우선순위 가중치
```python
rule_priorities = {
    # Tier 1: 매우 확실한 규칙
    'large_vertical_gap': 1.0,      # 최고 우선순위
    'section_headers': 0.95,
    'numbered_lists': 0.9,
    
    # Tier 2: 높은 확실성
    'indentation_change': 0.8,
    'triple_condition': 0.75,       # 짧은줄+마침표+대문자
    
    # Tier 3: 중간 확실성
    'medium_gap_with_pattern': 0.6,
    'line_length_change': 0.5,
    'weak_indicators': 0.3          # 최저 우선순위
}
```

### 6.6 점수 계산 (개선)
```python
def calculate_paragraph_break_score(current_line, next_line, thresholds):
    score = 0.0
    details = []
    
    # Tier 1 규칙들
    if next_line['y'] - current_line['y'] > thresholds['large_para_gap']:
        score += rule_priorities['large_vertical_gap']
        details.append("large_gap")
    
    if is_section_header(current_line['text']) or is_section_header(next_line['text']):
        score += rule_priorities['section_headers']
        details.append("section_header")
    
    if starts_with_number_or_bullet(next_line['text']):
        score += rule_priorities['numbered_lists']
        details.append("numbered_list")
    
    # Tier 2 규칙들
    indent_change = abs(current_line['x'] - next_line['x'])
    if indent_change > thresholds['avg_char_width'] * 3:
        score += rule_priorities['indentation_change']
        details.append("indentation_change")
    
    # 삼중 조건 (짧은줄 + 마침표 + 대문자)
    if (is_short_line(current_line, thresholds) and
        current_line['text'].rstrip().endswith('.') and
        next_line['text'] and next_line['text'][0].isupper()):
        score += rule_priorities['triple_condition']
        details.append("triple_condition")
    
    return score, details

def should_break_paragraph(score, details, threshold=0.7):
    """임계값 이상이면 문단 구분"""
    return score >= threshold, score, details
```

---

## 🚀 단계별 구현 계획

### 7.1 Phase 1: Tier 1 규칙 (즉시 적용)
```python
def apply_tier1_rules(lines, thresholds):
    """매우 확실한 규칙들만 적용 (신뢰도 95%+)"""
    breaks = []
    
    for i in range(len(lines) - 1):
        current, next_line = lines[i], lines[i + 1]
        gap = next_line['y'] - current['y']
        
        # Rule 1: 큰 간격 (절대적 확실성)
        if gap > thresholds['large_para_gap']:
            breaks.append(i)
            continue
            
        # Rule 2: 섹션 헤더 (100% 확실성)
        if is_section_header(current['text']) or is_section_header(next_line['text']):
            breaks.append(i)
            continue
            
        # Rule 3: 번호 목록 (100% 확실성)
        if starts_with_number_or_bullet(next_line['text']):
            breaks.append(i)
            continue
    
    return breaks
```

### 7.2 Phase 2: Tier 2 규칙 (검증 후 적용)
```python
def apply_tier2_rules(lines, thresholds, existing_breaks):
    """높은 확실성 규칙들 적용 (신뢰도 80-90%)"""
    additional_breaks = []
    
    for i in range(len(lines) - 1):
        if i in existing_breaks:  # 이미 구분된 곳은 스킵
            continue
            
        current, next_line = lines[i], lines[i + 1]
        gap = next_line['y'] - current['y']
        
        # Rule 4: 들여쓰기 변화
        indent_change = abs(current['x'] - next_line['x'])
        if (gap > thresholds['line_gap'] and 
            indent_change > thresholds['avg_char_width'] * 3):
            additional_breaks.append(i)
            continue
            
        # Rule 5: 삼중 조건 (짧은줄 + 마침표 + 대문자)
        if (gap > thresholds['small_para_gap'] and
            is_short_line(current, thresholds) and
            current['text'].rstrip().endswith('.') and
            next_line['text'] and next_line['text'][0].isupper()):
            additional_breaks.append(i)
    
    return additional_breaks
```

### 7.3 Phase 3: 통합 적용
```python
def detect_paragraph_breaks_progressive(lines, thresholds, apply_tier2=True, apply_tier3=False):
    """단계별로 규칙을 적용하여 문단 구분"""
    
    # Phase 1: 확실한 규칙들
    tier1_breaks = apply_tier1_rules(lines, thresholds)
    logger.info(f"Tier 1 breaks: {len(tier1_breaks)} found")
    
    all_breaks = set(tier1_breaks)
    
    # Phase 2: 높은 확실성 규칙들 (옵션)
    if apply_tier2:
        tier2_breaks = apply_tier2_rules(lines, thresholds, all_breaks)
        all_breaks.update(tier2_breaks)
        logger.info(f"Tier 2 breaks: {len(tier2_breaks)} additional found")
    
    # Phase 3: 중간 확실성 규칙들 (더 신중하게)
    if apply_tier3:
        tier3_breaks = apply_tier3_rules(lines, thresholds, all_breaks)
        all_breaks.update(tier3_breaks)
        logger.info(f"Tier 3 breaks: {len(tier3_breaks)} additional found")
    
    return sorted(list(all_breaks))
```

---

## 7. 구현 예시 (Implementation Example)

### 7.1 보조 함수들
```python
def is_section_header(text):
    """섹션 헤더 감지"""
    section_keywords = [
        'abstract', 'introduction', 'method', 'methods', 'result', 'results',
        'discussion', 'conclusion', 'conclusions', 'references', 'bibliography',
        'resumen', 'kurzfassung', 'zusammenfassung'
    ]
    text_lower = text.lower().strip()
    return any(keyword in text_lower for keyword in section_keywords)

def starts_with_number_or_bullet(text):
    """번호나 불릿으로 시작하는지 확인"""
    import re
    patterns = [
        r'^\d+\.?\s',           # "1. " or "1 "
        r'^\(\d+\)',           # "(1)"
        r'^[a-zA-Z]\.?\s',     # "a. " or "A "
        r'^[-•*▪▫○●]\s',       # bullet points
        r'^[IVX]+\.?\s'        # Roman numerals
    ]
    return any(re.match(pattern, text) for pattern in patterns)

def is_short_line(line, thresholds):
    """짧은 줄인지 판단"""
    if 'width' in line:
        avg_width = thresholds.get('avg_line_width', 500)  # 기본값
        return line['width'] < avg_width * 0.7
    else:
        # 폭 정보가 없으면 텍스트 길이로 추정
        return len(line['text']) < 50
```

### 7.2 문단 조립
```python
def build_paragraphs(lines, paragraph_breaks):
    """줄들을 문단으로 조립"""
    paragraphs = []
    start = 0
    
    for break_point in paragraph_breaks:
        paragraph_lines = lines[start:break_point + 1]
        paragraph_text = '\n'.join([line['text'] for line in paragraph_lines])
        paragraphs.append(paragraph_text.strip())
        start = break_point + 1
    
    # 마지막 문단
    if start < len(lines):
        paragraph_lines = lines[start:]
        paragraph_text = '\n'.join([line['text'] for line in paragraph_lines])
        paragraphs.append(paragraph_text.strip())
    
    return [p for p in paragraphs if p]  # 빈 문단 제거
```

### 7.3 권장 사용법
```python
def process_ocr_data_with_smart_paragraphs(data, conservative_mode=True):
    """스마트 문단 구분 처리"""
    
    # 1. 적응적 임계값 계산
    thresholds, avg_font_height = calculate_font_aware_thresholds(data)
    
    # 2. 줄 정보 구조화
    lines = structure_lines_from_ocr_data(data, thresholds)
    
    # 3. 단계별 문단 구분
    if conservative_mode:
        # 보수적 모드: Tier 1만 적용
        breaks = detect_paragraph_breaks_progressive(lines, thresholds, 
                                                   apply_tier2=False, apply_tier3=False)
    else:
        # 적극적 모드: Tier 1+2 적용
        breaks = detect_paragraph_breaks_progressive(lines, thresholds, 
                                                   apply_tier2=True, apply_tier3=False)
    
    # 4. 문단 조립
    paragraphs = build_paragraphs(lines, breaks)
    
    # 5. 최종 텍스트 생성
    final_text = '\n\n'.join(paragraphs)
    
    logger.info(f"Generated {len(lines)} lines → {len(paragraphs)} paragraphs")
    logger.info(f"Paragraph breaks at positions: {breaks}")
    
    return final_text, calculate_confidence(data)
```

---

## 💡 권장 구현 순서

### Phase 1 (즉시 적용): Tier 1 규칙
- ✅ **큰 수직 간격**: `gap > font_height * 2.5`
- ✅ **섹션 헤더**: "Abstract", "Introduction" 등
- ✅ **번호 목록**: "1.", "(a)", "•" 등

### Phase 2 (테스트 후): Tier 2 규칙
- 🔄 **들여쓰기 변화**: 의도적 레이아웃 변화
- 🔄 **삼중 조건**: 짧은줄 + 마침표 + 대문자

### Phase 3 (신중하게): Tier 3 규칙
- ⚠️ **중간 간격 + 패턴**: 상황에 따라 적용
- ⚠️ **줄 길이 변화**: 사용자 설정 옵션으로

---

## 8. 테스트 및 검증 (Testing and Validation)

### 8.1 테스트 케이스
```python
test_cases = [
    {
        'name': '기본 문단 구분',
        'input': ['문장 하나.', '새로운 문단 시작.'],
        'expected_breaks': [0]
    },
    {
        'name': '학술 논문 섹션',
        'input': ['Abstract', '이 논문은...', 'Introduction', '배경 설명...'],
        'expected_breaks': [1, 2]
    },
    {
        'name': '목록 구조',
        'input': ['1. 첫 번째', '2. 두 번째', '3. 세 번째'],
        'expected_breaks': [0, 1]
    }
]
```

### 8.2 성능 지표
```python
def evaluate_paragraph_detection(predicted_breaks, actual_breaks):
    precision = len(set(predicted_breaks) & set(actual_breaks)) / len(predicted_breaks)
    recall = len(set(predicted_breaks) & set(actual_breaks)) / len(actual_breaks)
    f1_score = 2 * (precision * recall) / (precision + recall)
    
    return {'precision': precision, 'recall': recall, 'f1': f1_score}
```

---

## 9. 향후 개선 방향

1. **머신러닝 통합**: 규칙 기반 + ML 모델 하이브리드
2. **문서 유형별 특화**: 논문, 소설, 기술문서 등 유형별 규칙셋
3. **다국어 지원 확장**: 더 많은 언어의 특수 규칙
4. **사용자 피드백 학습**: 사용자 수정사항을 통한 규칙 개선
5. **실시간 조정**: UI를 통한 실시간 규칙 파라미터 조정

---

이 규칙들을 단계적으로 구현하여 더 정확한 문단 구분을 달성할 수 있습니다.