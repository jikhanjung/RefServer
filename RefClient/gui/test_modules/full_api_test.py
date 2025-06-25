"""
전체 API 테스트 (모든 엔드포인트)
"""

import time
from .base_test import BaseTest


class FullApiTest(BaseTest):
    """전체 API 엔드포인트 테스트"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.test_name = "전체 API"
        
    def run_test(self) -> dict:
        """전체 API 테스트 실행"""
        result = {
            'name': self.test_name,
            'success': False,
            'error': None,
            'details': {},
            'tests_passed': 0,
            'tests_total': 0
        }
        
        try:
            self.log("=== 전체 API 테스트 시작 ===", "INFO")
            
            if not self.wait_for_server():
                result['error'] = "서버 연결 실패"
                return result
            
            # 모든 API 엔드포인트 테스트
            api_endpoints = [
                # 기본 상태 API
                ("GET", "/health", "헬스체크"),
                ("GET", "/status", "서버 상태"),
                ("GET", "/stats", "시스템 통계"),
                
                # 검색 및 논문 API
                ("GET", "/search", "논문 검색"),
                ("GET", "/search?q=test", "쿼리 검색"),
                
                # 잘못된 엔드포인트 (404 테스트)
                ("GET", "/nonexistent", "404 테스트"),
                
                # API 버전 정보 (있을 경우)
                ("GET", "/version", "버전 정보"),
                ("GET", "/api/v1", "API 버전"),
            ]
            
            result['tests_total'] = len(api_endpoints)
            
            for i, (method, endpoint, description) in enumerate(api_endpoints):
                self.progress_update.emit(int((i / len(api_endpoints)) * 100))
                
                try:
                    test_result = self.test_endpoint(method, endpoint, description)
                    if test_result:
                        result['tests_passed'] += 1
                        result['details'][f"{method}_{endpoint.replace('/', '_')}"] = "PASS"
                    else:
                        result['details'][f"{method}_{endpoint.replace('/', '_')}"] = "FAIL"
                        
                except Exception as e:
                    self.log(f"엔드포인트 {endpoint} 테스트 실패: {e}", "ERROR")
                    result['details'][f"{method}_{endpoint.replace('/', '_')}"] = f"ERROR: {e}"
                    
                time.sleep(0.5)  # API 부하 방지
            
            # 최종 결과 판정
            success_rate = result['tests_passed'] / result['tests_total']
            result['success'] = success_rate >= 0.7  # 70% 이상 성공
            
            self.log(f"전체 API 테스트 완료: {result['tests_passed']}/{result['tests_total']} 성공", 
                    "PASS" if result['success'] else "FAIL")
                    
        except Exception as e:
            result['error'] = str(e)
            self.log(f"전체 API 테스트 중 오류: {e}", "ERROR")
            
        self.progress_update.emit(100)
        return result
        
    def test_endpoint(self, method: str, endpoint: str, description: str) -> bool:
        """개별 엔드포인트 테스트"""
        self.log(f"{description} 테스트: {method} {endpoint}", "INFO")
        
        try:
            response = self.make_request(method, endpoint)
            
            # 예상되는 성공 응답들
            if endpoint == "/nonexistent":
                # 404 테스트의 경우
                if response.status_code == 404:
                    self.log(f"✓ {description} 성공: 404 응답 정상", "PASS")
                    return True
                else:
                    self.log(f"✗ {description} 실패: 예상 404, 실제 {response.status_code}", "FAIL")
                    return False
                    
            elif response.status_code in [200, 201, 302]:
                # 일반적인 성공 응답
                try:
                    # JSON 응답 확인
                    if 'application/json' in response.headers.get('content-type', ''):
                        data = response.json()
                        self.log(f"✓ {description} 성공: JSON 응답", "PASS")
                    else:
                        # HTML 또는 기타 응답
                        self.log(f"✓ {description} 성공: {response.status_code}", "PASS")
                    return True
                except:
                    # JSON 파싱 실패해도 HTTP 상태가 성공이면 OK
                    self.log(f"✓ {description} 성공: {response.status_code}", "PASS")
                    return True
                    
            elif response.status_code == 401:
                # 인증 필요한 엔드포인트 (정상적인 동작)
                self.log(f"✓ {description} 성공: 인증 필요 (401)", "PASS")
                return True
                
            elif response.status_code == 403:
                # 권한 없음 (정상적인 동작)
                self.log(f"✓ {description} 성공: 권한 없음 (403)", "PASS")
                return True
                
            elif response.status_code == 405:
                # 메서드 불허 (정상적인 동작)
                self.log(f"✓ {description} 성공: 메서드 불허 (405)", "PASS")
                return True
                
            elif response.status_code >= 500:
                # 서버 오류
                self.log(f"✗ {description} 실패: 서버 오류 {response.status_code}", "FAIL")
                return False
                
            else:
                # 기타 클라이언트 오류
                self.log(f"✗ {description} 실패: HTTP {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ {description} 예외: {e}", "FAIL")
            return False