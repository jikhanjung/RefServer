#!/usr/bin/env python3
"""
RefServer 관리자 시스템 테스트 스크립트 (v0.1.12)
백업, 일관성 검증, 재해 복구 등 시스템 관리 기능을 테스트합니다.
"""

import requests
import json
import time
import os
import sys
from typing import Dict, Optional

class RefServerAdminTester:
    def __init__(self, base_url: str = "http://localhost:8060", username: str = "admin", password: str = "admin123"):
        """
        Initialize Admin System tester
        
        Args:
            base_url: RefServer API base URL
            username: Admin username
            password: Admin password
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefServer-Admin-Tester/1.0'
        })
        
        self.username = username
        self.password = password
        self.auth_token = None
        
        # Test results
        self.results = {
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'tests': []
        }
        
        # Store test data
        self.test_backup_id = None
        self.is_superuser = False
    
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
    
    def admin_login(self):
        """Login to admin interface"""
        self.log("Testing admin login...")
        
        try:
            # Get login page (should work without auth)
            response = self.session.get(f"{self.base_url}/admin/login")
            if response.status_code != 200:
                self.log("❌ Cannot access login page", "ERROR")
                return False
            
            # Attempt login
            login_data = {
                'username': self.username,
                'password': self.password
            }
            
            response = self.session.post(f"{self.base_url}/admin/login", data=login_data)
            success = self.assert_response(response, [200, 302], "Admin Login")
            
            if success:
                # Check if we got redirected to dashboard or got a token
                if response.status_code == 302:
                    self.log("   ✅ Login successful (redirected)")
                else:
                    self.log("   ✅ Login successful")
                
                # Try to access dashboard to verify login
                dashboard_response = self.session.get(f"{self.base_url}/admin/dashboard")
                if dashboard_response.status_code == 200:
                    self.log("   ✅ Dashboard access confirmed")
                    
                    # Check if user is superuser (needed for some tests)
                    if 'superuser' in dashboard_response.text.lower() or 'super' in dashboard_response.text.lower():
                        self.is_superuser = True
                        self.log("   ✅ Superuser privileges detected")
                    
                    return True
                else:
                    self.log("   ❌ Cannot access dashboard after login", "ERROR")
                    return False
            
            return False
            
        except Exception as e:
            self.log(f"Admin login failed: {e}", "ERROR")
            self.results['failed'] += 1
            return False
    
    def test_admin_dashboard(self):
        """Test admin dashboard access"""
        self.log("Testing admin dashboard...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/dashboard")
            success = self.assert_response(response, 200, "Admin Dashboard")
            
            if success:
                # Check for key dashboard elements
                content = response.text.lower()
                if 'dashboard' in content:
                    self.log("   ✅ Dashboard content loaded")
                if 'papers' in content:
                    self.log("   ✅ Papers section available")
                if 'backup' in content:
                    self.log("   ✅ Backup management section available (v0.1.12)")
        
        except Exception as e:
            self.log(f"Dashboard test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_status(self):
        """Test backup system status"""
        self.log("Testing backup system status...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/backup/status")
            success = self.assert_response(response, 200, "Backup Status")
            
            if success:
                data = response.json()
                
                # Check SQLite backup status
                sqlite_status = data.get('sqlite', {})
                self.log(f"   SQLite scheduler running: {sqlite_status.get('scheduler_running', False)}")
                self.log(f"   SQLite total backups: {sqlite_status.get('total_backups', 0)}")
                
                # Check ChromaDB backup status  
                chromadb_status = data.get('chromadb', {})
                self.log(f"   ChromaDB directory exists: {chromadb_status.get('directory_exists', False)}")
                self.log(f"   ChromaDB total backups: {chromadb_status.get('total_backups', 0)}")
                
                # Check unified backup availability
                unified_available = data.get('unified_backup_available', False)
                self.log(f"   Unified backup available: {unified_available}")
        
        except Exception as e:
            self.log(f"Backup status test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_trigger(self):
        """Test manual backup triggering"""
        self.log("Testing manual backup trigger...")
        
        try:
            # Test snapshot backup (fastest)
            backup_data = {
                'backup_type': 'snapshot',
                'compress': True,
                'description': 'Test backup from admin tester',
                'retention_days': 1,  # Short retention for test
                'unified': False  # SQLite only for speed
            }
            
            response = self.session.post(f"{self.base_url}/admin/backup/trigger", data=backup_data)
            success = self.assert_response(response, 200, "Manual Backup Trigger")
            
            if success:
                data = response.json()
                self.test_backup_id = data.get('backup_id')
                self.log(f"   Backup ID: {self.test_backup_id}")
                self.log(f"   Backup type: {data.get('type')}")
                self.log(f"   Status: {data.get('status')}")
                
                if data.get('status') == 'completed':
                    self.log(f"   ✅ Backup completed successfully")
                    self.log(f"   Size: {data.get('size_bytes', 0)} bytes")
                else:
                    self.log(f"   ⚠️ Backup status: {data.get('status')}")
        
        except Exception as e:
            self.log(f"Backup trigger test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_history(self):
        """Test backup history retrieval"""
        self.log("Testing backup history...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/backup/history?limit=10")
            success = self.assert_response(response, 200, "Backup History")
            
            if success:
                data = response.json()
                backups = data.get('backups', [])
                total = data.get('total', 0)
                
                self.log(f"   Total backup records: {total}")
                self.log(f"   Recent backups returned: {len(backups)}")
                
                if backups:
                    latest = backups[0]
                    self.log(f"   Latest backup: {latest.get('backup_id')} ({latest.get('status')})")
        
        except Exception as e:
            self.log(f"Backup history test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_health_check(self):
        """Test backup health check"""
        self.log("Testing backup health check...")
        
        try:
            response = self.session.post(f"{self.base_url}/admin/backup/health-check")
            success = self.assert_response(response, 200, "Backup Health Check")
            
            if success:
                data = response.json()
                self.log(f"   Health check status: {data.get('status')}")
                self.log(f"   Timestamp: {data.get('timestamp')}")
                
                backup_status = data.get('backup_status', {})
                if backup_status:
                    self.log(f"   Scheduler running: {backup_status.get('scheduler_running', False)}")
        
        except Exception as e:
            self.log(f"Backup health check test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_verification(self):
        """Test backup verification"""
        if not self.test_backup_id:
            self.skip_test("Backup Verification", "No backup ID available")
            return
        
        self.log("Testing backup verification...")
        
        try:
            response = self.session.post(f"{self.base_url}/admin/backup/verify/{self.test_backup_id}")
            success = self.assert_response(response, 200, "Backup Verification")
            
            if success:
                data = response.json()
                self.log(f"   Backup ID: {data.get('backup_id')}")
                self.log(f"   Integrity check: {data.get('integrity_check')}")
                
                if data.get('integrity_check') == 'passed':
                    self.log(f"   ✅ Backup integrity verified")
                else:
                    self.log(f"   ❌ Backup integrity failed")
        
        except Exception as e:
            self.log(f"Backup verification test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_summary(self):
        """Test consistency check summary"""
        self.log("Testing consistency check summary...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/consistency/summary")
            success = self.assert_response(response, 200, "Consistency Summary")
            
            if success:
                data = response.json()
                self.log(f"   Status: {data.get('status', 'unknown')}")
                self.log(f"   SQLite papers: {data.get('sqlite_papers', 0)}")
                self.log(f"   ChromaDB papers: {data.get('chromadb_papers', 0)}")
                self.log(f"   Counts match: {data.get('counts_match', False)}")
                
                if data.get('last_check'):
                    self.log(f"   Last check: {data.get('last_check')}")
        
        except Exception as e:
            self.log(f"Consistency summary test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_check(self):
        """Test full consistency check"""
        self.log("Testing full consistency check...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/consistency/check")
            success = self.assert_response(response, 200, "Full Consistency Check")
            
            if success:
                data = response.json()
                self.log(f"   Overall status: {data.get('overall_status')}")
                self.log(f"   Total issues: {data.get('total_issues', 0)}")
                self.log(f"   Duration: {data.get('duration_seconds', 0):.2f} seconds")
                
                issues_by_severity = data.get('issues_by_severity', {})
                if issues_by_severity:
                    self.log(f"   Critical: {issues_by_severity.get('critical', 0)}")
                    self.log(f"   High: {issues_by_severity.get('high', 0)}")
                    self.log(f"   Medium: {issues_by_severity.get('medium', 0)}")
                    self.log(f"   Low: {issues_by_severity.get('low', 0)}")
                
                if data.get('total_issues', 0) == 0:
                    self.log(f"   ✅ No consistency issues found")
                else:
                    self.log(f"   ⚠️ Found {data.get('total_issues')} consistency issues")
        
        except Exception as e:
            self.log(f"Consistency check test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_auto_fix(self):
        """Test automatic consistency fix (superuser only)"""
        if not self.is_superuser:
            self.skip_test("Consistency Auto Fix", "Requires superuser privileges")
            return
        
        self.log("Testing consistency auto fix...")
        
        try:
            response = self.session.post(f"{self.base_url}/admin/consistency/fix")
            success = self.assert_response(response, 200, "Consistency Auto Fix")
            
            if success:
                data = response.json()
                self.log(f"   Fixed count: {data.get('fixed_count', 0)}")
                self.log(f"   Failed count: {data.get('failed_count', 0)}")
                
                if data.get('fixed_count', 0) > 0:
                    self.log(f"   ✅ Fixed {data.get('fixed_count')} issues")
                else:
                    self.log(f"   ✅ No issues needed fixing")
        
        except Exception as e:
            self.log(f"Consistency auto fix test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_disaster_recovery_status(self):
        """Test disaster recovery readiness status"""
        self.log("Testing disaster recovery status...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/disaster-recovery/status")
            success = self.assert_response(response, 200, "Disaster Recovery Status")
            
            if success:
                data = response.json()
                self.log(f"   Readiness score: {data.get('readiness_score')}")
                self.log(f"   Readiness level: {data.get('readiness_level')}")
                self.log(f"   SQLite backups: {data.get('sqlite_backups', 0)}")
                self.log(f"   ChromaDB backups: {data.get('chromadb_backups', 0)}")
                self.log(f"   Free disk space: {data.get('free_disk_space_gb', 0)} GB")
                self.log(f"   Scheduler running: {data.get('scheduler_running', False)}")
                
                scripts = data.get('recovery_scripts_available', {})
                self.log(f"   Recovery scripts: {scripts.get('disaster_recovery', False)}")
                self.log(f"   Backup check scripts: {scripts.get('backup_check', False)}")
                
                recommendations = data.get('recommendations', [])
                if recommendations:
                    active_recommendations = [r for r in recommendations if r]
                    if active_recommendations:
                        self.log(f"   Recommendations: {len(active_recommendations)} items")
                    else:
                        self.log(f"   ✅ No recommendations (system ready)")
        
        except Exception as e:
            self.log(f"Disaster recovery status test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_management_page(self):
        """Test backup management UI page"""
        self.log("Testing backup management page...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/backup")
            success = self.assert_response(response, 200, "Backup Management Page")
            
            if success:
                content = response.text.lower()
                if 'backup' in content and 'management' in content:
                    self.log("   ✅ Backup management UI loaded")
                if 'sqlite' in content and 'chromadb' in content:
                    self.log("   ✅ Dual database backup UI available")
                if 'trigger' in content or 'manual' in content:
                    self.log("   ✅ Manual backup controls available")
        
        except Exception as e:
            self.log(f"Backup management page test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_consistency_management_page(self):
        """Test consistency management UI page"""
        self.log("Testing consistency management page...")
        
        try:
            response = self.session.get(f"{self.base_url}/admin/consistency")
            success = self.assert_response(response, 200, "Consistency Management Page")
            
            if success:
                content = response.text.lower()
                if 'consistency' in content and 'management' in content:
                    self.log("   ✅ Consistency management UI loaded")
                if 'check' in content:
                    self.log("   ✅ Consistency check controls available")
                if 'sqlite' in content and 'chromadb' in content:
                    self.log("   ✅ Database consistency UI available")
        
        except Exception as e:
            self.log(f"Consistency management page test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_backup_restore(self):
        """Test backup restore (superuser only)"""
        if not self.is_superuser:
            self.skip_test("Backup Restore", "Requires superuser privileges")
            return
        
        if not self.test_backup_id:
            self.skip_test("Backup Restore", "No backup ID available")
            return
        
        self.log("Testing backup restore (dry run)...")
        
        # Note: We don't actually restore to avoid disrupting the system
        # Instead, we test that the endpoint is accessible and properly secured
        try:
            # Test with invalid backup ID to check validation
            response = self.session.post(f"{self.base_url}/admin/backup/restore/invalid-backup-id")
            expected_status = [404, 400]  # Should reject invalid ID
            success = self.assert_response(response, expected_status, "Backup Restore (Invalid ID)")
            
            if success:
                self.log("   ✅ Backup restore endpoint properly validates input")
        
        except Exception as e:
            self.log(f"Backup restore test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def run_all_tests(self):
        """Run all admin system tests"""
        self.log("🚀 Starting RefServer Admin System Tests (v0.1.12)")
        self.log("=" * 70)
        
        start_time = time.time()
        
        # Login first
        if not self.admin_login():
            self.log("❌ Cannot proceed without admin login", "ERROR")
            return False
        
        # Test admin interface
        self.log("\n🖥️ Testing Admin Interface")
        self.test_admin_dashboard()
        self.test_backup_management_page()
        self.test_consistency_management_page()
        
        # Test backup system (v0.1.12)
        self.log("\n🛡️ Testing Backup System (v0.1.12)")
        self.test_backup_status()
        self.test_backup_trigger()
        self.test_backup_history()
        self.test_backup_health_check()
        self.test_backup_verification()
        self.test_backup_restore()
        
        # Test consistency system (v0.1.12)
        self.log("\n⚖️ Testing Consistency System (v0.1.12)")
        self.test_consistency_summary()
        self.test_consistency_check()
        self.test_consistency_auto_fix()
        
        # Test disaster recovery system (v0.1.12)
        self.log("\n🚨 Testing Disaster Recovery System (v0.1.12)")
        self.test_disaster_recovery_status()
        
        # Print summary
        total_time = time.time() - start_time
        total_tests = self.results['passed'] + self.results['failed'] + self.results['skipped']
        
        self.log("=" * 70)
        self.log("📊 Admin System Test Summary")
        self.log(f"   Total tests: {total_tests}")
        self.log(f"   Passed: {self.results['passed']} ✅")
        self.log(f"   Failed: {self.results['failed']} ❌")
        self.log(f"   Skipped: {self.results['skipped']} ⏭️")
        
        if self.results['passed'] + self.results['failed'] > 0:
            success_rate = (self.results['passed']/(self.results['passed'] + self.results['failed'])*100)
            self.log(f"   Success rate: {success_rate:.1f}%")
        
        self.log(f"   Total time: {total_time:.2f}s")
        self.log(f"   Admin user: {self.username}")
        self.log(f"   Superuser privileges: {'Yes' if self.is_superuser else 'No'}")
        
        # Success criteria
        success_threshold = 85.0  # 85% success rate for admin tests
        is_success = (self.results['failed'] == 0) or (success_rate >= success_threshold)
        
        if is_success:
            self.log(f"   🎉 Admin system tests PASSED")
        else:
            self.log(f"   ⚠️ Admin system tests need attention")
        
        if not self.is_superuser:
            self.log(f"   ℹ️ Some tests were skipped due to non-superuser account")
            self.log(f"   💡 Run with superuser account for complete testing")
        
        return is_success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer Admin System Tester")
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
    tester = RefServerAdminTester(args.url, args.username, args.password)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()