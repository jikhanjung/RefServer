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
from datetime import datetime

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
            # Use blocks to preserve better line structure
            blocks = page.get_text("blocks")
            page_text = ""
            for block in blocks:
                # Block format: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(block) > 4 and isinstance(block[4], str):
                    page_text += block[4] + "\n"
            text_content += page_text + "\n"
        
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
            # Use blocks to preserve better line structure
            blocks = page.get_text("blocks")
            page_text = ""
            for block in blocks:
                # Block format: (x0, y0, x1, y1, "text", block_no, block_type)
                if len(block) > 4 and isinstance(block[4], str):
                    page_text += block[4] + "\n"
            page_texts.append(page_text.strip())
        
        doc.close()
        
        logger.info(f"Extracted page texts from {page_count} pages")
        return page_texts, page_count
        
    except Exception as e:
        logger.error(f"Error extracting page texts from PDF: {e}")
        return [], 0


def extract_page_text_with_formatting(pdf_path, page_number=1):
    """
    Extract text from a specific page with font size information
    
    Args:
        pdf_path: str, path to PDF file
        page_number: int, page number (1-indexed)
    
    Returns:
        str: formatted text with font size markers
    """
    try:
        doc = fitz.open(pdf_path)
        if page_number < 1 or page_number > len(doc):
            logger.error(f"Invalid page number {page_number}")
            return ""
            
        page = doc[page_number - 1]  # Convert to 0-indexed
        
        # Extract text with detailed formatting
        text_dict = page.get_text("dict")
        
        formatted_text = ""
        previous_font_size = None
        
        # Process blocks
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_text = ""
                    line_font_sizes = []
                    
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        font_size = round(span.get("size", 0))
                        font_name = span.get("font", "")
                        flags = span.get("flags", 0)
                        
                        # Check if bold (flag bit 16)
                        is_bold = bool(flags & 2**16)
                        
                        if text.strip():
                            line_text += text
                            line_font_sizes.append(font_size)
                    
                    if line_text.strip():
                        # Calculate average font size for the line
                        avg_font_size = sum(line_font_sizes) / len(line_font_sizes) if line_font_sizes else 0
                        avg_font_size = round(avg_font_size)
                        
                        # Add font size marker if it changed significantly
                        if previous_font_size is None or abs(avg_font_size - previous_font_size) > 2:
                            formatted_text += f"\n[FONT_SIZE:{avg_font_size}]\n"
                            previous_font_size = avg_font_size
                        
                        formatted_text += line_text.strip() + "\n"
        
        doc.close()
        
        logger.info(f"Extracted formatted text from page {page_number}")
        return formatted_text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting formatted text from PDF: {e}")
        return ""


def extract_first_pages_with_formatting(pdf_path, num_pages=2):
    """
    Extract text from first N pages with font size information for metadata extraction
    
    Args:
        pdf_path: str, path to PDF file
        num_pages: int, number of pages to extract (default: 2)
    
    Returns:
        str: combined formatted text from first pages
    """
    try:
        combined_text = ""
        
        for page_num in range(1, num_pages + 1):
            page_text = extract_page_text_with_formatting(pdf_path, page_num)
            if page_text:
                combined_text += f"\n[PAGE {page_num}]\n{page_text}\n"
            else:
                break  # Stop if we can't extract a page
        
        return combined_text.strip()
        
    except Exception as e:
        logger.error(f"Error extracting formatted pages: {e}")
        return ""

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
            'unpaper_args': '--layout double',
            'tesseract_config': ['-c', 'tessedit_pageseg_mode=4'],  # Single column with paragraphs
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

