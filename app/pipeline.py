import os
import logging
import uuid
import tempfile
import shutil
from typing import Dict, Optional, Tuple
from pathlib import Path
import time

# Import all processing modules
from ocr import process_pdf_with_ocr, extract_page_texts_from_pdf
from ocr_quality import assess_document_quality, is_quality_assessment_available
from embedding import generate_page_embeddings, compute_document_embedding_from_pages
from layout import analyze_pdf_layout, is_layout_service_available
from metadata import extract_paper_metadata, is_metadata_service_available
from db import (
    initialize_database, save_paper, save_embedding, save_metadata, 
    save_layout_analysis, update_ocr_quality, get_paper_by_content_id,
    save_page_embeddings_batch
)
from models import compute_content_id

logger = logging.getLogger(__name__)

class PDFProcessingPipeline:
    """
    Unified PDF processing pipeline that orchestrates all processing steps
    """
    
    def __init__(self, data_dir: str = "/data"):
        """
        Initialize PDF processing pipeline
        
        Args:
            data_dir: str, directory for storing processed files
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        self.pdfs_dir = self.data_dir / "pdfs"
        self.images_dir = self.data_dir / "images"
        self.temp_dir = self.data_dir / "temp"
        
        for dir_path in [self.pdfs_dir, self.images_dir, self.temp_dir]:
            dir_path.mkdir(exist_ok=True)
        
        logger.info(f"Initialized PDF processing pipeline with data directory: {self.data_dir}")
    
    def process_pdf(self, pdf_file_path: str, filename: str = None) -> Dict:
        """
        Complete PDF processing pipeline
        
        Args:
            pdf_file_path: str, path to uploaded PDF file
            filename: str, original filename (optional)
            
        Returns:
            Dict: processing results summary
        """
        # Generate unique document ID
        doc_id = str(uuid.uuid4())
        start_time = time.time()
        
        if not filename:
            filename = os.path.basename(pdf_file_path)
        
        logger.info(f"Starting PDF processing pipeline for: {filename} (ID: {doc_id})")
        
        # Initialize result structure
        result = {
            'doc_id': doc_id,
            'filename': filename,
            'success': False,
            'processing_time': 0,
            'steps_completed': [],
            'steps_failed': [],
            'warnings': [],
            'data': {}
        }
        
        temp_dir = None
        
        try:
            # Create temporary processing directory
            temp_dir = self.temp_dir / doc_id
            temp_dir.mkdir(exist_ok=True)
            
            # Copy PDF to permanent location
            pdf_final_path = self.pdfs_dir / f"{doc_id}.pdf"
            shutil.copy2(pdf_file_path, pdf_final_path)
            logger.info(f"PDF saved to: {pdf_final_path}")
            
            # Step 1: Save initial paper record
            logger.info("Step 1: Saving initial paper record")
            try:
                paper = save_paper(doc_id, filename, str(pdf_final_path))
                result['steps_completed'].append('save_paper')
                logger.info("Initial paper record saved successfully")
            except Exception as e:
                logger.error(f"Failed to save initial paper record: {e}")
                result['steps_failed'].append('save_paper')
                raise
            
            # Step 2: OCR Processing
            logger.info("Step 2: OCR Processing")
            try:
                ocr_result = process_pdf_with_ocr(
                    str(pdf_final_path), 
                    str(temp_dir), 
                    doc_id
                )
                
                if ocr_result['success']:
                    result['data']['ocr'] = {
                        'text_length': ocr_result['text_length'],
                        'language': ocr_result['detected_language'],
                        'page_count': ocr_result['page_count'],
                        'ocr_performed': ocr_result['ocr_performed']
                    }
                    result['steps_completed'].append('ocr')
                    
                    # Move first page image to permanent location
                    if ocr_result['first_page_image_path']:
                        image_final_path = self.images_dir / f"{doc_id}_page1.png"
                        shutil.copy2(ocr_result['first_page_image_path'], image_final_path)
                        result['data']['first_page_image'] = str(image_final_path)
                    
                    extracted_text = ocr_result['extracted_text']
                    logger.info(f"OCR completed: {ocr_result['text_length']} characters extracted")
                else:
                    raise Exception(f"OCR failed: {ocr_result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"OCR processing failed: {e}")
                result['steps_failed'].append('ocr')
                result['warnings'].append(f"OCR failed: {str(e)}")
                extracted_text = ""
            
            # Step 3: OCR Quality Assessment
            logger.info("Step 3: OCR Quality Assessment")
            ocr_quality = "unknown"
            quality_details = {}
            
            try:
                if is_quality_assessment_available() and result['data'].get('first_page_image'):
                    quality_summary, quality_details = assess_document_quality(
                        result['data']['first_page_image']
                    )
                    ocr_quality = quality_summary
                    result['data']['quality'] = quality_details
                    result['steps_completed'].append('quality_assessment')
                    logger.info(f"Quality assessment completed: {quality_summary}")
                else:
                    result['warnings'].append("Quality assessment service unavailable")
                    
            except Exception as e:
                logger.error(f"Quality assessment failed: {e}")
                result['steps_failed'].append('quality_assessment')
                result['warnings'].append(f"Quality assessment failed: {str(e)}")
            
            # Update paper with OCR data
            try:
                update_ocr_quality(doc_id, extracted_text, ocr_quality)
                logger.info("Paper updated with OCR data")
            except Exception as e:
                logger.error(f"Failed to update paper with OCR data: {e}")
                result['warnings'].append(f"Failed to update OCR data: {str(e)}")
            
            # Step 4: Page-level Embedding Generation
            logger.info("Step 4: Page-level Embedding Generation")
            try:
                if extracted_text and len(extracted_text.strip()) > 50:
                    # Extract page texts separately
                    page_texts, page_count = extract_page_texts_from_pdf(str(pdf_final_path))
                    
                    if page_texts and page_count > 0:
                        # Generate embeddings for each page
                        page_embeddings = generate_page_embeddings(page_texts)
                        
                        if page_embeddings and len(page_embeddings) == page_count:
                            # Prepare page embedding data for batch save
                            page_embeddings_data = []
                            for i, (page_text, page_embedding) in enumerate(zip(page_texts, page_embeddings)):
                                page_embeddings_data.append((i + 1, page_text, page_embedding))  # 1-based page numbering
                            
                            # Save page embeddings in batch
                            if save_page_embeddings_batch(doc_id, page_embeddings_data):
                                logger.info(f"Saved {len(page_embeddings_data)} page embeddings")
                                
                                # Compute document-level embedding as average of page embeddings
                                document_embedding = compute_document_embedding_from_pages(page_embeddings)
                                
                                if document_embedding is not None and len(document_embedding) > 0:
                                    # Compute content ID for deduplication
                                    content_id = compute_content_id(document_embedding)
                                    
                                    # Check for duplicates
                                    existing_paper = get_paper_by_content_id(content_id)
                                    if existing_paper:
                                        logger.warning(f"Similar paper found: {existing_paper.doc_id}")
                                        result['warnings'].append(f"Similar content detected (ID: {existing_paper.doc_id})")
                                    
                                    # Save document-level embedding
                                    save_embedding(doc_id, document_embedding)
                                    
                                    # Update paper with content_id
                                    paper = save_paper(doc_id, filename, str(pdf_final_path), content_id)
                                    
                                    result['data']['embedding'] = {
                                        'dimension': len(document_embedding),
                                        'content_id': content_id,
                                        'page_count': page_count,
                                        'pages_with_embeddings': len(page_embeddings_data)
                                    }
                                    result['steps_completed'].append('embedding')
                                    logger.info(f"Document embedding generated from {page_count} pages: {len(document_embedding)} dimensions")
                                else:
                                    raise Exception("Failed to generate valid document embedding from pages")
                            else:
                                raise Exception("Failed to save page embeddings")
                        else:
                            raise Exception(f"Page embedding generation failed: expected {page_count}, got {len(page_embeddings) if page_embeddings else 0}")
                    else:
                        raise Exception("No page texts extracted for embedding generation")
                else:
                    raise Exception("Text too short for embedding generation")
                    
            except Exception as e:
                logger.error(f"Embedding generation failed: {e}")
                result['steps_failed'].append('embedding')
                result['warnings'].append(f"Embedding failed: {str(e)}")
            
            # Step 5: Layout Analysis
            logger.info("Step 5: Layout Analysis")
            try:
                if is_layout_service_available():
                    layout_data, layout_success = analyze_pdf_layout(str(pdf_final_path))
                    
                    if layout_success:
                        # Save layout analysis
                        page_count = layout_data.get('page_count', 0)
                        save_layout_analysis(doc_id, layout_data, page_count)
                        
                        result['data']['layout'] = {
                            'page_count': page_count,
                            'total_elements': layout_data.get('total_elements', 0),
                            'element_types': layout_data.get('element_types', {})
                        }
                        result['steps_completed'].append('layout')
                        logger.info(f"Layout analysis completed: {page_count} pages analyzed")
                    else:
                        raise Exception(f"Layout analysis failed: {layout_data.get('error', 'Unknown error')}")
                else:
                    result['warnings'].append("Layout analysis service unavailable")
                    
            except Exception as e:
                logger.error(f"Layout analysis failed: {e}")
                result['steps_failed'].append('layout')
                result['warnings'].append(f"Layout analysis failed: {str(e)}")
            
            # Step 6: Metadata Extraction
            logger.info("Step 6: Metadata Extraction")
            try:
                if extracted_text and len(extracted_text.strip()) > 100:
                    if is_metadata_service_available():
                        metadata, metadata_success = extract_paper_metadata(extracted_text)
                        
                        if metadata_success:
                            # Save metadata
                            save_metadata(
                                doc_id,
                                title=metadata.get('title'),
                                authors=metadata.get('authors'),
                                journal=metadata.get('journal'),
                                year=metadata.get('year'),
                                doi=metadata.get('doi'),
                                abstract=metadata.get('abstract'),
                                keywords=metadata.get('keywords')
                            )
                            
                            result['data']['metadata'] = {
                                'title': metadata.get('title'),
                                'authors_count': len(metadata.get('authors', [])),
                                'year': metadata.get('year'),
                                'journal': metadata.get('journal'),
                                'extraction_method': metadata.get('extraction_method')
                            }
                            result['steps_completed'].append('metadata')
                            logger.info(f"Metadata extracted: {metadata.get('title', 'Unknown title')}")
                        else:
                            raise Exception(f"Metadata extraction failed: {metadata.get('error', 'Unknown error')}")
                    else:
                        result['warnings'].append("Metadata extraction service unavailable")
                else:
                    result['warnings'].append("Text too short for metadata extraction")
                    
            except Exception as e:
                logger.error(f"Metadata extraction failed: {e}")
                result['steps_failed'].append('metadata')
                result['warnings'].append(f"Metadata extraction failed: {str(e)}")
            
            # Step 7: Cleanup and Finalization
            logger.info("Step 7: Cleanup and Finalization")
            try:
                # Clean up temporary files
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir)
                
                # Calculate processing time
                processing_time = time.time() - start_time
                result['processing_time'] = round(processing_time, 2)
                
                # Determine overall success
                critical_steps = ['save_paper', 'ocr']
                critical_failures = [step for step in critical_steps if step in result['steps_failed']]
                
                if not critical_failures:
                    result['success'] = True
                    logger.info(f"PDF processing completed successfully in {processing_time:.2f}s")
                else:
                    logger.error(f"PDF processing failed due to critical step failures: {critical_failures}")
                
                result['steps_completed'].append('cleanup')
                
            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                result['warnings'].append(f"Cleanup failed: {str(e)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}")
            
            # Cleanup on failure
            try:
                if temp_dir and temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except:
                pass
            
            result['error'] = str(e)
            result['processing_time'] = time.time() - start_time
            return result
    
    def get_service_status(self) -> Dict:
        """
        Check status of all external services
        
        Returns:
            Dict: service availability status
        """
        logger.info("Checking service status...")
        
        status = {
            'database': False,
            'quality_assessment': False,
            'layout_analysis': False,
            'metadata_extraction': False,
            'timestamp': time.time()
        }
        
        try:
            # Test database
            initialize_database()
            status['database'] = True
            logger.info("Database: Available")
        except Exception as e:
            logger.error(f"Database: Unavailable - {e}")
        
        try:
            # Test quality assessment (LLaVA)
            status['quality_assessment'] = is_quality_assessment_available()
            logger.info(f"Quality Assessment: {'Available' if status['quality_assessment'] else 'Unavailable'}")
        except Exception as e:
            logger.error(f"Quality Assessment: Error - {e}")
        
        try:
            # Test layout analysis (Huridocs)
            status['layout_analysis'] = is_layout_service_available()
            logger.info(f"Layout Analysis: {'Available' if status['layout_analysis'] else 'Unavailable'}")
        except Exception as e:
            logger.error(f"Layout Analysis: Error - {e}")
        
        try:
            # Test metadata extraction (LLM)
            status['metadata_extraction'] = is_metadata_service_available()
            logger.info(f"Metadata Extraction: {'Available' if status['metadata_extraction'] else 'Unavailable'}")
        except Exception as e:
            logger.error(f"Metadata Extraction: Error - {e}")
        
        return status
    
    def cleanup_old_files(self, max_age_days: int = 7) -> Dict:
        """
        Clean up old temporary and processed files
        
        Args:
            max_age_days: int, maximum age of files to keep
            
        Returns:
            Dict: cleanup results
        """
        logger.info(f"Starting cleanup of files older than {max_age_days} days")
        
        cleanup_result = {
            'files_removed': 0,
            'bytes_freed': 0,
            'errors': []
        }
        
        import time
        cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
        
        try:
            # Clean temporary directory
            for file_path in self.temp_dir.rglob('*'):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
                    try:
                        file_size = file_path.stat().st_size
                        file_path.unlink()
                        cleanup_result['files_removed'] += 1
                        cleanup_result['bytes_freed'] += file_size
                    except Exception as e:
                        cleanup_result['errors'].append(f"Failed to remove {file_path}: {e}")
            
            # Remove empty directories in temp
            for dir_path in self.temp_dir.rglob('*'):
                if dir_path.is_dir() and not any(dir_path.iterdir()):
                    try:
                        dir_path.rmdir()
                    except Exception as e:
                        cleanup_result['errors'].append(f"Failed to remove directory {dir_path}: {e}")
            
            logger.info(f"Cleanup completed: {cleanup_result['files_removed']} files removed, "
                       f"{cleanup_result['bytes_freed']} bytes freed")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            cleanup_result['errors'].append(str(e))
        
        return cleanup_result

# Global pipeline instance
_pipeline = None

def get_pipeline() -> PDFProcessingPipeline:
    """
    Get global pipeline instance (singleton)
    
    Returns:
        PDFProcessingPipeline: pipeline instance
    """
    global _pipeline
    
    if _pipeline is None:
        _pipeline = PDFProcessingPipeline()
    
    return _pipeline

def process_uploaded_pdf(pdf_file_path: str, filename: str = None) -> Dict:
    """
    Process uploaded PDF through complete pipeline
    
    Args:
        pdf_file_path: str, path to uploaded PDF file
        filename: str, original filename
        
    Returns:
        Dict: processing results
    """
    try:
        pipeline = get_pipeline()
        return pipeline.process_pdf(pdf_file_path, filename)
    except Exception as e:
        logger.error(f"Error in PDF processing: {e}")
        return {
            'success': False,
            'error': str(e),
            'doc_id': None,
            'filename': filename,
            'processing_time': 0,
            'steps_completed': [],
            'steps_failed': ['pipeline_initialization']
        }

def check_all_services() -> Dict:
    """
    Check availability of all processing services
    
    Returns:
        Dict: service status
    """
    try:
        pipeline = get_pipeline()
        return pipeline.get_service_status()
    except Exception as e:
        logger.error(f"Error checking services: {e}")
        return {
            'database': False,
            'quality_assessment': False,
            'layout_analysis': False,
            'metadata_extraction': False,
            'error': str(e),
            'timestamp': time.time()
        }