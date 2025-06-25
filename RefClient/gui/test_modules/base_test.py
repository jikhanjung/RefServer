"""
기본 테스트 클래스 및 공통 유틸리티
"""

import requests
import time
import logging
from typing import Dict, List, Any
from PyQt6.QtCore import QObject, pyqtSignal


class BaseTest(QObject):
    """모든 테스트의 기본 클래스"""
    
    # 신호들
    log_message = pyqtSignal(str, str)  # message, level
    progress_update = pyqtSignal(int)   # progress (0-100)
    test_completed = pyqtSignal(dict)   # result dict
    
    def __init__(self, config_manager):
        super().__init__()
        self.config = config_manager
        self.server_url = config_manager.get_server_url()
        self.timeout = config_manager.get_connection_timeout()
        self.session = requests.Session()
        self.session.timeout = self.timeout
        self.deployment_mode = None  # 'gpu', 'cpu', 또는 None (감지 실패)
        
    def log(self, message: str, level: str = "INFO"):
        """로그 메시지 발송"""
        self.log_message.emit(message, level)
        
    def make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """API 요청 수행"""
        url = f"{self.server_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            self.log(f"{method} {endpoint} -> {response.status_code}", "DEBUG")
            return response
        except requests.RequestException as e:
            self.log(f"요청 실패 {method} {endpoint}: {e}", "ERROR")
            raise
            
    def wait_for_server(self, max_attempts: int = 3) -> bool:
        """서버 연결 대기"""
        for attempt in range(max_attempts):
            try:
                response = self.make_request("GET", "/health")
                if response.status_code == 200:
                    self.log("서버 연결 확인됨", "INFO")
                    return True
            except:
                self.log(f"서버 연결 시도 {attempt + 1}/{max_attempts}", "WARNING")
                time.sleep(2)
        
        self.log("서버 연결 실패", "ERROR")
        return False
        
    def detect_deployment_mode(self) -> str:
        """서버 배포 모드 감지 (GPU/CPU)"""
        if self.deployment_mode is not None:
            return self.deployment_mode
            
        try:
            # /status 엔드포인트에서 배포 정보 확인
            response = self.make_request("GET", "/status")
            if response.status_code == 200:
                data = response.json()
                
                # 배포 모드 정보가 있는 경우
                if 'deployment_mode' in data:
                    self.deployment_mode = data['deployment_mode'].lower()
                    self.log(f"배포 모드 감지: {self.deployment_mode.upper()}", "INFO")
                    return self.deployment_mode
                    
                # GPU 관련 정보로 추측
                gpu_info = data.get('gpu_available', False)
                if gpu_info:
                    self.deployment_mode = 'gpu'
                else:
                    self.deployment_mode = 'cpu'
                    
                self.log(f"배포 모드 추측: {self.deployment_mode.upper()} (GPU 가용: {gpu_info})", "INFO")
                return self.deployment_mode
                
        except Exception as e:
            self.log(f"배포 모드 감지 실패: {e}", "WARNING")
            
        # Ollama 연결 테스트로 배포 모드 추측
        try:
            # 간접적으로 Ollama 의존적 기능 테스트
            response = self.make_request("GET", "/health")
            if response.status_code == 200:
                data = response.json()
                # 헬스체크에서 Ollama 상태 확인
                if 'ollama_status' in data:
                    if data['ollama_status'] == 'available':
                        self.deployment_mode = 'gpu'
                    else:
                        self.deployment_mode = 'cpu'
                else:
                    # 기본값: CPU 모드로 가정 (안전한 선택)
                    self.deployment_mode = 'cpu'
                    
            self.log(f"헬스체크 기반 배포 모드: {self.deployment_mode.upper()}", "DEBUG")
            return self.deployment_mode
            
        except Exception as e:
            self.log(f"헬스체크 기반 모드 감지 실패: {e}", "WARNING")
            
        # 모든 감지 방법 실패 시 CPU 모드로 기본 설정
        self.deployment_mode = 'cpu'
        self.log("배포 모드를 CPU로 기본 설정", "WARNING")
        return self.deployment_mode
        
    def is_gpu_mode(self) -> bool:
        """GPU 모드인지 확인"""
        return self.detect_deployment_mode() == 'gpu'
        
    def is_cpu_mode(self) -> bool:
        """CPU 모드인지 확인"""
        return self.detect_deployment_mode() == 'cpu'
        
    def skip_if_cpu_mode(self, test_name: str) -> bool:
        """CPU 모드에서 특정 테스트를 건너뛸지 확인"""
        if self.is_cpu_mode():
            self.log(f"✓ {test_name} 건너뛰기 (CPU 모드)", "INFO")
            return True
        return False