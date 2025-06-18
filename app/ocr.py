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
        
        # Step 1: Extract text to detect language
        logger.info("Step 1: Extracting text for language detection")
        initial_text, page_count = extract_text_from_pdf(pdf_path)
        
        # Step 2: Detect language
        logger.info("Step 2: Detecting document language")
        detected_lang = detect_language(initial_text)
        tesseract_lang = get_tesseract_language(detected_lang)
        
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
        
        # Prepare results
        results = {
            'success': True,
            'ocr_pdf_path': ocr_pdf_path,
            'first_page_image_path': image_path,
            'extracted_text': final_text,
            'detected_language': detected_lang,
            'tesseract_language': tesseract_lang,
            'page_count': page_count,
            'ocr_performed': ocr_success and (ocr_pdf_path != pdf_path),
            'text_length': len(final_text)
        }
        
        logger.info(f"PDF processing completed successfully for {doc_id}")
        logger.info(f"Language: {detected_lang}, Pages: {page_count}, Text length: {len(final_text)}")
        
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