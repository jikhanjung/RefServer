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

from widgets.test_runner import TestRunnerWidget
from widgets.log_viewer import LogViewerWidget
from widgets.settings import SettingsWidget
from widgets.dashboard import DashboardWidget
from utils.config_manager import ConfigManager


class RefClientMainWindow(QMainWindow):
    """RefClient 메인 윈도우"""
    
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.test_runner = None
        self.setup_ui()
        self.setup_connections()
        self.load_settings()
        
    def setup_ui(self):
        """UI 초기화"""
        self.setWindowTitle("RefClient - RefServer GUI 테스트 클라이언트 v0.2.0")
        self.setGeometry(100, 100, 1200, 800)
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        
        # 툴바 영역
        toolbar_layout = QHBoxLayout()
        
        # 연결 상태 표시
        self.connection_status = QLabel("연결 안됨")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QLabel("서버 상태:"))
        toolbar_layout.addWidget(self.connection_status)
        
        main_layout.addLayout(toolbar_layout)
        
        # 메인 콘텐츠 영역 (좌우 분할)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # 왼쪽 패널 - 테스트 선택 및 컨트롤
        left_panel = self.create_left_panel()
        main_splitter.addWidget(left_panel)
        
        # 오른쪽 패널 - 결과 및 로그
        right_panel = self.create_right_panel()
        main_splitter.addWidget(right_panel)
        
        # 분할 비율 설정 (1:2)
        main_splitter.setSizes([400, 800])
        main_layout.addWidget(main_splitter)
        
        # 메뉴바 설정
        self.setup_menubar()
        
        # 상태바 설정
        self.setup_statusbar()
        
    def create_left_panel(self):
        """왼쪽 테스트 선택 패널 생성"""
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 테스트 카테고리 그룹
        test_group = QGroupBox("테스트 카테고리")
        test_layout = QVBoxLayout(test_group)
        
        # 테스트 체크박스들
        self.test_checkboxes = {}
        test_categories = [
            ("ocr_language", "언어 감지 OCR", "OCR 하이브리드 언어 감지 시스템 테스트"),
            ("api_core", "핵심 API", "RefServer 핵심 API 기능 테스트"),
            ("api_full", "전체 API", "모든 API 엔드포인트 종합 테스트"),
            ("admin_system", "관리자 시스템", "관리자 인터페이스 및 권한 관리 테스트"),
            ("backup_system", "백업 시스템", "백업, 복구, 일관성 검증 시스템 테스트")
        ]
        
        for key, name, tooltip in test_categories:
            checkbox = QCheckBox(name)
            checkbox.setToolTip(tooltip)
            checkbox.setChecked(True)  # 기본적으로 모든 테스트 선택
            self.test_checkboxes[key] = checkbox
            test_layout.addWidget(checkbox)
        
        left_layout.addWidget(test_group)
        
        # 컨트롤 버튼들
        control_group = QGroupBox("테스트 실행")
        control_layout = QVBoxLayout(control_group)
        
        self.run_all_btn = QPushButton("전체 실행")
        self.run_all_btn.setStyleSheet("font-weight: bold; min-height: 30px;")
        
        self.run_selected_btn = QPushButton("선택 실행")
        self.run_selected_btn.setMinimumHeight(30)
        
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(30)
        
        control_layout.addWidget(self.run_all_btn)
        control_layout.addWidget(self.run_selected_btn)
        control_layout.addWidget(self.stop_btn)
        
        left_layout.addWidget(control_group)
        
        # 설정 및 정보
        info_group = QGroupBox("설정 및 정보")
        info_layout = QVBoxLayout(info_group)
        
        self.settings_btn = QPushButton("서버 설정")
        self.help_btn = QPushButton("도움말")
        
        info_layout.addWidget(self.settings_btn)
        info_layout.addWidget(self.help_btn)
        
        left_layout.addWidget(info_group)
        
        # 여백 추가
        left_layout.addStretch()
        
        return left_widget
        
    def create_right_panel(self):
        """오른쪽 결과 표시 패널 생성"""
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 진행률 표시
        progress_group = QGroupBox("테스트 진행률")
        progress_layout = QVBoxLayout(progress_group)
        
        self.overall_progress = QProgressBar()
        self.overall_progress.setVisible(False)
        
        self.current_test_label = QLabel("대기 중...")
        self.current_test_label.setStyleSheet("font-weight: bold;")
        
        progress_layout.addWidget(self.current_test_label)
        progress_layout.addWidget(self.overall_progress)
        
        right_layout.addWidget(progress_group)
        
        # 탭 위젯 - 결과 및 로그
        self.tab_widget = QTabWidget()
        
        # 대시보드 탭
        self.dashboard_widget = DashboardWidget()
        self.tab_widget.addTab(self.dashboard_widget, "대시보드")
        
        # 테스트 결과 탭
        self.test_results_widget = self.create_test_results_widget()
        self.tab_widget.addTab(self.test_results_widget, "테스트 결과")
        
        # 로그 뷰어 탭
        self.log_viewer = LogViewerWidget()
        self.tab_widget.addTab(self.log_viewer, "상세 로그")
        
        right_layout.addWidget(self.tab_widget)
        
        return right_widget
        
    def create_test_results_widget(self):
        """테스트 결과 테이블 위젯 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 결과 요약
        summary_layout = QHBoxLayout()
        
        self.total_tests_label = QLabel("총 테스트: 0")
        self.passed_tests_label = QLabel("성공: 0")
        self.failed_tests_label = QLabel("실패: 0")
        self.success_rate_label = QLabel("성공률: 0%")
        
        self.passed_tests_label.setStyleSheet("color: green; font-weight: bold;")
        self.failed_tests_label.setStyleSheet("color: red; font-weight: bold;")
        self.success_rate_label.setStyleSheet("font-weight: bold;")
        
        summary_layout.addWidget(self.total_tests_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.passed_tests_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.failed_tests_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.success_rate_label)
        summary_layout.addStretch()
        
        layout.addLayout(summary_layout)
        
        # 테스트 결과 테이블
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels([
            "테스트 카테고리", "테스트명", "상태", "소요시간", "메시지"
        ])
        
        # 테이블 설정
        header = self.results_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        layout.addWidget(self.results_table)
        
        return widget
        
    def setup_menubar(self):
        """메뉴바 설정"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu('파일')
        
        export_action = QAction('결과 내보내기', self)
        export_action.triggered.connect(self.export_results)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
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
        
    def setup_connections(self):
        """신호/슬롯 연결 설정"""
        self.run_all_btn.clicked.connect(self.run_all_tests)
        self.run_selected_btn.clicked.connect(self.run_selected_tests)
        self.stop_btn.clicked.connect(self.stop_tests)
        self.settings_btn.clicked.connect(self.show_settings)
        self.help_btn.clicked.connect(self.show_about)
        
        # 타이머로 주기적 상태 체크
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.check_server_status)
        self.status_timer.start(10000)  # 10초마다
        
        # 초기 상태 체크
        QTimer.singleShot(1000, self.check_server_status)
        
    def load_settings(self):
        """설정 로드"""
        server_url = self.config_manager.get_server_url()
        self.log_viewer.add_log(f"서버 URL: {server_url}", "INFO")
        
    def check_server_status(self):
        """서버 연결 상태 확인"""
        try:
            import requests
            server_url = self.config_manager.get_server_url()
            
            response = requests.get(f"{server_url}/health", timeout=5)
            if response.status_code == 200:
                self.connection_status.setText("연결됨")
                self.connection_status.setStyleSheet("color: green; font-weight: bold;")
                self.statusBar().showMessage("서버 연결 정상")
            else:
                self.connection_status.setText("오류")
                self.connection_status.setStyleSheet("color: orange; font-weight: bold;")
                
        except Exception as e:
            self.connection_status.setText("연결 안됨")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.statusBar().showMessage(f"서버 연결 실패: {str(e)}")
            
    def run_all_tests(self):
        """모든 테스트 실행"""
        # 모든 체크박스 선택
        for checkbox in self.test_checkboxes.values():
            checkbox.setChecked(True)
        self.run_selected_tests()
        
    def run_selected_tests(self):
        """선택된 테스트만 실행"""
        selected_tests = []
        for key, checkbox in self.test_checkboxes.items():
            if checkbox.isChecked():
                selected_tests.append(key)
                
        if not selected_tests:
            QMessageBox.warning(self, "경고", "실행할 테스트를 선택해주세요.")
            return
            
        self.log_viewer.clear_logs()
        self.log_viewer.add_log(f"선택된 테스트: {', '.join(selected_tests)}", "INFO")
        
        # 테스트 러너 시작
        self.test_runner = TestRunnerWidget(selected_tests, self.config_manager)
        self.test_runner.test_started.connect(self.on_test_started)
        self.test_runner.test_progress.connect(self.on_test_progress)
        self.test_runner.test_completed.connect(self.on_test_completed)
        self.test_runner.log_message.connect(self.log_viewer.add_log)
        
        self.test_runner.start_tests()
        
        # UI 상태 업데이트
        self.run_all_btn.setEnabled(False)
        self.run_selected_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.overall_progress.setVisible(True)
        self.statusBar().showMessage("테스트 실행 중...")
        
    def stop_tests(self):
        """테스트 중지"""
        if self.test_runner:
            self.test_runner.stop_tests()
            
        self.on_test_completed()
        self.log_viewer.add_log("테스트가 사용자에 의해 중지되었습니다.", "WARNING")
        
    def on_test_started(self, test_name):
        """테스트 시작 시 호출"""
        self.current_test_label.setText(f"실행 중: {test_name}")
        self.log_viewer.add_log(f"테스트 시작: {test_name}", "INFO")
        
    def on_test_progress(self, progress):
        """테스트 진행률 업데이트"""
        self.overall_progress.setValue(progress)
        
    def on_test_completed(self):
        """모든 테스트 완료 시 호출"""
        self.run_all_btn.setEnabled(True)
        self.run_selected_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.overall_progress.setVisible(False)
        self.current_test_label.setText("완료")
        self.statusBar().showMessage("테스트 완료")
        
        # 결과 업데이트
        if self.test_runner:
            self.update_test_results(self.test_runner.get_results())
            
    def update_test_results(self, results):
        """테스트 결과 테이블 업데이트"""
        if not results:
            return
            
        # 결과 요약 업데이트
        total = len(results)
        passed = sum(1 for r in results if r.get('success', False))
        failed = total - passed
        success_rate = (passed / total * 100) if total > 0 else 0
        
        self.total_tests_label.setText(f"총 테스트: {total}")
        self.passed_tests_label.setText(f"성공: {passed}")
        self.failed_tests_label.setText(f"실패: {failed}")
        self.success_rate_label.setText(f"성공률: {success_rate:.1f}%")
        
        # 테이블 업데이트
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(result.get('category', '')))
            self.results_table.setItem(row, 1, QTableWidgetItem(result.get('name', '')))
            
            # 상태 셀 (색상 적용)
            status_item = QTableWidgetItem("성공" if result.get('success', False) else "실패")
            if result.get('success', False):
                status_item.setBackground(Qt.GlobalColor.green)
            else:
                status_item.setBackground(Qt.GlobalColor.red)
            self.results_table.setItem(row, 2, status_item)
            
            # 소요시간
            duration = result.get('duration', 0)
            self.results_table.setItem(row, 3, QTableWidgetItem(f"{duration:.2f}s"))
            
            # 메시지
            message = result.get('message', '')
            self.results_table.setItem(row, 4, QTableWidgetItem(message))
            
        # 대시보드 업데이트
        self.dashboard_widget.update_statistics({
            'total_tests': total,
            'passed_tests': passed,
            'failed_tests': failed,
            'success_rate': success_rate
        })
        
    def show_settings(self):
        """설정 다이얼로그 표시"""
        settings_dialog = SettingsWidget(self.config_manager, self)
        if settings_dialog.exec() == SettingsWidget.DialogCode.Accepted:
            self.load_settings()
            QTimer.singleShot(1000, self.check_server_status)
            
    def show_about(self):
        """정보 다이얼로그 표시"""
        about_text = """
        <h2>RefClient v0.2.0</h2>
        <p>RefServer GUI 테스트 클라이언트</p>
        <p>RefServer의 모든 API 테스트 기능을 GUI로 제공합니다.</p>
        <br>
        <p><b>주요 기능:</b></p>
        <ul>
        <li>통합 테스트 인터페이스</li>
        <li>실시간 테스트 모니터링</li>
        <li>테스트 결과 시각화</li>
        <li>배치 테스트 관리</li>
        </ul>
        <br>
        <p>개발: RefServer Team</p>
        """
        
        QMessageBox.about(self, "RefClient 정보", about_text)
        
    def export_results(self):
        """테스트 결과 내보내기"""
        # TODO: 구현 예정
        QMessageBox.information(self, "알림", "결과 내보내기 기능은 추후 버전에서 제공됩니다.")
        
    def closeEvent(self, event):
        """애플리케이션 종료 시 처리"""
        if self.test_runner and self.test_runner.is_running():
            reply = QMessageBox.question(
                self, '종료 확인',
                '테스트가 실행 중입니다. 정말 종료하시겠습니까?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.test_runner.stop_tests()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    app.setApplicationName("RefClient")
    app.setApplicationVersion("0.2.0")
    
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