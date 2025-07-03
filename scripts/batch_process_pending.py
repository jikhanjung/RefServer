#!/usr/bin/env python3
"""
Batch process pending GPU-intensive tasks with smart GPU memory management
This script finds papers with pending GPU tasks and processes them efficiently

GPU Memory Optimization Usage:
    # Recommended: Smart sequential processing (auto GPU management)
    python batch_process_pending.py --sequential
    
    # Process Ollama-dependent tasks (requires Ollama running)
    python batch_process_pending.py --ollama-tasks
    
    # Process non-Ollama tasks (can run when Ollama is stopped)
    python batch_process_pending.py --non-ollama-tasks

Individual Task Usage:
    python batch_process_pending.py --task ocr_quality
    python batch_process_pending.py --task layout
    python batch_process_pending.py --task metadata_llm

Utility:
    python batch_process_pending.py --check-ollama
    python batch_process_pending.py --all  # Legacy mode (may cause GPU OOM)

GPU Task Classification:
    Ollama-dependent: OCR Quality (LLaVA), LLM Metadata (Llama 3.2)
    Non-Ollama: Layout Analysis (Huridocs)
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app'))

from models import Paper, db
from ocr_quality import assess_document_quality, is_quality_assessment_available
from layout import analyze_pdf_layout, is_layout_service_available
from metadata import extract_paper_metadata, is_metadata_service_available
from db import save_layout_analysis, update_ocr_quality, save_metadata
from pdf2image import convert_from_path
import tempfile

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def process_pending_ocr_quality():
    """Process papers with pending OCR quality assessment"""
    if not is_quality_assessment_available():
        logger.error("OCR quality assessment service is not available")
        return 0, 0
    
    # Find papers that need OCR quality assessment
    papers = Paper.select().where(
        (Paper.ocr_quality_completed == False) | 
        (Paper.ocr_quality.is_null(True))
    )
    
    total = papers.count()
    processed = 0
    failed = 0
    
    logger.info(f"Found {total} papers with pending OCR quality assessment")
    
    for paper in papers:
        try:
            logger.info(f"Processing OCR quality for {paper.filename} ({paper.doc_id})")
            
            # Extract first page image if needed
            with tempfile.TemporaryDirectory() as temp_dir:
                # Convert first page to image
                images = convert_from_path(paper.file_path, first_page=1, last_page=1, dpi=200)
                if images:
                    first_page_path = os.path.join(temp_dir, "first_page.png")
                    images[0].save(first_page_path, "PNG")
                    
                    # Assess quality
                    quality_summary, quality_details = assess_document_quality(first_page_path)
                    
                    # Update paper
                    paper.ocr_quality = quality_summary
                    paper.ocr_quality_completed = True
                    paper.save()
                    
                    processed += 1
                    logger.info(f"✓ OCR quality assessment completed: {quality_summary}")
                else:
                    logger.error(f"Failed to extract first page image from {paper.filename}")
                    failed += 1
                    
        except Exception as e:
            logger.error(f"Error processing {paper.filename}: {e}")
            failed += 1
    
    logger.info(f"OCR quality batch processing completed: {processed}/{total} successful, {failed} failed")
    return processed, failed


def process_pending_layout():
    """Process papers with pending layout analysis"""
    if not is_layout_service_available():
        logger.error("Layout analysis service is not available")
        return 0, 0
    
    # Find papers that need layout analysis
    papers = Paper.select().where(Paper.layout_completed == False)
    
    total = papers.count()
    processed = 0
    failed = 0
    
    logger.info(f"Found {total} papers with pending layout analysis")
    
    for paper in papers:
        try:
            logger.info(f"Processing layout for {paper.filename} ({paper.doc_id})")
            
            # Analyze layout
            layout_data, layout_success = analyze_pdf_layout(paper.file_path)
            
            if layout_success:
                # Save layout analysis
                page_count = layout_data.get('page_count', 0)
                save_layout_analysis(paper.doc_id, layout_data, page_count)
                
                # Update paper
                paper.layout_completed = True
                paper.save()
                
                processed += 1
                logger.info(f"✓ Layout analysis completed: {page_count} pages")
            else:
                logger.error(f"Layout analysis failed: {layout_data.get('error', 'Unknown error')}")
                failed += 1
                
        except Exception as e:
            logger.error(f"Error processing {paper.filename}: {e}")
            failed += 1
    
    logger.info(f"Layout batch processing completed: {processed}/{total} successful, {failed} failed")
    return processed, failed


def process_pending_metadata_llm():
    """Process papers with pending LLM metadata extraction"""
    if not is_metadata_service_available():
        logger.error("Metadata extraction service is not available")
        return 0, 0
    
    # Find papers that need LLM metadata extraction
    papers = Paper.select().where(
        (Paper.metadata_llm_completed == False) &
        (Paper.ocr_text.is_null(False)) &
        (Paper.ocr_text != '')
    )
    
    total = papers.count()
    processed = 0
    failed = 0
    
    logger.info(f"Found {total} papers with pending LLM metadata extraction")
    
    for paper in papers:
        try:
            logger.info(f"Processing metadata for {paper.filename} ({paper.doc_id})")
            
            # Extract metadata
            metadata, metadata_success = extract_paper_metadata(paper.ocr_text)
            
            if metadata_success and metadata.get('extraction_method') in ['structured_llm', 'simple_llm']:
                # Save metadata
                save_metadata(
                    paper.doc_id,
                    title=metadata.get('title'),
                    authors=metadata.get('authors'),
                    journal=metadata.get('journal'),
                    year=metadata.get('year'),
                    doi=metadata.get('doi'),
                    abstract=metadata.get('abstract'),
                    keywords=metadata.get('keywords')
                )
                
                # Update paper
                paper.metadata_llm_completed = True
                paper.save()
                
                processed += 1
                logger.info(f"✓ LLM metadata extraction completed: {metadata.get('title', 'Unknown')}")
            else:
                logger.error(f"Metadata extraction failed or used rule-based method")
                failed += 1
                
        except Exception as e:
            logger.error(f"Error processing {paper.filename}: {e}")
            failed += 1
    
    logger.info(f"Metadata batch processing completed: {processed}/{total} successful, {failed} failed")
    return processed, failed


def check_ollama_status():
    """Check if Ollama is running and accessible"""
    import requests
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False


def stop_ollama():
    """Stop Ollama service"""
    import subprocess
    try:
        logger.info("Stopping Ollama service...")
        result = subprocess.run(['pkill', '-f', 'ollama'], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Ollama stopped successfully")
            return True
        else:
            logger.warning("Ollama may not have been running")
            return True
    except Exception as e:
        logger.error(f"Failed to stop Ollama: {e}")
        return False


def start_ollama():
    """Start Ollama service"""
    import subprocess
    import time
    try:
        logger.info("Starting Ollama service...")
        subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wait for Ollama to be ready
        for i in range(30):  # Wait up to 30 seconds
            time.sleep(1)
            if check_ollama_status():
                logger.info("Ollama started successfully")
                return True
        
        logger.error("Ollama failed to start within 30 seconds")
        return False
    except Exception as e:
        logger.error(f"Failed to start Ollama: {e}")
        return False


def process_ollama_tasks():
    """Process tasks that require Ollama (OCR quality + LLM metadata)"""
    logger.info("🔥 Processing Ollama-dependent tasks (OCR quality + LLM metadata)")
    
    if not check_ollama_status():
        logger.error("Ollama is not running. Please start Ollama first.")
        return 0, 0
    
    total_processed = 0
    total_failed = 0
    
    # Process OCR quality
    processed, failed = process_pending_ocr_quality()
    total_processed += processed
    total_failed += failed
    
    # Process LLM metadata
    processed, failed = process_pending_metadata_llm()
    total_processed += processed
    total_failed += failed
    
    return total_processed, total_failed


def process_non_ollama_tasks():
    """Process tasks that don't require Ollama (Layout analysis)"""
    logger.info("🏗️ Processing non-Ollama tasks (Layout analysis)")
    
    # Process layout analysis
    processed, failed = process_pending_layout()
    
    return processed, failed


