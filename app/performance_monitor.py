"""
Performance monitoring system for RefServer
Tracks job processing metrics, resource usage, and system performance
"""

import os
import time
import psutil
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


@dataclass
class JobMetrics:
    """Metrics for a single job processing"""
    job_id: str
    filename: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    
    # Step-level metrics
    steps_completed: List[str] = None
    steps_failed: List[str] = None
    step_durations: Dict[str, float] = None
    
    # Resource usage during processing
    peak_memory_mb: Optional[float] = None
    peak_cpu_percent: Optional[float] = None
    disk_io_read_mb: Optional[float] = None
    disk_io_write_mb: Optional[float] = None
    
    # Processing details
    file_size_mb: Optional[float] = None
    page_count: Optional[int] = None
    ocr_quality_score: Optional[float] = None
    embedding_dimension: Optional[int] = None
    
    def __post_init__(self):
        if self.steps_completed is None:
            self.steps_completed = []
        if self.steps_failed is None:
            self.steps_failed = []
        if self.step_durations is None:
            self.step_durations = {}
    
    def mark_completed(self, end_time: float = None):
        """Mark job as completed and calculate duration"""
        self.end_time = end_time or time.time()
        self.duration = self.end_time - self.start_time
        
    def mark_failed(self, error_message: str, end_time: float = None):
        """Mark job as failed"""
        self.success = False
        self.error_message = error_message
        self.mark_completed(end_time)
    
    def add_step_duration(self, step: str, duration: float):
        """Add duration for a processing step"""
        self.step_durations[step] = duration
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class SystemMetrics:
    """System resource metrics at a point in time"""
    timestamp: float
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    disk_free_mb: float
    active_jobs: int
    load_average: Optional[float] = None  # Unix only
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system
    """
    
    def __init__(self, 
                 metrics_retention_hours: int = 24,
                 system_metrics_interval: int = 30,
                 max_job_metrics: int = 1000):
        """
        Initialize performance monitor
        
        Args:
            metrics_retention_hours: How long to keep metrics data
            system_metrics_interval: Interval for system metrics collection (seconds)
            max_job_metrics: Maximum number of job metrics to retain
        """
        self.metrics_retention_hours = metrics_retention_hours
        self.system_metrics_interval = system_metrics_interval
        self.max_job_metrics = max_job_metrics
        
        # Job metrics storage
        self.job_metrics: Dict[str, JobMetrics] = {}
        self.completed_jobs: deque = deque(maxlen=max_job_metrics)
        
        # System metrics storage (time-series)
        self.system_metrics: deque = deque(maxlen=2880)  # 24h at 30s intervals
        
        # Active job tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self._job_lock = threading.Lock()
        
        # System monitoring thread
        self._monitoring_thread = None
        self._stop_monitoring = threading.Event()
        
        # Performance statistics cache
        self._stats_cache = {}
        self._stats_cache_time = 0
        self._stats_cache_ttl = 60  # Cache for 60 seconds
        
        logger.info(f"Performance monitor initialized: retention={metrics_retention_hours}h, "
                   f"interval={system_metrics_interval}s, max_jobs={max_job_metrics}")
    
    def start_monitoring(self):
        """Start system metrics collection"""
        if self._monitoring_thread is None or not self._monitoring_thread.is_alive():
            self._stop_monitoring.clear()
            self._monitoring_thread = threading.Thread(
                target=self._collect_system_metrics,
                daemon=True
            )
            self._monitoring_thread.start()
            logger.info("Performance monitoring started")
    
    def stop_monitoring(self):
        """Stop system metrics collection"""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5)
            logger.info("Performance monitoring stopped")
    
    def start_job_tracking(self, job_id: str, filename: str, file_size_mb: float = None) -> JobMetrics:
        """
        Start tracking metrics for a new job
        
        Args:
            job_id: Unique job identifier
            filename: Name of the file being processed
            file_size_mb: File size in MB
            
        Returns:
            JobMetrics: Job metrics object for tracking
        """
        with self._job_lock:
            metrics = JobMetrics(
                job_id=job_id,
                filename=filename,
                start_time=time.time(),
                file_size_mb=file_size_mb
            )
            
            self.job_metrics[job_id] = metrics
            self.active_jobs[job_id] = {
                'start_time': metrics.start_time,
                'filename': filename,
                'current_step': 'initializing'
            }
            
            logger.debug(f"Started tracking job {job_id}: {filename}")
            return metrics
    
    def update_job_step(self, job_id: str, step: str, start_time: float = None):
        """Update current step for a job"""
        with self._job_lock:
            if job_id in self.active_jobs:
                # Record duration of previous step if available
                if 'step_start_time' in self.active_jobs[job_id]:
                    prev_step = self.active_jobs[job_id].get('current_step')
                    if prev_step and prev_step != 'initializing':
                        duration = time.time() - self.active_jobs[job_id]['step_start_time']
                        if job_id in self.job_metrics:
                            self.job_metrics[job_id].add_step_duration(prev_step, duration)
                
                # Update to new step
                self.active_jobs[job_id]['current_step'] = step
                self.active_jobs[job_id]['step_start_time'] = start_time or time.time()
    
    def complete_job(self, job_id: str, 
                    success: bool = True, 
                    error_message: str = None,
                    result: Dict[str, Any] = None):
        """
        Mark job as completed and finalize metrics
        
        Args:
            job_id: Job identifier
            success: Whether job completed successfully
            error_message: Error message if failed
            result: Processing result with additional metrics
        """
        with self._job_lock:
            if job_id not in self.job_metrics:
                logger.warning(f"Job {job_id} not found in metrics tracking")
                return
            
            metrics = self.job_metrics[job_id]
            
            # Mark completion
            if success:
                metrics.mark_completed()
            else:
                metrics.mark_failed(error_message or "Unknown error")
            
            # Extract additional metrics from result
            if result:
                self._extract_metrics_from_result(metrics, result)
            
            # Record resource usage peaks
            self._record_resource_peaks(metrics)
            
            # Move to completed jobs
            self.completed_jobs.append(metrics)
            
            # Clean up active tracking
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            # Remove from active metrics (keep in completed_jobs)
            del self.job_metrics[job_id]
            
            logger.info(f"Job {job_id} completed: success={success}, "
                       f"duration={metrics.duration:.2f}s")
    
    def _extract_metrics_from_result(self, metrics: JobMetrics, result: Dict[str, Any]):
        """Extract additional metrics from processing result"""
        try:
            # Steps information
            if 'steps_completed' in result:
                metrics.steps_completed = result['steps_completed']
            if 'steps_failed' in result:
                metrics.steps_failed = result['steps_failed']
            
            # Processing details
            data = result.get('data', {})
            if 'page_count' in data:
                metrics.page_count = data['page_count']
            if 'ocr_quality_score' in data:
                metrics.ocr_quality_score = data['ocr_quality_score']
            if 'embedding_dimension' in data:
                metrics.embedding_dimension = data['embedding_dimension']
                
        except Exception as e:
            logger.error(f"Error extracting metrics from result: {e}")
    
    def _record_resource_peaks(self, metrics: JobMetrics):
        """Record peak resource usage during job processing"""
        try:
            # Get current resource usage as peak (simplified)
            process = psutil.Process()
            metrics.peak_memory_mb = process.memory_info().rss / 1024 / 1024
            metrics.peak_cpu_percent = process.cpu_percent()
            
            # Disk I/O (simplified - current session)
            io_counters = process.io_counters()
            if io_counters:
                metrics.disk_io_read_mb = io_counters.read_bytes / 1024 / 1024
                metrics.disk_io_write_mb = io_counters.write_bytes / 1024 / 1024
                
        except Exception as e:
            logger.debug(f"Error recording resource peaks: {e}")
    
    def _collect_system_metrics(self):
        """Background thread for collecting system metrics"""
        logger.info("System metrics collection thread started")
        
        while not self._stop_monitoring.wait(self.system_metrics_interval):
            try:
                # CPU and memory
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                # Disk usage
                disk = psutil.disk_usage('/')
                
                # Load average (Unix only)
                load_avg = None
                if hasattr(os, 'getloadavg'):
                    load_avg = os.getloadavg()[0]  # 1-minute load average
                
                # Create metrics record
                metrics = SystemMetrics(
                    timestamp=time.time(),
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_used_mb=memory.used / 1024 / 1024,
                    memory_available_mb=memory.available / 1024 / 1024,
                    disk_usage_percent=disk.percent,
                    disk_free_mb=disk.free / 1024 / 1024,
                    active_jobs=len(self.active_jobs),
                    load_average=load_avg
                )
                
                self.system_metrics.append(metrics)
                
                # Clean old metrics
                self._cleanup_old_metrics()
                
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
        
        logger.info("System metrics collection thread stopped")
    
    def _cleanup_old_metrics(self):
        """Remove old metrics beyond retention period"""
        cutoff_time = time.time() - (self.metrics_retention_hours * 3600)
        
        # Clean system metrics
        while (self.system_metrics and 
               self.system_metrics[0].timestamp < cutoff_time):
            self.system_metrics.popleft()
    
    def get_performance_stats(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get comprehensive performance statistics
        
        Args:
            force_refresh: Force recalculation of cached stats
            
        Returns:
            Dict containing performance statistics
        """
        current_time = time.time()
        
        # Return cached stats if recent enough
        if (not force_refresh and 
            self._stats_cache and 
            current_time - self._stats_cache_time < self._stats_cache_ttl):
            return self._stats_cache
        
        stats = self._calculate_performance_stats()
        
        # Cache the results
        self._stats_cache = stats
        self._stats_cache_time = current_time
        
        return stats
    
    def _calculate_performance_stats(self) -> Dict[str, Any]:
        """Calculate comprehensive performance statistics"""
        try:
            # Time windows for analysis
            now = time.time()
            hour_ago = now - 3600
            day_ago = now - 86400
            
            # Job statistics
            all_completed = list(self.completed_jobs)
            recent_jobs = [j for j in all_completed if j.start_time > hour_ago]
            today_jobs = [j for j in all_completed if j.start_time > day_ago]
            
            job_stats = {
                'total_completed': len(all_completed),
                'completed_last_hour': len(recent_jobs),
                'completed_today': len(today_jobs),
                'currently_active': len(self.active_jobs),
                'success_rate_overall': self._calculate_success_rate(all_completed),
                'success_rate_last_hour': self._calculate_success_rate(recent_jobs),
                'success_rate_today': self._calculate_success_rate(today_jobs)
            }
            
            # Performance metrics
            performance_stats = {
                'average_duration_seconds': self._calculate_average_duration(all_completed),
                'average_duration_last_hour': self._calculate_average_duration(recent_jobs),
                'median_duration_seconds': self._calculate_median_duration(all_completed),
                'fastest_job_seconds': self._calculate_fastest_job(all_completed),
                'slowest_job_seconds': self._calculate_slowest_job(all_completed)
            }
            
            # Step analysis
            step_stats = self._analyze_step_performance(all_completed)
            
            # Resource usage
            resource_stats = self._analyze_resource_usage()
            
            # System health
            system_health = self._calculate_system_health()
            
            # Error analysis
            error_stats = self._analyze_errors(today_jobs)
            
            return {
                'timestamp': now,
                'jobs': job_stats,
                'performance': performance_stats,
                'steps': step_stats,
                'resources': resource_stats,
                'system': system_health,
                'errors': error_stats,
                'active_jobs_details': self._get_active_jobs_details()
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance stats: {e}")
            return {'error': str(e), 'timestamp': time.time()}
    
    def _calculate_success_rate(self, jobs: List[JobMetrics]) -> float:
        """Calculate success rate for a list of jobs"""
        if not jobs:
            return 0.0
        successful = sum(1 for job in jobs if job.success)
        return (successful / len(jobs)) * 100.0
    
    def _calculate_average_duration(self, jobs: List[JobMetrics]) -> float:
        """Calculate average duration for completed jobs"""
        completed = [job for job in jobs if job.duration is not None]
        if not completed:
            return 0.0
        return sum(job.duration for job in completed) / len(completed)
    
    def _calculate_median_duration(self, jobs: List[JobMetrics]) -> float:
        """Calculate median duration for completed jobs"""
        completed = [job for job in jobs if job.duration is not None]
        if not completed:
            return 0.0
        durations = sorted(job.duration for job in completed)
        n = len(durations)
        if n % 2 == 0:
            return (durations[n//2 - 1] + durations[n//2]) / 2.0
        else:
            return durations[n//2]
    
    def _calculate_fastest_job(self, jobs: List[JobMetrics]) -> Optional[float]:
        """Find fastest job duration"""
        completed = [job for job in jobs if job.duration is not None]
        if not completed:
            return None
        return min(job.duration for job in completed)
    
    def _calculate_slowest_job(self, jobs: List[JobMetrics]) -> Optional[float]:
        """Find slowest job duration"""
        completed = [job for job in jobs if job.duration is not None]
        if not completed:
            return None
        return max(job.duration for job in completed)
    
    def _analyze_step_performance(self, jobs: List[JobMetrics]) -> Dict[str, Any]:
        """Analyze performance of individual processing steps"""
        step_durations = defaultdict(list)
        step_failures = defaultdict(int)
        step_successes = defaultdict(int)
        
        for job in jobs:
            # Collect step durations
            for step, duration in job.step_durations.items():
                step_durations[step].append(duration)
                step_successes[step] += 1
            
            # Count step failures
            for step in job.steps_failed:
                step_failures[step] += 1
        
        step_stats = {}
        for step in step_durations:
            durations = step_durations[step]
            step_stats[step] = {
                'average_duration': sum(durations) / len(durations),
                'min_duration': min(durations),
                'max_duration': max(durations),
                'success_count': step_successes[step],
                'failure_count': step_failures[step],
                'success_rate': (step_successes[step] / 
                               (step_successes[step] + step_failures[step])) * 100.0
            }
        
        return step_stats
    
    def _analyze_resource_usage(self) -> Dict[str, Any]:
        """Analyze system resource usage patterns"""
        if not self.system_metrics:
            return {}
        
        recent_metrics = [m for m in self.system_metrics 
                         if m.timestamp > time.time() - 3600]
        
        if not recent_metrics:
            return {}
        
        return {
            'cpu_usage': {
                'current': recent_metrics[-1].cpu_percent,
                'average_1h': sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics),
                'peak_1h': max(m.cpu_percent for m in recent_metrics)
            },
            'memory_usage': {
                'current_percent': recent_metrics[-1].memory_percent,
                'current_used_mb': recent_metrics[-1].memory_used_mb,
                'average_percent_1h': sum(m.memory_percent for m in recent_metrics) / len(recent_metrics),
                'peak_percent_1h': max(m.memory_percent for m in recent_metrics)
            },
            'disk_usage': {
                'current_percent': recent_metrics[-1].disk_usage_percent,
                'free_mb': recent_metrics[-1].disk_free_mb
            }
        }
    
    def _calculate_system_health(self) -> Dict[str, Any]:
        """Calculate overall system health indicators"""
        if not self.system_metrics:
            return {'status': 'unknown'}
        
        latest = self.system_metrics[-1]
        
        # Health scoring (0-100)
        cpu_health = max(0, 100 - latest.cpu_percent)
        memory_health = max(0, 100 - latest.memory_percent)
        disk_health = max(0, 100 - latest.disk_usage_percent)
        
        overall_health = (cpu_health + memory_health + disk_health) / 3
        
        # Determine status
        if overall_health >= 80:
            status = 'excellent'
        elif overall_health >= 60:
            status = 'good'
        elif overall_health >= 40:
            status = 'warning'
        else:
            status = 'critical'
        
        return {
            'status': status,
            'overall_score': overall_health,
            'cpu_health': cpu_health,
            'memory_health': memory_health,
            'disk_health': disk_health,
            'active_jobs': len(self.active_jobs)
        }
    
    def _analyze_errors(self, jobs: List[JobMetrics]) -> Dict[str, Any]:
        """Analyze error patterns"""
        failed_jobs = [job for job in jobs if not job.success]
        
        if not failed_jobs:
            return {'total_errors': 0, 'error_rate': 0.0}
        
        # Count error types
        error_types = defaultdict(int)
        for job in failed_jobs:
            if job.error_message:
                # Categorize errors
                error_msg = job.error_message.lower()
                if 'timeout' in error_msg:
                    error_types['timeout'] += 1
                elif 'connection' in error_msg or 'network' in error_msg:
                    error_types['network'] += 1
                elif 'memory' in error_msg or 'oom' in error_msg:
                    error_types['memory'] += 1
                elif 'permission' in error_msg or 'access' in error_msg:
                    error_types['permission'] += 1
                else:
                    error_types['other'] += 1
        
        return {
            'total_errors': len(failed_jobs),
            'error_rate': (len(failed_jobs) / len(jobs)) * 100.0 if jobs else 0.0,
            'error_types': dict(error_types)
        }
    
    def _get_active_jobs_details(self) -> List[Dict[str, Any]]:
        """Get details of currently active jobs"""
        details = []
        current_time = time.time()
        
        for job_id, info in self.active_jobs.items():
            runtime = current_time - info['start_time']
            details.append({
                'job_id': job_id,
                'filename': info['filename'],
                'current_step': info['current_step'],
                'runtime_seconds': runtime,
                'start_time': info['start_time']
            })
        
        return sorted(details, key=lambda x: x['start_time'])
    
    def export_metrics(self, format: str = 'json') -> str:
        """
        Export metrics data in specified format
        
        Args:
            format: Export format ('json' or 'csv')
            
        Returns:
            str: Exported data
        """
        if format == 'json':
            return self._export_json()
        elif format == 'csv':
            return self._export_csv()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _export_json(self) -> str:
        """Export metrics as JSON"""
        data = {
            'export_timestamp': time.time(),
            'completed_jobs': [job.to_dict() for job in self.completed_jobs],
            'system_metrics': [metrics.to_dict() for metrics in self.system_metrics],
            'performance_stats': self.get_performance_stats()
        }
        return json.dumps(data, indent=2, default=str)
    
    def _export_csv(self) -> str:
        """Export job metrics as CSV"""
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'job_id', 'filename', 'start_time', 'duration', 'success',
            'file_size_mb', 'page_count', 'ocr_quality_score',
            'steps_completed', 'steps_failed', 'error_message'
        ])
        
        # Write job data
        for job in self.completed_jobs:
            writer.writerow([
                job.job_id,
                job.filename,
                datetime.fromtimestamp(job.start_time).isoformat(),
                job.duration,
                job.success,
                job.file_size_mb,
                job.page_count,
                job.ocr_quality_score,
                '|'.join(job.steps_completed),
                '|'.join(job.steps_failed),
                job.error_message
            ])
        
        return output.getvalue()


# Global performance monitor instance
_performance_monitor = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance (singleton)"""
    global _performance_monitor
    
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
        _performance_monitor.start_monitoring()
    
    return _performance_monitor


def track_job_performance(job_id: str, filename: str, file_size_mb: float = None) -> JobMetrics:
    """Start tracking performance for a job"""
    monitor = get_performance_monitor()
    return monitor.start_job_tracking(job_id, filename, file_size_mb)


def complete_job_tracking(job_id: str, success: bool = True, 
                         error_message: str = None, result: Dict[str, Any] = None):
    """Complete performance tracking for a job"""
    monitor = get_performance_monitor()
    monitor.complete_job(job_id, success, error_message, result)


def update_job_step_tracking(job_id: str, step: str):
    """Update current processing step for a job"""
    monitor = get_performance_monitor()
    monitor.update_job_step(job_id, step)


def get_system_performance_stats() -> Dict[str, Any]:
    """Get current system performance statistics"""
    monitor = get_performance_monitor()
    return monitor.get_performance_stats()