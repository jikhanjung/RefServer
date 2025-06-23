# RefServer Background Scheduler
# Automatic cleanup and maintenance tasks

import asyncio
import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any

from duplicate_detector import get_duplicate_detector

logger = logging.getLogger(__name__)

class BackgroundScheduler:
    """
    Background scheduler for automatic maintenance tasks
    """
    
    def __init__(self):
        """Initialize background scheduler"""
        self.running = False
        self.scheduler_thread = None
        self.last_cleanup = None
        logger.info("BackgroundScheduler initialized")
    
    def start(self):
        """Start the background scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        logger.info("🕒 Starting background scheduler...")
        
        # Schedule automatic cleanup tasks
        self._schedule_tasks()
        
        # Start scheduler in background thread
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("✅ Background scheduler started successfully")
    
    def stop(self):
        """Stop the background scheduler"""
        if not self.running:
            logger.warning("Scheduler is not running")
            return
        
        logger.info("🛑 Stopping background scheduler...")
        self.running = False
        
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        schedule.clear()
        logger.info("✅ Background scheduler stopped")
    
    def _schedule_tasks(self):
        """Schedule all background tasks"""
        
        # Daily cleanup at 2 AM
        schedule.every().day.at("02:00").do(self._daily_cleanup)
        
        # Weekly comprehensive cleanup on Sunday at 3 AM
        schedule.every().sunday.at("03:00").do(self._weekly_comprehensive_cleanup)
        
        # Monthly deep cleanup - check if it's the 1st day of the month at 4 AM
        schedule.every().day.at("04:00").do(self._check_monthly_cleanup)
        
        logger.info("📅 Scheduled background tasks:")
        logger.info("  - Daily cleanup: Every day at 2:00 AM")
        logger.info("  - Weekly comprehensive cleanup: Sundays at 3:00 AM")
        logger.info("  - Monthly deep cleanup: 1st day of month at 4:00 AM")
    
    def _run_scheduler(self):
        """Run the scheduler loop"""
        logger.info("📍 Scheduler loop started")
        
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _daily_cleanup(self):
        """Daily cleanup task - light maintenance"""
        try:
            logger.info("🧹 Starting daily cleanup...")
            start_time = datetime.now()
            
            detector = get_duplicate_detector()
            
            # Clean up orphaned hashes only
            orphaned_stats = detector.cleanup_orphaned_hashes()
            
            # Clean up old detection logs (90 days)
            old_logs_cleaned = detector.cleanup_old_detection_logs(90)
            
            # Calculate totals
            total_orphaned = sum(orphaned_stats.values())
            total_cleaned = total_orphaned + old_logs_cleaned
            
            duration = datetime.now() - start_time
            
            logger.info(f"✅ Daily cleanup completed in {duration.total_seconds():.1f}s")
            logger.info(f"   - Orphaned hashes: {total_orphaned}")
            logger.info(f"   - Old detection logs: {old_logs_cleaned}")
            logger.info(f"   - Total cleaned: {total_cleaned}")
            
            self.last_cleanup = {
                'type': 'daily',
                'timestamp': start_time.isoformat(),
                'duration_seconds': duration.total_seconds(),
                'total_cleaned': total_cleaned,
                'details': {
                    'orphaned_hashes': orphaned_stats,
                    'old_detection_logs': old_logs_cleaned
                }
            }
            
        except Exception as e:
            logger.error(f"Daily cleanup failed: {e}")
    
    def _weekly_comprehensive_cleanup(self):
        """Weekly comprehensive cleanup - includes duplicate cleanup"""
        try:
            logger.info("🧹 Starting weekly comprehensive cleanup...")
            start_time = datetime.now()
            
            detector = get_duplicate_detector()
            
            # Comprehensive cleanup (6 months threshold, 90 days logs)
            cleanup_summary = detector.cleanup_all_hashes(6, 90)
            
            duration = datetime.now() - start_time
            
            if cleanup_summary.get('success'):
                total_cleaned = cleanup_summary['total_records_cleaned']
                
                logger.info(f"✅ Weekly comprehensive cleanup completed in {duration.total_seconds():.1f}s")
                logger.info(f"   - Total records cleaned: {total_cleaned}")
                logger.info(f"   - Orphaned: {sum(cleanup_summary['orphaned_hashes'].values())}")
                logger.info(f"   - Duplicates: {sum(cleanup_summary['duplicate_hashes'].values())}")
                logger.info(f"   - Unused: {sum(cleanup_summary['unused_hashes'].values())}")
                logger.info(f"   - Old logs: {cleanup_summary['old_detection_logs']}")
                
                self.last_cleanup = {
                    'type': 'weekly_comprehensive',
                    'timestamp': start_time.isoformat(),
                    'duration_seconds': duration.total_seconds(),
                    'total_cleaned': total_cleaned,
                    'details': cleanup_summary
                }
            else:
                logger.error(f"Weekly comprehensive cleanup failed: {cleanup_summary.get('error')}")
            
        except Exception as e:
            logger.error(f"Weekly comprehensive cleanup failed: {e}")
    
    def _check_monthly_cleanup(self):
        """Check if today is the 1st day of month and run monthly cleanup"""
        today = datetime.now()
        if today.day == 1:
            self._monthly_deep_cleanup()
    
    def _monthly_deep_cleanup(self):
        """Monthly deep cleanup - aggressive cleanup with longer thresholds"""
        try:
            logger.info("🧹 Starting monthly deep cleanup...")
            start_time = datetime.now()
            
            detector = get_duplicate_detector()
            
            # Deep cleanup (12 months threshold, 180 days logs)
            cleanup_summary = detector.cleanup_all_hashes(12, 180)
            
            duration = datetime.now() - start_time
            
            if cleanup_summary.get('success'):
                total_cleaned = cleanup_summary['total_records_cleaned']
                
                logger.info(f"✅ Monthly deep cleanup completed in {duration.total_seconds():.1f}s")
                logger.info(f"   - Total records cleaned: {total_cleaned}")
                logger.info(f"   - Orphaned: {sum(cleanup_summary['orphaned_hashes'].values())}")
                logger.info(f"   - Duplicates: {sum(cleanup_summary['duplicate_hashes'].values())}")
                logger.info(f"   - Unused: {sum(cleanup_summary['unused_hashes'].values())}")
                logger.info(f"   - Old logs: {cleanup_summary['old_detection_logs']}")
                
                self.last_cleanup = {
                    'type': 'monthly_deep',
                    'timestamp': start_time.isoformat(),
                    'duration_seconds': duration.total_seconds(),
                    'total_cleaned': total_cleaned,
                    'details': cleanup_summary
                }
            else:
                logger.error(f"Monthly deep cleanup failed: {cleanup_summary.get('error')}")
            
        except Exception as e:
            logger.error(f"Monthly deep cleanup failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current scheduler status
        
        Returns:
            Dict: Scheduler status information
        """
        try:
            next_jobs = []
            for job in schedule.jobs:
                next_jobs.append({
                    'job': str(job.job_func),
                    'next_run': job.next_run.isoformat() if job.next_run else None,
                    'interval': str(job.interval) if hasattr(job, 'interval') else None
                })
            
            return {
                'running': self.running,
                'thread_alive': self.scheduler_thread.is_alive() if self.scheduler_thread else False,
                'scheduled_jobs': len(schedule.jobs),
                'next_jobs': next_jobs,
                'last_cleanup': self.last_cleanup
            }
            
        except Exception as e:
            logger.error(f"Failed to get scheduler status: {e}")
            return {
                'running': False,
                'error': str(e)
            }
    
    def force_cleanup(self, cleanup_type: str = 'comprehensive') -> Dict[str, Any]:
        """
        Force immediate cleanup execution
        
        Args:
            cleanup_type: Type of cleanup ('daily', 'weekly', 'monthly')
            
        Returns:
            Dict: Cleanup results
        """
        try:
            logger.info(f"🔧 Forcing {cleanup_type} cleanup...")
            
            if cleanup_type == 'daily':
                self._daily_cleanup()
            elif cleanup_type == 'weekly' or cleanup_type == 'comprehensive':
                self._weekly_comprehensive_cleanup()
            elif cleanup_type == 'monthly':
                self._monthly_deep_cleanup()
            else:
                raise ValueError(f"Unknown cleanup type: {cleanup_type}")
            
            return {
                'success': True,
                'cleanup_type': cleanup_type,
                'last_cleanup': self.last_cleanup
            }
            
        except Exception as e:
            logger.error(f"Forced cleanup failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


# Global scheduler instance
_background_scheduler = None

def get_background_scheduler() -> BackgroundScheduler:
    """
    Get global background scheduler instance (singleton)
    
    Returns:
        BackgroundScheduler: Global scheduler instance
    """
    global _background_scheduler
    
    if _background_scheduler is None:
        _background_scheduler = BackgroundScheduler()
    
    return _background_scheduler

def start_background_scheduler():
    """Start the background scheduler"""
    scheduler = get_background_scheduler()
    scheduler.start()

def stop_background_scheduler():
    """Stop the background scheduler"""
    scheduler = get_background_scheduler()
    scheduler.stop()