def process_sequential():
    """Process all tasks sequentially with optimal GPU memory management"""
    logger.info("🔄 Starting sequential processing with GPU memory optimization")
    
    total_processed = 0
    total_failed = 0
    
    # Step 1: Process Ollama-dependent tasks if Ollama is running
    if check_ollama_status():
        logger.info("Step 1: Processing Ollama-dependent tasks...")
        processed, failed = process_ollama_tasks()
        total_processed += processed
        total_failed += failed
        
        # Step 2: Stop Ollama to free GPU memory
        logger.info("Step 2: Stopping Ollama to free GPU memory for layout analysis...")
        stop_ollama()
        
        # Wait a bit for GPU memory to be released
        import time
        time.sleep(5)
    else:
        logger.info("Ollama not running, skipping Ollama-dependent tasks")
    
    # Step 3: Process layout analysis with freed GPU memory
    logger.info("Step 3: Processing layout analysis with freed GPU memory...")
    processed, failed = process_non_ollama_tasks()
    total_processed += processed
    total_failed += failed
    
    # Step 4: Restart Ollama
    logger.info("Step 4: Restarting Ollama service...")
    if start_ollama():
        logger.info("✅ Sequential processing completed successfully")
    else:
        logger.warning("⚠️ Sequential processing completed, but failed to restart Ollama")
    
    return total_processed, total_failed


