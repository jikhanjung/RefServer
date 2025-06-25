"""
관리 기능 테스트 탭
RefServer의 관리자 관련 기능들을 테스트
"""

import base64
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QLabel, QLineEdit, QTextEdit, QTableWidget, QTableWidgetItem, 
    QHeaderView, QCheckBox, QTabWidget, QMessageBox, QProgressBar,
    QFormLayout, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
import requests
import json


class AdminTestWorker(QThread):
    """관리자 기능 테스트를 담당하는 워커 스레드"""
    
    # 시그널 정의
    test_started = pyqtSignal(str)  # test_name
    test_completed = pyqtSignal(str, dict)  # test_name, result
    test_failed = pyqtSignal(str, str)  # test_name, error
    log_message = pyqtSignal(str, str)  # message, level
    progress_updated = pyqtSignal(int)  # percentage
    
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.tests_to_run = []
        self.auth_token = None
        self.is_running = False
        
    def set_tests(self, tests):
        """실행할 테스트 목록 설정"""
        self.tests_to_run = tests
        
    def set_auth_token(self, token):
        """인증 토큰 설정"""
        self.auth_token = token
        
    def stop(self):
        """테스트 중지"""
        self.is_running = False
        
    def run(self):
        """관리자 기능 테스트 실행"""
        self.is_running = True
        
        server_url = self.config_manager.get_server_url()
        timeout = self.config_manager.get_connection_timeout()
        
        test_methods = {
            'admin_login': self._test_admin_login,
            'admin_dashboard': self._test_admin_dashboard,
            'papers_management': self._test_papers_management,
            'backup_system': self._test_backup_system,
            'consistency_check': self._test_consistency_check,
            'service_management': self._test_service_management,
            'performance_monitoring': self._test_performance_monitoring
        }
        
        total_tests = len(self.tests_to_run)
        
        for i, test_name in enumerate(self.tests_to_run):
            if not self.is_running:
                break
                
            if test_name in test_methods:
                try:
                    self.test_started.emit(test_name)
                    result = test_methods[test_name](server_url, timeout)
                    self.test_completed.emit(test_name, result)
                    
                except Exception as e:
                    self.test_failed.emit(test_name, str(e))
                    
            # 진행률 업데이트
            progress = int((i + 1) / total_tests * 100)
            self.progress_updated.emit(progress)
            
        self.is_running = False
        
    def _get_auth_headers(self):
        """인증 헤더 반환"""
        if self.auth_token:
            return {'Authorization': f'Bearer {self.auth_token}'}
        return {}
        
    def _test_admin_login(self, server_url, timeout):
        """관리자 로그인 테스트"""
        username = self.config_manager.get_admin_username()
        password = self.config_manager.get_admin_password()
        
        if not username or not password:
            return {
                'success': False,
                'error': '관리자 인증 정보가 설정되지 않았습니다'
            }
            
        try:
            # 로그인 시도
            login_data = {
                'username': username,
                'password': password
            }
            
            response = requests.post(
                f"{server_url}/admin/login",
                data=login_data,
                timeout=timeout,
                allow_redirects=False
            )
            
            # 로그인 성공 확인 (리다이렉트 또는 토큰 반환)
            if response.status_code in [200, 302]:
                # JWT 토큰이 있는지 확인
                auth_header = response.headers.get('Authorization')
                if auth_header:
                    self.auth_token = auth_header.replace('Bearer ', '')
                
                return {
                    'success': True,
                    'status_code': response.status_code,
                    'has_token': bool(auth_header),
                    'redirect_location': response.headers.get('Location', 'N/A')
                }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': f'로그인 실패: HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_admin_dashboard(self, server_url, timeout):
        """관리자 대시보드 테스트"""
        try:
            headers = self._get_auth_headers()
            response = requests.get(
                f"{server_url}/admin/dashboard",
                headers=headers,
                timeout=timeout
            )
            
            return {
                'success': response.status_code == 200,
                'status_code': response.status_code,
                'content_type': response.headers.get('Content-Type', 'unknown'),
                'content_length': len(response.content)
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_papers_management(self, server_url, timeout):
        """논문 관리 기능 테스트"""
        try:
            headers = self._get_auth_headers()
            
            # 논문 목록 조회
            response = requests.get(
                f"{server_url}/admin/papers",
                headers=headers,
                timeout=timeout
            )
            
            if response.status_code == 200:
                # 논문 통계 조회
                stats_response = requests.get(
                    f"{server_url}/stats",
                    headers=headers,
                    timeout=timeout
                )
                
                return {
                    'success': True,
                    'papers_page_accessible': True,
                    'stats_accessible': stats_response.status_code == 200,
                    'stats_data': stats_response.json() if stats_response.status_code == 200 else None
                }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': f'논문 목록 접근 실패: HTTP {response.status_code}'
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_backup_system(self, server_url, timeout):
        """백업 시스템 테스트"""
        try:
            headers = self._get_auth_headers()
            
            # 백업 상태 조회
            status_response = requests.get(
                f"{server_url}/admin/backup/status",
                headers=headers,
                timeout=timeout
            )
            
            # 백업 이력 조회
            history_response = requests.get(
                f"{server_url}/admin/backup/history",
                headers=headers,
                timeout=timeout
            )
            
            return {
                'success': status_response.status_code == 200,
                'status_accessible': status_response.status_code == 200,
                'history_accessible': history_response.status_code == 200,
                'status_data': status_response.json() if status_response.status_code == 200 else None,
                'history_data': history_response.json() if history_response.status_code == 200 else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_consistency_check(self, server_url, timeout):
        """일관성 검증 테스트"""
        try:
            headers = self._get_auth_headers()
            
            # 일관성 요약 조회
            summary_response = requests.get(
                f"{server_url}/admin/consistency/summary",
                headers=headers,
                timeout=timeout
            )
            
            return {
                'success': summary_response.status_code == 200,
                'summary_accessible': summary_response.status_code == 200,
                'summary_data': summary_response.json() if summary_response.status_code == 200 else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_service_management(self, server_url, timeout):
        """서비스 관리 테스트"""
        try:
            headers = self._get_auth_headers()
            
            # 서비스 상태 조회
            status_response = requests.get(
                f"{server_url}/admin/services/status",
                headers=headers,
                timeout=timeout
            )
            
            return {
                'success': status_response.status_code == 200,
                'status_accessible': status_response.status_code == 200,
                'services_count': len(status_response.json()) if status_response.status_code == 200 else 0,
                'services_data': status_response.json() if status_response.status_code == 200 else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_performance_monitoring(self, server_url, timeout):
        """성능 모니터링 테스트"""
        try:
            headers = self._get_auth_headers()
            
            # 성능 통계 조회
            stats_response = requests.get(
                f"{server_url}/performance/stats",
                headers=headers,
                timeout=timeout
            )
            
            # 큐 상태 조회
            queue_response = requests.get(
                f"{server_url}/queue/status",
                headers=headers,
                timeout=timeout
            )
            
            return {
                'success': stats_response.status_code == 200,
                'performance_accessible': stats_response.status_code == 200,
                'queue_accessible': queue_response.status_code == 200,
                'performance_data': stats_response.json() if stats_response.status_code == 200 else None,
                'queue_data': queue_response.json() if queue_response.status_code == 200 else None
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}


class AdminFunctionsTab(QWidget):
    """관리 기능 테스트 탭"""
    
    def __init__(self, config_manager, log_viewer):
        super().__init__()
        self.config_manager = config_manager
        self.log_viewer = log_viewer
        self.admin_worker = None
        self.test_results = {}
        self.setup_ui()
        
    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 탭 위젯 생성
        tab_widget = QTabWidget()
        
        # 인증 탭
        auth_tab = self.create_auth_tab()
        tab_widget.addTab(auth_tab, "🔐 인증")
        
        # 테스트 탭
        test_tab = self.create_test_tab()
        tab_widget.addTab(test_tab, "🧪 기능 테스트")
        
        # 서비스 관리 탭
        service_tab = self.create_service_tab()
        tab_widget.addTab(service_tab, "⚙️ 서비스 관리")
        
        layout.addWidget(tab_widget)
        
    def create_auth_tab(self):
        """인증 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 인증 정보 그룹
        auth_group = QGroupBox("🔐 관리자 인증 정보")
        auth_layout = QFormLayout(auth_group)
        
        self.username_edit = QLineEdit()
        self.username_edit.setText(self.config_manager.get_admin_username())
        auth_layout.addRow("사용자명:", self.username_edit)
        
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setText(self.config_manager.get_admin_password())
        auth_layout.addRow("비밀번호:", self.password_edit)
        
        # 인증 정보 저장 버튼
        save_btn = QPushButton("인증 정보 저장")
        save_btn.clicked.connect(self.save_auth_info)
        auth_layout.addRow("", save_btn)
        
        layout.addWidget(auth_group)
        
        # 로그인 테스트 그룹
        login_group = QGroupBox("🚀 로그인 테스트")
        login_layout = QVBoxLayout(login_group)
        
        login_btn_layout = QHBoxLayout()
        
        self.login_test_btn = QPushButton("로그인 테스트")
        self.login_test_btn.setStyleSheet("font-weight: bold; min-height: 30px; background-color: #28a745; color: white;")
        self.login_test_btn.clicked.connect(self.test_login)
        login_btn_layout.addWidget(self.login_test_btn)
        
        self.clear_auth_btn = QPushButton("인증 정보 지우기")
        self.clear_auth_btn.clicked.connect(self.clear_auth)
        login_btn_layout.addWidget(self.clear_auth_btn)
        
        login_layout.addLayout(login_btn_layout)
        
        # 로그인 결과 표시
        self.login_result_label = QLabel("로그인 테스트를 실행해주세요.")
        self.login_result_label.setWordWrap(True)
        self.login_result_label.setStyleSheet("padding: 10px; border: 1px solid #ddd; border-radius: 5px;")
        login_layout.addWidget(self.login_result_label)
        
        layout.addWidget(login_group)
        
        # 도움말
        help_group = QGroupBox("💡 도움말")
        help_layout = QVBoxLayout(help_group)
        
        help_text = QLabel("""
<b>기본 관리자 계정:</b>
• 사용자명: admin
• 비밀번호: admin123

<b>인증 정보 설정:</b>
1. 위에서 사용자명과 비밀번호를 입력
2. "인증 정보 저장" 버튼 클릭
3. "로그인 테스트" 버튼으로 인증 확인

<b>주의사항:</b>
• 관리자 기능 테스트는 유효한 인증 정보가 필요합니다
• 인증 정보는 로컬에 저장되며 암호화되지 않습니다
        """)
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-size: 11px;")
        help_layout.addWidget(help_text)
        
        layout.addWidget(help_group)
        layout.addStretch()
        
        return widget
        
    def create_test_tab(self):
        """테스트 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 테스트 선택 그룹
        test_group = QGroupBox("🧪 관리자 기능 테스트")
        test_layout = QVBoxLayout(test_group)
        
        self.test_checkboxes = {}
        tests = [
            ('admin_login', '관리자 로그인'),
            ('admin_dashboard', '관리자 대시보드'),
            ('papers_management', '논문 관리'),
            ('backup_system', '백업 시스템'),
            ('consistency_check', '일관성 검증'),
            ('service_management', '서비스 관리'),
            ('performance_monitoring', '성능 모니터링')
        ]
        
        for test_key, test_name in tests:
            checkbox = QCheckBox(test_name)
            checkbox.setChecked(True)
            self.test_checkboxes[test_key] = checkbox
            test_layout.addWidget(checkbox)
            
        # 테스트 컨트롤
        control_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("전체 선택")
        self.select_all_btn.clicked.connect(self.select_all_tests)
        control_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("전체 해제")
        self.deselect_all_btn.clicked.connect(self.deselect_all_tests)
        control_layout.addWidget(self.deselect_all_btn)
        
        control_layout.addStretch()
        
        self.run_admin_tests_btn = QPushButton("관리자 테스트 실행")
        self.run_admin_tests_btn.setStyleSheet("font-weight: bold; min-height: 30px; background-color: #007bff; color: white;")
        self.run_admin_tests_btn.clicked.connect(self.run_admin_tests)
        control_layout.addWidget(self.run_admin_tests_btn)
        
        self.stop_admin_tests_btn = QPushButton("중지")
        self.stop_admin_tests_btn.setStyleSheet("min-height: 30px; background-color: #dc3545; color: white;")
        self.stop_admin_tests_btn.clicked.connect(self.stop_admin_tests)
        self.stop_admin_tests_btn.setEnabled(False)
        control_layout.addWidget(self.stop_admin_tests_btn)
        
        test_layout.addLayout(control_layout)
        
        # 진행률
        self.admin_progress_label = QLabel("대기 중...")
        test_layout.addWidget(self.admin_progress_label)
        
        self.admin_progress_bar = QProgressBar()
        self.admin_progress_bar.setVisible(False)
        test_layout.addWidget(self.admin_progress_bar)
        
        layout.addWidget(test_group)
        
        # 테스트 결과 그룹
        result_group = QGroupBox("📊 테스트 결과")
        result_layout = QVBoxLayout(result_group)
        
        # 결과 테이블
        self.admin_result_table = QTableWidget()
        self.admin_result_table.setColumnCount(3)
        self.admin_result_table.setHorizontalHeaderLabels([
            "기능", "상태", "상세정보"
        ])
        
        # 테이블 설정
        header = self.admin_result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        result_layout.addWidget(self.admin_result_table)
        
        layout.addWidget(result_group)
        
        return widget
        
    def create_service_tab(self):
        """서비스 관리 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 서비스 상태 확인
        status_group = QGroupBox("⚙️ 서비스 상태")
        status_layout = QVBoxLayout(status_group)
        
        status_btn_layout = QHBoxLayout()
        
        self.check_services_btn = QPushButton("서비스 상태 확인")
        self.check_services_btn.clicked.connect(self.check_services_status)
        status_btn_layout.addWidget(self.check_services_btn)
        
        self.refresh_services_btn = QPushButton("새로고침")
        self.refresh_services_btn.clicked.connect(self.refresh_services)
        status_btn_layout.addWidget(self.refresh_services_btn)
        
        status_btn_layout.addStretch()
        status_layout.addLayout(status_btn_layout)
        
        # 서비스 상태 테이블
        self.services_table = QTableWidget()
        self.services_table.setColumnCount(4)
        self.services_table.setHorizontalHeaderLabels([
            "서비스", "상태", "실패 횟수", "마지막 오류"
        ])
        
        # 테이블 설정
        header = self.services_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        status_layout.addWidget(self.services_table)
        
        layout.addWidget(status_group)
        
        # 서비스 제어
        control_group = QGroupBox("🎛️ 서비스 제어")
        control_layout = QVBoxLayout(control_group)
        
        control_info = QLabel("서비스 제어 기능은 관리자 웹 인터페이스를 통해 사용할 수 있습니다.")
        control_info.setStyleSheet("color: #666; font-style: italic;")
        control_layout.addWidget(control_info)
        
        web_interface_btn = QPushButton("관리자 웹 인터페이스 열기")
        web_interface_btn.clicked.connect(self.open_admin_interface)
        control_layout.addWidget(web_interface_btn)
        
        layout.addWidget(control_group)
        layout.addStretch()
        
        return widget
        
    def save_auth_info(self):
        """인증 정보 저장"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "경고", "사용자명과 비밀번호를 모두 입력해주세요.")
            return
            
        self.config_manager.set_admin_username(username)
        self.config_manager.set_admin_password(password)
        
        self.log_viewer.add_log(f"관리자 인증 정보가 저장되었습니다: {username}", "INFO")
        
    def clear_auth(self):
        """인증 정보 지우기"""
        self.username_edit.clear()
        self.password_edit.clear()
        self.config_manager.set_admin_username("")
        self.config_manager.set_admin_password("")
        self.login_result_label.setText("인증 정보가 지워졌습니다.")
        self.log_viewer.add_log("관리자 인증 정보가 지워졌습니다.", "INFO")
        
    def test_login(self):
        """로그인 테스트"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "경고", "사용자명과 비밀번호를 입력해주세요.")
            return
            
        # 임시로 인증 정보 저장
        self.config_manager.set_admin_username(username)
        self.config_manager.set_admin_password(password)
        
        try:
            server_url = self.config_manager.get_server_url()
            
            # 로그인 시도
            login_data = {
                'username': username,
                'password': password
            }
            
            response = requests.post(
                f"{server_url}/admin/login",
                data=login_data,
                timeout=10,
                allow_redirects=False
            )
            
            if response.status_code in [200, 302]:
                self.login_result_label.setText("✅ 로그인 성공!")
                self.login_result_label.setStyleSheet("color: green; padding: 10px; border: 1px solid #28a745; border-radius: 5px;")
                self.log_viewer.add_log("관리자 로그인 테스트 성공", "PASS")
            else:
                self.login_result_label.setText(f"❌ 로그인 실패 (HTTP {response.status_code})")
                self.login_result_label.setStyleSheet("color: red; padding: 10px; border: 1px solid #dc3545; border-radius: 5px;")
                self.log_viewer.add_log(f"관리자 로그인 테스트 실패: HTTP {response.status_code}", "FAIL")
                
        except Exception as e:
            self.login_result_label.setText(f"❌ 로그인 오류: {str(e)}")
            self.login_result_label.setStyleSheet("color: red; padding: 10px; border: 1px solid #dc3545; border-radius: 5px;")
            self.log_viewer.add_log(f"관리자 로그인 테스트 오류: {str(e)}", "ERROR")
            
    def select_all_tests(self):
        """모든 테스트 선택"""
        for checkbox in self.test_checkboxes.values():
            checkbox.setChecked(True)
            
    def deselect_all_tests(self):
        """모든 테스트 해제"""
        for checkbox in self.test_checkboxes.values():
            checkbox.setChecked(False)
            
    def run_admin_tests(self):
        """관리자 테스트 실행"""
        selected_tests = [
            test_key for test_key, checkbox in self.test_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        if not selected_tests:
            self.log_viewer.add_log("실행할 관리자 테스트를 선택해주세요.", "WARNING")
            return
            
        # 인증 정보 확인
        username = self.config_manager.get_admin_username()
        password = self.config_manager.get_admin_password()
        
        if not username or not password:
            QMessageBox.warning(self, "경고", "관리자 인증 정보를 먼저 설정해주세요.")
            return
            
        # UI 상태 업데이트
        self.run_admin_tests_btn.setEnabled(False)
        self.stop_admin_tests_btn.setEnabled(True)
        self.admin_progress_bar.setVisible(True)
        self.admin_progress_bar.setValue(0)
        self.admin_progress_label.setText("관리자 테스트 준비 중...")
        
        # 결과 초기화
        self.test_results = {}
        self.admin_result_table.setRowCount(0)
        
        # 워커 스레드 시작
        self.admin_worker = AdminTestWorker(self.config_manager)
        self.admin_worker.set_tests(selected_tests)
        
        # 시그널 연결
        self.admin_worker.test_started.connect(self.on_admin_test_started)
        self.admin_worker.test_completed.connect(self.on_admin_test_completed)
        self.admin_worker.test_failed.connect(self.on_admin_test_failed)
        self.admin_worker.log_message.connect(self.log_viewer.add_log)
        self.admin_worker.progress_updated.connect(self.on_admin_progress_updated)
        self.admin_worker.finished.connect(self.on_admin_tests_finished)
        
        self.admin_worker.start()
        
    def stop_admin_tests(self):
        """관리자 테스트 중지"""
        if self.admin_worker:
            self.admin_worker.stop()
            self.log_viewer.add_log("관리자 테스트가 사용자에 의해 중지되었습니다.", "WARNING")
            
    def on_admin_test_started(self, test_name):
        """관리자 테스트 시작 시 호출"""
        self.admin_progress_label.setText(f"실행 중: {test_name}")
        
    def on_admin_test_completed(self, test_name, result):
        """관리자 테스트 완료 시 호출"""
        self.test_results[test_name] = {
            'success': True,
            'result': result
        }
        self.update_admin_result_table()
        
    def on_admin_test_failed(self, test_name, error):
        """관리자 테스트 실패 시 호출"""
        self.test_results[test_name] = {
            'success': False,
            'error': error
        }
        self.update_admin_result_table()
        
    def on_admin_progress_updated(self, progress):
        """관리자 테스트 진행률 업데이트"""
        self.admin_progress_bar.setValue(progress)
        
    def on_admin_tests_finished(self):
        """모든 관리자 테스트 완료 시 호출"""
        self.run_admin_tests_btn.setEnabled(True)
        self.stop_admin_tests_btn.setEnabled(False)
        self.admin_progress_bar.setVisible(False)
        self.admin_progress_label.setText("완료")
        
    def update_admin_result_table(self):
        """관리자 테스트 결과 테이블 업데이트"""
        self.admin_result_table.setRowCount(len(self.test_results))
        
        test_names = {
            'admin_login': '관리자 로그인',
            'admin_dashboard': '관리자 대시보드',
            'papers_management': '논문 관리',
            'backup_system': '백업 시스템',
            'consistency_check': '일관성 검증',
            'service_management': '서비스 관리',
            'performance_monitoring': '성능 모니터링'
        }
        
        for row, (test_key, test_data) in enumerate(self.test_results.items()):
            # 기능명
            function_name = test_names.get(test_key, test_key)
            self.admin_result_table.setItem(row, 0, QTableWidgetItem(function_name))
            
            # 상태
            if test_data['success']:
                result = test_data['result']
                if result.get('success', True):
                    status_item = QTableWidgetItem("✅ 성공")
                    status_item.setBackground(Qt.GlobalColor.green)
                else:
                    status_item = QTableWidgetItem("⚠️ 부분 성공")
                    status_item.setBackground(Qt.GlobalColor.yellow)
            else:
                status_item = QTableWidgetItem("❌ 실패")
                status_item.setBackground(Qt.GlobalColor.red)
                
            self.admin_result_table.setItem(row, 1, status_item)
            
            # 상세정보
            if test_data['success']:
                result = test_data['result']
                detail = self._format_admin_result_detail(test_key, result)
            else:
                detail = f"오류: {test_data['error']}"
                
            self.admin_result_table.setItem(row, 2, QTableWidgetItem(detail))
            
    def _format_admin_result_detail(self, test_key, result):
        """관리자 테스트 결과 상세정보 포맷"""
        if test_key == 'admin_login':
            status_code = result.get('status_code', 'Unknown')
            has_token = result.get('has_token', False)
            return f"HTTP {status_code}, 토큰: {'있음' if has_token else '없음'}"
            
        elif test_key == 'admin_dashboard':
            status_code = result.get('status_code', 'Unknown')
            content_length = result.get('content_length', 0)
            return f"HTTP {status_code}, 크기: {content_length} bytes"
            
        elif test_key == 'papers_management':
            papers_accessible = result.get('papers_page_accessible', False)
            stats_accessible = result.get('stats_accessible', False)
            return f"논문 페이지: {'접근 가능' if papers_accessible else '접근 불가'}, 통계: {'접근 가능' if stats_accessible else '접근 불가'}"
            
        elif test_key == 'backup_system':
            status_accessible = result.get('status_accessible', False)
            history_accessible = result.get('history_accessible', False)
            return f"상태: {'접근 가능' if status_accessible else '접근 불가'}, 이력: {'접근 가능' if history_accessible else '접근 불가'}"
            
        elif test_key == 'service_management':
            services_count = result.get('services_count', 0)
            return f"서비스 개수: {services_count}"
            
        else:
            return str(result.get('success', False))
            
    def check_services_status(self):
        """서비스 상태 확인"""
        try:
            server_url = self.config_manager.get_server_url()
            response = requests.get(f"{server_url}/status", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                circuit_breakers = data.get('circuit_breakers', {})
                
                self.update_services_table(circuit_breakers)
                self.log_viewer.add_log("서비스 상태를 확인했습니다.", "INFO")
            else:
                self.log_viewer.add_log(f"서비스 상태 확인 실패: HTTP {response.status_code}", "ERROR")
                
        except Exception as e:
            self.log_viewer.add_log(f"서비스 상태 확인 오류: {str(e)}", "ERROR")
            
    def update_services_table(self, circuit_breakers):
        """서비스 테이블 업데이트"""
        self.services_table.setRowCount(len(circuit_breakers))
        
        for row, (service_name, status) in enumerate(circuit_breakers.items()):
            # 서비스명
            self.services_table.setItem(row, 0, QTableWidgetItem(service_name.replace('_', ' ').title()))
            
            # 상태
            state = status.get('state', 'unknown')
            status_item = QTableWidgetItem(state.title())
            
            if state == 'closed':
                status_item.setBackground(Qt.GlobalColor.green)
            elif state == 'open':
                status_item.setBackground(Qt.GlobalColor.red)
            else:
                status_item.setBackground(Qt.GlobalColor.yellow)
                
            self.services_table.setItem(row, 1, status_item)
            
            # 실패 횟수
            failure_count = status.get('total_failures', 0)
            self.services_table.setItem(row, 2, QTableWidgetItem(str(failure_count)))
            
            # 마지막 오류
            last_error = status.get('last_error', 'None')
            if len(last_error) > 50:
                last_error = last_error[:47] + "..."
            self.services_table.setItem(row, 3, QTableWidgetItem(last_error))
            
    def refresh_services(self):
        """서비스 새로고침"""
        self.check_services_status()
        
    def open_admin_interface(self):
        """관리자 웹 인터페이스 열기"""
        import webbrowser
        server_url = self.config_manager.get_server_url()
        admin_url = f"{server_url}/admin"
        webbrowser.open(admin_url)
        self.log_viewer.add_log(f"관리자 웹 인터페이스를 열었습니다: {admin_url}", "INFO")