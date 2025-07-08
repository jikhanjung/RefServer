# Tesseract OCR 문단 구분 방식 비교

## 개요
RefServer에서 Tesseract OCR을 사용한 PDF 텍스트 추출 시 적용되는 문단 구분 방식에 대한 문서입니다.

## 기본 설정
- **PSM 모드**: 4 (단일 컬럼 + 문단 감지)
- **OCR 엔진**: 3 (기본 LSTM OCR 엔진)
- **해상도**: 300 DPI
- **좌표 기반 분석**: `pytesseract.image_to_data()` 사용

---

## 방식 1: 고정 임계값 방식 (Fixed Threshold)

### 설정값
```python
line_threshold = 20        # 줄바꿈 감지 (픽셀)
paragraph_threshold = 60   # 문단 구분 (픽셀)
```

### 동작 방식
1. **줄 감지**: Y좌표 차이가 20픽셀 이상이면 새로운 줄로 인식
2. **문단 구분**: Y좌표 차이가 60픽셀 이상이면 새로운 문단으로 인식
3. **스마트 섹션 인식**:
   - "Abstract", "Resumen", "Kurzfassung" 등 학술 논문 섹션 제목 감지
   - 50자 미만의 짧은 줄에서만 섹션 구분 적용
   - 35-60픽셀 사이의 중간 간격에서 섹션 제목일 때만 문단 구분

### 장점
- 설정이 단순하고 예측 가능
- 대부분의 표준 학술 논문에서 일관된 결과
- 디버깅 및 조정이 용이

### 단점
- PDF마다 폰트 크기, 줄 간격이 다를 때 부적절한 결과 가능
- 스캔 해상도에 민감
- 특수 레이아웃(2컬럼, 표, 그림 등)에서 오작동 가능

---

## 방식 2: 적응적 임계값 방식 (Adaptive Threshold)

### 설정값 (자동 계산)
```python
avg_height = 평균_문자_높이()
line_threshold = avg_height * 0.5      # 평균 문자 높이의 50%
paragraph_threshold = avg_height * 2.0  # 평균 문자 높이의 200%
```

### 동작 방식
1. **문자 높이 분석**:
   ```python
   # 각 텍스트 요소의 높이를 수집
   for i in range(len(data['text'])):
       if data['text'][i].strip() and data['conf'][i] > 0:
           heights.append(data['height'][i])
   
   avg_height = sum(heights) / len(heights)
   ```

2. **적응적 임계값 계산**:
   - **줄바꿈**: `avg_height * 0.5` (문자 높이의 절반)
   - **문단구분**: `avg_height * 2.0` (문자 높이의 2배)

3. **스마트 섹션 인식** (개선됨):
   - 중간 간격 기준: `paragraph_threshold * 0.6` (적응적)
   - 동일한 섹션 제목 감지 로직 적용

### 장점
- PDF마다 자동으로 최적 임계값 계산
- 폰트 크기, 스캔 해상도에 자동 적응
- 다양한 문서 형식에서 일관된 품질
- 로그로 계산된 임계값 확인 가능

### 단점
- 로직이 복잡하여 디버깅 어려울 수 있음
- 특이한 폰트나 레이아웃에서 예상치 못한 결과 가능
- 계산 오버헤드 약간 증가

---

## 코드 구현

### 공통 함수
```python
def perform_page_ocr_with_tesseract(pdf_path, page_number, language='eng', psm_mode=4):
    # PDF를 300 DPI 이미지로 변환
    images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number, dpi=300)
    
    # Tesseract 설정
    custom_config = f'--psm {psm_mode} --oem 3'
    
    # 좌표 정보와 함께 OCR 수행
    data = pytesseract.image_to_data(image, lang=language, config=custom_config, output_type=pytesseract.Output.DICT)
    
    # 문단 구분 처리
    extracted_text, avg_confidence = process_ocr_data_with_paragraphs(data)
    
    return extracted_text, avg_confidence
```

### 방식 1: 고정 임계값
```python
def process_ocr_data_with_paragraphs(data, line_threshold=20, paragraph_threshold=60):
    # 고정된 픽셀 값으로 줄/문단 구분
    # ... (기존 로직)
```

### 방식 2: 적응적 임계값
```python
def process_ocr_data_with_paragraphs(data, line_threshold=None, paragraph_threshold=None):
    # 문자 높이 통계 계산
    heights = [data['height'][i] for i in range(len(data['text'])) 
               if data['text'][i].strip() and data['conf'][i] > 0]
    
    if heights:
        avg_height = sum(heights) / len(heights)
        actual_line_threshold = line_threshold or (avg_height * 0.5)
        actual_paragraph_threshold = paragraph_threshold or (avg_height * 2.0)
    else:
        # 폴백 값
        actual_line_threshold = line_threshold or 20
        actual_paragraph_threshold = paragraph_threshold or 60
    
    # 계산된 임계값으로 줄/문단 구분
    # ... (동일한 구분 로직)
```

---

## 테스트 및 로그

### 로그 확인 방법
```bash
# Docker 로그에서 확인
docker logs refserver | grep "Adaptive thresholds"

# 예시 출력
# Adaptive thresholds: line=12.3, paragraph=24.6 (avg_height=24.6)
# Generated 15 lines, 4 paragraphs
```

### 비교 테스트 방법
1. **Page Viewer**에서 "Re-OCR with Tesseract" 실행
2. **OCR Results Comparison** 모달에서 결과 확인
3. 기존 텍스트와 새 OCR 텍스트의 문단 구분 비교
4. Docker 로그에서 계산된 임계값 확인

---

## 사용 권장사항

### 방식 1 (고정 임계값) 권장 상황
- 표준화된 학술 논문 처리
- 일관된 스캔 품질과 레이아웃
- 디버깅 및 미세 조정이 필요한 경우
- 성능이 중요한 대량 처리

### 방식 2 (적응적 임계값) 권장 상황
- 다양한 출처의 PDF 처리
- 폰트 크기나 스캔 품질이 일정하지 않은 경우
- 자동화된 배치 처리
- 최적의 문단 구분 품질이 필요한 경우

---

## 향후 개선 방향

1. **머신러닝 기반 문단 구분**
   - 텍스트 블록의 의미적 연관성 분석
   - 문서 구조 인식 모델 적용

2. **레이아웃 분석 연동**
   - Huridocs layout analysis 결과와 조합
   - 컬럼, 표, 그림 영역 고려

3. **사용자 설정 옵션**
   - 문단 구분 민감도 조절 UI
   - 문서 유형별 프리셋 제공

4. **성능 최적화**
   - 캐싱을 통한 반복 계산 방지
   - 병렬 처리 지원