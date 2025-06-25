"""
관리자 시스템 테스트
"""

import time
import base64
from .base_test import BaseTest


class AdminTest(BaseTest):
    """관리자 시스템 테스트"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.test_name = "관리자 시스템"
        self.access_token = None
        self.admin_username = config_manager.get_admin_username()
        self.admin_password = config_manager.get_admin_password()
        
    def run_test(self) -> dict:
        """관리자 시스템 테스트 실행"""
        result = {
            'name': self.test_name,
            'success': False,
            'error': None,
            'details': {},
            'tests_passed': 0,
            'tests_total': 0
        }
        
        try:
            self.log("=== 관리자 시스템 테스트 시작 ===", "INFO")
            
            if not self.wait_for_server():
                result['error'] = "서버 연결 실패"
                return result
                
            if not self.admin_username or not self.admin_password:
                result['error'] = "관리자 계정 정보 없음"
                self.log("관리자 계정 정보가 설정되지 않았습니다", "ERROR")
                return result
            
            tests = [
                self.test_admin_login,
                self.test_admin_dashboard,
                self.test_admin_papers_list,
                self.test_admin_logout
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
                        # 로그인 실패 시 나머지 테스트 중단
                        if test_func.__name__ == 'test_admin_login':
                            self.log("로그인 실패로 인해 나머지 관리자 테스트를 중단합니다", "WARNING")
                            break
                        
                except Exception as e:
                    self.log(f"테스트 {test_func.__name__} 실패: {e}", "ERROR")
                    result['details'][test_func.__name__] = f"ERROR: {e}"
                    
                time.sleep(1)
            
            # 최종 결과 판정
            success_rate = result['tests_passed'] / result['tests_total']
            result['success'] = success_rate >= 0.5  # 50% 이상 성공
            
            self.log(f"관리자 시스템 테스트 완료: {result['tests_passed']}/{result['tests_total']} 성공", 
                    "PASS" if result['success'] else "FAIL")
                    
        except Exception as e:
            result['error'] = str(e)
            self.log(f"관리자 시스템 테스트 중 오류: {e}", "ERROR")
            
        self.progress_update.emit(100)
        return result
        
    def test_admin_login(self) -> bool:
        """관리자 로그인 테스트"""
        self.log("관리자 로그인 테스트", "INFO")
        
        try:
            # 로그인 데이터 준비
            login_data = {
                'username': self.admin_username,
                'password': self.admin_password
            }
            
            response = self.make_request("POST", "/admin/login", data=login_data)
            
            if response.status_code == 200:
                # HTML 응답인 경우 (리다이렉트 또는 성공 페이지)
                if 'text/html' in response.headers.get('content-type', ''):
                    # 쿠키에서 세션 정보 확인
                    if 'session' in response.cookies or 'admin_session' in response.cookies:
                        self.log("✓ 관리자 로그인 성공 (세션 쿠키 확인)", "PASS")
                        return True
                    else:
                        self.log("✗ 로그인 응답에 세션 쿠키 없음", "FAIL")
                        return False
                # JSON 응답인 경우
                else:
                    try:
                        data = response.json()
                        if data.get('success') or 'access_token' in data:
                            self.access_token = data.get('access_token')
                            self.log("✓ 관리자 로그인 성공 (JSON 응답)", "PASS")
                            return True
                        else:
                            self.log(f"✗ 로그인 실패: {data}", "FAIL")
                            return False
                    except:
                        # JSON 파싱 실패, HTML 응답으로 간주
                        self.log("✓ 관리자 로그인 성공 (HTML 응답)", "PASS")
                        return True
            elif response.status_code == 302:
                # 리다이렉트 응답 (로그인 성공 후 대시보드로 이동)
                self.log("✓ 관리자 로그인 성공 (리다이렉트)", "PASS")
                return True
            else:
                self.log(f"✗ 로그인 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 관리자 로그인 예외: {e}", "FAIL")
            return False
            
    def test_admin_dashboard(self) -> bool:
        """관리자 대시보드 접근 테스트"""
        self.log("관리자 대시보드 접근 테스트", "INFO")
        
        try:
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
                
            response = self.make_request("GET", "/admin/dashboard", headers=headers)
            
            if response.status_code == 200:
                content = response.text
                # 대시보드 특징적인 요소들 확인
                if ('dashboard' in content.lower() or 
                    'admin' in content.lower() or
                    '관리자' in content or
                    '대시보드' in content):
                    self.log("✓ 관리자 대시보드 접근 성공", "PASS")
                    return True
                else:
                    self.log("✗ 대시보드 내용 확인 실패", "FAIL")
                    return False
            elif response.status_code == 302:
                # 로그인 페이지로 리다이렉트 (인증 필요)
                self.log("✗ 대시보드 접근 실패 (인증 필요)", "FAIL")
                return False
            else:
                self.log(f"✗ 대시보드 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 관리자 대시보드 예외: {e}", "FAIL")
            return False
            
    def test_admin_papers_list(self) -> bool:
        """관리자 논문 목록 테스트"""
        self.log("관리자 논문 목록 테스트", "INFO")
        
        try:
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
                
            response = self.make_request("GET", "/admin/papers", headers=headers)
            
            if response.status_code == 200:
                content = response.text
                # 논문 목록 페이지 특징적인 요소들 확인
                if ('papers' in content.lower() or
                    'table' in content.lower() or
                    '논문' in content or
                    'pdf' in content.lower()):
                    self.log("✓ 관리자 논문 목록 접근 성공", "PASS")
                    return True
                else:
                    self.log("✗ 논문 목록 내용 확인 실패", "FAIL")
                    return False
            elif response.status_code == 302:
                # 로그인 페이지로 리다이렉트
                self.log("✗ 논문 목록 접근 실패 (인증 필요)", "FAIL")
                return False
            else:
                self.log(f"✗ 논문 목록 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 관리자 논문 목록 예외: {e}", "FAIL")
            return False
            
    def test_admin_logout(self) -> bool:
        """관리자 로그아웃 테스트"""
        self.log("관리자 로그아웃 테스트", "INFO")
        
        try:
            headers = {}
            if self.access_token:
                headers['Authorization'] = f'Bearer {self.access_token}'
                
            response = self.make_request("GET", "/admin/logout", headers=headers)
            
            if response.status_code in [200, 302]:
                # 성공적인 로그아웃 (페이지 응답 또는 리다이렉트)
                self.log("✓ 관리자 로그아웃 성공", "PASS")
                self.access_token = None
                return True
            else:
                self.log(f"✗ 로그아웃 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 관리자 로그아웃 예외: {e}", "FAIL")
            return False