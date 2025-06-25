"""
핵심 API 테스트 (PDF 처리 파이프라인)
"""

import time
import json
import tempfile
import os
from .base_test import BaseTest


class CoreApiTest(BaseTest):
    """핵심 PDF 처리 API 테스트"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.test_name = "핵심 API"
        self.job_id = None
        
    def run_test(self) -> dict:
        """핵심 API 테스트 실행"""
        result = {
            'name': self.test_name,
            'success': False,
            'error': None,
            'details': {},
            'tests_passed': 0,
            'tests_total': 0
        }
        
        try:
            self.log("=== 핵심 API 테스트 시작 ===", "INFO")
            
            if not self.wait_for_server():
                result['error'] = "서버 연결 실패"
                return result
            
            tests = [
                self.test_upload_simple,
                self.test_job_status_polling,
                self.test_paper_info,
                self.test_download,
                self.test_search_api
            ]
            
            result['tests_total'] = len(tests)
            
            for i, test_func in enumerate(tests):
                self.progress_update.emit(int((i / len(tests)) * 100))
                
                try:
                    test_result = test_func()
                    if test_result:
                        result['tests_passed'] += 1
                        result['details'][test_func.__name__] = "PASS"
                    else:
                        result['details'][test_func.__name__] = "FAIL"
                        
                except Exception as e:
                    self.log(f"테스트 {test_func.__name__} 실패: {e}", "ERROR")
                    result['details'][test_func.__name__] = f"ERROR: {e}"
                    
                time.sleep(1)  # API 부하 방지
            
            # 최종 결과 판정
            success_rate = result['tests_passed'] / result['tests_total']
            result['success'] = success_rate >= 0.6  # 60% 이상 성공
            
            self.log(f"핵심 API 테스트 완료: {result['tests_passed']}/{result['tests_total']} 성공", 
                    "PASS" if result['success'] else "FAIL")
                    
        except Exception as e:
            result['error'] = str(e)
            self.log(f"핵심 API 테스트 중 오류: {e}", "ERROR")
            
        self.progress_update.emit(100)
        return result
        
    def create_test_pdf(self) -> str:
        """테스트용 간단한 PDF 생성"""
        try:
            # 간단한 텍스트 파일을 PDF로 변환하는 대신
            # 실제 PDF 바이너리 데이터 생성
            pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF for RefServer) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000010 00000 n 
0000000053 00000 n 
0000000125 00000 n 
0000000185 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
267
%%EOF"""
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                f.write(pdf_content)
                return f.name
                
        except Exception as e:
            self.log(f"테스트 PDF 생성 실패: {e}", "ERROR")
            return None
            
    def test_upload_simple(self) -> bool:
        """간단한 PDF 업로드 테스트"""
        self.log("PDF 업로드 테스트", "INFO")
        
        try:
            # 테스트 PDF 생성
            pdf_path = self.create_test_pdf()
            if not pdf_path:
                self.log("✗ 테스트 PDF 생성 실패", "FAIL")
                return False
                
            try:
                # PDF 업로드
                with open(pdf_path, 'rb') as f:
                    files = {'file': ('test.pdf', f, 'application/pdf')}
                    response = self.make_request("POST", "/upload", files=files)
                
                if response.status_code == 200:
                    data = response.json()
                    self.job_id = data.get('job_id')
                    if self.job_id:
                        self.log(f"✓ PDF 업로드 성공: job_id={self.job_id}", "PASS")
                        return True
                    else:
                        self.log(f"✗ job_id 누락: {data}", "FAIL")
                        return False
                else:
                    self.log(f"✗ 업로드 HTTP 오류: {response.status_code}", "FAIL")
                    return False
                    
            finally:
                # 임시 파일 정리
                if os.path.exists(pdf_path):
                    os.unlink(pdf_path)
                    
        except Exception as e:
            self.log(f"✗ PDF 업로드 예외: {e}", "FAIL")
            return False
            
    def test_job_status_polling(self) -> bool:
        """작업 상태 폴링 테스트"""
        self.log("작업 상태 폴링 테스트", "INFO")
        
        if not self.job_id:
            self.log("✗ job_id가 없음 (업로드 실패?)", "FAIL")
            return False
            
        try:
            max_attempts = 30  # 최대 30번 시도 (30초)
            for attempt in range(max_attempts):
                response = self.make_request("GET", f"/job/{self.job_id}")
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    progress = data.get('progress', 0)
                    
                    self.log(f"작업 상태: {status} ({progress}%)", "DEBUG")
                    
                    if status == 'completed':
                        self.log("✓ 작업 완료 확인", "PASS")
                        return True
                    elif status == 'failed':
                        error_msg = data.get('error', 'Unknown error')
                        self.log(f"✗ 작업 실패: {error_msg}", "FAIL")
                        return False
                    elif status in ['pending', 'processing']:
                        time.sleep(1)  # 1초 대기 후 재시도
                        continue
                    else:
                        self.log(f"✗ 알 수 없는 상태: {status}", "FAIL")
                        return False
                else:
                    self.log(f"✗ 상태 조회 HTTP 오류: {response.status_code}", "FAIL")
                    return False
                    
            self.log("✗ 작업 완료 시간 초과", "FAIL")
            return False
            
        except Exception as e:
            self.log(f"✗ 상태 폴링 예외: {e}", "FAIL")
            return False
            
    def test_paper_info(self) -> bool:
        """논문 정보 조회 테스트"""
        self.log("논문 정보 조회 테스트", "INFO")
        
        try:
            # 전체 논문 목록 조회
            response = self.make_request("GET", "/search")
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('results', [])
                
                if papers:
                    paper_id = papers[0].get('id')
                    if paper_id:
                        # 개별 논문 정보 조회
                        response = self.make_request("GET", f"/paper/{paper_id}")
                        
                        if response.status_code == 200:
                            paper_data = response.json()
                            if 'title' in paper_data and 'id' in paper_data:
                                self.log(f"✓ 논문 정보 조회 성공: {paper_data.get('title', 'No title')}", "PASS")
                                return True
                            else:
                                self.log(f"✗ 논문 정보 필드 누락: {paper_data}", "FAIL")
                                return False
                        else:
                            self.log(f"✗ 논문 정보 조회 HTTP 오류: {response.status_code}", "FAIL")
                            return False
                    else:
                        self.log("✗ 논문 ID 누락", "FAIL")
                        return False
                else:
                    self.log("✓ 논문 목록 비어있음 (정상)", "PASS")
                    return True
            else:
                self.log(f"✗ 논문 목록 조회 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 논문 정보 조회 예외: {e}", "FAIL")
            return False
            
    def test_download(self) -> bool:
        """PDF 다운로드 테스트"""
        self.log("PDF 다운로드 테스트", "INFO")
        
        try:
            # 전체 논문 목록 조회
            response = self.make_request("GET", "/search")
            
            if response.status_code == 200:
                data = response.json()
                papers = data.get('results', [])
                
                if papers:
                    paper_id = papers[0].get('id')
                    if paper_id:
                        # PDF 다운로드 시도
                        response = self.make_request("GET", f"/download/{paper_id}")
                        
                        if response.status_code == 200:
                            content_type = response.headers.get('content-type', '')
                            if 'application/pdf' in content_type:
                                self.log("✓ PDF 다운로드 성공", "PASS")
                                return True
                            else:
                                self.log(f"✗ 잘못된 content-type: {content_type}", "FAIL")
                                return False
                        else:
                            self.log(f"✗ PDF 다운로드 HTTP 오류: {response.status_code}", "FAIL")
                            return False
                    else:
                        self.log("✗ 논문 ID 누락", "FAIL")
                        return False
                else:
                    self.log("✓ 다운로드할 논문 없음 (정상)", "PASS")
                    return True
            else:
                self.log(f"✗ 논문 목록 조회 실패: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ PDF 다운로드 예외: {e}", "FAIL")
            return False
            
    def test_search_api(self) -> bool:
        """검색 API 테스트"""
        self.log("검색 API 테스트", "INFO")
        
        try:
            # 기본 검색
            response = self.make_request("GET", "/search")
            
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and 'total' in data:
                    total = data.get('total', 0)
                    self.log(f"✓ 기본 검색 성공: {total}개 결과", "PASS")
                    
                    # 쿼리 검색 테스트
                    response = self.make_request("GET", "/search", params={'q': 'test'})
                    
                    if response.status_code == 200:
                        search_data = response.json()
                        if 'results' in search_data:
                            self.log("✓ 쿼리 검색 성공", "PASS")
                            return True
                        else:
                            self.log(f"✗ 쿼리 검색 응답 형식 오류: {search_data}", "FAIL")
                            return False
                    else:
                        self.log(f"✗ 쿼리 검색 HTTP 오류: {response.status_code}", "FAIL")
                        return False
                else:
                    self.log(f"✗ 검색 응답 형식 오류: {data}", "FAIL")
                    return False
            else:
                self.log(f"✗ 기본 검색 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 검색 API 예외: {e}", "FAIL")
            return False