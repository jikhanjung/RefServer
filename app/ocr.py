import os
import logging
import tempfile
import shutil
import fitz  # PyMuPDF
from pdf2image import convert_from_path
import ocrmypdf
from pathlib import Path
import langdetect
from langdetect.lang_detect_exception import LangDetectException

logger = logging.getLogger(__name__)

# Language mapping for Tesseract
TESSERACT_LANG_MAP = {
    'en': 'eng',
    'ko': 'kor',
    'ja': 'jpn',
    'zh': 'chi_sim+chi_tra',
    'fr': 'fra',
    'de': 'deu',
    'es': 'spa',
    'it': 'ita',
    'ru': 'rus',
    'ar': 'ara'
}

# Priority languages for multi-language OCR sampling
# Ordered by global usage and OCR quality
PRIORITY_LANGUAGES = ['eng', 'kor', 'jpn', 'chi_sim', 'fra', 'deu', 'spa']

def extract_text_from_pdf(pdf_path):
    """
    Extract text from PDF using PyMuPDF
    
    Args:
        pdf_path: str, path to PDF file
    
    Returns:
        tuple: (text_content, page_count)
    """
    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            text_content += text + "\n"
        
        doc.close()
        
        logger.info(f"Extracted text from {page_count} pages")
        return text_content.strip(), page_count
        
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return "", 0

def extract_page_texts_from_pdf(pdf_path):
    """
    Extract text from PDF page by page using PyMuPDF
    
    Args:
        pdf_path: str, path to PDF file
    
    Returns:
        tuple: (page_texts, page_count) where page_texts is list of strings
    """
    try:
        doc = fitz.open(pdf_path)
        page_texts = []
        page_count = len(doc)
        
        for page_num in range(page_count):
            page = doc[page_num]
            text = page.get_text()
            page_texts.append(text.strip())
        
        doc.close()
        
        logger.info(f"Extracted page texts from {page_count} pages")
        return page_texts, page_count
        
    except Exception as e:
        logger.error(f"Error extracting page texts from PDF: {e}")
        return [], 0

def detect_language(text, min_confidence=0.7):
    """
    Detect language from text content
    
    Args:
        text: str, text content to analyze
        min_confidence: float, minimum confidence threshold
    
    Returns:
        str: detected language code (ISO 639-1) or 'en' as default
    """
    if not text or len(text.strip()) < 50:
        logger.warning("Text too short for reliable language detection, defaulting to English")
        return 'en'
    
    try:
        # Use first 1000 characters for detection (performance)
        sample_text = text[:1000].strip()
        
        detected_lang = langdetect.detect(sample_text)
        
        # Get confidence using detect_langs
        lang_probs = langdetect.detect_langs(sample_text)
        confidence = next((prob.prob for prob in lang_probs if prob.lang == detected_lang), 0)
        
        if confidence >= min_confidence:
            logger.info(f"Detected language: {detected_lang} (confidence: {confidence:.2f})")
            return detected_lang
        else:
            logger.warning(f"Low confidence language detection: {detected_lang} ({confidence:.2f}), defaulting to English")
            return 'en'
            
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}, defaulting to English")
        return 'en'
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}, defaulting to English")
        return 'en'

def get_tesseract_language(lang_code):
    """
    Convert ISO language code to Tesseract language parameter
    
    Args:
        lang_code: str, ISO 639-1 language code
    
    Returns:
        str: Tesseract language parameter
    """
    return TESSERACT_LANG_MAP.get(lang_code, 'eng')

