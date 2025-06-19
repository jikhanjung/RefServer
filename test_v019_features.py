#!/usr/bin/env python3
"""
Test script for RefServer v0.1.9 new features
Tests async error handling, performance monitoring, and queue management
"""

import os
import sys
import json
import time
import asyncio
import requests
import tempfile
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

# Add app directory to path for imports
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class V019FeatureTester:
    """Test suite for RefServer v0.1.9 new features"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.test_results = {}
        self.test_pdfs = []
        
        # Test configuration
        self.test_timeout = 300  # 5 minutes max per test
        self.concurrent_upload_count = 5
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all v0.1.9 feature tests"""
        print("🧪 RefServer v0.1.9 Feature Test Suite")
        print("=" * 50)
        
        try:
            # Check server health first
            if not self._check_server_health():
                return {"error": "Server is not accessible", "tests": {}}
            
            # Create test PDFs
            self._create_test_pdfs()
            
            # Run test categories
            test_categories = [
                ("Server Health", self._test_server_health),
                ("Performance Monitoring", self._test_performance_monitoring),
                ("Queue Management", self._test_queue_management),
                ("Error Handling & Retry", self._test_error_handling),
                ("Concurrent Processing", self._test_concurrent_processing),
                ("Priority Queue System", self._test_priority_queue),
                ("System Metrics", self._test_system_metrics),
                ("Export Functionality", self._test_export_functionality),
                ("Security Validation", self._test_security_validation)
            ]
            
            for category_name, test_func in test_categories:
                print(f"\n📋 Testing {category_name}...")
                try:
                    result = test_func()
                    self.test_results[category_name] = result
                    status = "✅ PASS" if result.get('success', False) else "❌ FAIL"
                    print(f"   {status}: {result.get('summary', 'No summary')}")
                except Exception as e:
                    self.test_results[category_name] = {
                        'success': False,
                        'error': str(e),
                        'summary': f"Test failed with exception: {e}"
                    }
                    print(f"   ❌ FAIL: Exception - {e}")
            
            # Generate summary
            summary = self._generate_test_summary()
            self.test_results['_summary'] = summary
            
            return self.test_results
            
        except Exception as e:
            logger.error(f"Test suite failed: {e}")
            return {"error": str(e), "tests": self.test_results}
        
        finally:
            # Cleanup test PDFs
            self._cleanup_test_files()
    
    def _check_server_health(self) -> bool:
        """Check if server is accessible"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            return response.status_code == 200
        except:
            return False
    
    def _create_test_pdfs(self):
        """Create test PDF files"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            for i in range(5):
                # Create temporary PDF file
                temp_fd, temp_path = tempfile.mkstemp(suffix=f'_test_{i}.pdf', prefix='refserver_test_')
                
                # Create PDF content
                c = canvas.Canvas(temp_path, pagesize=letter)
                c.drawString(100, 750, f"RefServer v0.1.9 Test Document #{i+1}")
                c.drawString(100, 720, f"Created: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                c.drawString(100, 690, "This is a test document for queue and performance testing.")
                
                # Add multiple pages for processing complexity
                for page in range(2 + i):  # Variable page count
                    c.showPage()
                    c.drawString(100, 750, f"Page {page + 2}")
                    c.drawString(100, 720, "Additional content for processing complexity.")
                
                c.save()
                os.close(temp_fd)
                
                self.test_pdfs.append({
                    'path': temp_path,
                    'filename': f'test_doc_{i+1}.pdf',
                    'size_mb': os.path.getsize(temp_path) / 1024 / 1024
                })
                
            logger.info(f"Created {len(self.test_pdfs)} test PDFs")
            
        except ImportError:
            logger.warning("reportlab not available, using dummy files")
            # Create dummy PDF files
            for i in range(5):
                temp_fd, temp_path = tempfile.mkstemp(suffix=f'_test_{i}.pdf', prefix='refserver_test_')
                with os.fdopen(temp_fd, 'wb') as f:
                    f.write(b'%PDF-1.4\n%dummy test file\n%%EOF\n')
                
                self.test_pdfs.append({
                    'path': temp_path,
                    'filename': f'test_doc_{i+1}.pdf',
                    'size_mb': os.path.getsize(temp_path) / 1024 / 1024
                })
    
    def _cleanup_test_files(self):
        """Clean up test PDF files"""
        for pdf_info in self.test_pdfs:
            try:
                if os.path.exists(pdf_info['path']):
                    os.unlink(pdf_info['path'])
            except:
                pass
    
    def _test_server_health(self) -> Dict[str, Any]:
        """Test basic server health and new endpoints"""
        try:
            results = {}
            
            # Test health endpoint
            response = requests.get(f"{self.base_url}/health", timeout=10)
            results['health'] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200
            }
            
            # Test status endpoint
            response = requests.get(f"{self.base_url}/status", timeout=10)
            results['status'] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200,
                'has_version': 'version' in response.json() if response.status_code == 200 else False
            }
            
            # Test new queue status endpoint
            response = requests.get(f"{self.base_url}/queue/status", timeout=10)
            results['queue_endpoint'] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200
            }
            
            # Test new performance endpoints
            response = requests.get(f"{self.base_url}/performance/stats", timeout=10)
            results['performance_endpoint'] = {
                'status_code': response.status_code,
                'accessible': response.status_code == 200
            }
            
            success = all(r.get('accessible', False) for r in results.values())
            
            return {
                'success': success,
                'summary': f"Server health check: {'all endpoints accessible' if success else 'some endpoints failed'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Server health test failed: {e}"
            }
    
    def _test_performance_monitoring(self) -> Dict[str, Any]:
        """Test performance monitoring functionality"""
        try:
            results = {}
            
            # Test performance stats endpoint
            response = requests.get(f"{self.base_url}/performance/stats", timeout=15)
            if response.status_code == 200:
                stats = response.json()
                results['stats_structure'] = {
                    'has_jobs': 'jobs' in stats,
                    'has_performance': 'performance' in stats,
                    'has_system': 'system' in stats,
                    'has_resources': 'resources' in stats
                }
            else:
                results['stats_structure'] = {'error': f"Status {response.status_code}"}
            
            # Test system metrics endpoint
            response = requests.get(f"{self.base_url}/performance/system", timeout=15)
            if response.status_code == 200:
                system = response.json()
                results['system_metrics'] = {
                    'has_cpu': 'cpu' in system,
                    'has_memory': 'memory' in system,
                    'has_disk': 'disk' in system,
                    'has_timestamp': 'timestamp' in system
                }
            else:
                results['system_metrics'] = {'error': f"Status {response.status_code}"}
            
            # Test job metrics endpoint
            response = requests.get(f"{self.base_url}/performance/jobs", timeout=15)
            if response.status_code == 200:
                jobs = response.json()
                results['job_metrics'] = {
                    'has_recent_jobs': 'recent_jobs' in jobs,
                    'has_active_jobs': 'active_jobs' in jobs,
                    'structure_valid': isinstance(jobs.get('recent_jobs', []), list)
                }
            else:
                results['job_metrics'] = {'error': f"Status {response.status_code}"}
            
            success = all(
                isinstance(r, dict) and 'error' not in r 
                for r in results.values()
            )
            
            return {
                'success': success,
                'summary': f"Performance monitoring: {'all endpoints working' if success else 'some endpoints failed'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Performance monitoring test failed: {e}"
            }
    
    def _test_queue_management(self) -> Dict[str, Any]:
        """Test job queue management"""
        try:
            results = {}
            
            # Test initial queue status
            response = requests.get(f"{self.base_url}/queue/status", timeout=10)
            if response.status_code == 200:
                initial_status = response.json()
                results['initial_queue'] = {
                    'accessible': True,
                    'queue_size': initial_status.get('queue_size', 0),
                    'active_jobs': initial_status.get('active_jobs', 0),
                    'max_concurrent': initial_status.get('max_concurrent', 0)
                }
            else:
                results['initial_queue'] = {'accessible': False, 'status': response.status_code}
            
            # Test priority upload endpoint
            if self.test_pdfs:
                test_pdf = self.test_pdfs[0]
                
                with open(test_pdf['path'], 'rb') as f:
                    files = {'file': (test_pdf['filename'], f, 'application/pdf')}
                    data = {'priority': 'high'}
                    
                    response = requests.post(
                        f"{self.base_url}/upload-priority",
                        files=files,
                        data=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        upload_result = response.json()
                        results['priority_upload'] = {
                            'success': True,
                            'job_id': upload_result.get('job_id'),
                            'priority': upload_result.get('priority'),
                            'status': upload_result.get('status')
                        }
                        
                        # Test queue status after upload
                        time.sleep(1)
                        response = requests.get(f"{self.base_url}/queue/status", timeout=10)
                        if response.status_code == 200:
                            after_status = response.json()
                            results['queue_after_upload'] = {
                                'queue_size': after_status.get('queue_size', 0),
                                'active_jobs': after_status.get('active_jobs', 0)
                            }
                    else:
                        results['priority_upload'] = {
                            'success': False,
                            'status': response.status_code,
                            'error': response.text
                        }
            
            success = results.get('initial_queue', {}).get('accessible', False)
            
            return {
                'success': success,
                'summary': f"Queue management: {'working properly' if success else 'failed to access queue'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Queue management test failed: {e}"
            }
    
    def _test_error_handling(self) -> Dict[str, Any]:
        """Test error handling and retry mechanisms"""
        try:
            results = {}
            
            # Test invalid file upload (should trigger error handling)
            try:
                # Create a non-PDF file
                temp_fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix='invalid_')
                with os.fdopen(temp_fd, 'w') as f:
                    f.write("This is not a PDF file")
                
                with open(temp_path, 'rb') as f:
                    files = {'file': ('invalid.txt', f, 'text/plain')}
                    
                    response = requests.post(
                        f"{self.base_url}/upload-priority",
                        files=files,
                        timeout=10
                    )
                    
                    results['invalid_file_handling'] = {
                        'rejects_non_pdf': response.status_code == 400,
                        'status_code': response.status_code
                    }
                
                os.unlink(temp_path)
                
            except Exception as e:
                results['invalid_file_handling'] = {'error': str(e)}
            
            # Test invalid priority parameter
            if self.test_pdfs:
                test_pdf = self.test_pdfs[0]
                
                with open(test_pdf['path'], 'rb') as f:
                    files = {'file': (test_pdf['filename'], f, 'application/pdf')}
                    data = {'priority': 'invalid_priority'}
                    
                    response = requests.post(
                        f"{self.base_url}/upload-priority",
                        files=files,
                        data=data,
                        timeout=10
                    )
                    
                    results['invalid_priority_handling'] = {
                        'rejects_invalid_priority': response.status_code == 400,
                        'status_code': response.status_code
                    }
            
            # Test non-existent job cancellation
            response = requests.post(f"{self.base_url}/queue/cancel/non-existent-job", timeout=10)
            results['invalid_job_cancel'] = {
                'handles_invalid_job': response.status_code in [400, 404],
                'status_code': response.status_code
            }
            
            success = (
                results.get('invalid_file_handling', {}).get('rejects_non_pdf', False) and
                results.get('invalid_priority_handling', {}).get('rejects_invalid_priority', False)
            )
            
            return {
                'success': success,
                'summary': f"Error handling: {'proper validation and error responses' if success else 'some validation issues'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Error handling test failed: {e}"
            }
    
    def _test_concurrent_processing(self) -> Dict[str, Any]:
        """Test concurrent job processing with queue limits"""
        try:
            results = {}
            job_ids = []
            
            # Get initial queue status
            response = requests.get(f"{self.base_url}/queue/status", timeout=10)
            if response.status_code == 200:
                initial_status = response.json()
                max_concurrent = initial_status.get('max_concurrent', 3)
                results['initial_status'] = initial_status
            else:
                max_concurrent = 3
                results['initial_status'] = {'error': 'Could not get initial status'}
            
            # Upload multiple PDFs concurrently
            def upload_pdf(pdf_info, priority='normal'):
                try:
                    with open(pdf_info['path'], 'rb') as f:
                        files = {'file': (pdf_info['filename'], f, 'application/pdf')}
                        data = {'priority': priority}
                        
                        response = requests.post(
                            f"{self.base_url}/upload-priority",
                            files=files,
                            data=data,
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            return response.json().get('job_id')
                        else:
                            logger.warning(f"Upload failed: {response.status_code}")
                            return None
                            
                except Exception as e:
                    logger.error(f"Upload error: {e}")
                    return None
            
            # Upload PDFs with different priorities
            priorities = ['low', 'normal', 'high', 'urgent', 'normal']
            
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = []
                for i, pdf_info in enumerate(self.test_pdfs[:5]):
                    priority = priorities[i % len(priorities)]
                    future = executor.submit(upload_pdf, pdf_info, priority)
                    futures.append(future)
                
                # Collect results
                for future in futures:
                    job_id = future.result(timeout=30)
                    if job_id:
                        job_ids.append(job_id)
            
            results['concurrent_uploads'] = {
                'attempted': len(self.test_pdfs[:5]),
                'successful': len(job_ids),
                'job_ids': job_ids
            }
            
            # Check queue status after uploads
            time.sleep(2)
            response = requests.get(f"{self.base_url}/queue/status", timeout=10)
            if response.status_code == 200:
                after_status = response.json()
                results['queue_after_concurrent'] = after_status
                
                # Verify queue management
                total_jobs = after_status.get('queue_size', 0) + after_status.get('active_jobs', 0)
                results['queue_management'] = {
                    'total_jobs_in_system': total_jobs,
                    'queue_size': after_status.get('queue_size', 0),
                    'active_jobs': after_status.get('active_jobs', 0),
                    'respects_concurrent_limit': after_status.get('active_jobs', 0) <= max_concurrent
                }
            
            success = (
                len(job_ids) > 0 and
                results.get('queue_management', {}).get('respects_concurrent_limit', False)
            )
            
            return {
                'success': success,
                'summary': f"Concurrent processing: {'queue limits respected, {len(job_ids)} jobs queued' if success else 'queue management issues'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Concurrent processing test failed: {e}"
            }
    
    def _test_priority_queue(self) -> Dict[str, Any]:
        """Test priority queue functionality"""
        try:
            results = {}
            
            # Upload PDFs with different priorities
            priorities = ['low', 'high', 'urgent', 'normal']
            job_info = []
            
            for i, priority in enumerate(priorities):
                if i >= len(self.test_pdfs):
                    break
                    
                pdf_info = self.test_pdfs[i]
                
                with open(pdf_info['path'], 'rb') as f:
                    files = {'file': (f'priority_test_{priority}_{i}.pdf', f, 'application/pdf')}
                    data = {'priority': priority}
                    
                    response = requests.post(
                        f"{self.base_url}/upload-priority",
                        files=files,
                        data=data,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        job_info.append({
                            'job_id': result.get('job_id'),
                            'priority': priority,
                            'upload_time': time.time()
                        })
            
            results['priority_uploads'] = {
                'attempted': len(priorities),
                'successful': len(job_info),
                'jobs': job_info
            }
            
            # Check queue status and order
            time.sleep(1)
            response = requests.get(f"{self.base_url}/queue/status", timeout=10)
            if response.status_code == 200:
                queue_status = response.json()
                queue_items = queue_status.get('queue_items', [])
                
                results['queue_order'] = {
                    'total_in_queue': len(queue_items),
                    'queue_items': queue_items[:5],  # First 5 items
                    'priority_order_correct': self._check_priority_order(queue_items)
                }
            
            success = len(job_info) > 0
            
            return {
                'success': success,
                'summary': f"Priority queue: {len(job_info)} jobs with different priorities queued",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Priority queue test failed: {e}"
            }
    
    def _check_priority_order(self, queue_items: List[Dict]) -> bool:
        """Check if queue items are in correct priority order"""
        try:
            priority_values = {'URGENT': 0, 'HIGH': 1, 'NORMAL': 2, 'LOW': 3}
            
            for i in range(len(queue_items) - 1):
                current_priority = priority_values.get(queue_items[i].get('priority', 'NORMAL'), 2)
                next_priority = priority_values.get(queue_items[i + 1].get('priority', 'NORMAL'), 2)
                
                if current_priority > next_priority:  # Lower number = higher priority
                    return False
            
            return True
            
        except:
            return False
    
    def _test_system_metrics(self) -> Dict[str, Any]:
        """Test system metrics collection"""
        try:
            results = {}
            
            # Test system metrics endpoint
            response = requests.get(f"{self.base_url}/performance/system", timeout=10)
            if response.status_code == 200:
                metrics = response.json()
                
                results['metrics_structure'] = {
                    'has_timestamp': 'timestamp' in metrics,
                    'has_cpu_data': 'cpu' in metrics and 'percent' in metrics.get('cpu', {}),
                    'has_memory_data': 'memory' in metrics and 'percent' in metrics.get('memory', {}),
                    'has_disk_data': 'disk' in metrics and 'percent' in metrics.get('disk', {}),
                    'has_job_data': 'jobs' in metrics
                }
                
                # Validate metric ranges
                cpu = metrics.get('cpu', {})
                memory = metrics.get('memory', {})
                disk = metrics.get('disk', {})
                
                results['metrics_validation'] = {
                    'cpu_percent_valid': 0 <= cpu.get('percent', -1) <= 100,
                    'memory_percent_valid': 0 <= memory.get('percent', -1) <= 100,
                    'disk_percent_valid': 0 <= disk.get('percent', -1) <= 100,
                    'memory_values_consistent': memory.get('used_mb', 0) <= memory.get('total_mb', 1),
                    'disk_values_consistent': disk.get('used_mb', 0) <= disk.get('total_mb', 1)
                }
                
            else:
                results['metrics_structure'] = {'error': f"Status {response.status_code}"}
                results['metrics_validation'] = {'error': 'Could not validate metrics'}
            
            success = (
                results.get('metrics_structure', {}).get('has_timestamp', False) and
                results.get('metrics_structure', {}).get('has_cpu_data', False) and
                results.get('metrics_validation', {}).get('cpu_percent_valid', False)
            )
            
            return {
                'success': success,
                'summary': f"System metrics: {'collecting valid data' if success else 'data collection issues'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"System metrics test failed: {e}"
            }
    
    def _test_export_functionality(self) -> Dict[str, Any]:
        """Test performance data export functionality"""
        try:
            results = {}
            
            # Test JSON export
            response = requests.get(f"{self.base_url}/performance/export?format=json", timeout=20)
            if response.status_code == 200:
                try:
                    export_data = response.json()
                    results['json_export'] = {
                        'success': True,
                        'has_export_timestamp': 'export_timestamp' in export_data,
                        'has_completed_jobs': 'completed_jobs' in export_data,
                        'has_system_metrics': 'system_metrics' in export_data,
                        'has_performance_stats': 'performance_stats' in export_data,
                        'data_size': len(str(export_data))
                    }
                except json.JSONDecodeError:
                    results['json_export'] = {'success': False, 'error': 'Invalid JSON format'}
            else:
                results['json_export'] = {'success': False, 'status': response.status_code}
            
            # Test CSV export
            response = requests.get(f"{self.base_url}/performance/export?format=csv", timeout=20)
            if response.status_code == 200:
                csv_content = response.text
                results['csv_export'] = {
                    'success': True,
                    'has_header': 'job_id,filename' in csv_content[:100],  # Check first 100 chars
                    'content_type': response.headers.get('content-type', ''),
                    'content_length': len(csv_content)
                }
            else:
                results['csv_export'] = {'success': False, 'status': response.status_code}
            
            # Test invalid format
            response = requests.get(f"{self.base_url}/performance/export?format=invalid", timeout=10)
            results['invalid_format'] = {
                'rejects_invalid': response.status_code == 400,
                'status': response.status_code
            }
            
            success = (
                results.get('json_export', {}).get('success', False) and
                results.get('csv_export', {}).get('success', False) and
                results.get('invalid_format', {}).get('rejects_invalid', False)
            )
            
            return {
                'success': success,
                'summary': f"Export functionality: {'JSON and CSV export working' if success else 'export issues detected'}",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Export functionality test failed: {e}"
            }
    
    def _test_security_validation(self) -> Dict[str, Any]:
        """Test file upload security validation system"""
        try:
            results = {}
            
            # Test 1: Security status endpoint
            response = requests.get(f"{self.base_url}/security/status", timeout=15)
            if response.status_code == 200:
                security_status = response.json()
                results['security_status'] = {
                    'success': True,
                    'enabled': security_status.get('enabled', False),
                    'max_file_size_mb': security_status.get('max_file_size_mb', 0),
                    'allowed_extensions': security_status.get('allowed_extensions', []),
                    'rate_limits': security_status.get('rate_limits', {}),
                    'quarantine_enabled': security_status.get('quarantine', {}).get('enabled', False)
                }
            else:
                results['security_status'] = {'success': False, 'status': response.status_code}
            
            # Test 2: Valid PDF upload (should pass security)
            if self.test_pdfs:
                test_pdf = self.test_pdfs[0]
                with open(test_pdf, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/upload",
                        files={'file': ('valid_test.pdf', f, 'application/pdf')},
                        timeout=30
                    )
                results['valid_upload'] = {
                    'success': response.status_code in [200, 201],
                    'status': response.status_code,
                    'passes_security': response.status_code != 400  # 400 would indicate security rejection
                }
            else:
                results['valid_upload'] = {'success': False, 'error': 'No test PDF available'}
            
            # Test 3: Invalid file type (should be rejected)
            try:
                # Create a temporary text file pretending to be PDF
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                    temp_file.write("This is not a PDF file")
                    temp_txt_path = temp_file.name
                
                with open(temp_txt_path, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/upload",
                        files={'file': ('malicious.pdf', f, 'text/plain')},
                        timeout=15
                    )
                
                results['invalid_file_rejection'] = {
                    'success': response.status_code == 400,  # Should be rejected
                    'status': response.status_code,
                    'properly_rejected': response.status_code in [400, 422]
                }
                
                # Cleanup
                os.unlink(temp_txt_path)
                
            except Exception as e:
                results['invalid_file_rejection'] = {'success': False, 'error': str(e)}
            
            # Test 4: Oversized file (create large dummy file)
            try:
                # Create a large dummy file (over typical limits)
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    # Write 101MB of data (should exceed typical 100MB limit)
                    chunk = b'x' * (1024 * 1024)  # 1MB chunk
                    for _ in range(101):  # 101MB total
                        temp_file.write(chunk)
                    large_file_path = temp_file.name
                
                with open(large_file_path, 'rb') as f:
                    response = requests.post(
                        f"{self.base_url}/upload",
                        files={'file': ('large_file.pdf', f, 'application/pdf')},
                        timeout=30
                    )
                
                results['oversized_file_rejection'] = {
                    'success': response.status_code in [400, 413],  # Should be rejected for size
                    'status': response.status_code,
                    'properly_rejected': response.status_code in [400, 413, 422]
                }
                
                # Cleanup
                os.unlink(large_file_path)
                
            except Exception as e:
                results['oversized_file_rejection'] = {'success': False, 'error': str(e)}
            
            # Test 5: Rate limiting (multiple rapid requests)
            try:
                rate_limit_responses = []
                for i in range(5):  # Try 5 rapid uploads
                    if self.test_pdfs:
                        with open(self.test_pdfs[0], 'rb') as f:
                            response = requests.post(
                                f"{self.base_url}/upload",
                                files={'file': (f'rate_test_{i}.pdf', f, 'application/pdf')},
                                timeout=10
                            )
                        rate_limit_responses.append(response.status_code)
                    time.sleep(0.1)  # Small delay between requests
                
                # Check if at least some requests succeeded and potentially some rate limited
                success_count = sum(1 for status in rate_limit_responses if status in [200, 201])
                results['rate_limiting'] = {
                    'success': success_count > 0,  # At least some should succeed
                    'response_codes': rate_limit_responses,
                    'success_count': success_count,
                    'potentially_rate_limited': any(status == 429 for status in rate_limit_responses)
                }
                
            except Exception as e:
                results['rate_limiting'] = {'success': False, 'error': str(e)}
            
            # Calculate overall success
            test_successes = [
                results.get('security_status', {}).get('success', False),
                results.get('valid_upload', {}).get('success', False),
                results.get('invalid_file_rejection', {}).get('success', False),
                results.get('oversized_file_rejection', {}).get('success', False),
                results.get('rate_limiting', {}).get('success', False)
            ]
            
            success_count = sum(test_successes)
            overall_success = success_count >= 3  # At least 3/5 tests should pass
            
            return {
                'success': overall_success,
                'summary': f"Security validation: {success_count}/5 tests passed",
                'details': results
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'summary': f"Security validation test failed: {e}"
            }
    
    def _generate_test_summary(self) -> Dict[str, Any]:
        """Generate overall test summary"""
        total_tests = len([k for k in self.test_results.keys() if k != '_summary'])
        passed_tests = len([k for k, v in self.test_results.items() 
                           if k != '_summary' and v.get('success', False)])
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        # Feature status summary
        feature_status = {
            'async_error_handling': self.test_results.get('Error Handling & Retry', {}).get('success', False),
            'performance_monitoring': self.test_results.get('Performance Monitoring', {}).get('success', False),
            'queue_management': self.test_results.get('Queue Management', {}).get('success', False),
            'concurrent_processing': self.test_results.get('Concurrent Processing', {}).get('success', False),
            'priority_queue': self.test_results.get('Priority Queue System', {}).get('success', False),
            'system_metrics': self.test_results.get('System Metrics', {}).get('success', False),
            'export_functionality': self.test_results.get('Export Functionality', {}).get('success', False),
            'security_validation': self.test_results.get('Security Validation', {}).get('success', False)
        }
        
        return {
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': total_tests - passed_tests,
            'success_rate': success_rate,
            'overall_status': 'PASS' if success_rate >= 80 else 'FAIL',
            'feature_status': feature_status,
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check specific test results and provide recommendations
        if not self.test_results.get('Performance Monitoring', {}).get('success', False):
            recommendations.append("Performance monitoring endpoints need attention")
        
        if not self.test_results.get('Queue Management', {}).get('success', False):
            recommendations.append("Job queue management system requires fixes")
        
        if not self.test_results.get('Error Handling & Retry', {}).get('success', False):
            recommendations.append("Error handling and validation needs improvement")
        
        if not self.test_results.get('Concurrent Processing', {}).get('success', False):
            recommendations.append("Concurrent processing limits may not be working correctly")
        
        if not recommendations:
            recommendations.append("All v0.1.9 features are working correctly!")
        
        return recommendations


def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test RefServer v0.1.9 features')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='RefServer base URL (default: http://localhost:8000)')
    parser.add_argument('--output', '-o', help='Output file for test results (JSON)')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose output')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    tester = V019FeatureTester(args.url)
    results = tester.run_all_tests()
    
    # Print summary
    print("\n" + "=" * 50)
    print("🎯 TEST SUMMARY")
    print("=" * 50)
    
    summary = results.get('_summary', {})
    print(f"📊 Tests: {summary.get('passed_tests', 0)}/{summary.get('total_tests', 0)} passed")
    print(f"📈 Success Rate: {summary.get('success_rate', 0):.1f}%")
    print(f"🏆 Overall: {summary.get('overall_status', 'UNKNOWN')}")
    
    print(f"\n🔧 Feature Status:")
    feature_status = summary.get('feature_status', {})
    for feature, status in feature_status.items():
        status_icon = "✅" if status else "❌"
        feature_name = feature.replace('_', ' ').title()
        print(f"   {status_icon} {feature_name}")
    
    print(f"\n💡 Recommendations:")
    for rec in summary.get('recommendations', []):
        print(f"   • {rec}")
    
    # Save results if requested
    if args.output:
        try:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")
        except Exception as e:
            print(f"\n❌ Failed to save results: {e}")
    
    # Exit with appropriate code
    success_rate = summary.get('success_rate', 0)
    exit_code = 0 if success_rate >= 80 else 1
    sys.exit(exit_code)


if __name__ == '__main__':
    main()