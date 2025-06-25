"""
설정 다이얼로그 위젯
서버 연결, 인증, 테스트 옵션 등 설정 관리
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QComboBox, QCheckBox, QPushButton,
    QGroupBox, QTabWidget, QWidget, QFileDialog, QMessageBox,
    QLabel, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import requests


class SettingsWidget(QDialog):
    """설정 다이얼로그"""
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle("RefClient 설정")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # 탭 위젯
        self.tab_widget = QTabWidget()
        
        # 서버 연결 탭
        self.connection_tab = self.create_connection_tab()
        self.tab_widget.addTab(self.connection_tab, "서버 연결")
        
        # 인증 탭
        self.auth_tab = self.create_auth_tab()
        self.tab_widget.addTab(self.auth_tab, "인증")
        
        # 로그 탭
        self.log_tab = self.create_log_tab()
        self.tab_widget.addTab(self.log_tab, "로그")
        
        # 고급 탭
        self.advanced_tab = self.create_advanced_tab()
        self.tab_widget.addTab(self.advanced_tab, "고급")
        
        layout.addWidget(self.tab_widget)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        self.test_connection_btn = QPushButton("연결 테스트")
        self.test_connection_btn.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_connection_btn)
        
        button_layout.addStretch()
        
        self.reset_btn = QPushButton("기본값으로 리셋")
        self.reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(self.reset_btn)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.ok_btn = QPushButton("확인")
        self.ok_btn.clicked.connect(self.accept_settings)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)
        
        layout.addLayout(button_layout)
        
    def create_connection_tab(self):
        """서버 연결 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 서버 설정 그룹
        server_group = QGroupBox("서버 설정")
        server_form = QFormLayout(server_group)
        
        self.server_url_edit = QLineEdit()
        self.server_url_edit.setPlaceholderText("http://localhost:8060")
        server_form.addRow("서버 URL:", self.server_url_edit)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setSuffix(" 초")
        server_form.addRow("연결 타임아웃:", self.timeout_spin)
        
        layout.addWidget(server_group)
        
        # 연결 상태 그룹
        status_group = QGroupBox("연결 상태")
        status_layout = QVBoxLayout(status_group)
        
        self.connection_status_label = QLabel("연결 상태를 확인하려면 '연결 테스트' 버튼을 클릭하세요.")
        self.connection_status_label.setWordWrap(True)
        status_layout.addWidget(self.connection_status_label)
        
        layout.addWidget(status_group)
        
        layout.addStretch()
        return widget
        
    def create_auth_tab(self):
        """인증 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 관리자 인증 그룹
        auth_group = QGroupBox("관리자 인증")
        auth_form = QFormLayout(auth_group)
        
        self.admin_username_edit = QLineEdit()
        self.admin_username_edit.setPlaceholderText("admin")
        auth_form.addRow("사용자명:", self.admin_username_edit)
        
        self.admin_password_edit = QLineEdit()
        self.admin_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.admin_password_edit.setPlaceholderText("비밀번호 입력")
        auth_form.addRow("비밀번호:", self.admin_password_edit)
        
        # 비밀번호 표시/숨김 체크박스
        self.show_password_check = QCheckBox("비밀번호 표시")
        self.show_password_check.toggled.connect(self.toggle_password_visibility)
        auth_form.addRow("", self.show_password_check)
        
        layout.addWidget(auth_group)
        
        # 인증 안내
        info_group = QGroupBox("인증 정보")
        info_layout = QVBoxLayout(info_group)
        
        info_text = QLabel("""
관리자 인증 정보는 다음 테스트에 필요합니다:
• 관리자 시스템 테스트
• 백업 시스템 테스트

