"""
Backup and restore system for RefServer
Handles SQLite database backups with scheduling and management
"""

import os
import sqlite3
import gzip
import json
import shutil
import hashlib
import io
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Literal
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import tarfile

logger = logging.getLogger("RefServerBackup")

BackupType = Literal["full", "incremental", "snapshot"]


class SQLiteBackupManager:
    """Manages SQLite database backups with scheduling and recovery capabilities"""
    
    def __init__(self, db_path: str, backup_dir: str = "/refdata/backups"):
        self.db_path = db_path
        self.backup_base_dir = Path(backup_dir)
        self.sqlite_backup_dir = self.backup_base_dir / "sqlite"
        self.metadata_dir = self.backup_base_dir / "metadata"
        
        # Create backup directories
        for subdir in ["daily", "weekly", "incremental", "snapshots"]:
            (self.sqlite_backup_dir / subdir).mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup history file
        self.history_file = self.metadata_dir / "backup_history.json"
        self.history = self._load_history()
        
        # Scheduler for automated backups
        self.scheduler = BackgroundScheduler()
        self._setup_scheduled_backups()
        
        logger.info(f"SQLiteBackupManager initialized with db_path={db_path}")
    
    def _load_history(self) -> List[Dict]:
        """Load backup history from JSON file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load backup history: {e}")
        return []
    
    def _save_history(self):
        """Save backup history to JSON file"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(self.history, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save backup history: {e}")
    
    def _add_to_history(self, backup_info: Dict):
        """Add backup record to history"""
        self.history.append(backup_info)
        # Keep only last 1000 records
        if len(self.history) > 1000:
            self.history = self.history[-1000:]
        self._save_history()
    
    def _setup_scheduled_backups(self):
        """Setup automated backup schedules"""
        # Daily full backup at 3 AM
        self.scheduler.add_job(
            func=lambda: self.create_backup("full", {"compress": True, "retention_days": 7}),
            trigger=CronTrigger(hour=3, minute=0),
            id="daily_full_backup",
            name="Daily Full Backup",
            replace_existing=True
        )
        
        # Weekly full backup on Sunday at 4 AM (longer retention)
        self.scheduler.add_job(
            func=lambda: self.create_backup("full", {"compress": True, "retention_days": 30, "is_weekly": True}),
            trigger=CronTrigger(day_of_week=6, hour=4, minute=0),
            id="weekly_full_backup",
            name="Weekly Full Backup",
            replace_existing=True
        )
        
        # Hourly incremental backup
        self.scheduler.add_job(
            func=lambda: self.create_backup("incremental", {"compress": True, "retention_days": 2}),
            trigger=IntervalTrigger(hours=1),
            id="hourly_incremental_backup",
            name="Hourly Incremental Backup",
            replace_existing=True
        )
        
        # Cleanup old backups daily
        self.scheduler.add_job(
            func=self.cleanup_old_backups,
            trigger=CronTrigger(hour=5, minute=0),
            id="cleanup_old_backups",
            name="Cleanup Old Backups",
            replace_existing=True
        )
        
        # Health check every hour
        self.scheduler.add_job(
            func=self._backup_health_check,
            trigger=IntervalTrigger(hours=1),
            id="backup_health_check",
            name="Backup Health Check",
            replace_existing=True
        )
        
        # Database consistency check daily
        self.scheduler.add_job(
            func=self._daily_consistency_check,
            trigger=CronTrigger(hour=6, minute=0),
            id="daily_consistency_check",
            name="Daily Consistency Check",
            replace_existing=True
        )
    
    def start_scheduler(self):
        """Start the backup scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Backup scheduler started")
    
    def stop_scheduler(self):
        """Stop the backup scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Backup scheduler stopped")
    
    def create_backup(self, backup_type: BackupType = "snapshot", 
                     options: Optional[Dict] = None) -> Dict:
        """
        Create a backup of the SQLite database
        
        Args:
            backup_type: Type of backup (full, incremental, snapshot)
            options: Backup options including compress, encrypt, description, retention_days
            
        Returns:
            Dictionary with backup details
        """
        options = options or {}
        compress = options.get("compress", True)
        description = options.get("description", "")
        retention_days = options.get("retention_days", 30)
        is_weekly = options.get("is_weekly", False)
        
        timestamp = datetime.now()
        backup_id = timestamp.strftime("%Y%m%d_%H%M%S")
        
        try:
            if backup_type == "full":
                backup_path = self._create_full_backup(timestamp, compress, is_weekly)
            elif backup_type == "incremental":
                backup_path = self._create_incremental_backup(timestamp, compress)
            elif backup_type == "snapshot":
                backup_path = self._create_snapshot_backup(timestamp, compress)
            else:
                raise ValueError(f"Invalid backup type: {backup_type}")
            
            # Verify backup integrity
            if not self._verify_backup(backup_path):
                raise Exception("Backup verification failed")
            
            # Calculate backup size
            backup_size = os.path.getsize(backup_path)
            
            # Create backup record
            backup_info = {
                "backup_id": backup_id,
                "type": backup_type,
                "path": str(backup_path),
                "timestamp": timestamp.isoformat(),
                "size_bytes": backup_size,
                "compressed": compress,
                "description": description,
                "retention_days": retention_days,
                "expire_date": (timestamp + timedelta(days=retention_days)).isoformat(),
                "checksum": self._calculate_checksum(backup_path),
                "status": "completed"
            }
            
            self._add_to_history(backup_info)
            logger.info(f"Backup created successfully: {backup_path}")
            
            return backup_info
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            error_info = {
                "backup_id": backup_id,
                "type": backup_type,
                "timestamp": timestamp.isoformat(),
                "status": "failed",
                "error": str(e)
            }
            self._add_to_history(error_info)
            raise
    
    def _create_full_backup(self, timestamp: datetime, compress: bool, is_weekly: bool) -> Path:
        """Create a full database backup"""
        subdir = "weekly" if is_weekly else "daily"
        filename = f"refserver_{timestamp.strftime('%Y-%m-%d')}_{'weekly' if is_weekly else 'daily'}.db"
        
        if compress:
            filename += ".gz"
            
        backup_path = self.sqlite_backup_dir / subdir / filename
        
        # Perform SQLite backup
        source_conn = sqlite3.connect(self.db_path)
        
        if compress:
            # Backup to temporary file first
            temp_path = backup_path.with_suffix('')
            dest_conn = sqlite3.connect(str(temp_path))
            source_conn.backup(dest_conn)
            dest_conn.close()
            
            # Compress the backup
            with open(temp_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove temporary file
            os.remove(temp_path)
        else:
            dest_conn = sqlite3.connect(str(backup_path))
            source_conn.backup(dest_conn)
            dest_conn.close()
        
        source_conn.close()
        return backup_path
    
    def _create_incremental_backup(self, timestamp: datetime, compress: bool) -> Path:
        """Create an incremental backup (WAL-based)"""
        filename = f"refserver_{timestamp.strftime('%Y%m%d_%H%M%S')}_incr.wal"
        if compress:
            filename += ".gz"
            
        backup_path = self.sqlite_backup_dir / "incremental" / filename
        
        # For now, create a snapshot (full implementation would use WAL)
        # This is a placeholder for proper incremental backup
        return self._create_snapshot_backup(timestamp, compress, subdir="incremental")
    
    def _create_snapshot_backup(self, timestamp: datetime, compress: bool, subdir: str = "snapshots") -> Path:
        """Create a quick snapshot backup"""
        filename = f"refserver_{timestamp.strftime('%Y%m%d_%H%M%S')}_snapshot.db"
        if compress:
            filename += ".gz"
            
        backup_path = self.sqlite_backup_dir / subdir / filename
        
        # Use SQLite backup API for consistency
        source_conn = sqlite3.connect(self.db_path)
        
        if compress:
            temp_path = backup_path.with_suffix('')
            dest_conn = sqlite3.connect(str(temp_path))
            source_conn.backup(dest_conn)
            dest_conn.close()
            
            with open(temp_path, 'rb') as f_in:
                with gzip.open(backup_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            os.remove(temp_path)
        else:
            dest_conn = sqlite3.connect(str(backup_path))
            source_conn.backup(dest_conn)
            dest_conn.close()
        
        source_conn.close()
        return backup_path
    
    def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        try:
            if backup_path.suffix == '.gz':
                # Decompress and verify
                with gzip.open(backup_path, 'rb') as f:
                    # Read first few bytes to ensure it's valid
                    header = f.read(16)
                    if not header.startswith(b'SQLite format 3'):
                        return False
            else:
                # Direct verification
                conn = sqlite3.connect(str(backup_path))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                conn.close()
                return result[0] == "ok"
            
            return True
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return False
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def cleanup_old_backups(self):
        """Remove backups that have exceeded their retention period"""
        current_time = datetime.now()
        removed_count = 0
        
        for backup in self.history[:]:  # Iterate over a copy
            if backup.get("status") == "completed":
                expire_date = datetime.fromisoformat(backup["expire_date"])
                if current_time > expire_date:
                    try:
                        backup_path = Path(backup["path"])
                        if backup_path.exists():
                            os.remove(backup_path)
                            logger.info(f"Removed expired backup: {backup_path}")
                        
                        self.history.remove(backup)
                        removed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to remove backup {backup['path']}: {e}")
        
        if removed_count > 0:
            self._save_history()
            logger.info(f"Cleaned up {removed_count} expired backups")
    
    def get_backup_status(self) -> Dict:
        """Get current backup system status"""
        total_size = 0
        backup_counts = {"full": 0, "incremental": 0, "snapshot": 0}
        
        for backup in self.history:
            if backup.get("status") == "completed":
                backup_counts[backup["type"]] += 1
                total_size += backup.get("size_bytes", 0)
        
        # Get latest backup info
        latest_backup = None
        if self.history:
            completed_backups = [b for b in self.history if b.get("status") == "completed"]
            if completed_backups:
                latest_backup = max(completed_backups, key=lambda x: x["timestamp"])
        
        return {
            "scheduler_running": self.scheduler.running,
            "total_backups": sum(backup_counts.values()),
            "backup_counts": backup_counts,
            "total_size_bytes": total_size,
            "latest_backup": latest_backup,
            "backup_directory": str(self.backup_base_dir),
            "scheduled_jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run": job.next_run_time.isoformat() if job.next_run_time else None
                }
                for job in self.scheduler.get_jobs()
            ]
        }
    
    def get_backup_history(self, limit: int = 50) -> List[Dict]:
        """Get backup history with optional limit"""
        return self.history[-limit:][::-1]  # Return most recent first
    
    def _backup_health_check(self):
        """Scheduled backup health check"""
        try:
            # Check if recent backup exists (within last 26 hours)
            current_time = datetime.now()
            recent_backup_found = False
            
            for backup in self.history:
                if backup.get("status") == "completed":
                    backup_time = datetime.fromisoformat(backup["timestamp"])
                    age_hours = (current_time - backup_time).total_seconds() / 3600
                    
                    if age_hours <= 26:  # Allow for some delay
                        recent_backup_found = True
                        break
            
            if not recent_backup_found:
                logger.warning("No recent backup found within last 26 hours")
                # Could send alert here
            
            # Check database integrity
            if os.path.exists(self.db_path):
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                conn.close()
                
                if result[0] != "ok":
                    logger.error("Database integrity check failed")
                    # Could trigger automatic recovery here
            
        except Exception as e:
            logger.error(f"Backup health check failed: {e}")
    
    def verify_backup_integrity(self, backup_path: Path) -> bool:
        """Verify the integrity of a specific backup file"""
        try:
            if backup_path.suffix == '.gz':
                # Test gzip file integrity
                with gzip.open(backup_path, 'rb') as f:
                    # Try to read a small chunk
                    f.read(1024)
                return True
            else:
                # Test SQLite database directly
                conn = sqlite3.connect(str(backup_path))
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                conn.close()
                return result[0] == "ok"
        except Exception:
            return False
    
    def _daily_consistency_check(self):
        """Scheduled daily consistency check"""
        try:
            from consistency_check import get_consistency_checker
            
            checker = get_consistency_checker()
            results = checker.run_full_consistency_check()
            
            # Log results
            if results["total_issues"] == 0:
                logger.info("Daily consistency check: All databases are consistent")
            else:
                logger.warning(f"Daily consistency check: Found {results['total_issues']} issues")
                
                # Auto-fix safe issues
                if results["issues_by_severity"]["critical"] == 0:
                    fix_results = checker.auto_fix_issues()
                    logger.info(f"Auto-fixed {fix_results['fixed_count']} consistency issues")
                else:
                    logger.error("Critical consistency issues detected - manual intervention required")
            
        except Exception as e:
            logger.error(f"Daily consistency check failed: {e}")
    
    def restore_backup(self, backup_id: str, target_path: Optional[str] = None) -> Dict:
        """
        Restore a backup to the database or a specified location
        
        Args:
            backup_id: ID of the backup to restore
            target_path: Optional target path (if None, restores to original DB)
            
        Returns:
            Dictionary with restore details
        """
        # Find backup in history
        backup_info = None
        for backup in self.history:
            if backup.get("backup_id") == backup_id:
                backup_info = backup
                break
        
        if not backup_info:
            raise ValueError(f"Backup not found: {backup_id}")
        
        if backup_info.get("status") != "completed":
            raise ValueError(f"Cannot restore failed backup: {backup_id}")
        
        backup_path = Path(backup_info["path"])
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        # Verify checksum
        if self._calculate_checksum(backup_path) != backup_info["checksum"]:
            raise ValueError("Backup checksum verification failed")
        
        # Default to original database path
        if target_path is None:
            target_path = self.db_path
            # Create safety backup before restore
            safety_backup = self.create_backup("snapshot", {
                "description": f"Safety backup before restore of {backup_id}",
                "retention_days": 7
            })
            logger.info(f"Created safety backup: {safety_backup['backup_id']}")
        
        try:
            # Restore the backup
            if backup_info["compressed"]:
                # Decompress and restore
                with gzip.open(backup_path, 'rb') as f_in:
                    with open(target_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # Direct copy
                shutil.copy2(backup_path, target_path)
            
            logger.info(f"Backup restored successfully: {backup_id} -> {target_path}")
            
            return {
                "backup_id": backup_id,
                "restored_to": target_path,
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            raise


class ChromaDBBackupManager:
    """Manages ChromaDB vector database backups"""
    
    def __init__(self, chromadb_dir: str = "/refdata/chromadb", backup_dir: str = "/refdata/backups"):
        self.chromadb_dir = Path(chromadb_dir)
        self.backup_base_dir = Path(backup_dir)
        self.chromadb_backup_dir = self.backup_base_dir / "chromadb"
        
        # Create backup directories
        for subdir in ["daily", "weekly", "snapshots"]:
            (self.chromadb_backup_dir / subdir).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"ChromaDBBackupManager initialized with chromadb_dir={chromadb_dir}")
    
    def create_backup(self, backup_type: str = "snapshot", compress: bool = True) -> Dict:
        """
        Create a backup of ChromaDB data
        
        Args:
            backup_type: Type of backup (full or snapshot)
            compress: Whether to compress the backup
            
        Returns:
            Dictionary with backup details
        """
        timestamp = datetime.now()
        backup_id = f"chromadb_{timestamp.strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Check if ChromaDB directory exists
            if not self.chromadb_dir.exists():
                raise FileNotFoundError(f"ChromaDB directory not found: {self.chromadb_dir}")
            
            # Determine backup subdirectory
            if backup_type == "full":
                subdir = "daily"
            else:
                subdir = "snapshots"
            
            # Create backup filename
            backup_filename = f"{backup_id}_{backup_type}.tar"
            if compress:
                backup_filename += ".gz"
            
            backup_path = self.chromadb_backup_dir / subdir / backup_filename
            
            # Create tar archive
            compression = "gz" if compress else None
            with tarfile.open(backup_path, f"w:{compression or ''}") as tar:
                # Add ChromaDB directory to archive
                tar.add(self.chromadb_dir, arcname="chromadb")
                
                # Add metadata
                metadata = {
                    "backup_id": backup_id,
                    "timestamp": timestamp.isoformat(),
                    "type": backup_type,
                    "chromadb_dir": str(self.chromadb_dir),
                    "version": "0.1.12"
                }
                metadata_str = json.dumps(metadata, indent=2)
                metadata_bytes = metadata_str.encode('utf-8')
                
                # Create TarInfo for metadata
                info = tarfile.TarInfo("backup_metadata.json")
                info.size = len(metadata_bytes)
                tar.addfile(info, io.BytesIO(metadata_bytes))
            
            # Calculate backup size
            backup_size = backup_path.stat().st_size
            
            logger.info(f"ChromaDB backup created: {backup_path} ({backup_size} bytes)")
            
            return {
                "backup_id": backup_id,
                "type": backup_type,
                "path": str(backup_path),
                "timestamp": timestamp.isoformat(),
                "size_bytes": backup_size,
                "compressed": compress,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"ChromaDB backup failed: {e}")
            raise
    
    def restore_backup(self, backup_path: str, target_dir: Optional[str] = None) -> Dict:
        """
        Restore a ChromaDB backup
        
        Args:
            backup_path: Path to the backup file
            target_dir: Optional target directory (default: original location)
            
        Returns:
            Dictionary with restore details
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        target_dir = Path(target_dir) if target_dir else self.chromadb_dir
        
        try:
            # Create safety backup if restoring to original location
            if target_dir == self.chromadb_dir and self.chromadb_dir.exists():
                safety_backup = self.create_backup("snapshot", compress=True)
                logger.info(f"Created safety backup before restore: {safety_backup['backup_id']}")
            
            # Clear target directory
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract backup
            compression = "gz" if backup_path.suffix == ".gz" else None
            with tarfile.open(backup_path, f"r:{compression or ''}") as tar:
                # Extract all members
                tar.extractall(target_dir.parent)
            
            logger.info(f"ChromaDB backup restored to: {target_dir}")
            
            return {
                "backup_path": str(backup_path),
                "restored_to": str(target_dir),
                "timestamp": datetime.now().isoformat(),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"ChromaDB restore failed: {e}")
            raise
    
    def cleanup_old_backups(self, retention_days: int = 7):
        """Remove ChromaDB backups older than retention period"""
        current_time = datetime.now()
        removed_count = 0
        
        for subdir in ["daily", "weekly", "snapshots"]:
            backup_dir = self.chromadb_backup_dir / subdir
            if not backup_dir.exists():
                continue
                
            for backup_file in backup_dir.glob("*.tar*"):
                file_age = current_time - datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_age.days > retention_days:
                    try:
                        backup_file.unlink()
                        removed_count += 1
                        logger.info(f"Removed old ChromaDB backup: {backup_file}")
                    except Exception as e:
                        logger.error(f"Failed to remove backup {backup_file}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old ChromaDB backups")


class UnifiedBackupManager:
    """Unified backup manager for SQLite and ChromaDB"""
    
    def __init__(self):
        self.sqlite_backup = get_backup_manager()
        self.chromadb_backup = ChromaDBBackupManager()
        
        # Backup coordination lock
        self._backup_lock = threading.Lock()
        
        logger.info("UnifiedBackupManager initialized")
    
    def create_unified_backup(self, backup_type: str = "snapshot", options: Optional[Dict] = None) -> Dict:
        """
        Create coordinated backup of both SQLite and ChromaDB
        
        Args:
            backup_type: Type of backup (full, incremental, snapshot)
            options: Backup options
            
        Returns:
            Dictionary with unified backup details
        """
        options = options or {}
        
        with self._backup_lock:
            timestamp = datetime.now()
            unified_id = f"unified_{timestamp.strftime('%Y%m%d_%H%M%S')}"
            
            results = {
                "unified_id": unified_id,
                "timestamp": timestamp.isoformat(),
                "type": backup_type,
                "components": {}
            }
            
            try:
                # Create SQLite backup
                sqlite_result = self.sqlite_backup.create_backup(backup_type, options)
                results["components"]["sqlite"] = sqlite_result
                
                # Create ChromaDB backup (only full or snapshot)
                if backup_type != "incremental":
                    chromadb_result = self.chromadb_backup.create_backup(
                        backup_type, 
                        compress=options.get("compress", True)
                    )
                    results["components"]["chromadb"] = chromadb_result
                
                results["status"] = "completed"
                logger.info(f"Unified backup completed: {unified_id}")
                
            except Exception as e:
                results["status"] = "failed"
                results["error"] = str(e)
                logger.error(f"Unified backup failed: {e}")
                raise
            
            return results
    
    def restore_unified_backup(self, sqlite_backup_id: str, chromadb_backup_path: Optional[str] = None) -> Dict:
        """
        Restore both SQLite and ChromaDB from backups
        
        Args:
            sqlite_backup_id: SQLite backup ID to restore
            chromadb_backup_path: Optional ChromaDB backup path
            
        Returns:
            Dictionary with restore details
        """
        with self._backup_lock:
            results = {
                "timestamp": datetime.now().isoformat(),
                "components": {}
            }
            
            try:
                # Restore SQLite
                sqlite_result = self.sqlite_backup.restore_backup(sqlite_backup_id)
                results["components"]["sqlite"] = sqlite_result
                
                # Restore ChromaDB if path provided
                if chromadb_backup_path:
                    chromadb_result = self.chromadb_backup.restore_backup(chromadb_backup_path)
                    results["components"]["chromadb"] = chromadb_result
                
                results["status"] = "success"
                logger.info("Unified restore completed")
                
            except Exception as e:
                results["status"] = "failed"
                results["error"] = str(e)
                logger.error(f"Unified restore failed: {e}")
                raise
            
            return results


# Singleton instances
_backup_manager: Optional[SQLiteBackupManager] = None
_chromadb_backup_manager: Optional[ChromaDBBackupManager] = None
_unified_backup_manager: Optional[UnifiedBackupManager] = None


def get_backup_manager(db_path: str = "/refdata/refserver.db") -> SQLiteBackupManager:
    """Get or create the backup manager singleton"""
    global _backup_manager
    if _backup_manager is None:
        _backup_manager = SQLiteBackupManager(db_path)
    return _backup_manager


def get_chromadb_backup_manager() -> ChromaDBBackupManager:
    """Get or create the ChromaDB backup manager singleton"""
    global _chromadb_backup_manager
    if _chromadb_backup_manager is None:
        _chromadb_backup_manager = ChromaDBBackupManager()
    return _chromadb_backup_manager


def get_unified_backup_manager() -> UnifiedBackupManager:
    """Get or create the unified backup manager singleton"""
    global _unified_backup_manager
    if _unified_backup_manager is None:
        _unified_backup_manager = UnifiedBackupManager()
    return _unified_backup_manager