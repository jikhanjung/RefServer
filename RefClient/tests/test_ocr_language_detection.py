#!/usr/bin/env python3
"""
Test script for enhanced OCR language detection
Tests the new hybrid language detection system (Text -> LLaVA -> Multi-OCR)
"""

import os
import sys
import tempfile
import logging
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from ocr import (
    detect_language_hybrid,
    detect_language_from_multilang_ocr, 
    detect_language_with_llava,
    detect_language,
    extract_text_from_pdf,
    TESSERACT_LANG_MAP,
    PRIORITY_LANGUAGES
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_pdf_with_text(text, filename):
    """
    Create a test PDF with given text for testing
    """
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import tempfile
        
        # Create temporary PDF
        temp_pdf = os.path.join(tempfile.gettempdir(), filename)
        
        c = canvas.Canvas(temp_pdf, pagesize=letter)
        
        # Try to use system fonts for different languages
        try:
            # For Korean text
            if any(ord(char) >= 0xAC00 and ord(char) <= 0xD7A3 for char in text):
                # Korean Hangul range
                c.setFont("Helvetica", 12)  # Fallback font
            else:
                c.setFont("Helvetica", 12)
        except:
            c.setFont("Helvetica", 12)
        
        # Add text to PDF
        y_position = 750
        for line in text.split('\n'):
            if line.strip():
                c.drawString(100, y_position, line)
                y_position -= 20
        
        c.save()
        logger.info(f"Created test PDF: {temp_pdf}")
        return temp_pdf
        
    except ImportError:
        logger.error("reportlab not available, cannot create test PDFs")
        return None
    except Exception as e:
        logger.error(f"Error creating test PDF: {e}")
        return None

def test_language_detection_methods():
    """
    Test different language detection methods
    """
    logger.info("=== Testing Language Detection Methods ===")
    
    # Test texts in different languages
    test_cases = [
        {
            'language': 'English',
            'expected': 'eng',
            'text': """
            Introduction to Machine Learning
            Machine learning is a subset of artificial intelligence that enables computers 
            to learn and make decisions without being explicitly programmed. This paper 
            reviews the fundamental concepts and applications of machine learning algorithms.
            """
        },
        {
            'language': 'Korean',
            'expected': 'kor', 
            'text': """
            기계학습 소개
            기계학습은 인공지능의 하위 분야로, 컴퓨터가 명시적으로 프로그래밍되지 
            않고도 학습하고 결정을 내릴 수 있게 하는 기술입니다. 이 논문은 기계학습 
            알고리즘의 기본 개념과 응용을 검토합니다.
            """
        },
        {
            'language': 'Japanese',
            'expected': 'jpn',
            'text': """
            機械学習の紹介
            機械学習は人工知能のサブセットであり、明示的にプログラムされることなく
            コンピュータが学習し決定を下すことを可能にします。この論文では機械学習
            アルゴリズムの基本概念とアプリケーションをレビューします。
            """
        },
        {
            'language': 'Chinese',
            'expected': 'chi_sim',
            'text': """
            机器学习简介
            机器学习是人工智能的子集，它使计算机能够在不被明确编程的情况下学习
            和做出决策。本文回顾了机器学习算法的基本概念和应用。
            """
        },
        {
            'language': 'French', 
            'expected': 'fra',
            'text': """
            Introduction à l'Apprentissage Automatique
            L'apprentissage automatique est un sous-ensemble de l'intelligence artificielle 
            qui permet aux ordinateurs d'apprendre et de prendre des décisions sans être 
            explicitement programmés. Cet article examine les concepts fondamentaux.
            """
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        logger.info(f"\n--- Testing {test_case['language']} ---")
        
        # Create test PDF
        pdf_path = create_test_pdf_with_text(
            test_case['text'], 
            f"test_{test_case['language'].lower()}.pdf"
        )
        
        if not pdf_path:
            logger.warning(f"Could not create PDF for {test_case['language']}")
            continue
        
        try:
            # Test 1: Text-based detection (existing method)
            detected_lang = detect_language(test_case['text'])
            text_based = TESSERACT_LANG_MAP.get(detected_lang, 'eng')
            
            # Test 2: Multi-language OCR sampling 
            try:
                ocr_based = detect_language_from_multilang_ocr(pdf_path)
            except Exception as e:
                logger.warning(f"Multi-OCR detection failed: {e}")
                ocr_based = 'eng'
            
            # Test 3: LLaVA visual detection
            try:
                llava_based = detect_language_with_llava(pdf_path)
                if not llava_based:
                    llava_based = 'not_available'
            except Exception as e:
                logger.warning(f"LLaVA detection failed: {e}")
                llava_based = 'not_available'
            
            # Test 4: Hybrid detection
            try:
                hybrid_result = detect_language_hybrid(pdf_path)
            except Exception as e:
                logger.warning(f"Hybrid detection failed: {e}")
                hybrid_result = 'eng'
            
            # Compile results
            test_result = {
                'language': test_case['language'],
                'expected': test_case['expected'],
                'text_based': text_based,
                'ocr_based': ocr_based,
                'llava_based': llava_based,
                'hybrid': hybrid_result
            }
            
            results.append(test_result)
            
            # Log results
            logger.info(f"Expected: {test_case['expected']}")
            logger.info(f"Text-based: {text_based}")
            logger.info(f"OCR-based: {ocr_based}")
            logger.info(f"LLaVA: {llava_based}")
            logger.info(f"Hybrid: {hybrid_result}")
            
            # Check accuracy
            methods = ['text_based', 'ocr_based', 'hybrid']
            for method in methods:
                if test_result[method] == test_case['expected']:
                    logger.info(f"✅ {method} detection: CORRECT")
                else:
                    logger.info(f"❌ {method} detection: INCORRECT")
            
        finally:
            # Clean up test PDF
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)
    
    return results

def test_edge_cases():
    """
    Test edge cases for language detection
    """
    logger.info("\n=== Testing Edge Cases ===")
    
    edge_cases = [
        {
            'name': 'Empty PDF',
            'text': '',
            'expected_fallback': 'eng'
        },
        {
            'name': 'Mixed Languages',
            'text': """
            Introduction 소개 紹介
            This is a mixed language document with English, Korean (안녕하세요), 
            and Japanese (こんにちは) text combined.
            """,
            'expected_fallback': 'eng'  # Should default to most common
        },
        {
            'name': 'Very Short Text',
            'text': "Hi 안녕",
            'expected_fallback': 'eng'
        }
    ]
    
    for case in edge_cases:
        logger.info(f"\n--- Testing {case['name']} ---")
        
        if case['text']:
            pdf_path = create_test_pdf_with_text(case['text'], f"test_{case['name'].lower().replace(' ', '_')}.pdf")
            
            if pdf_path:
                try:
                    result = detect_language_hybrid(pdf_path)
                    logger.info(f"Result: {result}")
                    logger.info(f"Expected fallback: {case['expected_fallback']}")
                    
                finally:
                    if os.path.exists(pdf_path):
                        os.unlink(pdf_path)
        else:
            logger.info("Skipping empty text case (requires image-only PDF)")

def print_summary(results):
    """
    Print summary of test results
    """
    logger.info("\n" + "="*60)
    logger.info("LANGUAGE DETECTION TEST SUMMARY")
    logger.info("="*60)
    
    methods = ['text_based', 'ocr_based', 'hybrid']
    method_scores = {method: 0 for method in methods}
    
    for result in results:
        logger.info(f"\n{result['language']}:")
        logger.info(f"  Expected: {result['expected']}")
        for method in methods:
            correct = result[method] == result['expected']
            status = "✅" if correct else "❌"
            logger.info(f"  {method}: {result[method]} {status}")
            if correct:
                method_scores[method] += 1
    
    logger.info(f"\nACCURACY SCORES:")
    total_tests = len(results)
    for method in methods:
        accuracy = (method_scores[method] / total_tests) * 100
        logger.info(f"  {method}: {method_scores[method]}/{total_tests} ({accuracy:.1f}%)")
    
    logger.info(f"\nPRIORITY LANGUAGES: {PRIORITY_LANGUAGES}")
    logger.info(f"SUPPORTED LANGUAGES: {list(TESSERACT_LANG_MAP.keys())}")

def main():
    """
    Main test function
    """
    logger.info("🚀 Starting OCR Language Detection Tests")
    
    try:
        # Test different language detection methods
        results = test_language_detection_methods()
        
        # Test edge cases
        test_edge_cases()
        
        # Print summary
        print_summary(results)
        
        logger.info("\n✅ OCR Language Detection Tests Completed")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())