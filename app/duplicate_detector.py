# RefServer Duplicate Prevention System
# Multi-layer duplicate detection for PDF papers

import os
import hashlib
import logging
import tempfile
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from pathlib import Path
import PyPDF2
import fitz  # PyMuPDF

from models import Paper, FileHash, ContentHash, SampleEmbeddingHash, DuplicateDetectionLog, serialize_vector, deserialize_vector
from embedding import get_embedding_model
import uuid
from peewee import fn

logger = logging.getLogger(__name__)

class DuplicateDetector:
    """
    Multi-layer duplicate prevention system for PDF papers
    
    Layer 0: File MD5 hash (1-3 seconds)
    Layer 1: Quick content hash (30 seconds)  
    Layer 2: Sample embedding hash (15 seconds)
    Layer 3: Full vector similarity (existing ChromaDB system)
    """
    
    def __init__(self):
        """Initialize duplicate detector"""
        self.embedding_model = None
        logger.info("DuplicateDetector initialized")
    
    def get_embedding_model_lazy(self):
        """Lazily load embedding model only when needed"""
        if self.embedding_model is None:
            self.embedding_model = get_embedding_model()
        return self.embedding_model
    
    def compute_file_hash(self, file_path: str) -> Tuple[str, int]:
        """
        Level 0: Compute MD5 hash of file content
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Tuple[str, int]: (md5_hash, file_size)
        """
        start_time = time.time()
        
        try:
            md5_hash = hashlib.md5()
            file_size = 0
            
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)
                    file_size += len(chunk)
            
            hash_result = md5_hash.hexdigest()
            processing_time = time.time() - start_time
            
            logger.info(f"Level 0: File hash computed in {processing_time:.2f}s - {hash_result[:8]}...")
            return hash_result, file_size
            
        except Exception as e:
            logger.error(f"Level 0: File hash computation failed: {e}")
            raise
    
    def check_file_duplicate(self, file_path: str, filename: str) -> Optional[str]:
        """
        Level 0: Check for file-level duplicates using MD5 hash
        
        Args:
            file_path: Path to PDF file
            filename: Original filename
            
        Returns:
            Optional[str]: Existing paper doc_id if duplicate found, None otherwise
        """
        try:
            file_md5, file_size = self.compute_file_hash(file_path)
            
            # Check if this exact file already exists
            existing_hash = FileHash.get_or_none(FileHash.file_md5 == file_md5)
            
            if existing_hash:
                logger.info(f"🎯 Level 0: Exact file duplicate detected - {existing_hash.paper.doc_id}")
                return existing_hash.paper.doc_id
            
            logger.info(f"✅ Level 0: No file duplicate found - {file_md5[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Level 0: File duplicate check failed: {e}")
            return None
    
    def save_file_hash(self, file_path: str, filename: str, paper_doc_id: str) -> bool:
        """
        Save file hash for future duplicate detection
        
        Args:
            file_path: Path to PDF file
            filename: Original filename
            paper_doc_id: Associated paper document ID
            
        Returns:
            bool: True if saved successfully
        """
        try:
            file_md5, file_size = self.compute_file_hash(file_path)
            paper = Paper.get(Paper.doc_id == paper_doc_id)
            
            # Create or update file hash record
            FileHash.replace(
                file_md5=file_md5,
                file_size=file_size,
                original_filename=filename,
                paper=paper
            ).execute()
            
            logger.info(f"✅ Level 0: File hash saved - {file_md5[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Level 0: Failed to save file hash: {e}")
            return False
    
    def extract_pdf_metadata_and_text(self, file_path: str) -> Dict:
        """
        Extract PDF metadata and first 3 pages text for content hashing
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Dict: PDF metadata and text content
        """
        start_time = time.time()
        
        try:
            # Extract using PyMuPDF for better reliability
            doc = fitz.open(file_path)
            
            # Get PDF metadata
            metadata = doc.metadata
            page_count = len(doc)
            
            # Extract first 3 pages text
            first_three_pages_text = ""
            max_pages = min(3, page_count)
            
            for page_num in range(max_pages):
                page = doc[page_num]
                text = page.get_text()
                first_three_pages_text += text + "\n"
            
            doc.close()
            
            # Truncate text if too long (keep first 5000 chars)
            if len(first_three_pages_text) > 5000:
                first_three_pages_text = first_three_pages_text[:5000] + "..."
            
            result = {
                'pdf_title': metadata.get('title', '').strip(),
                'pdf_author': metadata.get('author', '').strip(),
                'pdf_creator': metadata.get('creator', '').strip(),
                'page_count': page_count,
                'first_three_pages_text': first_three_pages_text.strip()
            }
            
            processing_time = time.time() - start_time
            logger.info(f"Level 1: PDF metadata extracted in {processing_time:.2f}s")
            
            return result
            
        except Exception as e:
            logger.error(f"Level 1: PDF metadata extraction failed: {e}")
            return {
                'pdf_title': '',
                'pdf_author': '',
                'pdf_creator': '',
                'page_count': 0,
                'first_three_pages_text': ''
            }
    
    def compute_content_hash(self, pdf_info: Dict) -> str:
        """
        Level 1: Compute SHA-256 hash of PDF metadata + first 3 pages text
        
        Args:
            pdf_info: Dictionary with PDF metadata and text
            
        Returns:
            str: SHA-256 hash
        """
        try:
            # Create hash input string
            hash_input = "|"
            hash_input += f"title:{pdf_info.get('pdf_title', '')}"
            hash_input += f"|author:{pdf_info.get('pdf_author', '')}"
            hash_input += f"|creator:{pdf_info.get('pdf_creator', '')}"
            hash_input += f"|pages:{pdf_info.get('page_count', 0)}"
            hash_input += f"|text:{pdf_info.get('first_three_pages_text', '')}"
            
            # Compute SHA-256 hash
            content_hash = hashlib.sha256(hash_input.encode('utf-8')).hexdigest()
            
            logger.info(f"Level 1: Content hash computed - {content_hash[:8]}...")
            return content_hash
            
        except Exception as e:
            logger.error(f"Level 1: Content hash computation failed: {e}")
            raise
    
    def check_content_duplicate(self, file_path: str) -> Optional[str]:
        """
        Level 1: Check for content-level duplicates using PDF metadata + first 3 pages
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            Optional[str]: Existing paper doc_id if duplicate found, None otherwise
        """
        try:
            pdf_info = self.extract_pdf_metadata_and_text(file_path)
            content_hash = self.compute_content_hash(pdf_info)
            
            # Check if this content hash already exists
            existing_hash = ContentHash.get_or_none(ContentHash.content_hash == content_hash)
            
            if existing_hash:
                logger.info(f"🎯 Level 1: Content duplicate detected - {existing_hash.paper.doc_id}")
                return existing_hash.paper.doc_id
            
            logger.info(f"✅ Level 1: No content duplicate found - {content_hash[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Level 1: Content duplicate check failed: {e}")
            return None
    
    def save_content_hash(self, file_path: str, paper_doc_id: str) -> bool:
        """
        Save content hash for future duplicate detection
        
        Args:
            file_path: Path to PDF file
            paper_doc_id: Associated paper document ID
            
        Returns:
            bool: True if saved successfully
        """
        try:
            pdf_info = self.extract_pdf_metadata_and_text(file_path)
            content_hash = self.compute_content_hash(pdf_info)
            paper = Paper.get(Paper.doc_id == paper_doc_id)
            
            # Create or update content hash record
            ContentHash.replace(
                content_hash=content_hash,
                pdf_title=pdf_info['pdf_title'],
                pdf_author=pdf_info['pdf_author'],
                pdf_creator=pdf_info['pdf_creator'],
                first_three_pages_text=pdf_info['first_three_pages_text'],
                page_count=pdf_info['page_count'],
                paper=paper
            ).execute()
            
            logger.info(f"✅ Level 1: Content hash saved - {content_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Level 1: Failed to save content hash: {e}")
            return False
    
    def extract_sample_text(self, file_path: str, strategy: str = 'first_last_middle') -> str:
        """
        Extract representative text sample from PDF for embedding
        
        Args:
            file_path: Path to PDF file
            strategy: Sampling strategy ('first_last_middle' or 'random_pages')
            
        Returns:
            str: Representative text sample
        """
        start_time = time.time()
        
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            sample_text = ""
            
            if strategy == 'first_last_middle':
                # Get first page, last page, and middle page
                pages_to_sample = []
                
                if page_count >= 1:
                    pages_to_sample.append(0)  # First page
                
                if page_count >= 3:
                    middle_page = page_count // 2
                    pages_to_sample.append(middle_page)  # Middle page
                
                if page_count >= 2:
                    pages_to_sample.append(page_count - 1)  # Last page
                
                # Remove duplicates and sort
                pages_to_sample = sorted(list(set(pages_to_sample)))
                
                for page_num in pages_to_sample:
                    page = doc[page_num]
                    text = page.get_text()
                    # Take first 1000 chars from each page
                    sample_text += text[:1000] + "\\n"
            
            elif strategy == 'random_pages':
                # Sample up to 3 random pages
                import random
                pages_to_sample = min(3, page_count)
                random_pages = random.sample(range(page_count), pages_to_sample)
                
                for page_num in sorted(random_pages):
                    page = doc[page_num]
                    text = page.get_text()
                    # Take first 1000 chars from each page
                    sample_text += text[:1000] + "\\n"
            
            doc.close()
            
            # Limit total sample text to 4000 characters
            if len(sample_text) > 4000:
                sample_text = sample_text[:4000] + "..."
            
            processing_time = time.time() - start_time
            logger.info(f"Level 2: Sample text extracted in {processing_time:.2f}s ({strategy})")
            
            return sample_text.strip()
            
        except Exception as e:
            logger.error(f"Level 2: Sample text extraction failed: {e}")
            return ""
    
    def compute_sample_embedding(self, sample_text: str) -> Optional[List[float]]:
        """
        Compute embedding for sample text
        
        Args:
            sample_text: Representative text sample
            
        Returns:
            Optional[List[float]]: Embedding vector or None if failed
        """
        try:
            if not sample_text or len(sample_text.strip()) < 50:
                logger.warning("Level 2: Sample text too short for embedding")
                return None
            
            model = self.get_embedding_model_lazy()
            if model is None:
                logger.warning("Level 2: Embedding model not available")
                return None
            
            # Generate embedding
            embedding = model.encode([sample_text])[0]
            
            logger.info(f"Level 2: Sample embedding computed - dim: {len(embedding)}")
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Level 2: Sample embedding computation failed: {e}")
            return None
    
    def compute_embedding_hash(self, embedding_vector: List[float]) -> str:
        """
        Compute SHA-256 hash of embedding vector
        
        Args:
            embedding_vector: Embedding vector
            
        Returns:
            str: SHA-256 hash
        """
        try:
            import numpy as np
            
            # Convert to numpy array and compute hash
            vector_array = np.array(embedding_vector, dtype=np.float32)
            vector_bytes = vector_array.tobytes()
            embedding_hash = hashlib.sha256(vector_bytes).hexdigest()
            
            logger.info(f"Level 2: Embedding hash computed - {embedding_hash[:8]}...")
            return embedding_hash
            
        except Exception as e:
            logger.error(f"Level 2: Embedding hash computation failed: {e}")
            raise
    
    def check_sample_embedding_duplicate(self, file_path: str, strategy: str = 'first_last_middle') -> Optional[str]:
        """
        Level 2: Check for duplicates using sample embedding hash
        
        Args:
            file_path: Path to PDF file
            strategy: Sampling strategy
            
        Returns:
            Optional[str]: Existing paper doc_id if duplicate found, None otherwise
        """
        try:
            sample_text = self.extract_sample_text(file_path, strategy)
            
            if not sample_text:
                logger.warning("Level 2: No sample text extracted")
                return None
            
            embedding_vector = self.compute_sample_embedding(sample_text)
            
            if not embedding_vector:
                logger.warning("Level 2: No embedding computed")
                return None
            
            embedding_hash = self.compute_embedding_hash(embedding_vector)
            
            # Check if this embedding hash already exists
            existing_hash = SampleEmbeddingHash.get_or_none(
                (SampleEmbeddingHash.embedding_hash == embedding_hash) &
                (SampleEmbeddingHash.sample_strategy == strategy)
            )
            
            if existing_hash:
                logger.info(f"🎯 Level 2: Sample embedding duplicate detected - {existing_hash.paper.doc_id}")
                return existing_hash.paper.doc_id
            
            logger.info(f"✅ Level 2: No sample embedding duplicate found - {embedding_hash[:8]}...")
            return None
            
        except Exception as e:
            logger.error(f"Level 2: Sample embedding duplicate check failed: {e}")
            return None
    
    def save_sample_embedding_hash(self, file_path: str, paper_doc_id: str, strategy: str = 'first_last_middle') -> bool:
        """
        Save sample embedding hash for future duplicate detection
        
        Args:
            file_path: Path to PDF file
            paper_doc_id: Associated paper document ID
            strategy: Sampling strategy
            
        Returns:
            bool: True if saved successfully
        """
        try:
            sample_text = self.extract_sample_text(file_path, strategy)
            
            if not sample_text:
                logger.warning("Level 2: No sample text to save")
                return False
            
            embedding_vector = self.compute_sample_embedding(sample_text)
            
            if not embedding_vector:
                logger.warning("Level 2: No embedding to save")
                return False
            
            embedding_hash = self.compute_embedding_hash(embedding_vector)
            paper = Paper.get(Paper.doc_id == paper_doc_id)
            
            # Serialize embedding vector
            vector_blob = serialize_vector(embedding_vector)
            
            # Create or update sample embedding hash record
            SampleEmbeddingHash.replace(
                embedding_hash=embedding_hash,
                sample_strategy=strategy,
                sample_text=sample_text,
                embedding_vector=vector_blob,
                vector_dim=len(embedding_vector),
                model_name='bge-m3',
                paper=paper
            ).execute()
            
            logger.info(f"✅ Level 2: Sample embedding hash saved - {embedding_hash[:8]}...")
            return True
            
        except Exception as e:
            logger.error(f"Level 2: Failed to save sample embedding hash: {e}")
            return False
    
    def check_all_layers(self, file_path: str, filename: str) -> Tuple[Optional[str], str, float]:
        """
        Check all duplicate detection layers progressively with performance monitoring
        
        Args:
            file_path: Path to PDF file
            filename: Original filename
            
        Returns:
            Tuple[Optional[str], str, float]: (existing_doc_id, detection_layer, processing_time)
        """
        start_time = time.time()
        detection_id = str(uuid.uuid4())
        
        # Initialize performance tracking
        layer_times = {'layer_0': None, 'layer_1': None, 'layer_2': None}
        file_size = 0
        duplicate_doc_id = None
        detection_layer = "No_Duplicate"
        error_message = None
        
        try:
            # Get file size for monitoring
            file_size = os.path.getsize(file_path)
            
            # Level 0: File hash check (fastest)
            logger.info("🔍 Starting Level 0: File hash duplicate check...")
            layer_0_start = time.time()
            duplicate_doc_id = self.check_file_duplicate(file_path, filename)
            layer_times['layer_0'] = time.time() - layer_0_start
            
            if duplicate_doc_id:
                detection_layer = "Level_0_File_Hash"
                processing_time = time.time() - start_time
                self._log_detection_performance(
                    detection_id, filename, file_size, "duplicate_found", detection_layer,
                    duplicate_doc_id, processing_time, layer_times, None
                )
                return duplicate_doc_id, detection_layer, processing_time
            
            # Level 1: Content hash check
            logger.info("🔍 Starting Level 1: Content hash duplicate check...")
            layer_1_start = time.time()
            duplicate_doc_id = self.check_content_duplicate(file_path)
            layer_times['layer_1'] = time.time() - layer_1_start
            
            if duplicate_doc_id:
                detection_layer = "Level_1_Content_Hash"
                processing_time = time.time() - start_time
                self._log_detection_performance(
                    detection_id, filename, file_size, "duplicate_found", detection_layer,
                    duplicate_doc_id, processing_time, layer_times, None
                )
                return duplicate_doc_id, detection_layer, processing_time
            
            # Level 2: Sample embedding hash check
            logger.info("🔍 Starting Level 2: Sample embedding duplicate check...")
            layer_2_start = time.time()
            duplicate_doc_id = self.check_sample_embedding_duplicate(file_path, 'first_last_middle')
            layer_times['layer_2'] = time.time() - layer_2_start
            
            if duplicate_doc_id:
                detection_layer = "Level_2_Sample_Embedding"
                processing_time = time.time() - start_time
                self._log_detection_performance(
                    detection_id, filename, file_size, "duplicate_found", detection_layer,
                    duplicate_doc_id, processing_time, layer_times, None
                )
                return duplicate_doc_id, detection_layer, processing_time
            
            # No duplicates found at any level
            processing_time = time.time() - start_time
            logger.info(f"✅ No duplicates detected across all layers in {processing_time:.2f}s")
            
            self._log_detection_performance(
                detection_id, filename, file_size, "no_duplicate", "No_Duplicate",
                None, processing_time, layer_times, None
            )
            
            return None, "No_Duplicate", processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_message = str(e)
            logger.error(f"Duplicate detection failed: {e}")
            
            self._log_detection_performance(
                detection_id, filename, file_size, "error", "Error",
                None, processing_time, layer_times, error_message
            )
            
            return None, "Error", processing_time
    
    def save_all_hashes(self, file_path: str, filename: str, paper_doc_id: str) -> Dict[str, bool]:
        """
        Save all hash types for a successfully processed paper
        
        Args:
            file_path: Path to PDF file
            filename: Original filename
            paper_doc_id: Associated paper document ID
            
        Returns:
            Dict[str, bool]: Success status for each hash type
        """
        results = {}
        
        try:
            # Save Level 0: File hash
            results['file_hash'] = self.save_file_hash(file_path, filename, paper_doc_id)
            
            # Save Level 1: Content hash
            results['content_hash'] = self.save_content_hash(file_path, paper_doc_id)
            
            # Save Level 2: Sample embedding hash
            results['sample_embedding_hash'] = self.save_sample_embedding_hash(file_path, paper_doc_id, 'first_last_middle')
            
            success_count = sum(results.values())
            logger.info(f"✅ Saved {success_count}/3 hash types for {paper_doc_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to save hashes for {paper_doc_id}: {e}")
            return {'file_hash': False, 'content_hash': False, 'sample_embedding_hash': False}
    
    def get_duplicate_stats(self) -> Dict:
        """
        Get statistics about duplicate detection database
        
        Returns:
            Dict: Statistics about stored hashes
        """
        try:
            stats = {
                'file_hashes_count': FileHash.select().count(),
                'content_hashes_count': ContentHash.select().count(),
                'sample_embedding_hashes_count': SampleEmbeddingHash.select().count(),
                'unique_papers_with_hashes': Paper.select().join(FileHash).count()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get duplicate stats: {e}")
            return {
                'file_hashes_count': 0,
                'content_hashes_count': 0,
                'sample_embedding_hashes_count': 0,
                'unique_papers_with_hashes': 0
            }
    
    def _log_detection_performance(self, detection_id: str, filename: str, file_size: int,
                                 detection_result: str, detection_layer: str, 
                                 duplicate_paper_id: Optional[str], total_processing_time: float,
                                 layer_times: Dict, error_message: Optional[str]) -> None:
        """
        Log performance metrics for duplicate detection
        
        Args:
            detection_id: Unique identifier for this detection attempt
            filename: Original filename
            file_size: File size in bytes
            detection_result: 'duplicate_found', 'no_duplicate', or 'error'
            detection_layer: Which layer detected the duplicate
            duplicate_paper_id: ID of duplicate paper if found
            total_processing_time: Total time spent
            layer_times: Dictionary with individual layer times
            error_message: Error message if detection failed
        """
        try:
            # Estimate time saved by duplicate detection
            time_saved = None
            if detection_result == "duplicate_found":
                # Estimate full pipeline processing time (varies by file size and system)
                # Base estimate: 60-300 seconds depending on file size and features
                estimated_full_processing = 60 + (file_size / (1024 * 1024)) * 20  # 60s base + 20s per MB
                time_saved = max(0, estimated_full_processing - total_processing_time)
            
            # Create detection log entry
            DuplicateDetectionLog.create(
                detection_id=detection_id,
                filename=filename,
                file_size=file_size,
                detection_result=detection_result,
                detection_layer=detection_layer,
                duplicate_paper_id=duplicate_paper_id,
                total_processing_time=total_processing_time,
                layer_0_time=layer_times.get('layer_0'),
                layer_1_time=layer_times.get('layer_1'),
                layer_2_time=layer_times.get('layer_2'),
                time_saved=time_saved,
                error_message=error_message
            )
            
            logger.info(f"📊 Detection performance logged: {detection_id}")
            
        except Exception as e:
            logger.error(f"Failed to log detection performance: {e}")
    
    def get_performance_stats(self, days: int = 30) -> Dict:
        """
        Get performance statistics for duplicate detection system
        
        Args:
            days: Number of days to analyze (default 30)
            
        Returns:
            Dict: Performance statistics
        """
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Query logs within date range
            logs = DuplicateDetectionLog.select().where(
                DuplicateDetectionLog.created_at >= start_date
            )
            
            # Initialize counters
            total_checks = logs.count()
            duplicates_found = logs.where(DuplicateDetectionLog.detection_result == 'duplicate_found').count()
            no_duplicates = logs.where(DuplicateDetectionLog.detection_result == 'no_duplicate').count()
            errors = logs.where(DuplicateDetectionLog.detection_result == 'error').count()
            
            # Layer performance
            layer_0_hits = logs.where(DuplicateDetectionLog.detection_layer == 'Level_0_File_Hash').count()
            layer_1_hits = logs.where(DuplicateDetectionLog.detection_layer == 'Level_1_Content_Hash').count()
            layer_2_hits = logs.where(DuplicateDetectionLog.detection_layer == 'Level_2_Sample_Embedding').count()
            
            # Time statistics
            duplicate_logs = list(logs.where(DuplicateDetectionLog.detection_result == 'duplicate_found'))
            total_time_saved = sum(log.time_saved or 0 for log in duplicate_logs)
            
            # Average processing times by layer
            avg_times = {}
            for layer in ['layer_0_time', 'layer_1_time', 'layer_2_time']:
                times = [getattr(log, layer) for log in logs if getattr(log, layer) is not None]
                avg_times[layer] = sum(times) / len(times) if times else 0
            
            # Detection rate (percentage of duplicates found)
            detection_rate = (duplicates_found / total_checks * 100) if total_checks > 0 else 0
            
            # Efficiency metrics
            layer_0_efficiency = (layer_0_hits / duplicates_found * 100) if duplicates_found > 0 else 0
            layer_1_efficiency = (layer_1_hits / duplicates_found * 100) if duplicates_found > 0 else 0
            layer_2_efficiency = (layer_2_hits / duplicates_found * 100) if duplicates_found > 0 else 0
            
            stats = {
                'analysis_period_days': days,
                'total_checks': total_checks,
                'duplicates_found': duplicates_found,
                'no_duplicates': no_duplicates,
                'errors': errors,
                'detection_rate_percent': round(detection_rate, 2),
                'layer_performance': {
                    'layer_0_hits': layer_0_hits,
                    'layer_1_hits': layer_1_hits,
                    'layer_2_hits': layer_2_hits,
                    'layer_0_efficiency_percent': round(layer_0_efficiency, 2),
                    'layer_1_efficiency_percent': round(layer_1_efficiency, 2),
                    'layer_2_efficiency_percent': round(layer_2_efficiency, 2)
                },
                'timing_stats': {
                    'total_time_saved_minutes': round(total_time_saved / 60, 2),
                    'avg_layer_0_time_seconds': round(avg_times.get('layer_0_time', 0), 3),
                    'avg_layer_1_time_seconds': round(avg_times.get('layer_1_time', 0), 3),
                    'avg_layer_2_time_seconds': round(avg_times.get('layer_2_time', 0), 3)
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get performance stats: {e}")
            return {
                'analysis_period_days': days,
                'total_checks': 0,
                'duplicates_found': 0,
                'no_duplicates': 0,
                'errors': 0,
                'detection_rate_percent': 0,
                'layer_performance': {
                    'layer_0_hits': 0,
                    'layer_1_hits': 0,
                    'layer_2_hits': 0,
                    'layer_0_efficiency_percent': 0,
                    'layer_1_efficiency_percent': 0,
                    'layer_2_efficiency_percent': 0
                },
                'timing_stats': {
                    'total_time_saved_minutes': 0,
                    'avg_layer_0_time_seconds': 0,
                    'avg_layer_1_time_seconds': 0,
                    'avg_layer_2_time_seconds': 0
                }
            }
    
    def get_recent_detections(self, limit: int = 50) -> List[Dict]:
        """
        Get recent duplicate detection attempts
        
        Args:
            limit: Maximum number of records to return
            
        Returns:
            List[Dict]: Recent detection records
        """
        try:
            logs = DuplicateDetectionLog.select().order_by(
                DuplicateDetectionLog.created_at.desc()
            ).limit(limit)
            
            records = []
            for log in logs:
                records.append({
                    'detection_id': log.detection_id,
                    'filename': log.filename,
                    'file_size_mb': round(log.file_size / (1024 * 1024), 2),
                    'detection_result': log.detection_result,
                    'detection_layer': log.detection_layer,
                    'duplicate_paper_id': log.duplicate_paper_id,
                    'total_processing_time': round(log.total_processing_time, 3),
                    'time_saved_minutes': round((log.time_saved or 0) / 60, 2),
                    'created_at': log.created_at.isoformat(),
                    'error_message': log.error_message
                })
            
            return records
            
        except Exception as e:
            logger.error(f"Failed to get recent detections: {e}")
            return []
    
    def cleanup_old_detection_logs(self, days_to_keep: int = 90) -> int:
        """
        Clean up old detection logs to manage database size
        
        Args:
            days_to_keep: Number of days of logs to keep
            
        Returns:
            int: Number of logs deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            deleted_count = DuplicateDetectionLog.delete().where(
                DuplicateDetectionLog.created_at < cutoff_date
            ).execute()
            
            logger.info(f"🧹 Cleaned up {deleted_count} old detection logs (older than {days_to_keep} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old detection logs: {e}")
            return 0
    
    def cleanup_orphaned_hashes(self) -> Dict[str, int]:
        """
        Clean up orphaned hash records that reference deleted papers
        
        Returns:
            Dict[str, int]: Number of orphaned records cleaned up by type
        """
        try:
            cleanup_stats = {
                'orphaned_file_hashes': 0,
                'orphaned_content_hashes': 0,
                'orphaned_sample_hashes': 0
            }
            
            # Find orphaned FileHash records
            orphaned_file_hashes = (FileHash
                                  .select()
                                  .join(Paper, on=(FileHash.paper == Paper.doc_id), join_type='LEFT OUTER')
                                  .where(Paper.doc_id.is_null()))
            
            cleanup_stats['orphaned_file_hashes'] = orphaned_file_hashes.count()
            if cleanup_stats['orphaned_file_hashes'] > 0:
                FileHash.delete().where(FileHash.file_md5.in_(
                    [h.file_md5 for h in orphaned_file_hashes]
                )).execute()
            
            # Find orphaned ContentHash records
            orphaned_content_hashes = (ContentHash
                                     .select()
                                     .join(Paper, on=(ContentHash.paper == Paper.doc_id), join_type='LEFT OUTER')
                                     .where(Paper.doc_id.is_null()))
            
            cleanup_stats['orphaned_content_hashes'] = orphaned_content_hashes.count()
            if cleanup_stats['orphaned_content_hashes'] > 0:
                ContentHash.delete().where(ContentHash.content_hash.in_(
                    [h.content_hash for h in orphaned_content_hashes]
                )).execute()
            
            # Find orphaned SampleEmbeddingHash records
            orphaned_sample_hashes = (SampleEmbeddingHash
                                    .select()
                                    .join(Paper, on=(SampleEmbeddingHash.paper == Paper.doc_id), join_type='LEFT OUTER')
                                    .where(Paper.doc_id.is_null()))
            
            cleanup_stats['orphaned_sample_hashes'] = orphaned_sample_hashes.count()
            if cleanup_stats['orphaned_sample_hashes'] > 0:
                SampleEmbeddingHash.delete().where(SampleEmbeddingHash.embedding_hash.in_(
                    [h.embedding_hash for h in orphaned_sample_hashes]
                )).execute()
            
            total_cleaned = sum(cleanup_stats.values())
            logger.info(f"🧹 Cleaned up {total_cleaned} orphaned hash records")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup orphaned hashes: {e}")
            return {
                'orphaned_file_hashes': 0,
                'orphaned_content_hashes': 0,
                'orphaned_sample_hashes': 0
            }
    
    def cleanup_duplicate_hashes(self) -> Dict[str, int]:
        """
        Clean up duplicate hash records for the same paper
        
        Returns:
            Dict[str, int]: Number of duplicate records cleaned up by type
        """
        try:
            cleanup_stats = {
                'duplicate_file_hashes': 0,
                'duplicate_content_hashes': 0,
                'duplicate_sample_hashes': 0
            }
            
            # Clean up duplicate FileHash records (keep newest for each paper)
            duplicate_file_query = """
                DELETE FROM filehash 
                WHERE file_md5 NOT IN (
                    SELECT file_md5 FROM (
                        SELECT file_md5, 
                               ROW_NUMBER() OVER (PARTITION BY paper_id ORDER BY created_at DESC) as rn
                        FROM filehash
                    ) WHERE rn = 1
                )
            """
            
            # Clean up duplicate ContentHash records (keep newest for each paper)
            duplicate_content_query = """
                DELETE FROM contenthash 
                WHERE content_hash NOT IN (
                    SELECT content_hash FROM (
                        SELECT content_hash, 
                               ROW_NUMBER() OVER (PARTITION BY paper_id ORDER BY created_at DESC) as rn
                        FROM contenthash
                    ) WHERE rn = 1
                )
            """
            
            # Clean up duplicate SampleEmbeddingHash records (keep newest for each paper+strategy)
            duplicate_sample_query = """
                DELETE FROM sampleembeddinghash 
                WHERE embedding_hash NOT IN (
                    SELECT embedding_hash FROM (
                        SELECT embedding_hash, 
                               ROW_NUMBER() OVER (PARTITION BY paper_id, sample_strategy ORDER BY created_at DESC) as rn
                        FROM sampleembeddinghash
                    ) WHERE rn = 1
                )
            """
            
            # Note: SQLite doesn't support these complex DELETE queries with window functions
            # So we'll use a different approach
            
            # For FileHash: find papers with multiple file hashes
            from models import db
            papers_with_multiple_file_hashes = (FileHash
                                              .select(FileHash.paper)
                                              .group_by(FileHash.paper)
                                              .having(fn.COUNT(FileHash.file_md5) > 1))
            
            for paper_hash in papers_with_multiple_file_hashes:
                paper_file_hashes = (FileHash
                                   .select()
                                   .where(FileHash.paper == paper_hash.paper)
                                   .order_by(FileHash.created_at.desc()))
                
                # Keep the newest, delete the rest
                hashes_to_delete = list(paper_file_hashes)[1:]  # Skip first (newest)
                for hash_to_delete in hashes_to_delete:
                    hash_to_delete.delete_instance()
                    cleanup_stats['duplicate_file_hashes'] += 1
            
            # Similar logic for ContentHash
            papers_with_multiple_content_hashes = (ContentHash
                                                 .select(ContentHash.paper)
                                                 .group_by(ContentHash.paper)
                                                 .having(fn.COUNT(ContentHash.content_hash) > 1))
            
            for paper_hash in papers_with_multiple_content_hashes:
                paper_content_hashes = (ContentHash
                                      .select()
                                      .where(ContentHash.paper == paper_hash.paper)
                                      .order_by(ContentHash.created_at.desc()))
                
                hashes_to_delete = list(paper_content_hashes)[1:]
                for hash_to_delete in hashes_to_delete:
                    hash_to_delete.delete_instance()
                    cleanup_stats['duplicate_content_hashes'] += 1
            
            # For SampleEmbeddingHash: group by paper AND strategy
            papers_with_multiple_sample_hashes = (SampleEmbeddingHash
                                                .select(SampleEmbeddingHash.paper, SampleEmbeddingHash.sample_strategy)
                                                .group_by(SampleEmbeddingHash.paper, SampleEmbeddingHash.sample_strategy)
                                                .having(fn.COUNT(SampleEmbeddingHash.embedding_hash) > 1))
            
            for paper_hash in papers_with_multiple_sample_hashes:
                paper_sample_hashes = (SampleEmbeddingHash
                                     .select()
                                     .where(
                                         (SampleEmbeddingHash.paper == paper_hash.paper) &
                                         (SampleEmbeddingHash.sample_strategy == paper_hash.sample_strategy)
                                     )
                                     .order_by(SampleEmbeddingHash.created_at.desc()))
                
                hashes_to_delete = list(paper_sample_hashes)[1:]
                for hash_to_delete in hashes_to_delete:
                    hash_to_delete.delete_instance()
                    cleanup_stats['duplicate_sample_hashes'] += 1
            
            total_cleaned = sum(cleanup_stats.values())
            logger.info(f"🧹 Cleaned up {total_cleaned} duplicate hash records")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup duplicate hashes: {e}")
            return {
                'duplicate_file_hashes': 0,
                'duplicate_content_hashes': 0,
                'duplicate_sample_hashes': 0
            }
    
    def cleanup_unused_hashes(self, months_threshold: int = 6) -> Dict[str, int]:
        """
        Clean up hash records that haven't been used for duplicate detection recently
        
        Args:
            months_threshold: Number of months of inactivity before cleanup
            
        Returns:
            Dict[str, int]: Number of unused records cleaned up by type
        """
        try:
            cleanup_stats = {
                'unused_file_hashes': 0,
                'unused_content_hashes': 0,
                'unused_sample_hashes': 0
            }
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=months_threshold * 30)
            
            # Find hashes that haven't been referenced in recent detection logs
            recent_detection_paper_ids = set()
            recent_detections = DuplicateDetectionLog.select().where(
                DuplicateDetectionLog.created_at >= cutoff_date
            )
            
            for detection in recent_detections:
                if detection.duplicate_paper_id:
                    recent_detection_paper_ids.add(detection.duplicate_paper_id)
            
            # Find old papers (created before threshold and not recently detected)
            old_papers = Paper.select().where(
                (Paper.created_at < cutoff_date) &
                (~(Paper.doc_id.in_(recent_detection_paper_ids)))
            )
            
            old_paper_ids = [p.doc_id for p in old_papers]
            
            if old_paper_ids:
                # Clean up FileHash records for old, unused papers
                unused_file_hashes = FileHash.select().where(FileHash.paper.in_(old_paper_ids))
                cleanup_stats['unused_file_hashes'] = unused_file_hashes.count()
                
                if cleanup_stats['unused_file_hashes'] > 0:
                    FileHash.delete().where(FileHash.paper.in_(old_paper_ids)).execute()
                
                # Clean up ContentHash records for old, unused papers
                unused_content_hashes = ContentHash.select().where(ContentHash.paper.in_(old_paper_ids))
                cleanup_stats['unused_content_hashes'] = unused_content_hashes.count()
                
                if cleanup_stats['unused_content_hashes'] > 0:
                    ContentHash.delete().where(ContentHash.paper.in_(old_paper_ids)).execute()
                
                # Clean up SampleEmbeddingHash records for old, unused papers
                unused_sample_hashes = SampleEmbeddingHash.select().where(SampleEmbeddingHash.paper.in_(old_paper_ids))
                cleanup_stats['unused_sample_hashes'] = unused_sample_hashes.count()
                
                if cleanup_stats['unused_sample_hashes'] > 0:
                    SampleEmbeddingHash.delete().where(SampleEmbeddingHash.paper.in_(old_paper_ids)).execute()
            
            total_cleaned = sum(cleanup_stats.values())
            logger.info(f"🧹 Cleaned up {total_cleaned} unused hash records (older than {months_threshold} months)")
            
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup unused hashes: {e}")
            return {
                'unused_file_hashes': 0,
                'unused_content_hashes': 0,
                'unused_sample_hashes': 0
            }
    
    def cleanup_all_hashes(self, months_threshold: int = 6, detection_logs_days: int = 90) -> Dict[str, any]:
        """
        Perform comprehensive cleanup of all hash data
        
        Args:
            months_threshold: Number of months for unused hash cleanup
            detection_logs_days: Number of days to keep detection logs
            
        Returns:
            Dict: Comprehensive cleanup statistics
        """
        try:
            logger.info("🧹 Starting comprehensive hash cleanup...")
            
            # Step 1: Clean up orphaned hashes
            logger.info("Step 1: Cleaning orphaned hashes...")
            orphaned_stats = self.cleanup_orphaned_hashes()
            
            # Step 2: Clean up duplicate hashes
            logger.info("Step 2: Cleaning duplicate hashes...")
            duplicate_stats = self.cleanup_duplicate_hashes()
            
            # Step 3: Clean up unused hashes
            logger.info(f"Step 3: Cleaning unused hashes (older than {months_threshold} months)...")
            unused_stats = self.cleanup_unused_hashes(months_threshold)
            
            # Step 4: Clean up old detection logs
            logger.info(f"Step 4: Cleaning old detection logs (older than {detection_logs_days} days)...")
            old_logs_cleaned = self.cleanup_old_detection_logs(detection_logs_days)
            
            # Calculate totals
            total_orphaned = sum(orphaned_stats.values())
            total_duplicates = sum(duplicate_stats.values())
            total_unused = sum(unused_stats.values())
            total_cleaned = total_orphaned + total_duplicates + total_unused + old_logs_cleaned
            
            cleanup_summary = {
                'success': True,
                'total_records_cleaned': total_cleaned,
                'orphaned_hashes': orphaned_stats,
                'duplicate_hashes': duplicate_stats,
                'unused_hashes': unused_stats,
                'old_detection_logs': old_logs_cleaned,
                'cleanup_completed_at': datetime.now().isoformat()
            }
            
            logger.info(f"✅ Comprehensive cleanup completed: {total_cleaned} records cleaned")
            
            return cleanup_summary
            
        except Exception as e:
            logger.error(f"Comprehensive cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'total_records_cleaned': 0
            }


# Global instance
_duplicate_detector = None

def get_duplicate_detector() -> DuplicateDetector:
    """
    Get global duplicate detector instance (singleton)
    
    Returns:
        DuplicateDetector: Global detector instance
    """
    global _duplicate_detector
    
    if _duplicate_detector is None:
        _duplicate_detector = DuplicateDetector()
    
    return _duplicate_detector