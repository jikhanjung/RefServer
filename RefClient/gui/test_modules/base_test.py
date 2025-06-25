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