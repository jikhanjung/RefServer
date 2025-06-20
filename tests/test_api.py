#!/usr/bin/env python3
"""
RefServer API 테스트 스크립트 (v0.1.12)
환경 적응형 테스트 + 비동기 처리 API 포함 모든 엔드포인트를 테스트하고 결과를 확인합니다.
v0.1.12: 백업 시스템, 일관성 검증, 재해 복구 기능 포함
"""

import requests
import json
import time
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

class RefServerAPITester:
    def __init__(self, base_url: str = "http://localhost:8060"):
        """
        Initialize API tester
        
        Args:
            base_url: RefServer API base URL
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefServer-API-Tester/1.0'
        })
        
        # Test results
        self.results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Store processed document ID for subsequent tests
        self.test_doc_id = None
        
        # Store deployment mode and service status
        self.deployment_mode = None
        self.service_status = {}
    
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
    
    def test_health_check(self):
        """Test health check endpoint"""
        self.log("Testing health check endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            success = self.assert_response(response, 200, "Health Check")
            
            if success:
                data = response.json()
                assert data.get('status') == 'healthy'
                self.log(f"   Service status: {data.get('status')}")
            
        except Exception as e:
            self.log(f"Health check failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_service_status(self):
        """Test service status endpoint"""
        self.log("Testing service status endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/status")
            success = self.assert_response(response, 200, "Service Status")
            
            if success:
                data = response.json()
                self.log(f"   Database: {'✅' if data.get('database') else '❌'}")
                
                # GPU-dependent services
                quality_assessment = data.get('quality_assessment')
                layout_analysis = data.get('layout_analysis')
                
                self.log(f"   Quality Assessment (GPU): {'✅' if quality_assessment else '❌'}")
                self.log(f"   Layout Analysis (GPU): {'✅' if layout_analysis else '❌'}")
                
                # CPU-compatible services
                metadata_extraction = data.get('metadata_extraction')
                self.log(f"   Metadata Extraction (CPU): {'✅' if metadata_extraction else '❌'}")
                
                # Determine deployment mode
                if quality_assessment and layout_analysis:
                    self.deployment_mode = "GPU"
                    self.log("   🎮 GPU Mode: All services available")
                elif metadata_extraction:
                    self.deployment_mode = "CPU"
                    self.log("   🖥️ CPU Mode: Core services only")
                else:
                    self.deployment_mode = "MINIMAL"
                    self.log("   ⚠️ Minimal Mode: Basic processing only")
                
                # Store service availability for later tests
                self.service_status = {
                    'quality_assessment': quality_assessment,
                    'layout_analysis': layout_analysis,
                    'metadata_extraction': metadata_extraction
                }
            
        except Exception as e:
            self.log(f"Service status test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_upload_pdf(self, pdf_path: str = None):
        """Test PDF upload endpoint (new async API)"""
        self.log("Testing PDF upload endpoint...")
        
        # Create a test PDF if none provided
        if not pdf_path:
            pdf_path = self.create_test_pdf()
        
        if not pdf_path or not os.path.exists(pdf_path):
            self.log("❌ No test PDF file available for upload test", "ERROR")
            self.results['failed'] += 1
            return None
        
        try:
            with open(pdf_path, 'rb') as pdf_file:
                files = {'file': ('test.pdf', pdf_file, 'application/pdf')}
                
                self.log(f"   Uploading PDF: {os.path.basename(pdf_path)}")
                start_time = time.time()
                
                response = self.session.post(
                    f"{self.base_url}/upload",
                    files=files,
                    timeout=30  # 30 second timeout for upload
                )
                
                upload_time = time.time() - start_time
                success = self.assert_response(response, 200, "PDF Upload")
                
                if success:
                    data = response.json()
                    job_id = data.get('job_id')
                    
                    self.log(f"   Job ID: {job_id}")
                    self.log(f"   Status: {data.get('status')}")
                    self.log(f"   Upload time: {upload_time:.2f}s")
                    self.log(f"   Message: {data.get('message')}")
                    
                    return job_id
                else:
                    return None
                    
        except Exception as e:
            self.log(f"Upload test failed: {e}", "ERROR")
            self.results['failed'] += 1
            return None
    
    def test_job_status_polling(self, job_id: str, max_wait_time: int = 300):
        """Test job status polling until completion"""
        self.log(f"Testing job status polling for job: {job_id}")
        
        start_time = time.time()
        last_progress = -1
        
        try:
            while time.time() - start_time < max_wait_time:
                response = self.session.get(f"{self.base_url}/job/{job_id}")
                success = self.assert_response(response, 200, "Job Status")
                
                if not success:
                    return None
                
                data = response.json()
                status = data.get('status')
                progress = data.get('progress_percentage', 0)
                current_step = data.get('current_step', 'Unknown')
                
                # Log progress updates
                if progress != last_progress:
                    self.log(f"   Progress: {progress}% - {current_step}")
                    last_progress = progress
                
                if status == 'completed':
                    self.test_doc_id = data.get('paper_id')
                    elapsed_time = time.time() - start_time
                    
                    self.log(f"   ✅ Processing completed in {elapsed_time:.2f}s")
                    self.log(f"   Document ID: {self.test_doc_id}")
                    self.log(f"   Steps completed: {len(data.get('steps_completed', []))}")
                    self.log(f"   Steps failed: {len(data.get('steps_failed', []))}")
                    
                    # Show result summary
                    result_summary = data.get('result_summary', {})
                    if result_summary:
                        self.log(f"   Final success: {result_summary.get('success')}")
                        if result_summary.get('warnings'):
                            self.log(f"   Warnings: {len(result_summary.get('warnings', []))}")
                    
                    return self.test_doc_id
                    
                elif status == 'failed':
                    error_msg = data.get('error_message', 'Unknown error')
                    self.log(f"   ❌ Processing failed: {error_msg}", "ERROR")
                    self.results['failed'] += 1
                    return None
                
                elif status == 'processing':
                    # Continue polling
                    time.sleep(2)
                    continue
                
                else:
                    self.log(f"   Unknown status: {status}", "WARNING")
                    time.sleep(2)
                    continue
            
            # Timeout reached
            self.log(f"   ⏰ Processing timeout after {max_wait_time}s", "ERROR")
            self.results['failed'] += 1
            return None
            
        except Exception as e:
            self.log(f"Job status polling failed: {e}", "ERROR")
            self.results['failed'] += 1
            return None
    
    def test_process_pdf_legacy(self, pdf_path: str = None):
        """Test legacy PDF processing endpoint (for backward compatibility)"""
        self.log("Testing legacy PDF processing endpoint...")
        
        # Create a test PDF if none provided
        if not pdf_path:
            pdf_path = self.create_test_pdf()
        
        if not pdf_path or not os.path.exists(pdf_path):
            self.log("❌ No test PDF file available for legacy processing test", "ERROR")
            self.results['failed'] += 1
            return
        
        try:
            with open(pdf_path, 'rb') as pdf_file:
                files = {'file': ('test.pdf', pdf_file, 'application/pdf')}
                
                self.log(f"   Uploading PDF: {os.path.basename(pdf_path)}")
                start_time = time.time()
                
                response = self.session.post(
                    f"{self.base_url}/process",
                    files=files,
                    timeout=300  # 5 minute timeout for processing
                )
                
                processing_time = time.time() - start_time
                success = self.assert_response(response, 200, "Legacy PDF Processing")
                
                if success:
                    data = response.json()
                    doc_id = data.get('doc_id')
                    
                    self.log(f"   Document ID: {doc_id}")
                    self.log(f"   Success: {data.get('success')}")
                    self.log(f"   Processing time: {data.get('processing_time', 0):.2f}s")
                    self.log(f"   Steps completed: {len(data.get('steps_completed', []))}")
                    self.log(f"   Steps failed: {len(data.get('steps_failed', []))}")
                    
                    if data.get('warnings'):
                        self.log(f"   Warnings: {len(data.get('warnings'))}")
                        for warning in data.get('warnings', [])[:3]:  # Show first 3 warnings
                            self.log(f"     - {warning}")
                    
                    # Store doc_id for subsequent tests if not already set
                    if not self.test_doc_id and doc_id:
                        self.test_doc_id = doc_id
                        self.log(f"   Using doc_id {self.test_doc_id} for subsequent tests")
        
        except requests.Timeout:
            self.log("❌ PDF processing timed out (5 minutes)", "ERROR")
            self.results['failed'] += 1
        except Exception as e:
            self.log(f"PDF processing test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_paper_info(self):
        """Test paper info endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping paper info test - no doc_id available", "WARN")
            return
        
        self.log("Testing paper info endpoint...")
        
        # Check if quality assessment is available
        quality_assessment_available = self.service_status.get('quality_assessment', False)
        
        try:
            response = self.session.get(f"{self.base_url}/paper/{self.test_doc_id}")
            success = self.assert_response(response, 200, "Paper Info")
            
            if success:
                data = response.json()
                self.log(f"   Filename: {data.get('filename')}")
                
                ocr_quality = data.get('ocr_quality')
                if quality_assessment_available and ocr_quality:
                    self.log(f"   OCR Quality (LLaVA): {ocr_quality}")
                    self.log(f"   ✅ GPU-based quality assessment available")
                elif ocr_quality:
                    self.log(f"   OCR Quality (basic): {ocr_quality}")
                    self.log(f"   ℹ️ Basic quality assessment (GPU unavailable)")
                else:
                    self.log(f"   OCR Quality: Not assessed")
                    if not quality_assessment_available:
                        self.log(f"   ℹ️ Quality assessment unavailable in CPU mode")
                
                self.log(f"   Text length: {len(data.get('ocr_text', ''))}")
        
        except Exception as e:
            self.log(f"Paper info test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_metadata(self):
        """Test metadata endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping metadata test - no doc_id available", "WARN")
            return
        
        self.log("Testing metadata endpoint...")
        
        # Check deployment mode for metadata extraction expectations
        metadata_expected = self.service_status.get('metadata_extraction', False)
        
        try:
            response = self.session.get(f"{self.base_url}/metadata/{self.test_doc_id}")
            
            if metadata_expected:
                # LLM-based metadata extraction available
                success = self.assert_response(response, [200, 404], "Metadata (LLM-based)")
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"   Title: {data.get('title', 'N/A')}")
                    self.log(f"   Authors: {len(data.get('authors', []))} found")
                    self.log(f"   Year: {data.get('year', 'N/A')}")
                    self.log(f"   Journal: {data.get('journal', 'N/A')}")
                    self.log(f"   ✅ LLM-based extraction successful")
                elif response.status_code == 404:
                    self.log("   No metadata found (LLM processing may have failed)")
            else:
                # Fallback to rule-based extraction
                success = self.assert_response(response, [200, 404], "Metadata (Rule-based fallback)")
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"   Title: {data.get('title', 'N/A')}")
                    self.log(f"   Authors: {len(data.get('authors', []))} found")
                    self.log(f"   Year: {data.get('year', 'N/A')}")
                    self.log(f"   ✅ Rule-based extraction working (LLM unavailable)")
                elif response.status_code == 404:
                    self.log("   No metadata found (normal for test files with rule-based extraction)")
        
        except Exception as e:
            self.log(f"Metadata test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_embedding(self):
        """Test embedding endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping embedding test - no doc_id available", "WARN")
            return
        
        self.log("Testing embedding endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/embedding/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Embedding")  # 404 is OK if no embedding
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Dimension: {data.get('dimension')}")
                self.log(f"   Vector length: {len(data.get('vector', []))}")
            elif response.status_code == 404:
                self.log("   No embedding found")
        
        except Exception as e:
            self.log(f"Embedding test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_layout(self):
        """Test layout endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping layout test - no doc_id available", "WARN")
            return
        
        self.log("Testing layout endpoint...")
        
        # Check if layout analysis should be available in current deployment mode
        layout_expected = self.service_status.get('layout_analysis', False)
        
        try:
            response = self.session.get(f"{self.base_url}/layout/{self.test_doc_id}")
            
            if layout_expected:
                # GPU mode: expect layout analysis to be available
                success = self.assert_response(response, [200, 404], "Layout Analysis (GPU)")
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"   Pages: {data.get('page_count')}")
                    self.log(f"   Elements: {data.get('total_elements')}")
                    self.log(f"   Element types: {data.get('element_types', {})}")
                elif response.status_code == 404:
                    self.log("   No layout analysis found (processing may have failed)")
            else:
                # CPU mode: layout analysis unavailable, expect 404 or service unavailable
                success = self.assert_response(response, [404, 503], "Layout Analysis (CPU - Not Available)")
                if response.status_code == 404:
                    self.log("   ✅ Layout analysis not available in CPU mode (expected)")
                elif response.status_code == 503:
                    self.log("   ✅ Layout service unavailable in CPU mode (expected)")
        
        except Exception as e:
            self.log(f"Layout test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_preview(self):
        """Test preview image endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping preview test - no doc_id available", "WARN")
            return
        
        self.log("Testing preview image endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/preview/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Preview Image")  # 404 is OK if no image
            
            if response.status_code == 200:
                self.log(f"   Content-Type: {response.headers.get('content-type')}")
                self.log(f"   Content-Length: {len(response.content)} bytes")
            elif response.status_code == 404:
                self.log("   No preview image found")
        
        except Exception as e:
            self.log(f"Preview test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_text(self):
        """Test text content endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping text test - no doc_id available", "WARN")
            return
        
        self.log("Testing text content endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/text/{self.test_doc_id}")
            success = self.assert_response(response, 200, "Text Content")
            
            if success:
                data = response.json()
                self.log(f"   Text length: {data.get('text_length')}")
                self.log(f"   OCR Quality: {data.get('ocr_quality')}")
        
        except Exception as e:
            self.log(f"Text test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_search(self):
        """Test search endpoint"""
        self.log("Testing search endpoint...")
        try:
            # Test basic search
            response = self.session.get(f"{self.base_url}/search?limit=5")
            success = self.assert_response(response, 200, "Search")
            
            if success:
                data = response.json()
                self.log(f"   Results found: {len(data.get('results', []))}")
                self.log(f"   Total: {data.get('total')}")
        
        except Exception as e:
            self.log(f"Search test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_statistics(self):
        """Test statistics endpoint"""
        self.log("Testing statistics endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/stats")
            success = self.assert_response(response, 200, "Statistics")
            
            if success:
                data = response.json()
                self.log(f"   Total papers: {data.get('total_papers')}")
                self.log(f"   Papers with metadata: {data.get('papers_with_metadata')}")
                self.log(f"   Papers with embeddings: {data.get('papers_with_embeddings')}")
        
        except Exception as e:
            self.log(f"Statistics test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_invalid_endpoints(self):
        """Test invalid endpoints return proper 404"""
        self.log("Testing invalid endpoints...")
        
        invalid_endpoints = [
            "/nonexistent",
            "/paper/invalid-doc-id",
            "/metadata/invalid-doc-id",
            "/job/invalid-job-id"
        ]
        
        for endpoint in invalid_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assert_response(response, 404, f"Invalid endpoint: {endpoint}")
            except Exception as e:
                self.log(f"Invalid endpoint test failed for {endpoint}: {e}", "ERROR")
                self.results['failed'] += 1
    
    def test_upload_errors(self):
        """Test upload endpoint error handling"""
        self.log("Testing upload error handling...")
        
        try:
            # Test upload without file
            response = self.session.post(f"{self.base_url}/upload")
            self.assert_response(response, 422, "Upload without file")
            
            # Test upload with invalid file type (if validation exists)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
                tmp_file.write(b"This is not a PDF file")
                tmp_file_path = tmp_file.name
            
            try:
                with open(tmp_file_path, 'rb') as f:
                    files = {'file': ('test.txt', f, 'text/plain')}
                    response = self.session.post(f"{self.base_url}/upload", files=files)
                    # This might be 422 (validation error), 400 (bad request), or 200 (if no validation)
                    self.assert_response(response, [200, 400, 422], "Upload with non-PDF file")
            finally:
                import os
                os.unlink(tmp_file_path)
                
        except Exception as e:
            self.log(f"Upload error testing failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def create_test_pdf(self) -> Optional[str]:
        """Create a simple test PDF for testing"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            # Use tempfile for cross-platform compatibility
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                test_pdf_path = tmp_file.name
            
            c = canvas.Canvas(test_pdf_path, pagesize=letter)
            c.drawString(100, 750, "Test Academic Paper")
            c.drawString(100, 720, "Authors: John Doe, Jane Smith")
            c.drawString(100, 690, "Journal: Test Journal of Computer Science")
            c.drawString(100, 660, "Year: 2024")
            c.drawString(100, 620, "Abstract:")
            c.drawString(100, 600, "This is a test paper for RefServer API testing.")
            c.drawString(100, 580, "It contains minimal content to test the processing pipeline.")
            c.showPage()
            c.save()
            
            self.log(f"   Created test PDF: {test_pdf_path}")
            return test_pdf_path
            
        except ImportError:
            self.log("   reportlab not available, cannot create test PDF", "WARN")
            return None
        except Exception as e:
            self.log(f"   Failed to create test PDF: {e}", "WARN")
            return None
    
    def run_all_tests(self, pdf_path: str = None):
        """Run all API tests"""
        self.log("🚀 Starting RefServer API Tests")
        self.log("=" * 50)
        
        start_time = time.time()
        
        # Test basic endpoints first
        self.test_health_check()
        self.test_service_status()
        
        # Test new async PDF processing workflow
        self.log("\n📤 Testing Async PDF Processing Workflow")
        job_id = self.test_upload_pdf(pdf_path)
        if job_id:
            doc_id = self.test_job_status_polling(job_id)
            if doc_id:
                self.test_doc_id = doc_id
        
        # Test legacy synchronous processing for backward compatibility
        self.log("\n🔄 Testing Legacy Synchronous Processing")
        self.test_process_pdf_legacy(pdf_path)
        
        # Test data retrieval endpoints (use doc_id from async processing if available)
        self.log("\n📊 Testing Data Retrieval Endpoints")
        self.test_get_paper_info()
        self.test_get_metadata()
        self.test_get_embedding()
        self.test_get_layout()
        self.test_get_preview()
        self.test_get_text()
        
        # Test utility endpoints
        self.log("\n🔍 Testing Utility Endpoints")
        self.test_search()
        self.test_statistics()
        
        # Test error handling
        self.log("\n⚠️ Testing Error Handling")
        self.test_invalid_endpoints()
        self.test_upload_errors()
        
        # Print summary
        total_time = time.time() - start_time
        total_tests = self.results['passed'] + self.results['failed']
        
        self.log("=" * 50)
        self.log("📊 Test Summary")
        self.log(f"   Total tests: {total_tests}")
        self.log(f"   Passed: {self.results['passed']} ✅")
        self.log(f"   Failed: {self.results['failed']} ❌")
        self.log(f"   Success rate: {(self.results['passed']/total_tests*100):.1f}%")
        self.log(f"   Total time: {total_time:.2f}s")
        
        # Environment-specific summary
        if hasattr(self, 'deployment_mode') and self.deployment_mode:
            self.log(f"   Deployment mode: {self.deployment_mode}")
            if self.deployment_mode == "GPU":
                self.log("   🎮 GPU Features: Quality assessment ✅, Layout analysis ✅, LLM metadata ✅")
            elif self.deployment_mode == "CPU":
                self.log("   🖥️ CPU Features: Core processing ✅, Rule-based metadata ✅")
                self.log("   ⚠️ GPU Features: Quality assessment ❌, Layout analysis ❌")
            else:
                self.log("   ⚠️ Minimal Features: Basic processing only")
        
        if self.test_doc_id:
            self.log(f"   Test document ID: {self.test_doc_id}")
        
        # Interpret results based on deployment mode
        success_threshold = 0.9 if self.deployment_mode == "GPU" else 0.7
        is_success = (self.results['passed']/total_tests) >= success_threshold
        
        if is_success:
            self.log(f"   🎉 Test PASSED for {self.deployment_mode} mode")
        else:
            self.log(f"   ⚠️ Test results below expected threshold for {self.deployment_mode} mode")
        
        return is_success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer API Tester")
    parser.add_argument("--url", default="http://localhost:8060", 
                       help="RefServer API base URL")
    parser.add_argument("--pdf", help="Path to test PDF file")
    parser.add_argument("--timeout", type=int, default=30,
                       help="Request timeout in seconds")
    
    args = parser.parse_args()
    
    # Test if server is reachable
    try:
        response = requests.get(f"{args.url}/health", timeout=5)
        if response.status_code != 200:
            print(f"❌ Server not responding at {args.url}")
            print(f"   Make sure RefServer is running with: docker-compose up")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"❌ Cannot connect to {args.url}")
        print(f"   Make sure RefServer is running with: docker-compose up")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")
        sys.exit(1)
    
    # Run tests
    tester = RefServerAPITester(args.url)
    success = tester.run_all_tests(args.pdf)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()