"""
로그 뷰어 위젯
실시간 로그 표시 및 관리
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QComboBox, QLabel, QCheckBox,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor, QColor, QTextCharFormat
import datetime
import os


class LogViewerWidget(QWidget):
    """로그 뷰어 위젯"""
    
    # 로그 레벨별 색상
    LOG_COLORS = {
        'DEBUG': QColor(128, 128, 128),    # 회색
        'INFO': QColor(0, 0, 0),           # 검정
        'WARNING': QColor(255, 140, 0),    # 주황
        'ERROR': QColor(255, 0, 0),        # 빨강
        'PASS': QColor(0, 128, 0),         # 초록
        'FAIL': QColor(255, 0, 0),         # 빨강
        'SKIP': QColor(128, 128, 0),       # 올리브
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_buffer = []
        self.max_log_lines = 10000  # 최대 로그 라인 수
        self.auto_scroll = True
        self.current_filter = "ALL"
        self.setup_ui()
        
    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 컨트롤 패널
        control_layout = QHBoxLayout()
        
        # 로그 레벨 필터
        control_layout.addWidget(QLabel("필터:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'PASS', 'FAIL'])
        self.filter_combo.currentTextChanged.connect(self.on_filter_changed)
        control_layout.addWidget(self.filter_combo)
        
        # 자동 스크롤 체크박스
        self.auto_scroll_checkbox = QCheckBox("자동 스크롤")
        self.auto_scroll_checkbox.setChecked(True)
        self.auto_scroll_checkbox.toggled.connect(self.on_auto_scroll_toggled)
        control_layout.addWidget(self.auto_scroll_checkbox)
        
        control_layout.addStretch()
        
        # 버튼들
        self.clear_btn = QPushButton("지우기")
        self.clear_btn.clicked.connect(self.clear_logs)
        control_layout.addWidget(self.clear_btn)
        
        self.save_btn = QPushButton("저장")
        self.save_btn.clicked.connect(self.save_logs)
        control_layout.addWidget(self.save_btn)
        
        layout.addLayout(control_layout)
        
        # 로그 표시 영역
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setFont(self.get_monospace_font())
        
        # 로그 영역 스타일 설정
        self.log_text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #cccccc;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)
        
        layout.addWidget(self.log_text_edit)
        
        # 상태 표시
        status_layout = QHBoxLayout()
        self.log_count_label = QLabel("로그: 0줄")
        status_layout.addWidget(self.log_count_label)
        status_layout.addStretch()
        
        layout.addLayout(status_layout)
        
    def get_monospace_font(self):
        """모노스페이스 폰트 반환"""
        from PyQt6.QtGui import QFont, QFontDatabase
        
        font = QFont()
        
        # 시스템에서 사용 가능한 모노스페이스 폰트 찾기
        monospace_fonts = [
            'Consolas', 'Monaco', 'Menlo', 'DejaVu Sans Mono',
            'Liberation Mono', 'Courier New', 'Courier'
        ]
        
        for font_name in monospace_fonts:
            if QFontDatabase.families().__contains__(font_name):
                font.setFamily(font_name)
                break
        else:
            # 모노스페이스 폰트를 찾지 못한 경우 시스템 기본 고정폭 폰트 사용
            font.setStyleHint(QFont.StyleHint.TypeWriter)
            
        font.setPointSize(9)
        return font
        
    def add_log(self, message: str, level: str = "INFO"):
        """로그 메시지 추가"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'full_text': f"[{timestamp}] {level}: {message}"
        }
        
        self.log_buffer.append(log_entry)
        
        # 버퍼 크기 제한
        if len(self.log_buffer) > self.max_log_lines:
            self.log_buffer.pop(0)
            
        # 필터 조건에 맞는 경우에만 표시
        if self.should_show_log(level):
            self.append_log_to_display(log_entry)
            
        # 로그 카운트 업데이트
        self.update_log_count()
        
    def should_show_log(self, level: str) -> bool:
        """로그가 현재 필터 조건에 맞는지 확인"""
        if self.current_filter == "ALL":
            return True
        return level == self.current_filter
        
    def append_log_to_display(self, log_entry: dict):
        """로그를 디스플레이에 추가"""
        cursor = self.log_text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # 로그 레벨에 따른 색상 설정
        format = QTextCharFormat()
        color = self.LOG_COLORS.get(log_entry['level'], QColor(255, 255, 255))
        format.setForeground(color)
        
        cursor.setCharFormat(format)
        cursor.insertText(log_entry['full_text'] + '\n')
        
        # 자동 스크롤
        if self.auto_scroll:
            self.log_text_edit.ensureCursorVisible()
            
    def clear_logs(self):
        """로그 지우기"""
        self.log_buffer.clear()
        self.log_text_edit.clear()
        self.update_log_count()
        
    def save_logs(self):
        """로그를 파일로 저장"""
        if not self.log_buffer:
            QMessageBox.information(self, "알림", "저장할 로그가 없습니다.")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"refclient_logs_{timestamp}.txt"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "로그 저장", default_filename,
            "텍스트 파일 (*.txt);;모든 파일 (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"RefClient 로그 - {datetime.datetime.now()}\n")
                    f.write("=" * 60 + "\n\n")
                    
                    for log_entry in self.log_buffer:
                        f.write(log_entry['full_text'] + '\n')
                        
                QMessageBox.information(self, "성공", f"로그가 저장되었습니다:\n{file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"로그 저장 실패:\n{str(e)}")
                
    def on_filter_changed(self, filter_text: str):
        """필터 변경 처리"""
        self.current_filter = filter_text
        self.refresh_display()
        
    def on_auto_scroll_toggled(self, checked: bool):
        """자동 스크롤 토글"""
        self.auto_scroll = checked
        
    def refresh_display(self):
        """필터에 따라 디스플레이 새로고침"""
        self.log_text_edit.clear()
        
        for log_entry in self.log_buffer:
            if self.should_show_log(log_entry['level']):
                self.append_log_to_display(log_entry)
                
    def update_log_count(self):
        """로그 카운트 업데이트"""
        total_logs = len(self.log_buffer)
        
        if self.current_filter == "ALL":
            displayed_logs = total_logs
        else:
            displayed_logs = sum(1 for log in self.log_buffer 
                               if log['level'] == self.current_filter)
            
        if self.current_filter == "ALL":
            self.log_count_label.setText(f"로그: {total_logs}줄")
        else:
            self.log_count_label.setText(f"로그: {displayed_logs}/{total_logs}줄 ({self.current_filter})")
            
    def get_log_stats(self) -> dict:
        """로그 통계 반환"""
        stats = {}
        for log_entry in self.log_buffer:
            level = log_entry['level']
            stats[level] = stats.get(level, 0) + 1
        return stats
        
    def export_filtered_logs(self, levels: list) -> str:
        """특정 레벨의 로그만 필터링하여 반환"""
        filtered_logs = []
        for log_entry in self.log_buffer:
            if log_entry['level'] in levels:
                filtered_logs.append(log_entry['full_text'])
        return '\n'.join(filtered_logs)