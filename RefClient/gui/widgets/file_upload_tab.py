"""
파일 업로드 테스트 탭
RefServer의 핵심 기능인 PDF 파일 업로드 및 처리를 테스트
"""

import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QLabel, QProgressBar, QTextEdit, QFileDialog, QTableWidget, 
    QTableWidgetItem, QHeaderView, QMessageBox, QCheckBox, QSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import requests
import json


class FileUploadWorker(QThread):
    """파일 업로드 및 처리를 담당하는 워커 스레드"""
    
    # 시그널 정의
    upload_started = pyqtSignal(str)  # filename
    upload_progress = pyqtSignal(str, int)  # filename, progress
    upload_completed = pyqtSignal(str, dict)  # filename, result
    upload_failed = pyqtSignal(str, str)  # filename, error
    log_message = pyqtSignal(str, str)  # message, level
    
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.files_to_upload = []
        self.is_running = False
        
    def add_files(self, file_paths):
        """업로드할 파일 목록 추가"""
        self.files_to_upload = file_paths
        
    def stop(self):
        """업로드 중지"""
        self.is_running = False
        
    def run(self):
        """파일 업로드 실행"""
        self.is_running = True
        
        server_url = self.config_manager.get_server_url()
        timeout = self.config_manager.get_connection_timeout()
        
        for i, file_path in enumerate(self.files_to_upload):
            if not self.is_running:
                break
                
            filename = os.path.basename(file_path)
            
            try:
                self.upload_started.emit(filename)
                self.log_message.emit(f"업로드 시작: {filename}", "INFO")
                
                # 파일 업로드
                with open(file_path, 'rb') as f:
                    files = {'file': (filename, f, 'application/pdf')}
                    response = requests.post(
                        f"{server_url}/upload",
                        files=files,
                        timeout=timeout
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    job_id = result.get('job_id')
                    
                    self.log_message.emit(f"업로드 성공: {filename} (Job ID: {job_id})", "INFO")
                    
                    # 작업 상태 폴링
                    final_result = self._poll_job_status(server_url, job_id, filename, timeout)
                    self.upload_completed.emit(filename, final_result)
                    
                else:
                    error_msg = f"업로드 실패: HTTP {response.status_code}"
                    self.upload_failed.emit(filename, error_msg)
                    self.log_message.emit(error_msg, "ERROR")
                    
            except Exception as e:
                error_msg = f"업로드 오류: {str(e)}"
                self.upload_failed.emit(filename, error_msg)
                self.log_message.emit(error_msg, "ERROR")
                
            # 다음 파일로 진행
            overall_progress = int((i + 1) / len(self.files_to_upload) * 100)
            self.upload_progress.emit("전체 진행률", overall_progress)
        
        self.is_running = False
        
    def _poll_job_status(self, server_url, job_id, filename, timeout):
        """작업 상태 폴링"""
        start_time = time.time()
        max_wait_time = 300  # 5분 최대 대기
        
        while self.is_running and (time.time() - start_time) < max_wait_time:
            try:
                response = requests.get(f"{server_url}/job/{job_id}", timeout=10)
                
                if response.status_code == 200:
                    job_status = response.json()
                    status = job_status.get('status', 'unknown')
                    progress = job_status.get('progress_percentage', 0)
                    
                    self.upload_progress.emit(filename, progress)
                    self.log_message.emit(f"{filename}: {status} ({progress}%)", "INFO")
                    
                    if status in ['completed', 'failed']:
                        return job_status
                        
                elif response.status_code == 404:
                    self.log_message.emit(f"작업 {job_id}를 찾을 수 없습니다", "WARNING")
                    break
                    
            except Exception as e:
                self.log_message.emit(f"상태 확인 오류: {str(e)}", "WARNING")
                
            time.sleep(2)  # 2초 대기
            
        return {"status": "timeout", "error": "작업 완료 대기 시간 초과"}


class FileUploadTab(QWidget):
    """파일 업로드 테스트 탭"""
    
    def __init__(self, config_manager, log_viewer):
        super().__init__()
        self.config_manager = config_manager
        self.log_viewer = log_viewer
        self.upload_worker = None
        self.setup_ui()
        
    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 파일 선택 그룹
        file_group = QGroupBox("📁 파일 선택")
        file_layout = QVBoxLayout(file_group)
        
        # 파일 선택 버튼들
        button_layout = QHBoxLayout()
        
        self.select_single_btn = QPushButton("단일 파일 선택")
        self.select_single_btn.clicked.connect(self.select_single_file)
        button_layout.addWidget(self.select_single_btn)
        
        self.select_multiple_btn = QPushButton("다중 파일 선택")
        self.select_multiple_btn.clicked.connect(self.select_multiple_files)
        button_layout.addWidget(self.select_multiple_btn)
        
        button_layout.addStretch()
        file_layout.addLayout(button_layout)
        
        # 선택된 파일 목록
        self.file_list_label = QLabel("선택된 파일: 없음")
        self.file_list_label.setWordWrap(True)
        file_layout.addWidget(self.file_list_label)
        
        layout.addWidget(file_group)
        
        # 업로드 설정 그룹
        settings_group = QGroupBox("⚙️ 업로드 설정")
        settings_layout = QHBoxLayout(settings_group)
        
        settings_layout.addWidget(QLabel("동시 업로드 수:"))
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 5)
        self.concurrent_spin.setValue(1)
        settings_layout.addWidget(self.concurrent_spin)
        
        self.auto_refresh_check = QCheckBox("결과 자동 새로고침")
        self.auto_refresh_check.setChecked(True)
        settings_layout.addWidget(self.auto_refresh_check)
        
        settings_layout.addStretch()
        layout.addWidget(settings_group)
        
        # 업로드 컨트롤 그룹
        control_group = QGroupBox("🚀 업로드 실행")
        control_layout = QVBoxLayout(control_group)
        
        # 컨트롤 버튼들
        control_button_layout = QHBoxLayout()
        
        self.upload_btn = QPushButton("업로드 시작")
        self.upload_btn.setStyleSheet("font-weight: bold; min-height: 35px; background-color: #28a745; color: white;")
        self.upload_btn.clicked.connect(self.start_upload)
        self.upload_btn.setEnabled(False)
        control_button_layout.addWidget(self.upload_btn)
        
        self.stop_btn = QPushButton("중지")
        self.stop_btn.setStyleSheet("min-height: 35px; background-color: #dc3545; color: white;")
        self.stop_btn.clicked.connect(self.stop_upload)
        self.stop_btn.setEnabled(False)
        control_button_layout.addWidget(self.stop_btn)
        
        self.clear_btn = QPushButton("결과 지우기")
        self.clear_btn.clicked.connect(self.clear_results)
        control_button_layout.addWidget(self.clear_btn)
        
        control_layout.addLayout(control_button_layout)
        
        # 진행률 표시
        self.progress_label = QLabel("대기 중...")
        control_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)
        
        layout.addWidget(control_group)
        
        # 업로드 결과 그룹
        result_group = QGroupBox("📊 업로드 결과")
        result_layout = QVBoxLayout(result_group)
        
        # 결과 요약
        summary_layout = QHBoxLayout()
        
        self.total_files_label = QLabel("총 파일: 0")
        self.success_files_label = QLabel("성공: 0")
        self.success_files_label.setStyleSheet("color: green; font-weight: bold;")
        self.failed_files_label = QLabel("실패: 0")
        self.failed_files_label.setStyleSheet("color: red; font-weight: bold;")
        
        summary_layout.addWidget(self.total_files_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.success_files_label)
        summary_layout.addWidget(QLabel("|"))
        summary_layout.addWidget(self.failed_files_label)
        summary_layout.addStretch()
        
        result_layout.addLayout(summary_layout)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels([
            "파일명", "상태", "처리 시간", "Job ID", "메시지"
        ])
        
        # 테이블 설정
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        
        result_layout.addWidget(self.result_table)
        
        layout.addWidget(result_group)
        
        # 초기 상태 설정
        self.selected_files = []
        self.upload_results = []
        
    def select_single_file(self):
        """단일 파일 선택"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "PDF 파일 선택",
            "",
            "PDF 파일 (*.pdf);;모든 파일 (*)"
        )
        
        if file_path:
            self.selected_files = [file_path]
            self.update_file_list()
            
    def select_multiple_files(self):
        """다중 파일 선택"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "PDF 파일들 선택",
            "",
            "PDF 파일 (*.pdf);;모든 파일 (*)"
        )
        
        if file_paths:
            self.selected_files = file_paths
            self.update_file_list()
            
    def update_file_list(self):
        """선택된 파일 목록 업데이트"""
        if not self.selected_files:
            self.file_list_label.setText("선택된 파일: 없음")
            self.upload_btn.setEnabled(False)
        else:
            file_names = [os.path.basename(f) for f in self.selected_files]
            if len(file_names) == 1:
                self.file_list_label.setText(f"선택된 파일: {file_names[0]}")
            else:
                self.file_list_label.setText(f"선택된 파일: {len(file_names)}개 파일\n{', '.join(file_names[:3])}" + 
                                           (f" 외 {len(file_names)-3}개" if len(file_names) > 3 else ""))
            self.upload_btn.setEnabled(True)
            
    def start_upload(self):
        """업로드 시작"""
        if not self.selected_files:
            QMessageBox.warning(self, "경고", "업로드할 파일을 선택해주세요.")
            return
            
        # UI 상태 업데이트
        self.upload_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("업로드 준비 중...")
        
        # 결과 초기화
        self.upload_results = []
        self.update_result_summary()
        
        # 워커 스레드 시작
        self.upload_worker = FileUploadWorker(self.config_manager)
        self.upload_worker.add_files(self.selected_files)
        
        # 시그널 연결
        self.upload_worker.upload_started.connect(self.on_upload_started)
        self.upload_worker.upload_progress.connect(self.on_upload_progress)
        self.upload_worker.upload_completed.connect(self.on_upload_completed)
        self.upload_worker.upload_failed.connect(self.on_upload_failed)
        self.upload_worker.log_message.connect(self.log_viewer.add_log)
        self.upload_worker.finished.connect(self.on_all_uploads_finished)
        
        self.upload_worker.start()
        
    def stop_upload(self):
        """업로드 중지"""
        if self.upload_worker:
            self.upload_worker.stop()
            self.log_viewer.add_log("업로드가 사용자에 의해 중지되었습니다.", "WARNING")
            
    def on_upload_started(self, filename):
        """업로드 시작 시 호출"""
        self.progress_label.setText(f"업로드 중: {filename}")
        
    def on_upload_progress(self, filename, progress):
        """업로드 진행률 업데이트"""
        if filename == "전체 진행률":
            self.progress_bar.setValue(progress)
        else:
            self.progress_label.setText(f"처리 중: {filename} ({progress}%)")
            
    def on_upload_completed(self, filename, result):
        """업로드 완료 시 호출"""
        self.upload_results.append({
            'filename': filename,
            'success': True,
            'result': result,
            'message': f"성공 - Job ID: {result.get('job_id', 'N/A')}"
        })
        self.update_result_table()
        self.update_result_summary()
        
    def on_upload_failed(self, filename, error):
        """업로드 실패 시 호출"""
        self.upload_results.append({
            'filename': filename,
            'success': False,
            'error': error,
            'message': f"실패: {error}"
        })
        self.update_result_table()
        self.update_result_summary()
        
    def on_all_uploads_finished(self):
        """모든 업로드 완료 시 호출"""
        self.upload_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("완료")
        
    def update_result_table(self):
        """결과 테이블 업데이트"""
        self.result_table.setRowCount(len(self.upload_results))
        
        for row, result in enumerate(self.upload_results):
            # 파일명
            self.result_table.setItem(row, 0, QTableWidgetItem(result['filename']))
            
            # 상태
            status_item = QTableWidgetItem("성공" if result['success'] else "실패")
            if result['success']:
                status_item.setBackground(Qt.GlobalColor.green)
            else:
                status_item.setBackground(Qt.GlobalColor.red)
            self.result_table.setItem(row, 1, status_item)
            
            # 처리 시간
            if result['success'] and 'result' in result:
                processing_time = result['result'].get('processing_time', 0)
                self.result_table.setItem(row, 2, QTableWidgetItem(f"{processing_time:.2f}s"))
            else:
                self.result_table.setItem(row, 2, QTableWidgetItem("N/A"))
                
            # Job ID
            if result['success'] and 'result' in result:
                job_id = result['result'].get('job_id', 'N/A')
                self.result_table.setItem(row, 3, QTableWidgetItem(str(job_id)))
            else:
                self.result_table.setItem(row, 3, QTableWidgetItem("N/A"))
                
            # 메시지
            self.result_table.setItem(row, 4, QTableWidgetItem(result['message']))
            
    def update_result_summary(self):
        """결과 요약 업데이트"""
        total = len(self.upload_results)
        success = sum(1 for r in self.upload_results if r['success'])
        failed = total - success
        
        self.total_files_label.setText(f"총 파일: {total}")
        self.success_files_label.setText(f"성공: {success}")
        self.failed_files_label.setText(f"실패: {failed}")
        
    def clear_results(self):
        """결과 지우기"""
        self.upload_results = []
        self.result_table.setRowCount(0)
        self.update_result_summary()
        self.log_viewer.add_log("업로드 결과가 지워졌습니다.", "INFO")