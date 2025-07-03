"""
Background PDF processing system
Handles asynchronous PDF processing jobs using FastAPI background tasks
"""

import os
import uuid
import logging
import asyncio
import datetime
from typing import Dict, Any, Optional
from fastapi import BackgroundTasks
from pathlib import Path

from models import ProcessingJob, Paper, db
from pipeline import PDFProcessingPipeline
from retry_utils import CircuitBreaker, RetryError
from performance_monitor import track_job_performance, complete_job_tracking, update_job_step_tracking
from job_queue import get_job_queue, JobPriority

logger = logging.getLogger(__name__)


class BackgroundProcessor:
    """Manages background PDF processing jobs"""
    
    def __init__(self):
        self.processor = PDFProcessingPipeline()
        self._active_jobs = {}  # job_id -> task info
        
        # Circuit breakers for external services
        self.ollama_circuit_breaker = CircuitBreaker(
            failure_threshold=3,
            reset_timeout=300.0,  # 5 minutes
            expected_exception=Exception
        )
        
        self.huridocs_circuit_breaker = CircuitBreaker(
            failure_threshold=2,
            reset_timeout=600.0,  # 10 minutes
            expected_exception=Exception
        )
        
        # Job queue integration
        self.job_queue = get_job_queue()
        # Set this processor as the job processor for the queue
        self.job_queue.set_job_processor(self._process_job_from_queue)
    
    def create_upload_job(self, filename: str, file_path: str) -> str:
        """
        Create a new processing job for uploaded PDF
        
        Args:
            filename: Original filename
            file_path: Path to uploaded file
            
        Returns:
            str: job_id for tracking
        """
        job_id = str(uuid.uuid4())
        
        try:
            # Create job record
            job = ProcessingJob.create(
                job_id=job_id,
                filename=filename,
                status='uploaded',
                current_step='uploaded',
                progress_percentage=0
            )
            
            logger.info(f"Created processing job {job_id} for file {filename}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create job for {filename}: {e}")
            raise
    
    def start_processing(self, job_id: str, file_path: str, background_tasks: BackgroundTasks):
        """
        Start background processing of uploaded PDF
        
        Args:
            job_id: Job identifier
            file_path: Path to uploaded PDF file
            background_tasks: FastAPI background tasks
        """
        try:
            # Update job status
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            job.status = 'processing'
            job.started_at = datetime.datetime.now()
            job.current_step = 'initializing'
            job.progress_percentage = 5
            job.save()
            
            # Add background task
            background_tasks.add_task(self._process_pdf_async, job_id, file_path)
            
            self._active_jobs[job_id] = {
                'status': 'processing',
                'started_at': job.started_at
            }
            
            logger.info(f"Started background processing for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to start processing for job {job_id}: {e}")
            self._mark_job_failed(job_id, f"Failed to start processing: {str(e)}")
    
    def submit_job_to_queue(self, job_id: str, filename: str, file_path: str, 
                           priority: JobPriority = JobPriority.NORMAL) -> bool:
        """
        Submit job to queue instead of immediate processing
        
        Args:
            job_id: Job identifier
            filename: Original filename
            file_path: Path to PDF file
            priority: Job priority level
            
        Returns:
            bool: True if job was queued successfully
        """
        try:
            # Update job status to queued
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            job.status = 'queued'
            job.current_step = 'queued'
            job.progress_percentage = 0
            job.save()
            
            # Submit to job queue
            success = self.job_queue.submit_job(job_id, filename, file_path, priority)
            
            if success:
                logger.info(f"Job {job_id} submitted to queue with priority {priority.name}")
            else:
                self._mark_job_failed(job_id, "Failed to submit to queue (queue may be full)")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to submit job {job_id} to queue: {e}")
            self._mark_job_failed(job_id, f"Queue submission failed: {str(e)}")
            return False
    
    def _process_job_from_queue(self, job_id: str, file_path: str) -> bool:
        """
        Process job from queue (called by JobQueue)
        
        Args:
            job_id: Job identifier
            file_path: Path to PDF file
            
        Returns:
            bool: True if processing succeeded
        """
        try:
            logger.info(f"Processing job {job_id} from queue")
            
            # Update job status
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            job.status = 'processing'
            job.started_at = datetime.datetime.now()
            job.current_step = 'initializing'
            job.progress_percentage = 5
            job.save()
            
            # Run the actual processing synchronously (we're already in a thread)
            result = self._run_synchronous_processing_from_queue(job, file_path)
            
            if result and result.get('success'):
                # Processing completed successfully
                job.status = 'completed'
                job.completed_at = datetime.datetime.now()
                job.current_step = 'completed'
                job.progress_percentage = 100
                job.set_result_summary(result)
                
                # Update steps completed/failed based on pipeline result
                if 'steps_completed' in result:
                    for step in result['steps_completed']:
                        job.add_completed_step(step)
                
                if 'steps_failed' in result:
                    for step in result['steps_failed']:
                        # Extract error message from warnings if available
                        error_msg = next((w for w in result.get('warnings', []) if step in w.lower()), f"{step} failed")
                        job.add_failed_step(step, error_msg)
                
                # Update GPU-intensive task pending status
                if result.get('data', {}).get('ocr_quality_pending'):
                    job.ocr_quality_pending = True
                if result.get('data', {}).get('layout_pending'):
                    job.layout_pending = True
                if result.get('data', {}).get('metadata_llm_pending'):
                    job.metadata_llm_pending = True
                
                # Link to created paper if available
                if result.get('doc_id'):
                    try:
                        paper = Paper.get(Paper.doc_id == result['doc_id'])
                        job.paper = paper
                    except Paper.DoesNotExist:
                        pass
                
                job.save()
                
                # Complete performance tracking
                complete_job_tracking(job_id, success=True, result=result)
                
                logger.info(f"Queue job {job_id} completed successfully")
                return True
                
            else:
                # Processing failed
                error_msg = result.get('error', 'Unknown processing error') if result else 'Processing failed'
                self._mark_job_failed(job_id, error_msg)
                
                # Complete performance tracking with failure
                complete_job_tracking(job_id, success=False, error_message=error_msg, result=result)
                
                return False
                
        except Exception as e:
            logger.error(f"Error processing queue job {job_id}: {e}")
            error_msg = f"Processing error: {str(e)}"
            self._mark_job_failed(job_id, error_msg)
            
            # Complete performance tracking with error
            complete_job_tracking(job_id, success=False, error_message=error_msg)
            
            return False
    
    def _run_synchronous_processing_from_queue(self, job: ProcessingJob, file_path: str) -> Dict[str, Any]:
        """
        Run synchronous processing for a job from the queue
        Similar to _run_synchronous_processing but adapted for queue processing
        """
        try:
            # Start performance tracking
            file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
            performance_metrics = track_job_performance(job.job_id, job.filename, file_size)
            
            # Extract filename from job
            filename = os.path.basename(file_path)
            
            # Enhanced progress callback with circuit breaker status and performance tracking
            def enhanced_progress_callback(step, progress):
                # Update job progress
                try:
                    current_job = ProcessingJob.get(ProcessingJob.job_id == job.job_id)
                    current_job.current_step = step
                    current_job.progress_percentage = progress
                    current_job.save()
                except:
                    pass  # Ignore database errors during progress updates
                
                # Update performance tracking
                update_job_step_tracking(job.job_id, step)
                
                # Log circuit breaker status
                if step in ['quality_assessment', 'metadata_extraction']:
                    breaker_status = f"Ollama CB: {self.ollama_circuit_breaker.state}"
                    logger.debug(f"Step {step}: {breaker_status}")
                elif step == 'layout_analysis':
                    breaker_status = f"Huridocs CB: {self.huridocs_circuit_breaker.state}"
                    logger.debug(f"Step {step}: {breaker_status}")
            
            # Check if GPU-intensive tasks should be skipped
            skip_gpu_intensive = os.environ.get('ENABLE_GPU_INTENSIVE_TASKS', 'true').lower() == 'false'
            
            # Use existing processor but with enhanced callbacks and service monitoring
            result = self.processor.process_pdf(
                file_path,
                filename=filename,
                progress_callback=enhanced_progress_callback,
                skip_gpu_intensive=skip_gpu_intensive
            )
            
            # Monitor service health and update circuit breakers based on result
            self._update_circuit_breakers_from_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in queue synchronous processing: {e}")
            # Check if this is a service failure that should trigger circuit breaker
            self._handle_processing_error(e)
            raise
    
    async def _process_pdf_async(self, job_id: str, file_path: str):
        """
        Asynchronous PDF processing function
        
        Args:
            job_id: Job identifier
            file_path: Path to PDF file
        """
        try:
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            logger.info(f"Starting async processing for job {job_id}")
            
            # Start performance tracking
            file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
            performance_metrics = track_job_performance(job_id, job.filename, file_size)
            
            # Processing steps with progress tracking
            steps = [
                ('ocr_processing', 'OCR and text extraction', 20),
                ('quality_assessment', 'OCR quality assessment', 35),
                ('embedding_generation', 'Generating embeddings', 50),
                ('layout_analysis', 'Layout analysis', 65),
                ('metadata_extraction', 'Metadata extraction', 80),
                ('database_storage', 'Saving to database', 95),
                ('finalization', 'Finalizing', 100)
            ]
            
            # Use the existing PDFProcessor with progress tracking
            result = await self._process_with_progress_tracking(job, file_path, steps)
            
            if result and result.get('success'):
                # Processing completed successfully
                job.status = 'completed'
                job.completed_at = datetime.datetime.now()
                job.current_step = 'completed'
                job.progress_percentage = 100
                job.set_result_summary(result)
                
                # Update steps completed/failed based on pipeline result
                if 'steps_completed' in result:
                    for step in result['steps_completed']:
                        job.add_completed_step(step)
                
                if 'steps_failed' in result:
                    for step in result['steps_failed']:
                        # Extract error message from warnings if available
                        error_msg = next((w for w in result.get('warnings', []) if step in w.lower()), f"{step} failed")
                        job.add_failed_step(step, error_msg)
                
                # Update GPU-intensive task pending status
                if result.get('data', {}).get('ocr_quality_pending'):
                    job.ocr_quality_pending = True
                if result.get('data', {}).get('layout_pending'):
                    job.layout_pending = True
                if result.get('data', {}).get('metadata_llm_pending'):
                    job.metadata_llm_pending = True
                
                # Link to created paper if available
                if result.get('doc_id'):
                    try:
                        paper = Paper.get(Paper.doc_id == result['doc_id'])
                        job.paper = paper
                    except Paper.DoesNotExist:
                        pass
                
                job.save()
                logger.info(f"Job {job_id} completed successfully with {len(result.get('steps_completed', []))} steps completed and {len(result.get('steps_failed', []))} steps failed")
                
                # Complete performance tracking
                complete_job_tracking(job_id, success=True, result=result)
                
            else:
                # Processing failed
                error_msg = result.get('error', 'Unknown processing error') if result else 'Processing failed'
                self._mark_job_failed(job_id, error_msg)
                
                # Complete performance tracking with failure
                complete_job_tracking(job_id, success=False, error_message=error_msg, result=result)
                
        except Exception as e:
            logger.error(f"Error in async processing for job {job_id}: {e}")
            error_msg = f"Processing error: {str(e)}"
            self._mark_job_failed(job_id, error_msg)
            
            # Complete performance tracking with error
            complete_job_tracking(job_id, success=False, error_message=error_msg)
        
        finally:
            # Clean up
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    async def _process_with_progress_tracking(self, job: ProcessingJob, file_path: str, steps: list) -> Dict[str, Any]:
        """
        Process PDF with detailed progress tracking
        
        Args:
            job: ProcessingJob instance
            file_path: Path to PDF file
            steps: List of (step_name, description, progress_percentage) tuples
            
        Returns:
            Dict: Processing result
        """
        try:
            # Run the actual processing (this is synchronous)
            # We'll wrap it to run in thread pool for better async handling
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._run_synchronous_processing, 
                job, file_path, steps
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in progress tracking for job {job.job_id}: {e}")
            raise
    
    def _run_synchronous_processing(self, job: ProcessingJob, file_path: str, steps: list) -> Dict[str, Any]:
        """
        Run the synchronous processing with progress updates and enhanced error handling
        
        Args:
            job: ProcessingJob instance
            file_path: Path to PDF file
            steps: Progress steps
            
        Returns:
            Dict: Processing result
        """
        try:
            # Extract filename from job
            filename = os.path.basename(file_path)
            
            # Enhanced progress callback with circuit breaker status and performance tracking
            def enhanced_progress_callback(step, progress):
                self._update_job_progress(job, step, progress)
                
                # Update performance tracking
                update_job_step_tracking(job.job_id, step)
                
                # Log circuit breaker status
                if step in ['quality_assessment', 'metadata_extraction']:
                    breaker_status = f"Ollama CB: {self.ollama_circuit_breaker.state}"
                    logger.debug(f"Step {step}: {breaker_status}")
                elif step == 'layout_analysis':
                    breaker_status = f"Huridocs CB: {self.huridocs_circuit_breaker.state}"
                    logger.debug(f"Step {step}: {breaker_status}")
            
            # Check if GPU-intensive tasks should be skipped
            skip_gpu_intensive = os.environ.get('ENABLE_GPU_INTENSIVE_TASKS', 'true').lower() == 'false'
            
            # Use existing processor but with enhanced callbacks and service monitoring
            result = self.processor.process_pdf(
                file_path,
                filename=filename,
                progress_callback=enhanced_progress_callback,
                skip_gpu_intensive=skip_gpu_intensive
            )
            
            # Monitor service health and update circuit breakers based on result
            self._update_circuit_breakers_from_result(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in synchronous processing: {e}")
            # Check if this is a service failure that should trigger circuit breaker
            self._handle_processing_error(e)
            raise
    
    def _update_circuit_breakers_from_result(self, result: Dict[str, Any]):
        """Update circuit breaker states based on processing result"""
        try:
            warnings = result.get('warnings', [])
            steps_failed = result.get('steps_failed', [])
            
            # Check for Ollama service issues
            ollama_issues = any('ollama' in str(w).lower() or 'llm' in str(w).lower() 
                             for w in warnings)
            if 'quality_assessment' in steps_failed or 'metadata_extraction' in steps_failed or ollama_issues:
                logger.warning("Ollama service issues detected, updating circuit breaker")
                # Circuit breaker will be updated automatically by the service calls
            
            # Check for Huridocs service issues  
            huridocs_issues = any('huridocs' in str(w).lower() or 'layout' in str(w).lower() 
                                for w in warnings)
            if 'layout_analysis' in steps_failed or huridocs_issues:
                logger.warning("Huridocs service issues detected, updating circuit breaker")
                # Circuit breaker will be updated automatically by the service calls
                
        except Exception as e:
            logger.error(f"Error updating circuit breakers: {e}")
    
    def _handle_processing_error(self, error: Exception):
        """Handle processing errors and update circuit breakers if needed"""
        try:
            error_str = str(error).lower()
            
            # Check for network/service errors that should trigger circuit breakers
            if any(keyword in error_str for keyword in ['connection', 'timeout', 'network', 'unreachable']):
                if 'ollama' in error_str or 'llm' in error_str:
                    logger.warning(f"Ollama service error detected: {error}")
                elif 'huridocs' in error_str or 'layout' in error_str:
                    logger.warning(f"Huridocs service error detected: {error}")
                    
        except Exception as e:
            logger.error(f"Error handling processing error: {e}")
    
    def _update_job_progress(self, job: ProcessingJob, step_name: str, progress: int):
        """Update job progress in database"""
        try:
            # Refresh job from database
            job = ProcessingJob.get(ProcessingJob.job_id == job.job_id)
            job.current_step = step_name
            job.progress_percentage = progress
            job.save()
            
        except Exception as e:
            logger.error(f"Failed to update job progress: {e}")
    
    def _mark_job_failed(self, job_id: str, error_message: str):
        """Mark job as failed with error message"""
        try:
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            job.status = 'failed'
            job.completed_at = datetime.datetime.now()
            job.error_message = error_message
            job.save()
            
            logger.error(f"Job {job_id} marked as failed: {error_message}")
            
        except Exception as e:
            logger.error(f"Failed to mark job {job_id} as failed: {e}")
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current status of a processing job
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dict: Job status information or None if not found
        """
        try:
            job = ProcessingJob.get(ProcessingJob.job_id == job_id)
            
            return {
                'job_id': job.job_id,
                'filename': job.filename,
                'status': job.status,
                'current_step': job.current_step,
                'progress_percentage': job.progress_percentage,
                'steps_completed': job.get_steps_completed(),
                'steps_failed': job.get_steps_failed(),
                'error_message': job.error_message,
                'result_summary': job.get_result_summary(),
                'created_at': job.created_at.isoformat() if job.created_at else None,
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'paper_id': job.paper.doc_id if job.paper else None
            }
            
        except ProcessingJob.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None
    
    def cleanup_old_jobs(self, days_old: int = 7):
        """
        Clean up old completed/failed jobs
        
        Args:
            days_old: Remove jobs older than this many days
        """
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_old)
            
            # Delete old completed/failed jobs
            deleted = (ProcessingJob
                      .delete()
                      .where(
                          (ProcessingJob.status.in_(['completed', 'failed'])) &
                          (ProcessingJob.created_at < cutoff_date)
                      )
                      .execute())
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old processing jobs")
                
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {e}")


# Global processor instance
background_processor = BackgroundProcessor()


def get_background_processor() -> BackgroundProcessor:
    """Get the global background processor instance"""
    return background_processor