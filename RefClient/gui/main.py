#!/usr/bin/env python3
"""
RefClient - RefServer GUI 테스트 클라이언트
PyQt6 기반 메인 애플리케이션
"""

import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QMenuBar, QStatusBar, QSplitter, QGroupBox,
    QCheckBox, QPushButton, QLabel, QProgressBar, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QFont

# Add tests directory to path for importing test modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tests'))

from widgets.log_viewer import LogViewerWidget
from widgets.settings import SettingsWidget
from widgets.file_upload_tab import FileUploadTab
from widgets.server_status_tab import ServerStatusTab
from widgets.admin_functions_tab import AdminFunctionsTab
from utils.config_manager import ConfigManager


class RefClientMainWindow(QMainWindow):
    """RefClient 메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.setup_ui()
        self.setup_connections()
        self.load_settings()
        
    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle("RefClient - RefServer GUI 테스트 클라이언트 v0.1.12")
        self.setGeometry(100, 100, 1400, 900)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        
        # 툴바 영역
        toolbar_layout = QHBoxLayout()
        
        # 연결 상태 및 배포 모드 표시
        self.connection_status = QLabel("연결 안됨")
        self.connection_status.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
        
        self.deployment_mode = QLabel("모드: 감지 중")
        self.deployment_mode.setStyleSheet("color: gray; font-weight: bold; padding: 5px;")
        
        toolbar_layout.addWidget(QLabel("서버 상태:"))
        toolbar_layout.addWidget(self.connection_status)
        toolbar_layout.addWidget(QLabel(" | "))
        toolbar_layout.addWidget(self.deployment_mode)
        toolbar_layout.addStretch()
        
        # 설정 버튼
        self.settings_btn = QPushButton("⚙️ 설정")
        self.settings_btn.clicked.connect(self.show_settings)
        toolbar_layout.addWidget(self.settings_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        # 메인 콘텐츠 영역 (상하 분할)
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # 상단 - 메인 기능 탭들
        self.main_tab_widget = QTabWidget()
        
        # 로그 뷰어 생성 (모든 탭에서 공유)
        self.log_viewer = LogViewerWidget()
        
        # 1. 파일 업로드 탭
        self.file_upload_tab = FileUploadTab(self.config_manager, self.log_viewer)
        self.main_tab_widget.addTab(self.file_upload_tab, "📁 파일 업로드")
        
        # 2. 서버 상태 탭
        self.server_status_tab = ServerStatusTab(self.config_manager, self.log_viewer)
        self.main_tab_widget.addTab(self.server_status_tab, "🔍 서버 상태")
        
        # 3. 관리 기능 탭
        self.admin_functions_tab = AdminFunctionsTab(self.config_manager, self.log_viewer)
        self.main_tab_widget.addTab(self.admin_functions_tab, "⚙️ 관리 기능")
        
        main_splitter.addWidget(self.main_tab_widget)
        
        # 하단 - 로그 뷰어
        log_group = QGroupBox("📋 실시간 로그")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_viewer)
        main_splitter.addWidget(log_group)
        
        # 분할 비율 설정 (3:1)
        main_splitter.setSizes([700, 200])
        main_layout.addWidget(main_splitter)
        
        # 메뉴바 설정
        self.setup_menubar()
        
        # 상태바 설정
        self.setup_statusbar()
        
    def setup_connections(self):
        """신호/슬롯 연결 설정"""
        # 타이머로 주기적 상태 체크
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_server_status)
        self.status_timer.start(10000)  # 10초마다
        
        # 초기 상태 체크
        QTimer.singleShot(1000, self.check_server_status)
        
    def load_settings(self):
        """설정 로드"""
        server_url = self.config_manager.get_server_url()
        self.log_viewer.add_log(f"설정 로드 완료. 서버 URL: {server_url}", "INFO")
        
    def check_server_status(self):
        """서버 연결 상태 및 배포 모드 확인"""
        try:
            import requests
            server_url = self.config_manager.get_server_url()
            
            response = requests.get(f"{server_url}/health", timeout=5)
            if response.status_code == 200:
                self.connection_status.setText("✅ 연결됨")
                self.connection_status.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                self.statusBar().showMessage("서버 연결 정상")
                
                # 배포 모드 감지
                self.detect_deployment_mode()
            else:
                self.connection_status.setText("⚠️ 오류")
                self.connection_status.setStyleSheet("color: orange; font-weight: bold; padding: 5px;")
                self.deployment_mode.setText("모드: 알 수 없음")
                self.deployment_mode.setStyleSheet("color: orange; font-weight: bold; padding: 5px;")
                
        except Exception as e:
            self.connection_status.setText("❌ 연결 안됨")
            self.connection_status.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.deployment_mode.setText("모드: 연결 안됨")
            self.deployment_mode.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
            self.statusBar().showMessage(f"서버 연결 실패")
            
    def detect_deployment_mode(self):
        """배포 모드 감지 및 표시"""
        try:
            import requests
            server_url = self.config_manager.get_server_url()
            
            # 상태 엔드포인트에서 배포 모드 정보 확인
            response = requests.get(f"{server_url}/status", timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # 배포 모드 정보가 있는 경우
                if 'deployment_mode' in data:
                    mode = data['deployment_mode'].upper()
                    self.deployment_mode.setText(f"모드: {mode}")
                    
                    if mode == 'GPU':
                        self.deployment_mode.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
                    else:
                        self.deployment_mode.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                    return
                    
                # GPU 정보로 추측
                gpu_available = data.get('gpu_available', False)
                if gpu_available:
                    mode = "GPU"
                    self.deployment_mode.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
                else:
                    mode = "CPU"
                    self.deployment_mode.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                    
                self.deployment_mode.setText(f"모드: {mode}")
                
            else:
                # 상태 API 실패 시 기본값
                self.deployment_mode.setText("모드: CPU (추정)")
                self.deployment_mode.setStyleSheet("color: gray; font-weight: bold; padding: 5px;")
                
        except Exception as e:
            self.deployment_mode.setText("모드: 감지 실패")
            self.deployment_mode.setStyleSheet("color: orange; font-weight: bold; padding: 5px;")
            
    def show_settings(self):
        """설정 다이얼로그 표시"""
        settings_dialog = SettingsWidget(self.config_manager, self)
        if settings_dialog.exec() == SettingsWidget.DialogCode.Accepted:
            self.load_settings()
            QTimer.singleShot(1000, self.check_server_status)
            
    def setup_menubar(self):
        """메뉴바 설정"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        exit_action = QAction('종료', self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # 도구 메뉴
        tools_menu = menubar.addMenu('도구')
        
        settings_action = QAction('설정', self)
        settings_action.triggered.connect(self.show_settings)
        tools_menu.addAction(settings_action)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu('도움말')
        
        about_action = QAction('정보', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_statusbar(self):
        """상태바 설정"""
        self.statusBar().showMessage("준비")
        
    def show_about(self):
        """정보 다이얼로그 표시"""
        about_text = '''
        <h2>RefClient v0.1.12</h2>
        <p>RefServer GUI 테스트 클라이언트</p>
        <p>RefServer의 모든 기능을 사용자 친화적인 GUI로 제공합니다.</p>
        <br>
        <p><b>주요 기능:</b></p>
        <ul>
        <li>📁 <b>파일 업로드</b>: PDF 파일 업로드 및 처리 테스트</li>
        <li>🔍 <b>서버 상태</b>: 서버 및 서비스 상태 점검</li>
        <li>⚙️ <b>관리 기능</b>: 관리자 기능 및 시스템 관리</li>
        </ul>
        <br>
        <p>개발: RefServer Team</p>
        '''
        
        QMessageBox.about(self, "RefClient 정보", about_text)
        
    def closeEvent(self, event):
        """애플리케이션 종료 시 처리"""
        # 모든 탭의 실행 중인 작업 확인
        running_tasks = []
        
        if hasattr(self.file_upload_tab, 'upload_worker') and self.file_upload_tab.upload_worker and self.file_upload_tab.upload_worker.isRunning():
            running_tasks.append("파일 업로드")
            
        if hasattr(self.server_status_tab, 'status_worker') and self.server_status_tab.status_worker and self.server_status_tab.status_worker.isRunning():
            running_tasks.append("서버 상태 테스트")
            
        if hasattr(self.admin_functions_tab, 'admin_worker') and self.admin_functions_tab.admin_worker and self.admin_functions_tab.admin_worker.isRunning():
            running_tasks.append("관리자 기능 테스트")
        
        if running_tasks:
            reply = QMessageBox.question(
                self, '종료 확인',
                f'다음 작업이 실행 중입니다: {", ".join(running_tasks)}\n정말 종료하시겠습니까?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 모든 실행 중인 작업 중지
                if hasattr(self.file_upload_tab, 'upload_worker') and self.file_upload_tab.upload_worker:
                    self.file_upload_tab.upload_worker.stop()
                if hasattr(self.server_status_tab, 'status_worker') and self.server_status_tab.status_worker:
                    self.server_status_tab.status_worker.stop()
                if hasattr(self.admin_functions_tab, 'admin_worker') and self.admin_functions_tab.admin_worker:
                    self.admin_functions_tab.admin_worker.stop()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()




def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    app.setApplicationName("RefClient")
    app.setApplicationVersion("0.1.12")
    
    # 애플리케이션 스타일 설정
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f0f0f0;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #cccccc;
            border-radius: 5px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #e1e1e1;
            border: 1px solid #adadad;
            border-radius: 3px;
            padding: 5px;
        }
        QPushButton:hover {
            background-color: #d1d1d1;
        }
        QPushButton:pressed {
            background-color: #b1b1b1;
        }
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #808080;
        }
    """)
    
    # 메인 윈도우 생성 및 표시
    window = RefClientMainWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())