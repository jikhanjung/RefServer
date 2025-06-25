"""
대시보드 위젯
테스트 통계 및 성과 지표 시각화
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QGridLayout, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette
import datetime


class StatisticCard(QFrame):
    """통계 카드 위젯"""
    
    def __init__(self, title: str, value: str = "0", color: str = "#3498db", parent=None):
        super().__init__(parent)
        self.title = title
        self.color = color
        self.setup_ui()
        self.set_value(value)
        
    def setup_ui(self):
        """UI 초기화"""
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {self.color};
                border-radius: 8px;
                background-color: white;
                margin: 5px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # 제목
        self.title_label = QLabel(self.title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(f"color: {self.color}; font-weight: bold; font-size: 12px;")
        layout.addWidget(self.title_label)
        
        # 값
        self.value_label = QLabel("0")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(self.value_label)
        
        self.setFixedSize(120, 80)
        
    def set_value(self, value: str):
        """값 설정"""
        self.value_label.setText(str(value))
        
    def set_color(self, color: str):
        """색상 변경"""
        self.color = color
        self.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {color};
                border-radius: 8px;
                background-color: white;
                margin: 5px;
            }}
        """)
        self.title_label.setStyleSheet(f"color: {color}; font-weight: bold; font-size: 12px;")


class DashboardWidget(QWidget):
    """대시보드 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.statistics = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'success_rate': 0.0,
            'last_run_time': None,
            'average_duration': 0.0
        }
        self.setup_ui()
        
        # 타이머로 주기적 업데이트
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # 1초마다 업데이트
        
    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 헤더
        header_layout = QHBoxLayout()
        
        title_label = QLabel("테스트 대시보드")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        self.last_update_label = QLabel("마지막 업데이트: -")
        self.last_update_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        header_layout.addWidget(self.last_update_label)
        
        layout.addLayout(header_layout)
        
        # 통계 카드들
        cards_layout = QHBoxLayout()
        
        self.total_card = StatisticCard("총 테스트", "0", "#3498db")
        self.passed_card = StatisticCard("성공", "0", "#27ae60")
        self.failed_card = StatisticCard("실패", "0", "#e74c3c")
        self.rate_card = StatisticCard("성공률", "0%", "#9b59b6")
        
        cards_layout.addWidget(self.total_card)
        cards_layout.addWidget(self.passed_card)
        cards_layout.addWidget(self.failed_card)
        cards_layout.addWidget(self.rate_card)
        cards_layout.addStretch()
        
        layout.addLayout(cards_layout)
        
        # 진행률 표시
        progress_group = QGroupBox("테스트 진행률")
        progress_layout = QVBoxLayout(progress_group)
        
        # 전체 진행률
        overall_layout = QHBoxLayout()
        overall_layout.addWidget(QLabel("전체:"))
        self.overall_progress = QProgressBar()
        self.overall_progress.setTextVisible(True)
        self.overall_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        overall_layout.addWidget(self.overall_progress)
        progress_layout.addLayout(overall_layout)
        
        # 성공률 진행률
        success_layout = QHBoxLayout()
        success_layout.addWidget(QLabel("성공률:"))
        self.success_progress = QProgressBar()
        self.success_progress.setTextVisible(True)
        self.success_progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #27ae60;
                border-radius: 5px;
            }
        """)
        success_layout.addWidget(self.success_progress)
        progress_layout.addLayout(success_layout)
        
        layout.addWidget(progress_group)
        
        # 상세 정보
        details_group = QGroupBox("상세 정보")
        details_layout = QGridLayout(details_group)
        
        # 라벨들
        details_layout.addWidget(QLabel("마지막 실행:"), 0, 0)
        self.last_run_label = QLabel("-")
        details_layout.addWidget(self.last_run_label, 0, 1)
        
        details_layout.addWidget(QLabel("평균 소요시간:"), 1, 0)
        self.avg_duration_label = QLabel("-")
        details_layout.addWidget(self.avg_duration_label, 1, 1)
        
        details_layout.addWidget(QLabel("상태:"), 2, 0)
        self.status_label = QLabel("대기 중")
        self.status_label.setStyleSheet("font-weight: bold;")
        details_layout.addWidget(self.status_label, 2, 1)
        
        layout.addWidget(details_group)
        
        # 여백 추가
        layout.addStretch()
        
    def update_statistics(self, stats: dict):
        """통계 정보 업데이트"""
        self.statistics.update(stats)
        self.statistics['last_run_time'] = datetime.datetime.now()
        self.update_display()
        
    def update_display(self):
        """디스플레이 업데이트"""
        # 통계 카드 업데이트
        self.total_card.set_value(str(self.statistics['total_tests']))
        self.passed_card.set_value(str(self.statistics['passed_tests']))
        self.failed_card.set_value(str(self.statistics['failed_tests']))
        self.rate_card.set_value(f"{self.statistics['success_rate']:.1f}%")
        
        # 진행률 바 업데이트
        total = self.statistics['total_tests']
        if total > 0:
            passed = self.statistics['passed_tests']
            self.overall_progress.setValue(int((passed / total) * 100))
            self.success_progress.setValue(int(self.statistics['success_rate']))
        else:
            self.overall_progress.setValue(0)
            self.success_progress.setValue(0)
            
        # 상세 정보 업데이트
        if self.statistics['last_run_time']:
            last_run_str = self.statistics['last_run_time'].strftime("%Y-%m-%d %H:%M:%S")
            self.last_run_label.setText(last_run_str)
        else:
            self.last_run_label.setText("-")
            
        if self.statistics['average_duration'] > 0:
            self.avg_duration_label.setText(f"{self.statistics['average_duration']:.1f}초")
        else:
            self.avg_duration_label.setText("-")
            
        # 상태 업데이트
        total = self.statistics['total_tests']
        passed = self.statistics['passed_tests']
        failed = self.statistics['failed_tests']
        
        if total == 0:
            self.status_label.setText("대기 중")
            self.status_label.setStyleSheet("color: #7f8c8d; font-weight: bold;")
        elif passed + failed < total:
            self.status_label.setText("실행 중")
            self.status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        elif failed == 0:
            self.status_label.setText("모든 테스트 성공")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        else:
            self.status_label.setText("일부 테스트 실패")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            
        # 마지막 업데이트 시간
        now = datetime.datetime.now()
        self.last_update_label.setText(f"마지막 업데이트: {now.strftime('%H:%M:%S')}")
        
    def set_running_status(self, is_running: bool, current_test: str = ""):
        """실행 상태 설정"""
        if is_running:
            if current_test:
                self.status_label.setText(f"실행 중: {current_test}")
            else:
                self.status_label.setText("실행 중")
            self.status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
        else:
            # 테스트 결과에 따라 상태 결정
            self.update_display()
            
    def reset_statistics(self):
        """통계 초기화"""
        self.statistics = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'success_rate': 0.0,
            'last_run_time': None,
            'average_duration': 0.0
        }
        self.update_display()
        
    def get_summary_text(self) -> str:
        """요약 텍스트 반환"""
        total = self.statistics['total_tests']
        passed = self.statistics['passed_tests']
        failed = self.statistics['failed_tests']
        rate = self.statistics['success_rate']
        
        if total == 0:
            return "아직 실행된 테스트가 없습니다."
            
        summary = f"""테스트 결과 요약:
        
총 테스트: {total}개
성공: {passed}개
실패: {failed}개
성공률: {rate:.1f}%

"""
        
        if self.statistics['last_run_time']:
            last_run = self.statistics['last_run_time'].strftime("%Y-%m-%d %H:%M:%S")
            summary += f"마지막 실행: {last_run}\n"
            
        if self.statistics['average_duration'] > 0:
            summary += f"평균 소요시간: {self.statistics['average_duration']:.1f}초"
            
        return summary