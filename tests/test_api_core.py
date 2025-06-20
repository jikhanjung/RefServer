#!/usr/bin/env python3
"""
RefServer Core API 테스트 스크립트 (v0.1.12)
PDF 처리 관련 핵심 API 기능을 테스트합니다.
"""

import requests
import json
import time
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

class RefServerCoreAPITester:
    def __init__(self, base_url: str = "http://localhost:8060"):
        """
        Initialize Core API tester
        
        Args:
            base_url: RefServer API base URL
        """
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'RefServer-Core-API-Tester/1.0'
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
                self.log(f"   Version: {data.get('version', 'Unknown')}")
                
                # GPU-dependent services
                quality_assessment = data.get('quality_assessment')
                layout_analysis = data.get('layout_analysis')
                
                self.log(f"   Quality Assessment (GPU): {'✅' if quality_assessment else '❌'}")
                self.log(f"   Layout Analysis (GPU): {'✅' if layout_analysis else '❌'}")
                
                # CPU-compatible services
                metadata_extraction = data.get('metadata_extraction')
                self.log(f"   Metadata Extraction (CPU): {'✅' if metadata_extraction else '❌'}")
                
                # v0.1.12 New services
                backup_system = data.get('backup_system')
                consistency_check = data.get('consistency_check')
                self.log(f"   Backup System (v0.1.12): {'✅' if backup_system else '❌'}")
                self.log(f"   Consistency Check (v0.1.12): {'✅' if consistency_check else '❌'}")
                
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
                    'metadata_extraction': metadata_extraction,
                    'backup_system': backup_system,
                    'consistency_check': consistency_check
                }
            
        except Exception as e:
            self.log(f"Service status test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_upload_pdf(self, pdf_path: str = None):
        """Test PDF upload endpoint (async API)"""
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
    
    def test_get_paper_info(self):
        """Test paper info endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping paper info test - no doc_id available", "WARN")
            return
        
        self.log("Testing paper info endpoint...")
        
        try:
            response = self.session.get(f"{self.base_url}/paper/{self.test_doc_id}")
            success = self.assert_response(response, 200, "Paper Info")
            
            if success:
                data = response.json()
                self.log(f"   Filename: {data.get('filename')}")
                self.log(f"   Processing time: {data.get('processing_time', 0):.2f}s")
                self.log(f"   Text length: {len(data.get('ocr_text', ''))}")
                
                # Check OCR quality based on service availability
                ocr_quality = data.get('ocr_quality')
                if self.service_status.get('quality_assessment') and ocr_quality:
                    self.log(f"   OCR Quality (LLaVA): {ocr_quality}")
                elif ocr_quality:
                    self.log(f"   OCR Quality (basic): {ocr_quality}")
                else:
                    self.log(f"   OCR Quality: Not assessed")
        
        except Exception as e:
            self.log(f"Paper info test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_get_metadata(self):
        """Test metadata endpoint"""
        if not self.test_doc_id:
            self.log("❌ Skipping metadata test - no doc_id available", "WARN")
            return
        
        self.log("Testing metadata endpoint...")
        
        try:
            response = self.session.get(f"{self.base_url}/metadata/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Metadata")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Title: {data.get('title', 'N/A')}")
                self.log(f"   Authors: {len(data.get('authors', []))} found")
                self.log(f"   Year: {data.get('year', 'N/A')}")
                self.log(f"   Journal: {data.get('journal', 'N/A')}")
                
                if self.service_status.get('metadata_extraction'):
                    self.log(f"   ✅ LLM-based extraction successful")
                else:
                    self.log(f"   ✅ Rule-based extraction working")
            else:
                self.log("   No metadata found")
        
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
            success = self.assert_response(response, [200, 404], "Embedding")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Dimension: {data.get('dimension')}")
                self.log(f"   Vector length: {len(data.get('vector', []))}")
                self.log(f"   ✅ BGE-M3 embedding generated")
            else:
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
        
        try:
            response = self.session.get(f"{self.base_url}/layout/{self.test_doc_id}")
            
            if self.service_status.get('layout_analysis'):
                success = self.assert_response(response, [200, 404], "Layout Analysis (GPU)")
                if response.status_code == 200:
                    data = response.json()
                    self.log(f"   Pages: {data.get('page_count')}")
                    self.log(f"   Elements: {data.get('total_elements')}")
                    self.log(f"   ✅ Huridocs layout analysis successful")
                else:
                    self.log("   No layout analysis found")
            else:
                success = self.assert_response(response, [404, 503], "Layout Analysis (CPU - Not Available)")
                self.log("   ✅ Layout analysis not available in CPU mode (expected)")
        
        except Exception as e:
            self.log(f"Layout test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_search_and_stats(self):
        """Test search and statistics endpoints"""
        self.log("Testing search endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/search?limit=5")
            success = self.assert_response(response, 200, "Search")
            
            if success:
                data = response.json()
                self.log(f"   Results found: {len(data.get('results', []))}")
                self.log(f"   Total: {data.get('total')}")
        except Exception as e:
            self.log(f"Search test failed: {e}", "ERROR")
            self.results['failed'] += 1
        
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
    
    def test_vector_search_api(self):
        """Test v0.1.10+ vector search APIs"""
        if not self.test_doc_id:
            self.log("❌ Skipping vector search tests - no doc_id available", "WARN")
            return
        
        self.log("Testing vector search APIs...")
        
        # Test similar documents search
        try:
            response = self.session.get(f"{self.base_url}/similar/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Similar Documents")
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Similar papers found: {len(data.get('similar_papers', []))}")
                self.log(f"   ✅ ChromaDB vector search working")
            else:
                self.log("   No similar documents found (expected for single test)")
        except Exception as e:
            self.log(f"Similar documents test failed: {e}", "ERROR")
            self.results['failed'] += 1
        
        # Test vector stats
        try:
            response = self.session.get(f"{self.base_url}/vector/stats")
            success = self.assert_response(response, 200, "Vector Database Stats")
            
            if success:
                data = response.json()
                self.log(f"   Total vectors: {data.get('total_vectors', 0)}")
                self.log(f"   Collections: {data.get('collections', [])}")
        except Exception as e:
            self.log(f"Vector stats test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def create_test_pdf(self) -> Optional[str]:
        """Create a simple test PDF for testing"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                test_pdf_path = tmp_file.name
            
            c = canvas.Canvas(test_pdf_path, pagesize=letter)
            c.drawString(100, 750, "Test Academic Paper for RefServer v0.1.12")
            c.drawString(100, 720, "Authors: John Doe, Jane Smith")
            c.drawString(100, 690, "Journal: Test Journal of Computer Science")
            c.drawString(100, 660, "Year: 2024")
            c.drawString(100, 620, "Abstract:")
            c.drawString(100, 600, "This is a test paper for RefServer API testing.")
            c.drawString(100, 580, "It contains minimal content to test the processing pipeline.")
            c.drawString(100, 560, "Testing: OCR, embedding generation, metadata extraction.")
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
        """Run all core API tests"""
        self.log("🚀 Starting RefServer Core API Tests (v0.1.12)")
        self.log("=" * 60)
        
        start_time = time.time()
        
        # Test basic health and status
        self.test_health_check()
        self.test_service_status()
        
        # Test async PDF processing workflow
        self.log("\n📤 Testing Async PDF Processing Workflow")
        job_id = self.test_upload_pdf(pdf_path)
        if job_id:
            doc_id = self.test_job_status_polling(job_id)
            if doc_id:
                self.test_doc_id = doc_id
        
        # Test data retrieval endpoints
        self.log("\n📊 Testing Data Retrieval Endpoints")
        self.test_get_paper_info()
        self.test_get_metadata()
        self.test_get_embedding()
        self.test_get_layout()
        
        # Test search and statistics
        self.log("\n🔍 Testing Search & Statistics")
        self.test_search_and_stats()
        
        # Test vector search (v0.1.10+)
        self.log("\n🧠 Testing Vector Search APIs")
        self.test_vector_search_api()
        
        # Print summary
        total_time = time.time() - start_time
        total_tests = self.results['passed'] + self.results['failed']
        
        self.log("=" * 60)
        self.log("📊 Core API Test Summary")
        self.log(f"   Total tests: {total_tests}")
        self.log(f"   Passed: {self.results['passed']} ✅")
        self.log(f"   Failed: {self.results['failed']} ❌")
        success_rate = (self.results['passed']/total_tests*100) if total_tests > 0 else 0
        self.log(f"   Success rate: {success_rate:.1f}%")
        self.log(f"   Total time: {total_time:.2f}s")
        
        if self.deployment_mode:
            self.log(f"   Deployment mode: {self.deployment_mode}")
            
        if self.test_doc_id:
            self.log(f"   Test document ID: {self.test_doc_id}")
        
        # Success criteria based on deployment mode
        success_threshold = 0.9 if self.deployment_mode == "GPU" else 0.75
        is_success = success_rate >= (success_threshold * 100)
        
        if is_success:
            self.log(f"   🎉 Core API tests PASSED for {self.deployment_mode} mode")
        else:
            self.log(f"   ⚠️ Core API tests below expected threshold for {self.deployment_mode} mode")
        
        return is_success

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer Core API Tester")
    parser.add_argument("--url", default="http://localhost:8060", 
                       help="RefServer API base URL")
    parser.add_argument("--pdf", help="Path to test PDF file")
    
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
    tester = RefServerCoreAPITester(args.url)
    success = tester.run_all_tests(args.pdf)
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()