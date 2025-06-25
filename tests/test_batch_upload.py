#!/usr/bin/env python3
"""
Batch upload test script for RefServer
- Uses existing PDF generation script to create test files
- Uploads all generated PDFs to the server
- Tests various API endpoints
- Provides comprehensive test results
"""

import os
import sys
import time
import json
import requests
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class RefServerBatchTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_dir = Path(__file__).parent
        self.pdf_dir = self.test_dir / "test_papers"
        self.results = {
            "pdf_generation": {"status": False, "files": []},
            "uploads": {"success": 0, "failed": 0, "details": []},
            "processing": {"completed": 0, "failed": 0, "details": []},
            "api_tests": {"passed": 0, "failed": 0, "details": []},
            "start_time": datetime.now(),
            "end_time": None
        }
        
    def print_header(self, text: str):
        """Print formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")
        
    def print_status(self, message: str, status: str = "info"):
        """Print status message with color"""
        if status == "success":
            print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")
        elif status == "error":
            print(f"{Colors.RED}✗ {message}{Colors.RESET}")
        elif status == "warning":
            print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")
        else:
            print(f"  {message}")
            
    def check_server_health(self) -> bool:
        """Check if RefServer is running and healthy"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                self.print_status("RefServer is healthy", "success")
                return True
            else:
                self.print_status(f"RefServer returned status {response.status_code}", "error")
                return False
        except requests.RequestException as e:
            self.print_status(f"Cannot connect to RefServer: {e}", "error")
            return False
            
    def generate_test_pdfs(self) -> bool:
        """Generate test PDFs using existing script"""
        self.print_header("Generating Test PDFs")
        
        # Create test directory if it doesn't exist
        self.pdf_dir.mkdir(exist_ok=True)
        
        # Run the PDF generation script
        create_script = self.test_dir / "create_test_pdfs.py"
        if not create_script.exists():
            self.print_status("create_test_pdfs.py not found", "error")
            return False
            
        try:
            # Generate multiple types of PDFs
            cmd = [
                sys.executable, 
                str(create_script), 
                "--multiple",
                "--output", str(self.pdf_dir)
            ]
            
            self.print_status("Running PDF generation script...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Count generated PDFs
                pdf_files = list(self.pdf_dir.glob("*.pdf"))
                self.results["pdf_generation"]["status"] = True
                self.results["pdf_generation"]["files"] = [f.name for f in pdf_files]
                
                self.print_status(f"Generated {len(pdf_files)} test PDFs", "success")
                for pdf in pdf_files[:5]:  # Show first 5
                    self.print_status(f"  - {pdf.name}", "info")
                if len(pdf_files) > 5:
                    self.print_status(f"  ... and {len(pdf_files) - 5} more", "info")
                    
                return True
            else:
                self.print_status(f"PDF generation failed: {result.stderr}", "error")
                return False
                
        except Exception as e:
            self.print_status(f"Error generating PDFs: {e}", "error")
            return False
            
    def upload_pdf(self, pdf_path: Path) -> Optional[str]:
        """Upload a single PDF and return job_id"""
        try:
            with open(pdf_path, 'rb') as f:
                files = {'file': (pdf_path.name, f, 'application/pdf')}
                response = requests.post(
                    f"{self.base_url}/upload",
                    files=files,
                    timeout=30
                )
                
            if response.status_code == 202:
                data = response.json()
                return data.get('job_id')
            else:
                self.print_status(f"Upload failed for {pdf_path.name}: {response.status_code}", "error")
                return None
                
        except Exception as e:
            self.print_status(f"Error uploading {pdf_path.name}: {e}", "error")
            return None
            
    def check_job_status(self, job_id: str) -> Dict:
        """Check processing job status"""
        try:
            response = requests.get(f"{self.base_url}/job/{job_id}", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {"status": "error", "error": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    def wait_for_processing(self, job_id: str, timeout: int = 300) -> bool:
        """Wait for job to complete processing"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.check_job_status(job_id)
            
            if status.get("status") == "completed":
                return True
            elif status.get("status") == "failed":
                self.print_status(f"Job {job_id} failed: {status.get('error')}", "error")
                return False
                
            # Show progress
            progress = status.get("progress", 0)
            current_step = status.get("current_step", "unknown")
            print(f"\r  Processing {job_id}: {progress}% - {current_step}", end="", flush=True)
            
            time.sleep(2)
            
        self.print_status(f"\nJob {job_id} timed out after {timeout}s", "warning")
        return False
        
    def test_api_endpoints(self, doc_id: str) -> Dict:
        """Test various API endpoints for a processed document"""
        endpoints = [
            ("paper", f"/paper/{doc_id}"),
            ("metadata", f"/metadata/{doc_id}"),
            ("embedding", f"/embedding/{doc_id}"),
            ("layout", f"/layout/{doc_id}"),
            ("text", f"/text/{doc_id}"),
            ("preview", f"/preview/{doc_id}"),
        ]
        
        results = {"passed": 0, "failed": 0, "details": {}}
        
        for name, endpoint in endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    results["passed"] += 1
                    results["details"][name] = "success"
                else:
                    results["failed"] += 1
                    results["details"][name] = f"status {response.status_code}"
            except Exception as e:
                results["failed"] += 1
                results["details"][name] = f"error: {str(e)}"
                
        return results
        
    def run_batch_upload_test(self):
        """Run the complete batch upload test"""
        self.print_header("RefServer Batch Upload Test")
        
        # Step 1: Check server health
        if not self.check_server_health():
            self.print_status("Server is not available. Exiting.", "error")
            return False
            
        # Step 2: Generate test PDFs
        if not self.generate_test_pdfs():
            self.print_status("Failed to generate test PDFs. Exiting.", "error")
            return False
            
        # Step 3: Upload all PDFs
        self.print_header("Uploading PDFs to Server")
        
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        job_mappings = {}  # pdf_name -> (job_id, doc_id)
        
        for pdf_file in pdf_files:
            self.print_status(f"Uploading {pdf_file.name}...")
            job_id = self.upload_pdf(pdf_file)
            
            if job_id:
                job_mappings[pdf_file.name] = {"job_id": job_id, "doc_id": None}
                self.results["uploads"]["success"] += 1
                self.results["uploads"]["details"].append({
                    "file": pdf_file.name,
                    "job_id": job_id,
                    "status": "uploaded"
                })
                self.print_status(f"  Job ID: {job_id}", "success")
            else:
                self.results["uploads"]["failed"] += 1
                self.results["uploads"]["details"].append({
                    "file": pdf_file.name,
                    "status": "failed"
                })
                
        # Step 4: Wait for processing to complete
        self.print_header("Processing Status")
        
        for pdf_name, job_info in job_mappings.items():
            if job_info["job_id"]:
                self.print_status(f"\nProcessing {pdf_name}...")
                
                if self.wait_for_processing(job_info["job_id"]):
                    # Get final status to extract doc_id
                    final_status = self.check_job_status(job_info["job_id"])
                    doc_id = final_status.get("result", {}).get("doc_id")
                    
                    if doc_id:
                        job_info["doc_id"] = doc_id
                        self.results["processing"]["completed"] += 1
                        self.print_status(f"\n  ✓ Completed: {doc_id}", "success")
                    else:
                        self.results["processing"]["failed"] += 1
                        self.print_status(f"\n  ✗ No doc_id returned", "error")
                else:
                    self.results["processing"]["failed"] += 1
                    
        # Step 5: Test API endpoints for processed documents
        self.print_header("Testing API Endpoints")
        
        tested_count = 0
        for pdf_name, job_info in job_mappings.items():
            if job_info.get("doc_id") and tested_count < 3:  # Test first 3 documents
                self.print_status(f"\nTesting endpoints for {pdf_name}...")
                
                api_results = self.test_api_endpoints(job_info["doc_id"])
                self.results["api_tests"]["passed"] += api_results["passed"]
                self.results["api_tests"]["failed"] += api_results["failed"]
                
                for endpoint, result in api_results["details"].items():
                    if result == "success":
                        self.print_status(f"  {endpoint}: {result}", "success")
                    else:
                        self.print_status(f"  {endpoint}: {result}", "error")
                        
                tested_count += 1
                
        # Final summary
        self.results["end_time"] = datetime.now()
        self.print_summary()
        
    def print_summary(self):
        """Print test summary"""
        self.print_header("Test Summary")
        
        duration = (self.results["end_time"] - self.results["start_time"]).total_seconds()
        
        print(f"{Colors.BOLD}Duration:{Colors.RESET} {duration:.2f} seconds\n")
        
        print(f"{Colors.BOLD}PDF Generation:{Colors.RESET}")
        print(f"  - Files created: {len(self.results['pdf_generation']['files'])}")
        
        print(f"\n{Colors.BOLD}Upload Results:{Colors.RESET}")
        print(f"  - Successful: {self.results['uploads']['success']}")
        print(f"  - Failed: {self.results['uploads']['failed']}")
        
        print(f"\n{Colors.BOLD}Processing Results:{Colors.RESET}")
        print(f"  - Completed: {self.results['processing']['completed']}")
        print(f"  - Failed: {self.results['processing']['failed']}")
        
        print(f"\n{Colors.BOLD}API Tests:{Colors.RESET}")
        print(f"  - Passed: {self.results['api_tests']['passed']}")
        print(f"  - Failed: {self.results['api_tests']['failed']}")
        
        # Overall status
        total_tests = (
            self.results['uploads']['success'] + 
            self.results['uploads']['failed'] +
            self.results['api_tests']['passed'] + 
            self.results['api_tests']['failed']
        )
        
        total_passed = (
            self.results['uploads']['success'] +
            self.results['processing']['completed'] +
            self.results['api_tests']['passed']
        )
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        print(f"\n{Colors.BOLD}Overall Success Rate:{Colors.RESET} {success_rate:.1f}%")
        
        if success_rate >= 90:
            self.print_status("\nAll tests completed successfully! 🎉", "success")
        elif success_rate >= 70:
            self.print_status("\nMost tests passed with some issues.", "warning")
        else:
            self.print_status("\nMany tests failed. Please check the logs.", "error")
            
        # Save detailed results
        results_file = self.test_dir / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        print(f"\nDetailed results saved to: {results_file}")
        
def main():
    """Main test execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description="RefServer Batch Upload Test")
    parser.add_argument("--url", default="http://localhost:8000", help="RefServer base URL")
    parser.add_argument("--cleanup", action="store_true", help="Clean up test files after completion")
    
    args = parser.parse_args()
    
    tester = RefServerBatchTester(base_url=args.url)
    
    try:
        tester.run_batch_upload_test()
        
        if args.cleanup:
            print("\nCleaning up test files...")
            import shutil
            if tester.pdf_dir.exists():
                shutil.rmtree(tester.pdf_dir)
                print("Test files cleaned up.")
                
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n{Colors.RED}Test failed with error: {e}{Colors.RESET}")
        
if __name__ == "__main__":
    main()