def extract_sample_region_from_pdf(pdf_path, region_ratio=0.3):
    """
    Extract a sample region from first page for language detection OCR
    
    Args:
        pdf_path: str, path to PDF file
        region_ratio: float, ratio of page to extract (0.3 = top 30%)
    
    Returns:
        PIL.Image or None: Cropped image of sample region
    """
    try:
        from PIL import Image
        
        # Convert first page to image
        images = convert_from_path(
            pdf_path,
            first_page=1,
            last_page=1,
            dpi=200,  # Higher DPI for better OCR
            fmt='PNG'
        )
        
        if not images:
            logger.error("No images generated from PDF")
            return None
        
        image = images[0]
        width, height = image.size
        
        # Extract top region (where titles/headers usually are)
        crop_height = int(height * region_ratio)
        sample_region = image.crop((0, 0, width, crop_height))
        
        logger.debug(f"Extracted sample region: {width}x{crop_height} from {width}x{height}")
        return sample_region
        
    except Exception as e:
        logger.error(f"Error extracting sample region: {e}")
        return None

def ocr_sample_region(image, tesseract_lang):
    """
    Perform OCR on sample image region with specific language
    
    Args:
        image: PIL.Image, image to process
        tesseract_lang: str, Tesseract language code
    
    Returns:
        tuple: (extracted_text, confidence_score)
    """
    try:
        import pytesseract
        from PIL import Image
        import tempfile
        import os
        
        # Save image to temporary file
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            image.save(temp_file.name, 'PNG')
            temp_path = temp_file.name
        
        try:
            # Get text with confidence
            data = pytesseract.image_to_data(
                temp_path,
                lang=tesseract_lang,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and calculate average confidence
            words = []
            confidences = []
            
            for i, word in enumerate(data['text']):
                if word.strip():
                    words.append(word)
                    conf = data['conf'][i]
                    if conf > 0:  # Valid confidence
                        confidences.append(conf)
            
            extracted_text = ' '.join(words)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0
            
            logger.debug(f"OCR {tesseract_lang}: '{extracted_text[:50]}...' (conf: {avg_confidence:.1f})")
            return extracted_text, avg_confidence
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
                
    except ImportError:
        logger.error("pytesseract not available for direct OCR sampling")
        return "", 0
    except Exception as e:
        logger.error(f"Error in OCR sampling with {tesseract_lang}: {e}")
        return "", 0

def detect_language_from_multilang_ocr(pdf_path, max_languages=4):
    """
    Detect language by trying OCR with multiple languages on sample region
    
    Args:
        pdf_path: str, path to PDF file
        max_languages: int, maximum number of languages to try
    
    Returns:
        str: Best detected Tesseract language code
    """
    try:
        logger.info("Starting multi-language OCR sampling for language detection")
        
        # Extract sample region from first page
        sample_image = extract_sample_region_from_pdf(pdf_path)
        if not sample_image:
            logger.warning("Could not extract sample region, defaulting to English")
            return 'eng'
        
        # Try OCR with priority languages
        ocr_results = []
        languages_to_try = PRIORITY_LANGUAGES[:max_languages]
        
        for tesseract_lang in languages_to_try:
            logger.debug(f"Trying OCR with language: {tesseract_lang}")
            text, confidence = ocr_sample_region(sample_image, tesseract_lang)
            
            if text and confidence > 0:
                # Calculate language detection score
                lang_score = calculate_language_score(text, confidence, tesseract_lang)
                ocr_results.append({
                    'language': tesseract_lang,
                    'text': text,
                    'ocr_confidence': confidence,
                    'text_length': len(text.strip()),
                    'lang_score': lang_score
                })
                
                logger.debug(f"Result {tesseract_lang}: conf={confidence:.1f}, "
                           f"len={len(text)}, score={lang_score:.2f}")
        
        if not ocr_results:
            logger.warning("No successful OCR results, defaulting to English")
            return 'eng'
        
        # Sort by language score (higher is better)
        ocr_results.sort(key=lambda x: x['lang_score'], reverse=True)
        best_result = ocr_results[0]
        
        logger.info(f"Multi-language OCR detection: {best_result['language']} "
                   f"(score: {best_result['lang_score']:.2f}, "
                   f"confidence: {best_result['ocr_confidence']:.1f})")
        
        return best_result['language']
        
    except Exception as e:
        logger.error(f"Error in multi-language OCR detection: {e}")
        return 'eng'

def calculate_language_score(text, ocr_confidence, tesseract_lang):
    """
    Calculate composite score for language detection quality
    
    Args:
        text: str, OCR extracted text
        ocr_confidence: float, Tesseract confidence score
        tesseract_lang: str, Tesseract language code
    
    Returns:
        float: Composite language score (higher is better)
    """
    if not text or ocr_confidence <= 0:
        return 0.0
    
    # Base score from OCR confidence (0-100)
    confidence_score = ocr_confidence / 100.0
    
    # Text length bonus (more text = more reliable)
    text_length = len(text.strip())
    length_bonus = min(text_length / 100.0, 1.0)  # Cap at 1.0
    
    # Try language detection on OCR result
    try:
        detected_lang = langdetect.detect(text)
        lang_probs = langdetect.detect_langs(text)
        lang_confidence = next((prob.prob for prob in lang_probs if prob.lang == detected_lang), 0)
        
        # Language match bonus
        expected_iso_lang = {
            'eng': 'en', 'kor': 'ko', 'jpn': 'ja', 
            'chi_sim': 'zh', 'fra': 'fr', 'deu': 'de', 'spa': 'es'
        }.get(tesseract_lang, 'en')
        
        lang_match_bonus = 0.5 if detected_lang == expected_iso_lang else 0.0
        
        # Combine scores
        composite_score = (confidence_score * 0.4 + 
                          length_bonus * 0.3 + 
                          lang_confidence * 0.2 + 
                          lang_match_bonus)
        
        logger.debug(f"Score breakdown for {tesseract_lang}: "
                    f"conf={confidence_score:.2f}, len={length_bonus:.2f}, "
                    f"lang={lang_confidence:.2f}, match={lang_match_bonus:.2f} "
                    f"-> {composite_score:.2f}")
        
        return composite_score
        
    except Exception:
        # Fallback to simple scoring if language detection fails
        return confidence_score * 0.6 + length_bonus * 0.4

def detect_language_with_llava(pdf_path):
    """
    Detect language using LLaVA visual analysis (GPU environments only)
    
    Args:
        pdf_path: str, path to PDF file
    
    Returns:
        str: Detected Tesseract language code or None if failed
    """
    try:
        import requests
        import json
        import os
        
        # Check if LLaVA is available
        llava_url = os.getenv('LLAVA_URL', 'http://host.docker.internal:11434')
        
        # Extract first page image
        sample_image = extract_sample_region_from_pdf(pdf_path, region_ratio=0.5)  # Larger region for LLaVA
        if not sample_image:
            logger.warning("Could not extract image for LLaVA analysis")
            return None
        
        # Save image to temporary file for LLaVA
        import tempfile
        import base64
        import io
        
        # Convert image to base64
        img_buffer = io.BytesIO()
        sample_image.save(img_buffer, format='PNG')
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
        
        # Prepare LLaVA prompt
        prompt = """
        Analyze this document image and identify the primary language used in the text.
        Look at the characters, writing system, and text patterns.
        
        Respond with ONLY one of these language codes:
        - eng (for English)
        - kor (for Korean/Hangul)
        - jpn (for Japanese/Hiragana/Katakana/Kanji)
        - chi_sim (for Chinese Simplified/Traditional)
        - fra (for French)
        - deu (for German)
        - spa (for Spanish)
        - rus (for Russian/Cyrillic)
        - ara (for Arabic)
        
        If you cannot determine the language clearly, respond with 'eng'.
        """
        
        # Make request to LLaVA
        llava_request = {
            "model": "llava",
            "prompt": prompt,
            "images": [img_base64],
            "stream": False
        }
        
        logger.info("Requesting LLaVA visual language detection...")
        response = requests.post(
            f"{llava_url}/api/generate",
            json=llava_request,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            llava_response = result.get('response', '').strip().lower()
            
            # Extract language code from response
            detected_lang = None
            for lang_code in PRIORITY_LANGUAGES:
                if lang_code in llava_response:
                    detected_lang = lang_code
                    break
            
            if detected_lang:
                logger.info(f"LLaVA detected language: {detected_lang}")
                return detected_lang
            else:
                logger.warning(f"LLaVA response unclear: '{llava_response}', using fallback")
                return None
        else:
            logger.warning(f"LLaVA request failed: {response.status_code}")
            return None
            
    except Exception as e:
        logger.debug(f"LLaVA language detection not available: {e}")
        return None

def detect_language_hybrid(pdf_path):
    """
    Hybrid language detection: Text-based -> Multi-OCR -> LLaVA (if available)
    
    Args:
        pdf_path: str, path to PDF file
    
    Returns:
        str: Best detected Tesseract language code
    """
    logger.info("Starting hybrid language detection")
    
    # Step 1: Try text-based detection first (fastest)
    initial_text, _ = extract_text_from_pdf(pdf_path)
    if initial_text and len(initial_text.strip()) >= 50:
        detected_lang = detect_language(initial_text)
        tesseract_lang = get_tesseract_language(detected_lang)
        logger.info(f"Text-based detection successful: {tesseract_lang}")
        return tesseract_lang
    
    logger.info("No sufficient text found, trying visual methods")
    
    # Step 2: Try LLaVA visual detection (if GPU available)
    llava_lang = detect_language_with_llava(pdf_path)
    if llava_lang:
        logger.info(f"LLaVA visual detection successful: {llava_lang}")
        return llava_lang
    
    # Step 3: Fallback to multi-language OCR sampling
    logger.info("LLaVA not available, using multi-language OCR sampling")
    ocr_lang = detect_language_from_multilang_ocr(pdf_path)
    logger.info(f"Multi-language OCR detection result: {ocr_lang}")
    return ocr_lang

def check_pdf_needs_ocr(pdf_path, min_text_length=100):
    """
    Check if PDF needs OCR by analyzing existing text content
    
    Args:
        pdf_path: str, path to PDF file
        min_text_length: int, minimum text length to consider as having text
    
    Returns:
        bool: True if OCR is needed, False otherwise
    """
    try:
        text_content, _ = extract_text_from_pdf(pdf_path)
        
        # Remove whitespace and check length
        clean_text = ''.join(text_content.split())
        
        needs_ocr = len(clean_text) < min_text_length
        
        logger.info(f"PDF text analysis: {len(clean_text)} characters, OCR needed: {needs_ocr}")
        return needs_ocr
        
    except Exception as e:
        logger.error(f"Error checking PDF text content: {e}")
        # If we can't analyze, assume OCR is needed
        return True

def perform_ocr(input_pdf_path, output_pdf_path, language='eng', force_ocr=False):
    """
    Perform OCR on PDF using ocrmypdf
    
    Args:
        input_pdf_path: str, path to input PDF
        output_pdf_path: str, path to output OCR'd PDF
        language: str, Tesseract language parameter
        force_ocr: bool, force OCR even if text exists
    
    Returns:
        bool: True if OCR was successful, False otherwise
    """
    try:
        # Check if OCR is needed
        if not force_ocr and not check_pdf_needs_ocr(input_pdf_path):
            logger.info("PDF already contains sufficient text, skipping OCR")
            # Just copy the file
            shutil.copy2(input_pdf_path, output_pdf_path)
            return True
        
        logger.info(f"Starting OCR with language: {language}")
        
        # OCR parameters
        ocr_options = {
            'language': language,
            'output_type': 'pdf',
            'pdf_renderer': 'hocr',
            'optimize': 1,
            'jpeg_quality': 95,
            'png_quality': 95,
            'deskew': True,
            'clean': True,
            'clean_final': True,
            'unpaper_args': '--layout double --pre-rotate 90',
        }
        
        # Perform OCR
        ocrmypdf.ocr(
            input_pdf_path,
            output_pdf_path,
            **ocr_options
        )
        
        logger.info(f"OCR completed successfully: {output_pdf_path}")
        return True
        
    except ocrmypdf.exceptions.PriorOcrFoundError:
        logger.info("PDF already contains OCR text, copying original")
        shutil.copy2(input_pdf_path, output_pdf_path)
        return True
        
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        # If OCR fails, copy original file
        try:
            shutil.copy2(input_pdf_path, output_pdf_path)
            logger.info("Copied original PDF after OCR failure")
        except Exception as copy_error:
            logger.error(f"Failed to copy original PDF: {copy_error}")
        return False

def extract_first_page_image(pdf_path, output_path, dpi=150):
    """
    Extract first page as image for quality assessment
    
    Args:
        pdf_path: str, path to PDF file
        output_path: str, path to save image
        dpi: int, image resolution
    
    Returns:
        str: path to saved image or None if failed
    """
    try:
        # Convert first page to image
        images = convert_from_path(
            pdf_path,
            first_page=1,
            last_page=1,
            dpi=dpi,
            fmt='PNG'
        )
        
        if images:
            images[0].save(output_path, 'PNG')
            logger.info(f"First page image saved: {output_path}")
            return output_path
        else:
            logger.error("No images generated from PDF")
            return None
            
    except Exception as e:
        logger.error(f"Error extracting first page image: {e}")
        return None

def process_pdf_with_ocr(pdf_path, output_dir, doc_id):
    """
    Complete PDF OCR processing pipeline
    
    Args:
        pdf_path: str, path to input PDF
        output_dir: str, directory to save processed files
        doc_id: str, document ID for file naming
    
    Returns:
        dict: Processing results with paths and metadata
    """
    try:
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Define output paths
        ocr_pdf_path = os.path.join(output_dir, f"{doc_id}_ocr.pdf")
        first_page_image_path = os.path.join(output_dir, f"{doc_id}_page1.png")
        
        # Step 1: Extract initial text and get page count
        logger.info("Step 1: Extracting initial text")
        initial_text, page_count = extract_text_from_pdf(pdf_path)
        
        # Step 2: Hybrid language detection
        logger.info("Step 2: Hybrid language detection (Text -> LLaVA -> Multi-OCR)")
        tesseract_lang = detect_language_hybrid(pdf_path)
        
        # Step 3: Perform OCR if needed
        logger.info("Step 3: Performing OCR")
        ocr_success = perform_ocr(pdf_path, ocr_pdf_path, tesseract_lang)
        
        # Step 4: Extract final text from OCR'd PDF
        logger.info("Step 4: Extracting final text")
        if ocr_success and os.path.exists(ocr_pdf_path):
            final_text, _ = extract_text_from_pdf(ocr_pdf_path)
        else:
            final_text = initial_text
            ocr_pdf_path = pdf_path  # Use original if OCR failed
        
        # Step 5: Extract first page image
        logger.info("Step 5: Extracting first page image")
        image_path = extract_first_page_image(pdf_path, first_page_image_path)
        
        # Convert tesseract language back to ISO for metadata
        iso_lang = {v: k for k, v in TESSERACT_LANG_MAP.items()}.get(tesseract_lang, 'en')
        
        # Prepare results
        results = {
            'success': True,
            'ocr_pdf_path': ocr_pdf_path,
            'first_page_image_path': image_path,
            'extracted_text': final_text,
            'detected_language': iso_lang,
            'tesseract_language': tesseract_lang,
            'page_count': page_count,
            'ocr_performed': ocr_success and (ocr_pdf_path != pdf_path),
            'text_length': len(final_text),
            'language_detection_method': 'hybrid'  # New field for tracking method used
        }
        
        logger.info(f"PDF processing completed successfully for {doc_id}")
        logger.info(f"Language: {iso_lang} ({tesseract_lang}), Pages: {page_count}, Text length: {len(final_text)}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in PDF OCR processing: {e}")
        return {
            'success': False,
            'error': str(e),
            'ocr_pdf_path': None,
            'first_page_image_path': None,
            'extracted_text': '',
            'detected_language': 'en',
            'tesseract_language': 'eng',
            'page_count': 0,
            'ocr_performed': False,
            'text_length': 0
        }