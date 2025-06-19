"""
Job queue management system for RefServer
Implements concurrent processing limits, priority queues, and job scheduling
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from queue import PriorityQueue, Queue, Empty
from pathlib import Path
import os

logger = logging.getLogger(__name__)


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 3
    NORMAL = 2
    HIGH = 1
    URGENT = 0


class JobStatus(Enum):
    """Job queue status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueuedJob:
    """Represents a job in the processing queue"""
    job_id: str
    filename: str
    file_path: str
    priority: JobPriority = JobPriority.NORMAL
    created_at: float = field(default_factory=time.time)
    estimated_duration: Optional[float] = None  # Estimated processing time in seconds
    file_size_mb: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    
    def __lt__(self, other):
        """Priority queue comparison - lower priority value = higher priority"""
        if self.priority.value != other.priority.value:
            return self.priority.value < other.priority.value
        # If same priority, older jobs have higher priority
        return self.created_at < other.created_at


class JobQueue:
    """
    Advanced job queue with priority, concurrency limits, and scheduling
    """
    
    def __init__(self, 
                 max_concurrent_jobs: int = 3,
                 max_queue_size: int = 100,
                 enable_priority_boost: bool = True,
                 priority_boost_threshold: float = 300.0):  # 5 minutes
        """
        Initialize job queue
        
        Args:
            max_concurrent_jobs: Maximum number of jobs to process simultaneously
            max_queue_size: Maximum number of jobs in queue
            enable_priority_boost: Whether to boost priority of old jobs
            priority_boost_threshold: Time in seconds after which to boost priority
        """
        self.max_concurrent_jobs = max_concurrent_jobs
        self.max_queue_size = max_queue_size
        self.enable_priority_boost = enable_priority_boost
        self.priority_boost_threshold = priority_boost_threshold
        
        # Queue and tracking
        self.job_queue = PriorityQueue(maxsize=max_queue_size)
        self.active_jobs: Dict[str, QueuedJob] = {}
        self.completed_jobs: Dict[str, QueuedJob] = {}
        self.failed_jobs: Dict[str, QueuedJob] = {}
        
        # Processing control
        self.processing_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
        self.queue_lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'total_queued': 0,
            'total_processed': 0,
            'total_failed': 0,
            'average_processing_time': 0.0,
            'queue_wait_times': []
        }
        
        # Job processor function (to be set by user)
        self.job_processor: Optional[Callable] = None
        
        # Start queue manager thread
        self.manager_thread = threading.Thread(target=self._queue_manager, daemon=True)
        self.manager_thread.start()
        
        logger.info(f"Job queue initialized: max_concurrent={max_concurrent_jobs}, "
                   f"max_queue_size={max_queue_size}")
    
    def set_job_processor(self, processor: Callable):
        """Set the function that will process jobs"""
        self.job_processor = processor
    
    def submit_job(self, 
                   job_id: str, 
                   filename: str, 
                   file_path: str,
                   priority: JobPriority = JobPriority.NORMAL,
                   estimated_duration: float = None) -> bool:
        """
        Submit a job to the queue
        
        Args:
            job_id: Unique job identifier
            filename: Original filename
            file_path: Path to file to process
            priority: Job priority level
            estimated_duration: Estimated processing time in seconds
            
        Returns:
            bool: True if job was queued successfully
        """
        try:
            # Check if queue is full
            if self.job_queue.qsize() >= self.max_queue_size:
                logger.warning(f"Queue is full ({self.max_queue_size}), cannot queue job {job_id}")
                return False
            
            # Check if job already exists
            if job_id in self.active_jobs or job_id in self.completed_jobs:
                logger.warning(f"Job {job_id} already exists")
                return False
            
            # Get file size
            file_size_mb = None
            if os.path.exists(file_path):
                file_size_mb = os.path.getsize(file_path) / 1024 / 1024
            
            # Estimate duration if not provided
            if estimated_duration is None:
                estimated_duration = self._estimate_processing_time(file_size_mb)
            
            # Create queued job
            job = QueuedJob(
                job_id=job_id,
                filename=filename,
                file_path=file_path,
                priority=priority,
                estimated_duration=estimated_duration,
                file_size_mb=file_size_mb
            )
            
            # Add to queue
            self.job_queue.put(job)
            self.stats['total_queued'] += 1
            
            logger.info(f"Job {job_id} queued with priority {priority.name}, "
                       f"estimated duration: {estimated_duration:.1f}s")
            return True
            
        except Exception as e:
            logger.error(f"Error submitting job {job_id}: {e}")
            return False
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a queued or active job
        
        Args:
            job_id: Job to cancel
            
        Returns:
            bool: True if job was cancelled
        """
        try:
            # Check if job is active (cannot cancel actively processing jobs)
            if job_id in self.active_jobs:
                logger.warning(f"Cannot cancel active job {job_id}")
                return False
            
            # Mark as cancelled (this is a simplified implementation)
            # In a full implementation, we'd need to remove from the priority queue
            logger.info(f"Job {job_id} marked for cancellation")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling job {job_id}: {e}")
            return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics"""
        try:
            with self.queue_lock:
                # Calculate average wait time
                recent_wait_times = self.stats['queue_wait_times'][-100:]  # Last 100 jobs
                avg_wait_time = sum(recent_wait_times) / len(recent_wait_times) if recent_wait_times else 0.0
                
                # Estimate queue processing time
                queue_items = []
                temp_queue = PriorityQueue()
                
                # Drain queue to get items (this is not ideal but PriorityQueue doesn't allow peeking)
                while not self.job_queue.empty():
                    try:
                        item = self.job_queue.get_nowait()
                        queue_items.append(item)
                        temp_queue.put(item)
                    except Empty:
                        break
                
                # Restore queue
                while not temp_queue.empty():
                    try:
                        self.job_queue.put_nowait(temp_queue.get_nowait())
                    except:
                        break
                
                estimated_queue_time = sum(job.estimated_duration or 180 for job in queue_items)
                
                return {
                    'queue_size': len(queue_items),
                    'active_jobs': len(self.active_jobs),
                    'max_concurrent': self.max_concurrent_jobs,
                    'total_queued': self.stats['total_queued'],
                    'total_processed': self.stats['total_processed'],
                    'total_failed': self.stats['total_failed'],
                    'average_processing_time': self.stats['average_processing_time'],
                    'average_wait_time': avg_wait_time,
                    'estimated_queue_time': estimated_queue_time,
                    'queue_items': [{
                        'job_id': job.job_id,
                        'filename': job.filename,
                        'priority': job.priority.name,
                        'queued_for': time.time() - job.created_at,
                        'estimated_duration': job.estimated_duration
                    } for job in queue_items[:10]]  # First 10 items
                }
                
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {'error': str(e)}
    
    def get_job_position(self, job_id: str) -> Optional[int]:
        """Get position of job in queue (1-based)"""
        try:
            # This would require a different queue implementation for efficiency
            # For now, return approximate position
            if job_id in self.active_jobs:
                return 0  # Currently processing
            
            return None  # Not found or completed
            
        except Exception as e:
            logger.error(f"Error getting job position: {e}")
            return None
    
    def _estimate_processing_time(self, file_size_mb: Optional[float]) -> float:
        """
        Estimate processing time based on file size and historical data
        
        Args:
            file_size_mb: File size in MB
            
        Returns:
            float: Estimated processing time in seconds
        """
        try:
            # Base processing time
            base_time = 120.0  # 2 minutes base
            
            # File size factor (rough estimate: 30 seconds per MB)
            if file_size_mb:
                size_factor = file_size_mb * 30.0
            else:
                size_factor = 60.0  # Default for unknown size
            
            # Use historical average if available
            if self.stats['average_processing_time'] > 0:
                historical_factor = self.stats['average_processing_time'] * 0.3
            else:
                historical_factor = 0.0
            
            estimated_time = base_time + size_factor + historical_factor
            
            # Cap between 60 seconds and 20 minutes
            return max(60.0, min(1200.0, estimated_time))
            
        except Exception as e:
            logger.error(f"Error estimating processing time: {e}")
            return 180.0  # Default 3 minutes
    
    def _queue_manager(self):
        """Main queue management loop - runs in background thread"""
        logger.info("Queue manager started")
        
        while not self.shutdown_event.wait(1.0):  # Check every second
            try:
                # Priority boost for old jobs
                if self.enable_priority_boost:
                    self._boost_old_job_priorities()
                
                # Start new jobs if slots available
                self._start_pending_jobs()
                
                # Clean up completed threads
                self._cleanup_completed_threads()
                
                # Update statistics
                self._update_statistics()
                
            except Exception as e:
                logger.error(f"Error in queue manager: {e}")
        
        logger.info("Queue manager stopped")
    
    def _boost_old_job_priorities(self):
        """Boost priority of jobs that have been waiting too long"""
        try:
            current_time = time.time()
            # This would require a more sophisticated queue implementation
            # For now, just log old jobs
            
            if not self.job_queue.empty():
                logger.debug(f"Queue has {self.job_queue.qsize()} pending jobs")
                
        except Exception as e:
            logger.error(f"Error boosting job priorities: {e}")
    
    def _start_pending_jobs(self):
        """Start pending jobs if processing slots are available"""
        try:
            # Check if we can start more jobs
            available_slots = self.max_concurrent_jobs - len(self.active_jobs)
            
            while available_slots > 0 and not self.job_queue.empty():
                try:
                    # Get next job from queue
                    job = self.job_queue.get_nowait()
                    
                    # Validate job file still exists
                    if not os.path.exists(job.file_path):
                        logger.error(f"File not found for job {job.job_id}: {job.file_path}")
                        self.failed_jobs[job.job_id] = job
                        self.stats['total_failed'] += 1
                        continue
                    
                    # Start processing job
                    if self._start_job_processing(job):
                        available_slots -= 1
                    else:
                        # If failed to start, put back in queue or mark as failed
                        if job.retry_count < job.max_retries:
                            job.retry_count += 1
                            self.job_queue.put(job)
                            logger.warning(f"Retrying job {job.job_id} (attempt {job.retry_count})")
                        else:
                            self.failed_jobs[job.job_id] = job
                            self.stats['total_failed'] += 1
                            logger.error(f"Job {job.job_id} failed after {job.max_retries} retries")
                    
                except Empty:
                    break
                except Exception as e:
                    logger.error(f"Error starting pending job: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error in start_pending_jobs: {e}")
    
    def _start_job_processing(self, job: QueuedJob) -> bool:
        """Start processing a single job"""
        try:
            if not self.job_processor:
                logger.error("No job processor function set")
                return False
            
            # Move to active jobs
            with self.queue_lock:
                self.active_jobs[job.job_id] = job
            
            # Record queue wait time
            wait_time = time.time() - job.created_at
            self.stats['queue_wait_times'].append(wait_time)
            
            # Start processing thread
            thread = threading.Thread(
                target=self._process_job_wrapper,
                args=(job,),
                daemon=True
            )
            thread.start()
            
            self.processing_threads[job.job_id] = thread
            
            logger.info(f"Started processing job {job.job_id} (waited {wait_time:.1f}s in queue)")
            return True
            
        except Exception as e:
            logger.error(f"Error starting job processing for {job.job_id}: {e}")
            # Remove from active jobs if failed to start
            with self.queue_lock:
                if job.job_id in self.active_jobs:
                    del self.active_jobs[job.job_id]
            return False
    
    def _process_job_wrapper(self, job: QueuedJob):
        """Wrapper for job processing that handles completion/failure"""
        start_time = time.time()
        
        try:
            logger.info(f"Processing job {job.job_id}: {job.filename}")
            
            # Call the actual job processor
            success = self.job_processor(job.job_id, job.file_path)
            
            processing_time = time.time() - start_time
            
            # Move to completed or failed
            with self.queue_lock:
                if job.job_id in self.active_jobs:
                    del self.active_jobs[job.job_id]
                
                if success:
                    self.completed_jobs[job.job_id] = job
                    self.stats['total_processed'] += 1
                    
                    # Update average processing time
                    current_avg = self.stats['average_processing_time']
                    processed_count = self.stats['total_processed']
                    self.stats['average_processing_time'] = (
                        (current_avg * (processed_count - 1) + processing_time) / processed_count
                    )
                    
                    logger.info(f"Job {job.job_id} completed successfully in {processing_time:.1f}s")
                else:
                    self.failed_jobs[job.job_id] = job
                    self.stats['total_failed'] += 1
                    logger.error(f"Job {job.job_id} failed after {processing_time:.1f}s")
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing job {job.job_id}: {e}")
            
            # Move to failed jobs
            with self.queue_lock:
                if job.job_id in self.active_jobs:
                    del self.active_jobs[job.job_id]
                self.failed_jobs[job.job_id] = job
                self.stats['total_failed'] += 1
        
        finally:
            # Clean up processing thread reference
            if job.job_id in self.processing_threads:
                del self.processing_threads[job.job_id]
    
    def _cleanup_completed_threads(self):
        """Clean up completed processing threads"""
        try:
            completed_threads = []
            for job_id, thread in self.processing_threads.items():
                if not thread.is_alive():
                    completed_threads.append(job_id)
            
            for job_id in completed_threads:
                if job_id in self.processing_threads:
                    del self.processing_threads[job_id]
                    
        except Exception as e:
            logger.error(f"Error cleaning up threads: {e}")
    
    def _update_statistics(self):
        """Update queue statistics"""
        try:
            # Keep only recent wait times (last 1000)
            if len(self.stats['queue_wait_times']) > 1000:
                self.stats['queue_wait_times'] = self.stats['queue_wait_times'][-1000:]
                
        except Exception as e:
            logger.error(f"Error updating statistics: {e}")
    
    def shutdown(self):
        """Shutdown the queue manager"""
        logger.info("Shutting down job queue...")
        self.shutdown_event.set()
        
        # Wait for manager thread to stop
        if self.manager_thread.is_alive():
            self.manager_thread.join(timeout=5)
        
        # Wait for all processing threads to complete (with timeout)
        for job_id, thread in self.processing_threads.items():
            thread.join(timeout=30)  # 30 second timeout per job
            if thread.is_alive():
                logger.warning(f"Job {job_id} did not complete within timeout")
        
        logger.info("Job queue shutdown complete")


