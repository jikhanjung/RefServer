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

logger = logging.getLogger(__name__)


class BackgroundProcessor:
    """Manages background PDF processing jobs"""
    
    def __init__(self):
        self.processor = PDFProcessingPipeline()
        self._active_jobs = {}  # job_id -> task info
    
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
                
                # Link to created paper if available
                if result.get('doc_id'):
                    try:
                        paper = Paper.get(Paper.doc_id == result['doc_id'])
                        job.paper = paper
                    except Paper.DoesNotExist:
                        pass
                
                job.save()
                logger.info(f"Job {job_id} completed successfully with {len(result.get('steps_completed', []))} steps completed and {len(result.get('steps_failed', []))} steps failed")
                
            else:
                # Processing failed
                error_msg = result.get('error', 'Unknown processing error') if result else 'Processing failed'
                self._mark_job_failed(job_id, error_msg)
                
        except Exception as e:
            logger.error(f"Error in async processing for job {job_id}: {e}")
            self._mark_job_failed(job_id, f"Processing error: {str(e)}")
        
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
        Run the synchronous processing with progress updates
        
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
            
            # Use existing processor but with progress callbacks
            result = self.processor.process_pdf(
                file_path,
                filename=filename,
                progress_callback=lambda step, progress: self._update_job_progress(job, step, progress)
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error in synchronous processing: {e}")
            raise
    
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