def main():
    parser = argparse.ArgumentParser(description='Batch process pending GPU-intensive tasks')
    
    # Individual task options
    parser.add_argument('--task', choices=['ocr_quality', 'layout', 'metadata_llm'],
                        help='Specific task to process')
    
    # Grouped task options
    parser.add_argument('--ollama-tasks', action='store_true',
                        help='Process Ollama-dependent tasks (OCR quality + LLM metadata)')
    parser.add_argument('--non-ollama-tasks', action='store_true',
                        help='Process non-Ollama tasks (Layout analysis)')
    
    # Processing strategies
    parser.add_argument('--all', action='store_true',
                        help='Process all pending tasks (may cause GPU memory issues)')
    parser.add_argument('--sequential', action='store_true',
                        help='Process tasks sequentially with optimal GPU memory management')
    
    # Other options
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of papers to process')
    parser.add_argument('--check-ollama', action='store_true',
                        help='Check Ollama status and exit')
    
    args = parser.parse_args()
    
    # Check Ollama status
    if args.check_ollama:
        if check_ollama_status():
            print("✅ Ollama is running and accessible")
            sys.exit(0)
        else:
            print("❌ Ollama is not running or not accessible")
            sys.exit(1)
    
    # Validate arguments
    options_count = sum([
        bool(args.task), args.ollama_tasks, args.non_ollama_tasks, 
        args.all, args.sequential
    ])
    
    if options_count == 0:
        parser.error('Please specify one of: --task, --ollama-tasks, --non-ollama-tasks, --all, or --sequential')
    elif options_count > 1:
        parser.error('Please specify only one processing option')
    
    # Connect to database
    if not db.is_closed():
        db.close()
    db.connect()
    
    try:
        total_processed = 0
        total_failed = 0
        
        if args.sequential:
            # Sequential processing with GPU optimization
            total_processed, total_failed = process_sequential()
            
        elif args.ollama_tasks:
            # Process Ollama-dependent tasks
            total_processed, total_failed = process_ollama_tasks()
            
        elif args.non_ollama_tasks:
            # Process non-Ollama tasks
            total_processed, total_failed = process_non_ollama_tasks()
            
        elif args.task:
            # Process specific task
            if args.task == 'ocr_quality':
                processed, failed = process_pending_ocr_quality()
            elif args.task == 'layout':
                processed, failed = process_pending_layout()
            elif args.task == 'metadata_llm':
                processed, failed = process_pending_metadata_llm()
            
            total_processed += processed
            total_failed += failed
            
        elif args.all:
            # Process all tasks (legacy mode)
            logger.warning("⚠️ Using --all may cause GPU memory issues. Consider using --sequential instead.")
            
            processed, failed = process_pending_ocr_quality()
            total_processed += processed
            total_failed += failed
            
            processed, failed = process_pending_layout()
            total_processed += processed
            total_failed += failed
            
            processed, failed = process_pending_metadata_llm()
            total_processed += processed
            total_failed += failed
        
        logger.info(f"\n📊 Batch processing summary:")
        logger.info(f"Total processed: {total_processed}")
        logger.info(f"Total failed: {total_failed}")
        
    finally:
        db.close()


if __name__ == "__main__":
    main()