def regenerate_pdf_text_layer(input_pdf_path, output_pdf_path, language='eng', backup_original=True):
    """
    Regenerate PDF text layer using ocrmypdf with force OCR
    
    Args:
        input_pdf_path: str, path to input PDF
        output_pdf_path: str, path to output PDF with new text layer
        language: str, Tesseract language parameter
        backup_original: bool, whether to backup original PDF
    
    Returns:
        dict: Processing results with success status and details
    """
    try:
        import shutil
        
        # Backup original if requested
        backup_path = None
        if backup_original:
            backup_path = f"{input_pdf_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(input_pdf_path, backup_path)
            logger.info(f"Original PDF backed up to: {backup_path}")
        
        logger.info(f"Regenerating PDF text layer with language: {language}")
        
        # OCR parameters for text layer regeneration
        ocr_options = {
            'language': language,
            'output_type': 'pdf',
            'pdf_renderer': 'hocr',
            'force_ocr': True,  # Force OCR even if text already exists
            'optimize': 1,
            'jpeg_quality': 95,
            'png_quality': 95,
            'deskew': True,
            'clean': False,
            'clean_final': False,
            'remove_background': False,  # Preserve original appearance
            'rotate_pages': True,
            'skip_text': False,  # Include text layer
            'tesseract_config': ['-c', 'tessedit_pageseg_mode=4']  # Single column with paragraphs
        }
        
        # Perform OCR with text layer regeneration
        ocrmypdf.ocr(
            input_pdf_path,
            output_pdf_path,
            **ocr_options
        )
        
        logger.info(f"PDF text layer regenerated successfully: {output_pdf_path}")
        
        return {
            'success': True,
            'output_path': output_pdf_path,
            'backup_path': backup_path,
            'language': language,
            'message': 'PDF text layer regenerated successfully'
        }
        
    except ocrmypdf.exceptions.ExitCodeException as e:
        logger.error(f"ocrmypdf failed with exit code: {e}")
        return {
            'success': False,
            'error': f"OCR processing failed: {str(e)}",
            'backup_path': backup_path
        }
        
    except Exception as e:
        logger.error(f"PDF text layer regeneration failed: {e}")
        return {
            'success': False,
            'error': str(e),
            'backup_path': backup_path
        }

def perform_page_ocr_with_tesseract(pdf_path, page_number, language='eng', psm_mode=4):
    """
    Perform OCR on a specific page using Tesseract with paragraph detection
    
    Args:
        pdf_path: str, path to PDF file
        page_number: int, page number (1-based)
        language: str, Tesseract language parameter
        psm_mode: int, Page Segmentation Mode (4 = single column with paragraphs)
    
    Returns:
        tuple: (extracted_text, confidence_score)
    """
    try:
        import pytesseract
        from PIL import Image
        
        # Convert specific page to image
        images = convert_from_path(
            pdf_path,
            first_page=page_number,
            last_page=page_number,
            dpi=300,  # High DPI for better OCR
            fmt='PNG'
        )
        
        if not images:
            logger.error(f"No images generated for page {page_number}")
            return "", 0
        
        image = images[0]
        
        # Configure Tesseract with PSM for better paragraph detection
        custom_config = f'--psm {psm_mode} --oem 3'
        
        # Get text with detailed data including coordinates
        data = pytesseract.image_to_data(
            image,
            lang=language,
            config=custom_config,
            output_type=pytesseract.Output.DICT
        )
        
        # Process text with paragraph detection
        extracted_text, avg_confidence = process_ocr_data_with_paragraphs(data)
        
        logger.info(f"Tesseract OCR page {page_number}: {len(extracted_text)} chars, confidence: {avg_confidence:.1f}")
        return extracted_text, avg_confidence
        
    except ImportError:
        logger.error("pytesseract not available for page OCR")
        return "", 0
    except Exception as e:
        logger.error(f"Error in page OCR with Tesseract: {e}")
        return "", 0


