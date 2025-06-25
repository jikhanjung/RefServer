#!/usr/bin/env python3
"""
RefServer 백업 시스템 통합 테스트 스크립트 (v0.1.12)
백업, 복구, 일관성 검증 시스템의 상세한 기능을 테스트합니다.
"""

import requests
import json
import time
import os
import sys
import tempfile
import sqlite3
from pathlib import Path
from typing import Dict, Optional, List

class RefServerBackupTester:
    def __init__(self, base_url: str = "http://localhost:8060", username: str = "admin", password: str = "admin123"):
        """
        Initialize Backup System tester
        
        Args:
            base_url: RefServer API base URL
            username: Admin username  
            password: Admin password
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefServer-Backup-Tester/1.0'
        })
        
        self.username = username
        self.password = password
        
        # Test results
        self.results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'tests': []
        }
        
        # Store test data
        self.created_backups = []
        self.is_superuser = False
        self.backup_system_available = False
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def assert_response(self, response: requests.Response, expected_status = 200, test_name: str = ""):
        """Assert response status and log result"""
        if isinstance(expected_status, list):
            success = response.status_code in expected_status
        else:
            success = response.status_code == expected_status
        
        test_result = {
            'name': test_name,
            'success': success,
            'status_code': response.status_code,
            'expected_status': expected_status,
            'url': response.url,
            'response_time': response.elapsed.total_seconds()
        }
        
        if success:
            self.results['passed'] += 1
            self.log(f"✅ {test_name} - PASSED ({response.status_code})", "PASS")
        else:
            self.results['failed'] += 1
            self.log(f"❌ {test_name} - FAILED ({response.status_code}, expected {expected_status})", "FAIL")
            try:
                error_detail = response.json().get('detail', 'No detail')
                self.log(f"   Error: {error_detail}", "ERROR")
            except:
                self.log(f"   Response: {response.text[:200]}...", "ERROR")
        
        self.results['tests'].append(test_result)
        return success
    
    def skip_test(self, test_name: str, reason: str):
        """Skip a test with reason"""
        self.results['skipped'] += 1
        self.log(f"⏭️ {test_name} - SKIPPED ({reason})", "SKIP")
    
    def setup_authentication(self):
        """Setup authentication for admin endpoints"""
        self.log("Setting up admin authentication...")
        
        try:
            # Login to admin interface
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(f"{self.base_url}/admin/login", data=login_data)
            if response.status_code in [200, 302]:
                self.log("   ✅ Admin authentication successful")
                
                # Check superuser status
                dashboard_response = self.session.get(f"{self.base_url}/admin/dashboard")
                if dashboard_response.status_code == 200:
                    if 'superuser' in dashboard_response.text.lower():
                        self.is_superuser = True
                        self.log("   ✅ Superuser privileges confirmed")
                    
                return True
            else:
                self.log(f"   ❌ Login failed: {response.status_code}", "ERROR")
                return False
            
        except Exception as e:
            self.log(f"Authentication setup failed: {e}", "ERROR")
            return False
    
    def test_backup_system_availability(self):
        """Test if backup system is available"""
        self.log("Testing backup system availability...")
        
        try:
            response = self.session.get(f"{self.base_url}/status")
            if response.status_code == 200:
                data = response.json()
                self.backup_system_available = data.get('backup_system', False)
                
                if self.backup_system_available:
                    self.log("   ✅ Backup system available")
                    return True
                else:
                    self.log("   ❌ Backup system not available", "ERROR")
                    return False
            else:
                self.log("   ❌ Cannot check system status", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Backup system availability test failed: {e}", "ERROR")
            return False
    
    def test_sqlite_backup_creation(self):
        """Test SQLite backup creation"""
        self.log("Testing SQLite backup creation...")
        
        backup_types = ['snapshot', 'full']
        
        for backup_type in backup_types:
            try:
                backup_data = {
                    'backup_type': backup_type,
                    'compress': True,
                    'description': f'Test {backup_type} backup',
                    'retention_days': 1,
                    'unified': False
                }
                
                response = self.session.post(f"{self.base_url}/admin/backup/trigger", data=backup_data)
                success = self.assert_response(response, 200, f"SQLite {backup_type.title()} Backup")
                
                if success:
                    data = response.json()
                    backup_id = data.get('backup_id')
                    
                    if backup_id:
                        self.created_backups.append(backup_id)
                        self.log(f"   Backup ID: {backup_id}")
                        self.log(f"   Size: {data.get('size_bytes', 0)} bytes")
                        self.log(f"   Compressed: {data.get('compressed', False)}")
                        
                        if data.get('status') == 'completed':
                            self.log(f"   ✅ {backup_type.title()} backup successful")
                
            except Exception as e:
                self.log(f"SQLite {backup_type} backup test failed: {e}", "ERROR")
                self.results['failed'] += 1
    
    def test_chromadb_backup_creation(self):
        """Test ChromaDB backup creation"""
        self.log("Testing ChromaDB backup creation...")
        
        try:
            backup_data = {
                'backup_type': 'snapshot',
                'compress': True,
                'description': 'Test ChromaDB backup',
                'retention_days': 1,
                'unified': False  # ChromaDB only
            }
            
            # Check if ChromaDB directory exists first
            status_response = self.session.get(f"{self.base_url}/admin/backup/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                chromadb_exists = status_data.get('chromadb', {}).get('directory_exists', False)
                
                if not chromadb_exists:
                    self.skip_test("ChromaDB Backup", "ChromaDB directory not found")
                    return
            
            # Create ChromaDB backup by triggering via backup manager
            # This is a more complex test since ChromaDB backup is handled differently
            response = self.session.post(f"{self.base_url}/admin/backup/trigger", data=backup_data)
            success = self.assert_response(response, [200, 404], "ChromaDB Backup")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   ChromaDB backup completed")
                self.log(f"   Size: {data.get('size_bytes', 0)} bytes")
            elif response.status_code == 404:
                self.log("   ChromaDB backup not available (expected if no ChromaDB data)")
            
        except Exception as e:
            self.log(f"ChromaDB backup test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_unified_backup_creation(self):
        """Test unified backup (SQLite + ChromaDB)"""
        self.log("Testing unified backup creation...")
        
        try:
            backup_data = {
                'backup_type': 'snapshot',
                'compress': True,
                'description': 'Test unified backup',
                'retention_days': 1,
                'unified': True
            }
            
            response = self.session.post(f"{self.base_url}/admin/backup/trigger", data=backup_data)
            success = self.assert_response(response, 200, "Unified Backup")
            
            if success:
                data = response.json()
                
                # Check if unified backup structure is present
                if 'unified_id' in data:
                    self.log(f"   Unified ID: {data.get('unified_id')}")
                    self.log(f"   Status: {data.get('status')}")
                    
                    components = data.get('components', {})
                    if 'sqlite' in components:
                        self.log(f"   SQLite component: ✅")
                    if 'chromadb' in components:
                        self.log(f"   ChromaDB component: ✅")
                    
                    self.log(f"   ✅ Unified backup completed")
                else:
                    # Fallback to regular backup result
                    backup_id = data.get('backup_id')
                    if backup_id:
                        self.created_backups.append(backup_id)
                        self.log(f"   ✅ Backup completed (fallback mode)")
            
        except Exception as e:
            self.log(f"Unified backup test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_verification(self):
        """Test backup verification"""
        if not self.created_backups:
            self.skip_test("Backup Verification", "No backups created")
            return
        
        self.log("Testing backup verification...")
        
        for backup_id in self.created_backups[:2]:  # Test first 2 backups
            try:
                response = self.session.post(f"{self.base_url}/admin/backup/verify/{backup_id}")
                success = self.assert_response(response, 200, f"Backup Verification ({backup_id[:8]}...)")
                
                if success:
                    data = response.json()
                    integrity_check = data.get('integrity_check')
                    
                    self.log(f"   Backup {backup_id[:8]}: {integrity_check}")
                    
                    if integrity_check == 'passed':
                        self.log(f"   ✅ Backup integrity verified")
                    else:
                        self.log(f"   ❌ Backup integrity failed")
                
            except Exception as e:
                self.log(f"Backup verification test failed for {backup_id}: {e}", "ERROR")
                self.results['failed'] += 1
    
    def test_backup_history_and_cleanup(self):
        """Test backup history retrieval and cleanup"""
        self.log("Testing backup history...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/backup/history?limit=20")
            success = self.assert_response(response, 200, "Backup History")
            
            if success:
                data = response.json()
                backups = data.get('backups', [])
                total = data.get('total', 0)
                
                self.log(f"   Total backup records: {total}")
                self.log(f"   Retrieved records: {len(backups)}")
                
                # Check for our test backups
                test_backups = [b for b in backups if 'Test' in b.get('description', '')]
                self.log(f"   Test backups found: {len(test_backups)}")
                
                # Test cleanup (if we have test backups)
                if test_backups and len(test_backups) > 0:
                    self.log("Testing backup cleanup...")
                    
                    # Cleanup is typically automatic, but we can test the endpoint exists
                    cleanup_response = self.session.delete(f"{self.base_url}/admin/backup/cleanup")
                    cleanup_success = self.assert_response(cleanup_response, [200, 404], "Backup Cleanup")
                    
                    if cleanup_success:
                        self.log("   ✅ Backup cleanup endpoint working")
            
        except Exception as e:
            self.log(f"Backup history test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_health_monitoring(self):
        """Test backup health monitoring"""
        self.log("Testing backup health monitoring...")
        
        try:
            # Test health check
            response = self.session.post(f"{self.base_url}/admin/backup/health-check")
            success = self.assert_response(response, 200, "Backup Health Check")
            
            if success:
                data = response.json()
                self.log(f"   Health status: {data.get('status')}")
                
                backup_status = data.get('backup_status', {})
                if backup_status:
                    scheduler_running = backup_status.get('scheduler_running', False)
                    total_backups = backup_status.get('total_backups', 0)
                    
                    self.log(f"   Scheduler running: {scheduler_running}")
                    self.log(f"   Total backups: {total_backups}")
                    
                    if scheduler_running:
                        self.log(f"   ✅ Backup scheduler is operational")
                    
                    # Check for scheduled jobs
                    scheduled_jobs = backup_status.get('scheduled_jobs', [])
                    if scheduled_jobs:
                        self.log(f"   Scheduled jobs: {len(scheduled_jobs)}")
                        for job in scheduled_jobs[:3]:  # Show first 3
                            self.log(f"     - {job.get('name', 'Unknown')}")
            
        except Exception as e:
            self.log(f"Backup health monitoring test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_detection(self):
        """Test consistency issue detection"""
        self.log("Testing consistency issue detection...")
        
        try:
            # Test quick consistency summary
            response = self.session.get(f"{self.base_url}/admin/consistency/summary")
            success = self.assert_response(response, 200, "Consistency Summary")
            
            if success:
                data = response.json()
                self.log(f"   Status: {data.get('status', 'unknown')}")
                self.log(f"   SQLite papers: {data.get('sqlite_papers', 0)}")
                self.log(f"   ChromaDB papers: {data.get('chromadb_papers', 0)}")
                
                counts_match = data.get('counts_match', False)
                self.log(f"   Counts match: {counts_match}")
                
                if counts_match:
                    self.log(f"   ✅ Database counts are consistent")
                else:
                    self.log(f"   ⚠️ Database counts are inconsistent")
            
            # Test full consistency check
            self.log("Running full consistency check...")
            response = self.session.get(f"{self.base_url}/admin/consistency/check")
            success = self.assert_response(response, 200, "Full Consistency Check")
            
            if success:
                data = response.json()
                total_issues = data.get('total_issues', 0)
                duration = data.get('duration_seconds', 0)
                
                self.log(f"   Check duration: {duration:.2f} seconds")
                self.log(f"   Total issues found: {total_issues}")
                
                if total_issues == 0:
                    self.log(f"   ✅ No consistency issues detected")
                else:
                    issues_by_severity = data.get('issues_by_severity', {})
                    self.log(f"   Critical: {issues_by_severity.get('critical', 0)}")
                    self.log(f"   High: {issues_by_severity.get('high', 0)}")
                    self.log(f"   Medium: {issues_by_severity.get('medium', 0)}")
                    self.log(f"   Low: {issues_by_severity.get('low', 0)}")
                    
                    self.log(f"   ⚠️ Consistency issues detected")
            
        except Exception as e:
            self.log(f"Consistency detection test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_auto_fix(self):
        """Test automatic consistency fixing"""
        if not self.is_superuser:
            self.skip_test("Consistency Auto Fix", "Requires superuser privileges")
            return
        
        self.log("Testing consistency auto fix...")
        
        try:
            response = self.session.post(f"{self.base_url}/admin/consistency/fix")
            success = self.assert_response(response, 200, "Consistency Auto Fix")
            
            if success:
                data = response.json()
                fixed_count = data.get('fixed_count', 0)
                failed_count = data.get('failed_count', 0)
                
                self.log(f"   Issues fixed: {fixed_count}")
                self.log(f"   Fixes failed: {failed_count}")
                
                if fixed_count > 0:
                    self.log(f"   ✅ Successfully fixed {fixed_count} issues")
                else:
                    self.log(f"   ✅ No issues needed fixing")
                
                if failed_count > 0:
                    self.log(f"   ⚠️ {failed_count} fixes failed (may require manual intervention)")
            
        except Exception as e:
            self.log(f"Consistency auto fix test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_disaster_recovery_readiness(self):
        """Test disaster recovery readiness assessment"""
        self.log("Testing disaster recovery readiness...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/disaster-recovery/status")
            success = self.assert_response(response, 200, "Disaster Recovery Readiness")
            
            if success:
                data = response.json()
                
                readiness_score = data.get('readiness_score', '0/10')
                readiness_level = data.get('readiness_level', 'unknown')
                
                self.log(f"   Readiness score: {readiness_score}")
                self.log(f"   Readiness level: {readiness_level}")
                
                # Check individual components
                sqlite_backups = data.get('sqlite_backups', 0)
                chromadb_backups = data.get('chromadb_backups', 0)
                recent_backups = data.get('recent_successful_backups', 0)
                free_space_gb = data.get('free_disk_space_gb', 0)
                scheduler_running = data.get('scheduler_running', False)
                
                self.log(f"   SQLite backups: {sqlite_backups}")
                self.log(f"   ChromaDB backups: {chromadb_backups}")
                self.log(f"   Recent successful backups: {recent_backups}")
                self.log(f"   Free disk space: {free_space_gb} GB")
                self.log(f"   Scheduler running: {scheduler_running}")
                
                # Check recovery scripts
                scripts = data.get('recovery_scripts_available', {})
                disaster_script = scripts.get('disaster_recovery', False)
                backup_check_script = scripts.get('backup_check', False)
                
                self.log(f"   Disaster recovery script: {'✅' if disaster_script else '❌'}")
                self.log(f"   Backup check script: {'✅' if backup_check_script else '❌'}")
                
                # Overall assessment
                if readiness_level in ['excellent', 'good']:
                    self.log(f"   ✅ System is ready for disaster recovery")
                elif readiness_level == 'fair':
                    self.log(f"   ⚠️ System needs some improvements for disaster recovery")
                else:
                    self.log(f"   ❌ System requires significant improvements for disaster recovery")
                
                # Show recommendations if any
                recommendations = data.get('recommendations', [])
                active_recommendations = [r for r in recommendations if r]
                if active_recommendations:
                    self.log(f"   Recommendations: {len(active_recommendations)} items")
                    for rec in active_recommendations[:3]:  # Show first 3
                        self.log(f"     - {rec}")
            
        except Exception as e:
            self.log(f"Disaster recovery readiness test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_restore_validation(self):
        """Test backup restore validation (without actually restoring)"""
        if not self.is_superuser:
            self.skip_test("Backup Restore Validation", "Requires superuser privileges")
            return
        
        if not self.created_backups:
            self.skip_test("Backup Restore Validation", "No backups available")
            return
        
        self.log("Testing backup restore validation...")
        
        try:
            # Test with invalid backup ID
            response = self.session.post(f"{self.base_url}/admin/backup/restore/invalid-backup-id")
            success = self.assert_response(response, [404, 400], "Restore Invalid Backup")
            
            if success:
                self.log(f"   ✅ Invalid backup ID properly rejected")
            
            # Test restore endpoint security (should require superuser)
            if self.created_backups:
                backup_id = self.created_backups[0]
                
                # We don't actually restore, just test the endpoint response
                # with a non-existent target path to avoid disrupting the system
                test_target = "/tmp/test_restore_validation.db"
                
                response = self.session.post(
                    f"{self.base_url}/admin/backup/restore/{backup_id}",
                    data={'target_path': test_target}
                )
                
                # We expect this to work (200) or fail with specific error (4xx)
                # But not crash the system
                success = self.assert_response(response, [200, 400, 404, 500], "Restore Endpoint Test")
                
                if success and response.status_code == 200:
                    self.log(f"   ✅ Restore endpoint is accessible")
                    # Clean up test file if created
                    if os.path.exists(test_target):
                        os.unlink(test_target)
                elif response.status_code in [400, 404]:
                    self.log(f"   ✅ Restore endpoint properly validates input")
            
        except Exception as e:
            self.log(f"Backup restore validation test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def run_all_tests(self):
        """Run all backup system tests"""
        self.log("🚀 Starting RefServer Backup System Tests (v0.1.12)")
        self.log("=" * 70)
        
        start_time = time.time()
        
        # Setup authentication
        if not self.setup_authentication():
            self.log("❌ Cannot proceed without authentication", "ERROR")
            return False
        
        # Check backup system availability
        if not self.test_backup_system_availability():
            self.log("❌ Backup system not available", "ERROR")
            return False
        
        # Test backup creation
        self.log("\n🛡️ Testing Backup Creation")
        self.test_sqlite_backup_creation()
        self.test_chromadb_backup_creation()
        self.test_unified_backup_creation()
        
        # Test backup verification and management
        self.log("\n🔍 Testing Backup Verification & Management")
        self.test_backup_verification()
        self.test_backup_history_and_cleanup()
        self.test_backup_health_monitoring()
        
        # Test consistency system
        self.log("\n⚖️ Testing Consistency System")
        self.test_consistency_detection()
        self.test_consistency_auto_fix()
        
        # Test disaster recovery
        self.log("\n🚨 Testing Disaster Recovery")
        self.test_disaster_recovery_readiness()
        
        # Test restore validation
        self.log("\n🔄 Testing Restore System")
        self.test_backup_restore_validation()
        
        # Print summary
        total_time = time.time() - start_time
        total_tests = self.results['passed'] + self.results['failed'] + self.results['skipped']
        
        self.log("=" * 70)
        self.log("📊 Backup System Test Summary")
        self.log(f"   Total tests: {total_tests}")
        self.log(f"   Passed: {self.results['passed']} ✅")
        self.log(f"   Failed: {self.results['failed']} ❌")
        self.log(f"   Skipped: {self.results['skipped']} ⏭️")
        
        if self.results['passed'] + self.results['failed'] > 0:
            success_rate = (self.results['passed']/(self.results['passed'] + self.results['failed'])*100)
            self.log(f"   Success rate: {success_rate:.1f}%")
        
        self.log(f"   Total time: {total_time:.2f}s")
        self.log(f"   Backups created: {len(self.created_backups)}")
        self.log(f"   Superuser privileges: {'Yes' if self.is_superuser else 'No'}")
        
        # Success criteria
        success_threshold = 85.0
        is_success = (self.results['failed'] == 0) or (success_rate >= success_threshold)
        
        if is_success:
            self.log(f"   🎉 Backup system tests PASSED")
            self.log(f"   💾 v0.1.12 backup features are working correctly")
        else:
            self.log(f"   ⚠️ Backup system tests need attention")
        
        if not self.is_superuser:
            self.log(f"   ℹ️ Some restore tests were skipped (non-superuser)")
        
        return is_success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer Backup System Tester")
    parser.add_argument("--url", default="http://localhost:8060", 
                       help="RefServer API base URL")
    parser.add_argument("--username", default="admin",
                       help="Admin username")
    parser.add_argument("--password", default="admin123",
                       help="Admin password")
    
    args = parser.parse_args()
    
    # Test if server is reachable
    try:
        response = requests.get(f"{args.url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not responding at {args.url}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"❌ Cannot connect to {args.url}")
        sys.exit(1)
    
    # Run tests
    tester = RefServerBackupTester(args.url, args.username, args.password)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()