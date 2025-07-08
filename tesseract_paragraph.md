
# Tesseract OCR 문단 구분 문제와 해결 방법

## 🔍 Tesseract 기본 동작 특성

- **라인 단위(line-level)로 텍스트를 추출**합니다.
- 문단 구분 없이 연속된 줄로 결과가 나오는 경우가 많습니다.
- 줄 바꿈은 포함하지만, **문단 간 공백 줄(paragraph break)** 은 감지되지 않습니다.
- `tesseract image.png stdout` 과 같은 기본 명령어는 별도의 레이아웃 분석 없이 OCR만 수행합니다.

---

## ✅ 해결 방법 (문단 구분이 필요한 경우)

### 1. `--psm` 옵션 조정
Tesseract에는 페이지 세그멘테이션 모드(PSM)가 있습니다.
- 기본값은 `--psm 3` (자동 페이지 분석)
- 문단 추출이 필요한 경우 `--psm 1` 또는 `--psm 4`를 시도해보세요.

```bash
tesseract input.png output.txt --psm 1
```

### 2. 레이아웃 인식 + 후처리 조합
문단 감지를 정확히 하려면 다음과 같은 조합을 사용하는 것이 효과적입니다:
- **Tesseract로 텍스트 추출**
- **PDFMiner, PyMuPDF 등으로 레이아웃 좌표를 분석**
- **줄 간 간격 또는 블록 좌표를 기반으로 문단 구분 추가 후처리**

### 3. OCR Layout 도구 사용
- [`OCRmyPDF`](https://github.com/ocrmypdf/OCRmyPDF)는 PDF 내부의 레이아웃을 보존하면서 Tesseract 기반으로 OCR합니다.
- [`Huridocs`의 `pdf-document-layout-analysis`](https://github.com/huridocs/pdf-document-layout-analysis) 등과 같이 **레이아웃 분석 전용 툴**을 병행하면 문단 감지가 용이합니다.

---

## 🔧 예시: 간단한 문단 나눔 후처리 (Python)

```python
def insert_paragraph_breaks(lines, threshold=15):
    paragraph = []
    paragraphs = []
    prev_y = None
    for line, y in lines:
        if prev_y is not None and abs(y - prev_y) > threshold:
            paragraphs.append("\n".join(paragraph))
            paragraph = []
        paragraph.append(line)
        prev_y = y
    if paragraph:
        paragraphs.append("\n".join(paragraph))
    return "\n\n".join(paragraphs)
```

---

## 결론

- **Tesseract는 원래 문단 단위까지는 잘 인식하지 않도록 설계되어 있습니다.**
- 문단 구분이 필요하다면 **PSM 조정 + 후처리 + 레이아웃 분석 도구 병행**이 필요합니다.

