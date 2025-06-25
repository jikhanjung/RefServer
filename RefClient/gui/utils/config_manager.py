"""
설정 관리 클래스
QSettings를 사용하여 애플리케이션 설정을 저장/로드
"""

from PyQt6.QtCore import QSettings
import os


class ConfigManager:
    """설정 관리 클래스"""
    
    def __init__(self):
        self.settings = QSettings("RefClient", "RefClient")
        self._load_default_settings()
        
    def _load_default_settings(self):
        """기본 설정값 로드"""
        # 기본값들
        defaults = {
            'server_url': 'http://localhost:8060',
            'connection_timeout': 30,
            'admin_username': 'admin',
            'admin_password': '',  # 보안상 기본값은 빈 문자열
            'log_level': 'INFO',
            'auto_save_logs': True,
            'log_file_path': os.path.expanduser('~/RefClient_logs'),
            'window_geometry': None,
            'window_state': None
        }
        
        # 기본값이 없는 경우에만 설정
        for key, default_value in defaults.items():
            if not self.settings.contains(key):
                self.settings.setValue(key, default_value)
                
    def get_server_url(self) -> str:
        """서버 URL 반환"""
        return self.settings.value('server_url', 'http://localhost:8060')
        
    def set_server_url(self, url: str):
        """서버 URL 설정"""
        self.settings.setValue('server_url', url)
        
    def get_connection_timeout(self) -> int:
        """연결 타임아웃 반환"""
        return int(self.settings.value('connection_timeout', 30))
        
    def set_connection_timeout(self, timeout: int):
        """연결 타임아웃 설정"""
        self.settings.setValue('connection_timeout', timeout)
        
    def get_admin_username(self) -> str:
        """관리자 사용자명 반환"""
        return self.settings.value('admin_username', 'admin')
        
    def set_admin_username(self, username: str):
        """관리자 사용자명 설정"""
        self.settings.setValue('admin_username', username)
        
    def get_admin_password(self) -> str:
        """관리자 비밀번호 반환"""
        return self.settings.value('admin_password', '')
        
    def set_admin_password(self, password: str):
        """관리자 비밀번호 설정"""
        self.settings.setValue('admin_password', password)
        
    def get_test_settings(self) -> dict:
        """테스트 실행에 필요한 모든 설정 반환"""
        return {
            'server_url': self.get_server_url(),
            'connection_timeout': self.get_connection_timeout(),
            'admin_username': self.get_admin_username(),
            'admin_password': self.get_admin_password()
        }
        
    def get_log_level(self) -> str:
        """로그 레벨 반환"""
        return self.settings.value('log_level', 'INFO')
        
    def set_log_level(self, level: str):
        """로그 레벨 설정"""
        self.settings.setValue('log_level', level)
        
    def get_auto_save_logs(self) -> bool:
        """자동 로그 저장 설정 반환"""
        return self.settings.value('auto_save_logs', True, type=bool)
        
    def set_auto_save_logs(self, enabled: bool):
        """자동 로그 저장 설정"""
        self.settings.setValue('auto_save_logs', enabled)
        
    def get_log_file_path(self) -> str:
        """로그 파일 경로 반환"""
        default_path = os.path.expanduser('~/RefClient_logs')
        return self.settings.value('log_file_path', default_path)
        
    def set_log_file_path(self, path: str):
        """로그 파일 경로 설정"""
        self.settings.setValue('log_file_path', path)
        
    def save_window_geometry(self, geometry):
        """윈도우 지오메트리 저장"""
        self.settings.setValue('window_geometry', geometry)
        
    def get_window_geometry(self):
        """윈도우 지오메트리 반환"""
        return self.settings.value('window_geometry', None)
        
    def save_window_state(self, state):
        """윈도우 상태 저장"""
        self.settings.setValue('window_state', state)
        
    def get_window_state(self):
        """윈도우 상태 반환"""
        return self.settings.value('window_state', None)
        
    def get_test_settings(self) -> dict:
        """테스트 관련 설정 반환"""
        return {
            'server_url': self.get_server_url(),
            'timeout': self.get_connection_timeout(),
            'admin_username': self.get_admin_credentials()[0],
            'admin_password': self.get_admin_password_decoded(),
            'log_level': self.get_log_level()
        }
        
    def reset_to_defaults(self):
        """설정을 기본값으로 리셋"""
        self.settings.clear()
        self._load_default_settings()
        
    def export_settings(self, file_path: str) -> bool:
        """설정을 파일로 내보내기"""
        try:
            import json
            
            settings_data = {}
            for key in self.settings.allKeys():
                settings_data[key] = self.settings.value(key)
                
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, indent=2, ensure_ascii=False)
                
            return True
        except Exception:
            return False
            
    def import_settings(self, file_path: str) -> bool:
        """파일에서 설정 가져오기"""
        try:
            import json
            
            with open(file_path, 'r', encoding='utf-8') as f:
                settings_data = json.load(f)
                
            for key, value in settings_data.items():
                self.settings.setValue(key, value)
                
            return True
        except Exception:
            return False