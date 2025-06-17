#!/usr/bin/env python3
"""
RefServer API 테스트 스크립트
모든 API 엔드포인트를 테스트하고 결과를 확인합니다.
"""

import requests
import json
import time
import os
import sys
from pathlib import Path
from typing import Dict, Optional

class RefServerAPITester:
    def __init__(self, base_url: str = "http://localhost:8000"):
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
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp"""
        timestamp = time.strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def assert_response(self, response: requests.Response, expected_status: int = 200, test_name: str = ""):
        """Assert response status and log result"""
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
                self.log(f"   Quality Assessment: {'✅' if data.get('quality_assessment') else '❌'}")
                self.log(f"   Layout Analysis: {'✅' if data.get('layout_analysis') else '❌'}")
                self.log(f"   Metadata Extraction: {'✅' if data.get('metadata_extraction') else '❌'}")
            
        except Exception as e:
            self.log(f"Service status test failed: {e}", "ERROR")
            self.results['failed'] += 1
    
    def test_process_pdf(self, pdf_path: str = None):
        """Test PDF processing endpoint"""
        self.log("Testing PDF processing endpoint...")
        
        # Create a test PDF if none provided
        if not pdf_path:
            pdf_path = self.create_test_pdf()
        
        if not pdf_path or not os.path.exists(pdf_path):
            self.log("❌ No test PDF file available for processing test", "ERROR")
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
                success = self.assert_response(response, 200, "PDF Processing")
                
                if success:
                    data = response.json()
                    self.test_doc_id = data.get('doc_id')
                    
                    self.log(f"   Document ID: {self.test_doc_id}")
                    self.log(f"   Success: {data.get('success')}")
                    self.log(f"   Processing time: {data.get('processing_time', 0):.2f}s")
                    self.log(f"   Steps completed: {len(data.get('steps_completed', []))}")
                    self.log(f"   Steps failed: {len(data.get('steps_failed', []))}")
                    
                    if data.get('warnings'):
                        self.log(f"   Warnings: {len(data.get('warnings'))}")
                        for warning in data.get('warnings', [])[:3]:  # Show first 3 warnings
                            self.log(f"     - {warning}")
                    
                    # Store doc_id for subsequent tests
                    if self.test_doc_id:
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
        try:
            response = self.session.get(f"{self.base_url}/paper/{self.test_doc_id}")
            success = self.assert_response(response, 200, "Paper Info")
            
            if success:
                data = response.json()
                self.log(f"   Filename: {data.get('filename')}")
                self.log(f"   OCR Quality: {data.get('ocr_quality')}")
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
        try:
            response = self.session.get(f"{self.base_url}/metadata/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Metadata")  # 404 is OK if no metadata extracted
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Title: {data.get('title', 'N/A')}")
                self.log(f"   Authors: {len(data.get('authors', []))} found")
                self.log(f"   Year: {data.get('year', 'N/A')}")
                self.log(f"   Journal: {data.get('journal', 'N/A')}")
            elif response.status_code == 404:
                self.log("   No metadata found (this is normal for test files)")
        
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
        try:
            response = self.session.get(f"{self.base_url}/layout/{self.test_doc_id}")
            success = self.assert_response(response, [200, 404], "Layout Analysis")  # 404 is OK if no layout
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"   Pages: {data.get('page_count')}")
                self.log(f"   Elements: {data.get('total_elements')}")
                self.log(f"   Element types: {data.get('element_types', {})}")
            elif response.status_code == 404:
                self.log("   No layout analysis found")
        
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
            "/metadata/invalid-doc-id"
        ]
        
        for endpoint in invalid_endpoints:
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                self.assert_response(response, 404, f"Invalid endpoint: {endpoint}")
            except Exception as e:
                self.log(f"Invalid endpoint test failed for {endpoint}: {e}", "ERROR")
                self.results['failed'] += 1
    
    def create_test_pdf(self) -> Optional[str]:
        """Create a simple test PDF for testing"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            
            test_pdf_path = "/tmp/test_paper.pdf"
            
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
        
        # Test PDF processing (this may take a while)
        self.test_process_pdf(pdf_path)
        
        # Test data retrieval endpoints
        self.test_get_paper_info()
        self.test_get_metadata()
        self.test_get_embedding()
        self.test_get_layout()
        self.test_get_preview()
        self.test_get_text()
        
        # Test utility endpoints
        self.test_search()
        self.test_statistics()
        
        # Test error handling
        self.test_invalid_endpoints()
        
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
        
        if self.test_doc_id:
            self.log(f"   Test document ID: {self.test_doc_id}")
        
        return self.results['failed'] == 0

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer API Tester")
    parser.add_argument("--url", default="http://localhost:8000", 
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