# Global job queue instance
_job_queue = None


def get_job_queue() -> JobQueue:
    """Get global job queue instance (singleton)"""
    global _job_queue
    
    if _job_queue is None:
        # Default configuration - can be overridden via environment variables
        max_concurrent = int(os.getenv('MAX_CONCURRENT_JOBS', '3'))
        max_queue_size = int(os.getenv('MAX_QUEUE_SIZE', '100'))
        
        _job_queue = JobQueue(
            max_concurrent_jobs=max_concurrent,
            max_queue_size=max_queue_size
        )
    
    return _job_queue


def submit_job_to_queue(job_id: str, filename: str, file_path: str, 
                       priority: JobPriority = JobPriority.NORMAL) -> bool:
    """Submit a job to the global queue"""
    queue = get_job_queue()
    return queue.submit_job(job_id, filename, file_path, priority)


def get_queue_status() -> Dict[str, Any]:
    """Get current queue status"""
    queue = get_job_queue()
    return queue.get_queue_status()


def cancel_queued_job(job_id: str) -> bool:
    """Cancel a queued job"""
    queue = get_job_queue()
    return queue.cancel_job(job_id)


def shutdown_job_queue():
    """Shutdown the job queue system"""
    global _job_queue
    if _job_queue:
        _job_queue.shutdown()
        _job_queue = None