def process_ocr_data_with_paragraphs(data, line_threshold=None, paragraph_threshold=None, conservative_mode=False):
    """
    Process Tesseract OCR data with progressive paragraph detection rules
    
    Args:
        data: dict, Tesseract output from image_to_data
        line_threshold: int, vertical distance to consider new line (optional)
        paragraph_threshold: int, vertical distance to consider new paragraph (optional)
        conservative_mode: bool, if True only apply Tier 1 rules, if False apply Tier 1+2
    
    Returns:
        tuple: (formatted_text, average_confidence)
    """
    try:
        mode_text = "Tier 1 only" if conservative_mode else "Tier 1+2"
        logger.debug(f"Processing OCR data with {len(data['text'])} text elements using {mode_text} rules")
        
        # Calculate font-aware adaptive thresholds
        thresholds, avg_font_height = calculate_font_aware_thresholds(data)
        
        # Override with user-provided values if specified
        if line_threshold:
            thresholds['line_gap'] = line_threshold
        if paragraph_threshold:
            thresholds['large_para_gap'] = paragraph_threshold
        
        logger.debug(f"Font-aware thresholds: line_gap={thresholds['line_gap']:.1f}, large_para_gap={thresholds['large_para_gap']:.1f}, avg_font_height={avg_font_height:.1f}")
        
        # Structure lines from OCR data
        lines = structure_lines_from_ocr_data(data, thresholds)
        logger.debug(f"Structured {len(lines)} lines from OCR data")
        
        # Apply progressive paragraph detection rules
        paragraph_breaks = detect_paragraph_breaks_progressive(lines, thresholds, apply_tier2=not conservative_mode)
        
        # Build paragraphs
        paragraphs = build_paragraphs(lines, paragraph_breaks)
        logger.debug(f"Built {len(paragraphs)} paragraphs")
        
        # Join paragraphs with double newlines
        formatted_text = '\n\n'.join(paragraphs)
        
        # Calculate average confidence
        confidences = [data['conf'][i] for i in range(len(data['text'])) 
                      if data['text'][i].strip() and data['conf'][i] > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        logger.info(f"Generated {len(lines)} lines → {len(paragraphs)} paragraphs ({mode_text} rules)")
        if paragraph_breaks:
            logger.info(f"Paragraph breaks applied at line positions: {paragraph_breaks}")
        
        return formatted_text, avg_confidence
        
    except Exception as e:
        logger.error(f"Error processing OCR data with Tier 1 rules: {e}")
        # Fallback to simple word joining
        try:
            words = []
            for i in range(len(data['text'])):
                word = data['text'][i].strip()
                if word:
                    words.append(word)
            return ' '.join(words), 0
        except:
            return "", 0


def calculate_font_aware_thresholds(data):
    """
    Calculate font-aware adaptive thresholds based on OCR character statistics
    
    Args:
        data: dict, Tesseract output from image_to_data
    
    Returns:
        tuple: (thresholds_dict, avg_font_height)
    """
    try:
        # 1. Collect character heights and confidences (improved filtering)
        heights = []
        confidences = []
        
        for i in range(len(data['text'])):
            if data['text'][i].strip() and data['conf'][i] > 50:  # Only high-confidence text
                heights.append(data['height'][i])
                confidences.append(data['conf'][i])
        
        if not heights:
            # Fallback to default values
            logger.warning("No valid character heights found, using fallback thresholds")
            return {
                'tiny_gap': 6, 'line_gap': 16, 'small_para_gap': 30,
                'medium_para_gap': 40, 'large_para_gap': 60, 'section_gap': 80,
                'avg_char_width': 12, 'avg_font_height': 20
            }, 20
        
        # 2. Calculate weighted average (confidence-based)
        weighted_heights = [h * c for h, c in zip(heights, confidences)]
        avg_font_height = sum(weighted_heights) / sum(confidences)
        
        # 3. Remove outliers (beyond 2 standard deviations)
        import numpy as np
        height_std = np.std(heights)
        filtered_heights = [h for h in heights if abs(h - avg_font_height) < 2 * height_std]
        avg_font_height = np.mean(filtered_heights) if filtered_heights else avg_font_height
        
        # 4. Calculate hierarchical thresholds
        thresholds = {
            'tiny_gap': avg_font_height * 0.3,      # Word spacing
            'line_gap': avg_font_height * 0.8,      # Normal line break
            'small_para_gap': avg_font_height * 1.5, # Weak paragraph break
            'medium_para_gap': avg_font_height * 2.0, # Medium paragraph break
            'large_para_gap': avg_font_height * 2.5,  # Strong paragraph break (Tier 1)
            'section_gap': avg_font_height * 4.0,    # Section break
            'avg_char_width': avg_font_height * 0.6,  # Estimated character width
            'avg_font_height': avg_font_height        # Reference font height
        }
        
        logger.debug(f"Font analysis: avg_height={avg_font_height:.1f}, samples={len(filtered_heights)}")
        
        return thresholds, avg_font_height
        
    except Exception as e:
        logger.error(f"Error calculating font-aware thresholds: {e}")
        # Return safe defaults
        return {
            'tiny_gap': 6, 'line_gap': 16, 'small_para_gap': 30,
            'medium_para_gap': 40, 'large_para_gap': 60, 'section_gap': 80,
            'avg_char_width': 12, 'avg_font_height': 20
        }, 20


def structure_lines_from_ocr_data(data, thresholds):
    """
    Structure OCR data into lines with position information
    
    Args:
        data: dict, Tesseract output from image_to_data
        thresholds: dict, calculated thresholds
    
    Returns:
        list: List of line dictionaries with text, y, x, width info
    """
    lines = []
    current_line = []
    current_y = None
    current_x_start = None
    current_x_end = None
    
    for i in range(len(data['text'])):
        word = data['text'][i].strip()
        if not word:
            continue
            
        x = data['left'][i]
        y = data['top'][i]
        width = data['width'][i]
        height = data['height'][i]
        
        # Detect line breaks based on Y coordinate
        if current_y is None:
            current_y = y
            current_x_start = x
            current_x_end = x + width
        elif abs(y - current_y) > thresholds['line_gap']:
            # New line detected
            if current_line:
                lines.append({
                    'text': ' '.join(current_line),
                    'y': current_y,
                    'x': current_x_start,
                    'width': current_x_end - current_x_start
                })
            current_line = [word]
            current_y = y
            current_x_start = x
            current_x_end = x + width
        else:
            current_line.append(word)
            current_x_end = max(current_x_end, x + width)
    
    # Add last line
    if current_line:
        lines.append({
            'text': ' '.join(current_line),
            'y': current_y,
            'x': current_x_start,
            'width': current_x_end - current_x_start
        })
    
    return lines


def is_section_header(text):
    """
    Detect academic paper section headers
    
    Args:
        text: str, text to check
    
    Returns:
        bool: True if text appears to be a section header
    """
    section_keywords = [
        'abstract', 'introduction', 'method', 'methods', 'result', 'results',
        'discussion', 'conclusion', 'conclusions', 'references', 'bibliography',
        'resumen', 'kurzfassung', 'zusammenfassung', 'keywords', 'acknowledgments'
    ]
    text_lower = text.lower().strip()
    return any(keyword in text_lower for keyword in section_keywords)


def starts_with_number_or_bullet(text):
    """
    Check if text starts with numbering or bullet point
    
    Args:
        text: str, text to check
    
    Returns:
        bool: True if text starts with number/bullet
    """
    import re
    patterns = [
        r'^\d+\.?\s',           # "1. " or "1 "
        r'^\(\d+\)',           # "(1)"
        r'^[a-zA-Z]\.?\s',     # "a. " or "A "
        r'^[-•*▪▫○●]\s',       # bullet points
        r'^[IVX]+\.?\s'        # Roman numerals "I.", "II."
    ]
    return any(re.match(pattern, text) for pattern in patterns)


def apply_tier1_rules(lines, thresholds):
    """
    Apply Tier 1 paragraph detection rules (95%+ confidence)
    
    Args:
        lines: list, structured line data
        thresholds: dict, calculated thresholds
    
    Returns:
        list: Indices where paragraph breaks should occur
    """
    breaks = []
    
    for i in range(len(lines) - 1):
        current_line = lines[i]
        next_line = lines[i + 1]
        gap = next_line['y'] - current_line['y']
        
        # Rule 1: Large vertical gap (absolute certainty)
        if gap > thresholds['large_para_gap']:
            breaks.append(i)
            logger.debug(f"Tier 1 Rule 1 (large gap): break at line {i} (gap={gap:.1f})")
            continue
            
        # Rule 2: Section headers (100% certainty)
        if is_section_header(current_line['text']) or is_section_header(next_line['text']):
            breaks.append(i)
            logger.debug(f"Tier 1 Rule 2 (section header): break at line {i}")
            continue
            
        # Rule 3: Numbered/bulleted lists (100% certainty)
        if starts_with_number_or_bullet(next_line['text']):
            breaks.append(i)
            logger.debug(f"Tier 1 Rule 3 (numbered list): break at line {i}")
            continue
    
    return breaks


def apply_tier2_rules(lines, thresholds, existing_breaks):
    """
    Apply Tier 2 paragraph detection rules (80-90% confidence)
    
    Args:
        lines: list, structured line data
        thresholds: dict, calculated thresholds
        existing_breaks: set, already identified break points
    
    Returns:
        list: Additional indices where paragraph breaks should occur
    """
    additional_breaks = []
    
    for i in range(len(lines) - 1):
        if i in existing_breaks:  # Skip already identified breaks
            continue
            
        current_line = lines[i]
        next_line = lines[i + 1]
        gap = next_line['y'] - current_line['y']
        
        # Rule 4: Indentation change (high confidence)
        indent_change = abs(current_line['x'] - next_line['x'])
        if (gap > thresholds['line_gap'] and 
            indent_change > thresholds['avg_char_width'] * 3):
            additional_breaks.append(i)
            logger.debug(f"Tier 2 Rule 4 (indentation): break at line {i} (gap={gap:.1f}, indent_change={indent_change:.1f})")
            continue
            
        # Rule 5: Triple condition (short line + period + capital start)
        if (gap > thresholds['small_para_gap'] and
            is_short_line(current_line, thresholds) and
            current_line['text'].rstrip().endswith('.') and
            next_line['text'] and len(next_line['text']) > 0 and next_line['text'][0].isupper()):
            additional_breaks.append(i)
            logger.debug(f"Tier 2 Rule 5 (triple condition): break at line {i}")
            continue
    
    return additional_breaks


def is_short_line(line, thresholds):
    """
    Determine if a line is considered short
    
    Args:
        line: dict, line data with text and width info
        thresholds: dict, calculated thresholds
    
    Returns:
        bool: True if line is considered short
    """
    # Method 1: Use width if available
    if 'width' in line and line['width'] > 0:
        # Estimate average line width from font height
        estimated_avg_width = thresholds['avg_font_height'] * 25  # Rough estimate: 25 chars per line
        return line['width'] < estimated_avg_width * 0.7
    
    # Method 2: Use text length as fallback
    text_length = len(line['text'])
    return text_length < 50  # Less than 50 characters is considered short


def detect_paragraph_breaks_progressive(lines, thresholds, apply_tier2=True):
    """
    Apply paragraph detection rules progressively by tier
    
    Args:
        lines: list, structured line data
        thresholds: dict, calculated thresholds
        apply_tier2: bool, whether to apply Tier 2 rules
    
    Returns:
        list: All paragraph break indices sorted
    """
    # Phase 1: Apply Tier 1 rules (highest confidence)
    tier1_breaks = apply_tier1_rules(lines, thresholds)
    logger.debug(f"Tier 1 found {len(tier1_breaks)} breaks: {tier1_breaks}")
    
    all_breaks = set(tier1_breaks)
    
    # Phase 2: Apply Tier 2 rules if enabled
    if apply_tier2:
        tier2_breaks = apply_tier2_rules(lines, thresholds, all_breaks)
        all_breaks.update(tier2_breaks)
        logger.debug(f"Tier 2 found {len(tier2_breaks)} additional breaks: {tier2_breaks}")
        logger.info(f"Total breaks: Tier 1 ({len(tier1_breaks)}) + Tier 2 ({len(tier2_breaks)}) = {len(all_breaks)}")
    else:
        logger.info(f"Only Tier 1 applied: {len(tier1_breaks)} breaks found")
    
    return sorted(list(all_breaks))


def build_paragraphs(lines, paragraph_breaks):
    """
    Assemble lines into paragraphs based on break points
    
    Args:
        lines: list, structured line data
        paragraph_breaks: list, indices where paragraphs should break
    
    Returns:
        list: List of paragraph texts
    """
    paragraphs = []
    start = 0
    
    for break_point in paragraph_breaks:
        paragraph_lines = lines[start:break_point + 1]
        paragraph_text = '\n'.join([line['text'] for line in paragraph_lines])
        if paragraph_text.strip():
            paragraphs.append(paragraph_text.strip())
        start = break_point + 1
    
    # Add last paragraph
    if start < len(lines):
        paragraph_lines = lines[start:]
        paragraph_text = '\n'.join([line['text'] for line in paragraph_lines])
        if paragraph_text.strip():
            paragraphs.append(paragraph_text.strip())
    
    return paragraphs

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