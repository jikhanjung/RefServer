"""
서버 상태 점검 탭
RefServer의 다양한 서비스 상태를 점검하고 모니터링
"""

import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QPushButton, 
    QLabel, QProgressBar, QTextEdit, QTableWidget, QTableWidgetItem, 
    QHeaderView, QCheckBox, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import requests
import json


class ServerStatusWorker(QThread):
    """서버 상태 점검을 담당하는 워커 스레드"""
    
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
        self.is_running = False
        
    def set_tests(self, tests):
        """실행할 테스트 목록 설정"""
        self.tests_to_run = tests
        
    def stop(self):
        """테스트 중지"""
        self.is_running = False
        
    def run(self):
        """서버 상태 테스트 실행"""
        self.is_running = True
        
        server_url = self.config_manager.get_server_url()
        timeout = self.config_manager.get_connection_timeout()
        
        test_methods = {
            'health_check': self._test_health_check,
            'server_status': self._test_server_status,
            'deployment_mode': self._test_deployment_mode,
            'service_availability': self._test_service_availability,
            'api_endpoints': self._test_api_endpoints,
            'performance_stats': self._test_performance_stats,
            'circuit_breakers': self._test_circuit_breakers
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
        
    def _test_health_check(self, server_url, timeout):
        """기본 헬스 체크"""
        start_time = time.time()
        response = requests.get(f"{server_url}/health", timeout=timeout)
        response_time = time.time() - start_time
        
        return {
            'status_code': response.status_code,
            'response_time': round(response_time * 1000, 2),  # ms
            'response': response.json() if response.status_code == 200 else response.text,
            'success': response.status_code == 200
        }
        
    def _test_server_status(self, server_url, timeout):
        """서버 상태 정보"""
        start_time = time.time()
        response = requests.get(f"{server_url}/status", timeout=timeout)
        response_time = time.time() - start_time
        
        result = {
            'status_code': response.status_code,
            'response_time': round(response_time * 1000, 2),
            'success': response.status_code == 200
        }
        
        if response.status_code == 200:
            data = response.json()
            result['response'] = data
            result['deployment_mode'] = data.get('deployment_mode', 'Unknown')
            result['version'] = data.get('version', 'Unknown')
        else:
            result['response'] = response.text
            
        return result
        
    def _test_deployment_mode(self, server_url, timeout):
        """배포 모드 감지"""
        try:
            response = requests.get(f"{server_url}/status", timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                deployment_mode = data.get('deployment_mode', 'Unknown')
                
                services = {
                    'database': data.get('database', False),
                    'quality_assessment': data.get('quality_assessment', False),
                    'layout_analysis': data.get('layout_analysis', False),
                    'metadata_extraction': data.get('metadata_extraction', False)
                }
                
                return {
                    'success': True,
                    'deployment_mode': deployment_mode,
                    'services': services,
                    'gpu_features_available': services['quality_assessment'] and services['layout_analysis']
                }
            else:
                return {'success': False, 'error': f'HTTP {response.status_code}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_service_availability(self, server_url, timeout):
        """서비스 가용성 테스트"""
        services_to_test = [
            ('Database', f"{server_url}/stats"),
            ('Vector DB', f"{server_url}/vector/stats"),
            ('Performance', f"{server_url}/performance/stats"),
            ('Queue', f"{server_url}/queue/status")
        ]
        
        results = {}
        
        for service_name, endpoint in services_to_test:
            try:
                start_time = time.time()
                response = requests.get(endpoint, timeout=min(timeout, 10))
                response_time = time.time() - start_time
                
                results[service_name] = {
                    'available': response.status_code == 200,
                    'status_code': response.status_code,
                    'response_time': round(response_time * 1000, 2)
                }
                
            except Exception as e:
                results[service_name] = {
                    'available': False,
                    'error': str(e),
                    'response_time': timeout * 1000
                }
                
        return {
            'success': True,
            'services': results,
            'total_available': sum(1 for r in results.values() if r.get('available', False))
        }
        
    def _test_api_endpoints(self, server_url, timeout):
        """주요 API 엔드포인트 테스트"""
        endpoints = [
            ('GET', '/health', 'Health Check'),
            ('GET', '/status', 'Service Status'),
            ('GET', '/stats', 'Statistics'),
            ('GET', '/search?q=test', 'Search'),
            ('GET', '/admin/dashboard', 'Admin Dashboard (no auth)'),
        ]
        
        results = {}
        
        for method, endpoint, description in endpoints:
            try:
                start_time = time.time()
                if method == 'GET':
                    response = requests.get(f"{server_url}{endpoint}", timeout=10)
                response_time = time.time() - start_time
                
                # HTTP 상태 코드에 따른 성공 판정
                expected_codes = [200, 401, 403, 302]  # 인증 오류나 리다이렉트도 정상 응답으로 간주
                success = response.status_code in expected_codes
                
                results[description] = {
                    'success': success,
                    'status_code': response.status_code,
                    'response_time': round(response_time * 1000, 2),
                    'endpoint': endpoint
                }
                
            except Exception as e:
                results[description] = {
                    'success': False,
                    'error': str(e),
                    'endpoint': endpoint
                }
                
        return {
            'success': True,
            'endpoints': results,
            'total_success': sum(1 for r in results.values() if r.get('success', False))
        }
        
    def _test_performance_stats(self, server_url, timeout):
        """성능 통계 테스트"""
        try:
            start_time = time.time()
            response = requests.get(f"{server_url}/performance/stats", timeout=timeout)
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'response_time': round(response_time * 1000, 2),
                    'stats': data
                }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    def _test_circuit_breakers(self, server_url, timeout):
        """Circuit Breaker 상태 테스트"""
        try:
            # 먼저 /status에서 circuit_breakers 정보 확인
            response = requests.get(f"{server_url}/status", timeout=timeout)
            
            if response.status_code == 200:
                data = response.json()
                circuit_breakers = data.get('circuit_breakers', {})
                
                if circuit_breakers:
                    # Circuit breaker 정보 분석
                    total_breakers = len(circuit_breakers)
                    open_breakers = sum(1 for cb in circuit_breakers.values() 
                                      if cb.get('state') == 'open')
                    
                    return {
                        'success': True,
                        'circuit_breakers': circuit_breakers,
                        'total_breakers': total_breakers,
                        'open_breakers': open_breakers,
                        'healthy_breakers': total_breakers - open_breakers
                    }
                else:
                    return {
                        'success': True,
                        'circuit_breakers': {},
                        'message': 'No circuit breakers found'
                    }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}


class ServerStatusTab(QWidget):
    """서버 상태 점검 탭"""
    
    def __init__(self, config_manager, log_viewer):
        super().__init__()
        self.config_manager = config_manager
        self.log_viewer = log_viewer
        self.status_worker = None
        self.test_results = {}
        self.setup_ui()
        
        # 자동 새로고침 타이머
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.run_quick_check)
        
    def setup_ui(self):
        """UI 초기화"""
        layout = QVBoxLayout(self)
        
        # 빠른 상태 확인 그룹
        quick_group = QGroupBox("⚡ 빠른 상태 확인")
        quick_layout = QVBoxLayout(quick_group)
        
        # 연결 상태 표시
        status_layout = QHBoxLayout()
        
        self.connection_status = QLabel("연결 상태: 확인 중...")
        self.connection_status.setStyleSheet("font-weight: bold; padding: 5px;")
        status_layout.addWidget(self.connection_status)
        
        self.deployment_mode = QLabel("배포 모드: 감지 중...")
        self.deployment_mode.setStyleSheet("font-weight: bold; padding: 5px;")
        status_layout.addWidget(self.deployment_mode)
        
        status_layout.addStretch()
        
        self.quick_refresh_btn = QPushButton("빠른 확인")
        self.quick_refresh_btn.clicked.connect(self.run_quick_check)
        status_layout.addWidget(self.quick_refresh_btn)
        
        quick_layout.addLayout(status_layout)
        
        # 자동 새로고침 설정
        auto_layout = QHBoxLayout()
        self.auto_refresh_check = QCheckBox("자동 새로고침 (30초)")
        self.auto_refresh_check.toggled.connect(self.toggle_auto_refresh)
        auto_layout.addWidget(self.auto_refresh_check)
        auto_layout.addStretch()
        quick_layout.addLayout(auto_layout)
        
        layout.addWidget(quick_group)
        
        # 상세 테스트 그룹
        detail_group = QGroupBox("🔍 상세 테스트")
        detail_layout = QVBoxLayout(detail_group)
        
        # 테스트 선택
        test_selection_layout = QHBoxLayout()
        
        self.test_checkboxes = {}
        tests = [
            ('health_check', '헬스 체크'),
            ('server_status', '서버 상태'),
            ('deployment_mode', '배포 모드'),
            ('service_availability', '서비스 가용성'),
            ('api_endpoints', 'API 엔드포인트'),
            ('performance_stats', '성능 통계'),
            ('circuit_breakers', 'Circuit Breaker')
        ]
        
        for i, (test_key, test_name) in enumerate(tests):
            checkbox = QCheckBox(test_name)
            checkbox.setChecked(True)
            self.test_checkboxes[test_key] = checkbox
            test_selection_layout.addWidget(checkbox)
            
            if i == 3:  # 줄바꿈
                detail_layout.addLayout(test_selection_layout)
                test_selection_layout = QHBoxLayout()
                
        if test_selection_layout.count() > 0:
            detail_layout.addLayout(test_selection_layout)
        
        # 테스트 컨트롤
        control_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("전체 선택")
        self.select_all_btn.clicked.connect(self.select_all_tests)
        control_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("전체 해제")
        self.deselect_all_btn.clicked.connect(self.deselect_all_tests)
        control_layout.addWidget(self.deselect_all_btn)
        
        control_layout.addStretch()
        
        self.run_tests_btn = QPushButton("선택된 테스트 실행")
        self.run_tests_btn.setStyleSheet("font-weight: bold; min-height: 30px; background-color: #007bff; color: white;")
        self.run_tests_btn.clicked.connect(self.run_selected_tests)
        control_layout.addWidget(self.run_tests_btn)
        
        self.stop_tests_btn = QPushButton("중지")
        self.stop_tests_btn.setStyleSheet("min-height: 30px; background-color: #dc3545; color: white;")
        self.stop_tests_btn.clicked.connect(self.stop_tests)
        self.stop_tests_btn.setEnabled(False)
        control_layout.addWidget(self.stop_tests_btn)
        
        detail_layout.addLayout(control_layout)
        
        # 진행률
        self.progress_label = QLabel("대기 중...")
        detail_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        detail_layout.addWidget(self.progress_bar)
        
        layout.addWidget(detail_group)
        
        # 테스트 결과 그룹
        result_group = QGroupBox("📊 테스트 결과")
        result_layout = QVBoxLayout(result_group)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels([
            "테스트", "상태", "응답시간", "상세정보"
        ])
        
        # 테이블 설정
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        
        result_layout.addWidget(self.result_table)
        
        layout.addWidget(result_group)
        
        # 초기 빠른 확인 실행
        QTimer.singleShot(1000, self.run_quick_check)
        
    def run_quick_check(self):
        """빠른 상태 확인"""
        try:
            server_url = self.config_manager.get_server_url()
            
            # 헬스 체크
            try:
                response = requests.get(f"{server_url}/health", timeout=5)
                if response.status_code == 200:
                    self.connection_status.setText("연결 상태: ✅ 연결됨")
                    self.connection_status.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                else:
                    self.connection_status.setText(f"연결 상태: ⚠️ 오류 (HTTP {response.status_code})")
                    self.connection_status.setStyleSheet("color: orange; font-weight: bold; padding: 5px;")
            except:
                self.connection_status.setText("연결 상태: ❌ 연결 실패")
                self.connection_status.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
                
            # 배포 모드 확인
            try:
                response = requests.get(f"{server_url}/status", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    mode = data.get('deployment_mode', 'Unknown')
                    self.deployment_mode.setText(f"배포 모드: {mode}")
                    
                    if mode == 'GPU':
                        self.deployment_mode.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
                    elif mode == 'CPU':
                        self.deployment_mode.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                    else:
                        self.deployment_mode.setStyleSheet("color: gray; font-weight: bold; padding: 5px;")
                else:
                    self.deployment_mode.setText("배포 모드: 알 수 없음")
                    self.deployment_mode.setStyleSheet("color: gray; font-weight: bold; padding: 5px;")
            except:
                self.deployment_mode.setText("배포 모드: 확인 실패")
                self.deployment_mode.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
                
        except Exception as e:
            self.log_viewer.add_log(f"빠른 상태 확인 오류: {str(e)}", "WARNING")
            
    def toggle_auto_refresh(self, checked):
        """자동 새로고침 토글"""
        if checked:
            self.auto_refresh_timer.start(30000)  # 30초
            self.log_viewer.add_log("자동 새로고침이 활성화되었습니다 (30초 간격)", "INFO")
        else:
            self.auto_refresh_timer.stop()
            self.log_viewer.add_log("자동 새로고침이 비활성화되었습니다", "INFO")
            
    def select_all_tests(self):
        """모든 테스트 선택"""
        for checkbox in self.test_checkboxes.values():
            checkbox.setChecked(True)
            
    def deselect_all_tests(self):
        """모든 테스트 해제"""
        for checkbox in self.test_checkboxes.values():
            checkbox.setChecked(False)
            
    def run_selected_tests(self):
        """선택된 테스트 실행"""
        selected_tests = [
            test_key for test_key, checkbox in self.test_checkboxes.items()
            if checkbox.isChecked()
        ]
        
        if not selected_tests:
            self.log_viewer.add_log("실행할 테스트를 선택해주세요.", "WARNING")
            return
            
        # UI 상태 업데이트
        self.run_tests_btn.setEnabled(False)
        self.stop_tests_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("테스트 준비 중...")
        
        # 결과 초기화
        self.test_results = {}
        self.result_table.setRowCount(0)
        
        # 워커 스레드 시작
        self.status_worker = ServerStatusWorker(self.config_manager)
        self.status_worker.set_tests(selected_tests)
        
        # 시그널 연결
        self.status_worker.test_started.connect(self.on_test_started)
        self.status_worker.test_completed.connect(self.on_test_completed)
        self.status_worker.test_failed.connect(self.on_test_failed)
        self.status_worker.log_message.connect(self.log_viewer.add_log)
        self.status_worker.progress_updated.connect(self.on_progress_updated)
        self.status_worker.finished.connect(self.on_all_tests_finished)
        
        self.status_worker.start()
        
    def stop_tests(self):
        """테스트 중지"""
        if self.status_worker:
            self.status_worker.stop()
            self.log_viewer.add_log("테스트가 사용자에 의해 중지되었습니다.", "WARNING")
            
    def on_test_started(self, test_name):
        """테스트 시작 시 호출"""
        self.progress_label.setText(f"실행 중: {test_name}")
        self.log_viewer.add_log(f"테스트 시작: {test_name}", "INFO")
        
    def on_test_completed(self, test_name, result):
        """테스트 완료 시 호출"""
        self.test_results[test_name] = {
            'success': True,
            'result': result
        }
        self.update_result_table()
        self.log_viewer.add_log(f"테스트 완료: {test_name}", "PASS")
        
    def on_test_failed(self, test_name, error):
        """테스트 실패 시 호출"""
        self.test_results[test_name] = {
            'success': False,
            'error': error
        }
        self.update_result_table()
        self.log_viewer.add_log(f"테스트 실패: {test_name} - {error}", "FAIL")
        
    def on_progress_updated(self, progress):
        """진행률 업데이트"""
        self.progress_bar.setValue(progress)
        
    def on_all_tests_finished(self):
        """모든 테스트 완료 시 호출"""
        self.run_tests_btn.setEnabled(True)
        self.stop_tests_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("완료")
        
        # 결과 요약
        total = len(self.test_results)
        success = sum(1 for r in self.test_results.values() if r['success'])
        self.log_viewer.add_log(f"테스트 완료: {success}/{total} 성공", "INFO")
        
    def update_result_table(self):
        """결과 테이블 업데이트"""
        self.result_table.setRowCount(len(self.test_results))
        
        test_names = {
            'health_check': '헬스 체크',
            'server_status': '서버 상태',
            'deployment_mode': '배포 모드',
            'service_availability': '서비스 가용성',
            'api_endpoints': 'API 엔드포인트',
            'performance_stats': '성능 통계',
            'circuit_breakers': 'Circuit Breaker'
        }
        
        for row, (test_key, test_data) in enumerate(self.test_results.items()):
            # 테스트명
            test_name = test_names.get(test_key, test_key)
            self.result_table.setItem(row, 0, QTableWidgetItem(test_name))
            
            # 상태
            if test_data['success']:
                result = test_data['result']
                if result.get('success', True):
                    status_item = QTableWidgetItem("✅ 성공")
                    status_item.setBackground(QColor(200, 255, 200))
                else:
                    status_item = QTableWidgetItem("⚠️ 부분 성공")
                    status_item.setBackground(QColor(255, 255, 200))
            else:
                status_item = QTableWidgetItem("❌ 실패")
                status_item.setBackground(QColor(255, 200, 200))
            
            self.result_table.setItem(row, 1, status_item)
            
            # 응답시간
            if test_data['success']:
                result = test_data['result']
                response_time = result.get('response_time', 'N/A')
                if isinstance(response_time, (int, float)):
                    self.result_table.setItem(row, 2, QTableWidgetItem(f"{response_time} ms"))
                else:
                    self.result_table.setItem(row, 2, QTableWidgetItem("N/A"))
            else:
                self.result_table.setItem(row, 2, QTableWidgetItem("N/A"))
                
            # 상세정보
            if test_data['success']:
                result = test_data['result']
                detail = self._format_result_detail(test_key, result)
            else:
                detail = f"오류: {test_data['error']}"
                
            self.result_table.setItem(row, 3, QTableWidgetItem(detail))
            
    def _format_result_detail(self, test_key, result):
        """결과 상세정보 포맷"""
        if test_key == 'health_check':
            return f"상태: {result.get('response', {}).get('status', 'Unknown')}"
            
        elif test_key == 'server_status':
            mode = result.get('deployment_mode', 'Unknown')
            version = result.get('version', 'Unknown')
            return f"모드: {mode}, 버전: {version}"
            
        elif test_key == 'deployment_mode':
            mode = result.get('deployment_mode', 'Unknown')
            gpu_available = result.get('gpu_features_available', False)
            return f"모드: {mode}, GPU 기능: {'사용가능' if gpu_available else '사용불가'}"
            
        elif test_key == 'service_availability':
            available = result.get('total_available', 0)
            total = len(result.get('services', {}))
            return f"가용 서비스: {available}/{total}"
            
        elif test_key == 'api_endpoints':
            success = result.get('total_success', 0)
            total = len(result.get('endpoints', {}))
            return f"정상 엔드포인트: {success}/{total}"
            
        elif test_key == 'circuit_breakers':
            total = result.get('total_breakers', 0)
            open_count = result.get('open_breakers', 0)
            return f"Circuit Breaker: {total-open_count}/{total} 정상"
            
        else:
            return str(result.get('success', False))