기본 계정: admin / admin123
        """)
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #666666;")
        info_layout.addWidget(info_text)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return widget
        
    def create_log_tab(self):
        """로그 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 로그 설정 그룹
        log_group = QGroupBox("로그 설정")
        log_form = QFormLayout(log_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        log_form.addRow("로그 레벨:", self.log_level_combo)
        
        self.auto_save_check = QCheckBox("자동으로 로그 파일 저장")
        log_form.addRow("", self.auto_save_check)
        
        # 로그 파일 경로
        log_path_layout = QHBoxLayout()
        self.log_path_edit = QLineEdit()
        self.log_path_edit.setPlaceholderText("로그 파일 저장 경로")
        log_path_layout.addWidget(self.log_path_edit)
        
        self.browse_log_path_btn = QPushButton("찾아보기")
        self.browse_log_path_btn.clicked.connect(self.browse_log_path)
        log_path_layout.addWidget(self.browse_log_path_btn)
        
        log_form.addRow("저장 경로:", log_path_layout)
        
        layout.addWidget(log_group)
        
        layout.addStretch()
        return widget
        
    def create_advanced_tab(self):
        """고급 탭 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 설정 관리 그룹
        config_group = QGroupBox("설정 관리")
        config_layout = QVBoxLayout(config_group)
        
        # 내보내기/가져오기 버튼
        import_export_layout = QHBoxLayout()
        
        self.export_settings_btn = QPushButton("설정 내보내기")
        self.export_settings_btn.clicked.connect(self.export_settings)
        import_export_layout.addWidget(self.export_settings_btn)
        
        self.import_settings_btn = QPushButton("설정 가져오기")
        self.import_settings_btn.clicked.connect(self.import_settings)
        import_export_layout.addWidget(self.import_settings_btn)
        
        config_layout.addLayout(import_export_layout)
        
        layout.addWidget(config_group)
        
        # 시스템 정보 그룹
        system_group = QGroupBox("시스템 정보")
        system_layout = QVBoxLayout(system_group)
        
        system_info = QTextEdit()
        system_info.setReadOnly(True)
        system_info.setMaximumHeight(100)
        
        import sys
        import platform
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        
        info_text = f"""Python: {sys.version.split()[0]}
PyQt6: {PYQT_VERSION_STR}
Qt: {QT_VERSION_STR}
플랫폼: {platform.system()} {platform.release()}
"""
        system_info.setPlainText(info_text)
        system_layout.addWidget(system_info)
        
        layout.addWidget(system_group)
        
        layout.addStretch()
        return widget
        
    def load_settings(self):
        """현재 설정 로드"""
        # 서버 연결 설정
        self.server_url_edit.setText(self.config_manager.get_server_url())
        self.timeout_spin.setValue(self.config_manager.get_connection_timeout())
        
        # 인증 설정
        username = self.config_manager.get_admin_username()
        password = self.config_manager.get_admin_password()
        self.admin_username_edit.setText(username)
        self.admin_password_edit.setText(password)
        
        # 로그 설정
        self.log_level_combo.setCurrentText(self.config_manager.get_log_level())
        self.auto_save_check.setChecked(self.config_manager.get_auto_save_logs())
        self.log_path_edit.setText(self.config_manager.get_log_file_path())
        
    def accept_settings(self):
        """설정 저장 및 적용"""
        try:
            # 서버 연결 설정 저장
            self.config_manager.set_server_url(self.server_url_edit.text())
            self.config_manager.set_connection_timeout(self.timeout_spin.value())
            
            # 인증 설정 저장
            self.config_manager.set_admin_username(self.admin_username_edit.text())
            self.config_manager.set_admin_password(self.admin_password_edit.text())
            
            # 로그 설정 저장
            self.config_manager.set_log_level(self.log_level_combo.currentText())
            self.config_manager.set_auto_save_logs(self.auto_save_check.isChecked())
            self.config_manager.set_log_file_path(self.log_path_edit.text())
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"설정 저장 중 오류가 발생했습니다:\n{str(e)}")
            
    def test_connection(self):
        """서버 연결 테스트"""
        server_url = self.server_url_edit.text()
        timeout = self.timeout_spin.value()
        
        if not server_url:
            self.connection_status_label.setText("❌ 서버 URL을 입력해주세요.")
            self.connection_status_label.setStyleSheet("color: red;")
            return
            
        try:
            self.connection_status_label.setText("⏳ 연결 테스트 중...")
            self.connection_status_label.setStyleSheet("color: orange;")
            self.test_connection_btn.setEnabled(False)
            
            # 블로킹하지 않도록 짧은 타임아웃 사용
            response = requests.get(f"{server_url}/health", timeout=min(timeout, 10))
            
            if response.status_code == 200:
                data = response.json()
                status = data.get('status', 'unknown')
                
                if status == 'healthy':
                    self.connection_status_label.setText("✅ 연결 성공! 서버가 정상 상태입니다.")
                    self.connection_status_label.setStyleSheet("color: green;")
                else:
                    self.connection_status_label.setText(f"⚠️ 연결되었지만 서버 상태가 비정상입니다: {status}")
                    self.connection_status_label.setStyleSheet("color: orange;")
            else:
                self.connection_status_label.setText(f"❌ 서버 응답 오류: HTTP {response.status_code}")
                self.connection_status_label.setStyleSheet("color: red;")
                
        except requests.exceptions.ConnectTimeout:
            self.connection_status_label.setText("❌ 연결 타임아웃: 서버에 연결할 수 없습니다.")
            self.connection_status_label.setStyleSheet("color: red;")
        except requests.exceptions.ConnectionError:
            self.connection_status_label.setText("❌ 연결 실패: 서버가 실행 중인지 확인해주세요.")
            self.connection_status_label.setStyleSheet("color: red;")
        except Exception as e:
            self.connection_status_label.setText(f"❌ 연결 오류: {str(e)}")
            self.connection_status_label.setStyleSheet("color: red;")
        finally:
            self.test_connection_btn.setEnabled(True)
            
    def toggle_password_visibility(self, checked: bool):
        """비밀번호 표시/숨김 토글"""
        if checked:
            self.admin_password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.admin_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
            
    def browse_log_path(self):
        """로그 저장 경로 찾아보기"""
        directory = QFileDialog.getExistingDirectory(
            self, "로그 저장 경로 선택", self.log_path_edit.text()
        )
        if directory:
            self.log_path_edit.setText(directory)
            
    def reset_to_defaults(self):
        """기본값으로 리셋"""
        reply = QMessageBox.question(
            self, "설정 리셋",
            "모든 설정을 기본값으로 되돌리시겠습니까?\n\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.reset_to_defaults()
            self.load_settings()
            QMessageBox.information(self, "완료", "설정이 기본값으로 초기화되었습니다.")
            
    def export_settings(self):
        """설정 내보내기"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "설정 내보내기", "refclient_settings.json",
            "JSON 파일 (*.json);;모든 파일 (*)"
        )
        
        if file_path:
            if self.config_manager.export_settings(file_path):
                QMessageBox.information(self, "성공", f"설정이 내보내졌습니다:\n{file_path}")
            else:
                QMessageBox.critical(self, "오류", "설정 내보내기에 실패했습니다.")
                
    def import_settings(self):
        """설정 가져오기"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "설정 가져오기", "",
            "JSON 파일 (*.json);;모든 파일 (*)"
        )
        
        if file_path:
            reply = QMessageBox.question(
                self, "설정 가져오기",
                "현재 설정을 가져올 설정으로 덮어쓰시겠습니까?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                if self.config_manager.import_settings(file_path):
                    self.load_settings()
                    QMessageBox.information(self, "성공", "설정을 가져왔습니다.")
                else:
                    QMessageBox.critical(self, "오류", "설정 가져오기에 실패했습니다.")