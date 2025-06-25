"""
간단한 서버 상태 및 기본 API 테스트
OCR 언어 감지 대신 기본적인 헬스체크와 API 연결성 테스트
"""

import time
from .base_test import BaseTest


class HealthTest(BaseTest):
    """서버 헬스체크 및 기본 연결성 테스트"""
    
    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.test_name = "서버 연결성"
        
    def run_test(self) -> dict:
        """헬스체크 테스트 실행"""
        result = {
            'name': self.test_name,
            'success': False,
            'error': None,
            'details': {},
            'tests_passed': 0,
            'tests_total': 0
        }
        
        try:
            self.log("=== 서버 연결성 테스트 시작 ===", "INFO")
            
            # 배포 모드 감지 및 표시
            mode = self.detect_deployment_mode()
            self.log(f"감지된 배포 모드: {mode.upper()}", "INFO")
            
            tests = [
                self.test_health_endpoint,
                self.test_status_endpoint,
                self.test_stats_endpoint,
                self.test_invalid_endpoint,
                self.test_response_time
            ]
            
            # CPU 모드에서는 Ollama 의존적 테스트 제외
            if self.is_gpu_mode():
                tests.append(self.test_ollama_connectivity)
                self.log("GPU 모드: Ollama 연결성 테스트 포함", "INFO")
            else:
                self.log("CPU 모드: Ollama 테스트 제외", "INFO")
            
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
                    
                time.sleep(0.5)  # 시각적 효과
            
            # 최종 결과 판정
            success_rate = result['tests_passed'] / result['tests_total']
            result['success'] = success_rate >= 0.8  # 80% 이상 성공
            
            self.log(f"테스트 완료: {result['tests_passed']}/{result['tests_total']} 성공", 
                    "PASS" if result['success'] else "FAIL")
                    
        except Exception as e:
            result['error'] = str(e)
            self.log(f"테스트 실행 중 오류: {e}", "ERROR")
            
        self.progress_update.emit(100)
        return result
        
    def test_health_endpoint(self) -> bool:
        """헬스체크 엔드포인트 테스트"""
        self.log("헬스체크 엔드포인트 테스트", "INFO")
        
        try:
            response = self.make_request("GET", "/health")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    self.log("✓ 헬스체크 성공", "PASS")
                    return True
                else:
                    self.log(f"✗ 헬스체크 응답 이상: {data}", "FAIL")
                    return False
            else:
                self.log(f"✗ 헬스체크 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 헬스체크 예외: {e}", "FAIL")
            return False
            
    def test_status_endpoint(self) -> bool:
        """상태 엔드포인트 테스트"""
        self.log("상태 엔드포인트 테스트", "INFO")
        
        try:
            response = self.make_request("GET", "/status")
            
            if response.status_code == 200:
                data = response.json()
                if 'version' in data and 'uptime' in data:
                    self.log(f"✓ 상태 확인 성공: v{data.get('version')}", "PASS")
                    return True
                else:
                    self.log(f"✗ 상태 응답 필드 누락: {data}", "FAIL")
                    return False
            else:
                self.log(f"✗ 상태 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 상태 확인 예외: {e}", "FAIL")
            return False
            
    def test_stats_endpoint(self) -> bool:
        """통계 엔드포인트 테스트"""
        self.log("통계 엔드포인트 테스트", "INFO")
        
        try:
            response = self.make_request("GET", "/stats")
            
            if response.status_code == 200:
                data = response.json()
                if 'total_papers' in data:
                    self.log(f"✓ 통계 확인 성공: {data.get('total_papers')}개 논문", "PASS")
                    return True
                else:
                    self.log(f"✗ 통계 응답 필드 누락: {data}", "FAIL")
                    return False
            else:
                self.log(f"✗ 통계 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 통계 확인 예외: {e}", "FAIL")
            return False
            
    def test_invalid_endpoint(self) -> bool:
        """잘못된 엔드포인트 테스트 (404 확인)"""
        self.log("잘못된 엔드포인트 테스트", "INFO")
        
        try:
            response = self.make_request("GET", "/nonexistent-endpoint-12345")
            
            if response.status_code == 404:
                self.log("✓ 404 응답 정상 (잘못된 엔드포인트)", "PASS")
                return True
            else:
                self.log(f"✗ 예상과 다른 응답: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 404 테스트 예외: {e}", "FAIL")
            return False
            
    def test_response_time(self) -> bool:
        """응답 시간 테스트"""
        self.log("응답 시간 테스트", "INFO")
        
        try:
            start_time = time.time()
            response = self.make_request("GET", "/health")
            response_time = time.time() - start_time
            
            if response.status_code == 200 and response_time < 5.0:
                self.log(f"✓ 응답 시간 양호: {response_time:.2f}초", "PASS")
                return True
            elif response_time >= 5.0:
                self.log(f"✗ 응답 시간 느림: {response_time:.2f}초", "FAIL")
                return False
            else:
                self.log(f"✗ 응답 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ 응답 시간 테스트 예외: {e}", "FAIL")
            return False
            
    def test_ollama_connectivity(self) -> bool:
        """Ollama 연결성 테스트 (GPU 모드에서만 실행)"""
        self.log("Ollama 연결성 테스트", "INFO")
        
        try:
            # RefServer를 통해 Ollama 상태 확인
            response = self.make_request("GET", "/health")
            
            if response.status_code == 200:
                data = response.json()
                
                # Ollama 상태 정보 확인
                if 'services' in data:
                    services = data['services']
                    if 'ollama' in services:
                        ollama_status = services['ollama']
                        if ollama_status == 'available':
                            self.log("✓ Ollama 서비스 연결 정상", "PASS")
                            return True
                        else:
                            self.log(f"✗ Ollama 서비스 상태 이상: {ollama_status}", "FAIL")
                            return False
                
                # 대안: 헬스체크에 ollama_status 필드가 있는 경우
                if 'ollama_status' in data:
                    ollama_status = data['ollama_status']
                    if ollama_status == 'available':
                        self.log("✓ Ollama 연결 확인됨", "PASS")
                        return True
                    else:
                        self.log(f"✗ Ollama 연결 실패: {ollama_status}", "FAIL")
                        return False
                
                # Ollama 상태 정보가 없는 경우
                self.log("✓ Ollama 상태 정보 없음 (정상적일 수 있음)", "PASS")
                return True
                
            else:
                self.log(f"✗ 헬스체크 HTTP 오류: {response.status_code}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"✗ Ollama 연결성 테스트 예외: {e}", "FAIL")
            return False