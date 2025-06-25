"""
테스트 실행 위젯
백그라운드에서 내부 테스트 모듈을 실행하고 결과를 수집
"""

from PyQt6.QtCore import QObject, QThread, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget
import sys
import os
import time
import json
from typing import List, Dict

# 내부 테스트 모듈들 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from test_modules.health_test import HealthTest
from test_modules.core_api_test import CoreApiTest
from test_modules.full_api_test import FullApiTest
from test_modules.admin_test import AdminTest
from test_modules.backup_test import BackupTest


class TestWorker(QObject):
    """테스트 실행 워커 (백그라운드 스레드에서 실행)"""
    
    # 신호들
    test_started = pyqtSignal(str)  # 테스트 시작
    test_progress = pyqtSignal(int)  # 진행률 (0-100)
    test_completed = pyqtSignal(dict)  # 개별 테스트 완료
    all_completed = pyqtSignal(list)  # 모든 테스트 완료
    log_message = pyqtSignal(str, str)  # 로그 메시지 (message, level)
    error_occurred = pyqtSignal(str)  # 에러 발생
    
    def __init__(self, test_categories: List[str], config_manager):
        super().__init__()
        self.test_categories = test_categories
        self.config_manager = config_manager
        self.is_running = False
        self.should_stop = False
        self.results = []
        
        # 테스트 클래스 매핑
        self.test_classes = {
            'ocr_language': {
                'name': '서버 연결성',
                'class': HealthTest,
                'timeout': 60
            },
            'api_core': {
                'name': '핵심 API',
                'class': CoreApiTest,
                'timeout': 300
            },
            'api_full': {
                'name': '전체 API',
                'class': FullApiTest,
                'timeout': 300
            },
            'admin_system': {
                'name': '관리자 시스템',
                'class': AdminTest,
                'timeout': 180
            },
            'backup_system': {
                'name': '백업 시스템',
                'class': BackupTest,
                'timeout': 240
            }
        }
        
    def run_tests(self):
        """테스트 실행"""
        self.is_running = True
        self.should_stop = False
        self.results = []
        
        try:
            total_tests = len(self.test_categories)
            self.log_message.emit(f"총 {total_tests}개 테스트 카테고리 실행 시작", "INFO")
            
            for i, test_category in enumerate(self.test_categories):
                if self.should_stop:
                    self.log_message.emit("테스트 중지 요청됨", "WARNING")
                    break
                    
                # 테스트 시작 신호
                test_info = self.test_classes.get(test_category)
                if not test_info:
                    self.log_message.emit(f"알 수 없는 테스트 카테고리: {test_category}", "ERROR")
                    continue
                    
                test_name = test_info['name']
                self.test_started.emit(test_name)
                self.log_message.emit(f"테스트 시작: {test_name}", "INFO")
                
                # 진행률 업데이트
                progress = int((i / total_tests) * 100)
                self.test_progress.emit(progress)
                
                # 테스트 실행
                start_time = time.time()
                result = self.run_single_test(test_category, test_info)
                duration = time.time() - start_time
                
                result['duration'] = duration
                result['category'] = test_name
                
                self.results.append(result)
                self.test_completed.emit(result)
                
                # 결과 로깅
                if result['success']:
                    self.log_message.emit(f"테스트 완료: {test_name} - 성공 ({duration:.1f}초)", "PASS")
                else:
                    self.log_message.emit(f"테스트 완료: {test_name} - 실패 ({duration:.1f}초)", "FAIL")
                    self.log_message.emit(f"  오류: {result.get('error', 'Unknown error')}", "ERROR")
                    
            # 모든 테스트 완료
            final_progress = 100
            self.test_progress.emit(final_progress)
            
            # 최종 결과 요약
            total = len(self.results)
            passed = sum(1 for r in self.results if r['success'])
            failed = total - passed
            
            self.log_message.emit(f"모든 테스트 완료: {passed}/{total} 성공", "INFO")
            self.all_completed.emit(self.results)
            
        except Exception as e:
            self.error_occurred.emit(f"테스트 실행 중 오류: {str(e)}")
            self.log_message.emit(f"테스트 실행 중 오류: {str(e)}", "ERROR")
        finally:
            self.is_running = False
            
    def run_single_test(self, test_category: str, test_info: dict) -> dict:
        """단일 테스트 실행 - 내부 테스트 클래스 사용"""
        result = {
            'name': test_info['name'],
            'success': False,
            'error': None,
            'output': '',
            'details': {}
        }
        
        try:
            # 테스트 클래스 인스턴스 생성
            test_class = test_info['class']
            test_instance = test_class(self.config_manager)
            
            # 테스트 인스턴스의 신호를 연결
            test_instance.log_message.connect(self.log_message.emit)
            test_instance.progress_update.connect(self.test_progress.emit)
            
            self.log_message.emit(f"테스트 인스턴스 생성 완료: {test_info['name']}", "DEBUG")
            
            # 테스트 실행
            test_result = test_instance.run_test()
            
            # 결과 처리
            result.update(test_result)
            
            self.log_message.emit(f"테스트 실행 완료: {test_info['name']}", "DEBUG")
            
            return result
            
        except Exception as e:
            result['error'] = f"테스트 실행 오류: {str(e)}"
            self.log_message.emit(f"테스트 오류: {e}", "ERROR")
            
        return result
        
    def parse_test_output(self, test_category: str, output_lines: List[str]) -> dict:
        """테스트 출력 파싱하여 상세 정보 추출"""
        details = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'success_rate': 0.0
        }
        
        try:
            # 각 테스트별 출력 패턴 분석
            for line in output_lines:
                line_lower = line.lower()
                
                # 성공/실패 카운트 찾기
                if 'passed:' in line_lower and 'failed:' in line_lower:
                    # "Passed: 15 ✅ Failed: 3 ❌" 형태
                    import re
                    match = re.search(r'passed:\s*(\d+).*failed:\s*(\d+)', line_lower)
                    if match:
                        details['passed_tests'] = int(match.group(1))
                        details['failed_tests'] = int(match.group(2))
                        details['total_tests'] = details['passed_tests'] + details['failed_tests']
                        
                # 성공률 찾기
                elif 'success rate:' in line_lower:
                    # "Success rate: 83.3%" 형태
                    import re
                    match = re.search(r'success rate:\s*(\d+\.?\d*)%', line_lower)
                    if match:
                        details['success_rate'] = float(match.group(1))
                        
                # 총 테스트 수 찾기
                elif 'total tests:' in line_lower:
                    import re
                    match = re.search(r'total tests:\s*(\d+)', line_lower)
                    if match:
                        details['total_tests'] = int(match.group(1))
                        
        except Exception as e:
            self.log_message.emit(f"출력 파싱 오류: {str(e)}", "DEBUG")
            
        return details
        
    def stop(self):
        """테스트 중지"""
        self.should_stop = True


class TestRunnerWidget(QObject):
    """테스트 실행 관리 위젯"""
    
    # 신호들
    test_started = pyqtSignal(str)
    test_progress = pyqtSignal(int)
    test_completed = pyqtSignal(dict)
    all_completed = pyqtSignal(list)
    log_message = pyqtSignal(str, str)
    
    def __init__(self, test_categories: List[str], config_manager, parent=None):
        super().__init__(parent)
        self.test_categories = test_categories
        self.config_manager = config_manager
        self.worker = None
        self.worker_thread = None
        self.results = []
        
    def start_tests(self):
        """테스트 시작"""
        if self.worker_thread and self.worker_thread.isRunning():
            self.log_message.emit("이미 테스트가 실행 중입니다", "WARNING")
            return
            
        # 워커 스레드 생성
        self.worker_thread = QThread()
        self.worker = TestWorker(self.test_categories, self.config_manager)
        self.worker.moveToThread(self.worker_thread)
        
        # 신호 연결
        self.worker_thread.started.connect(self.worker.run_tests)
        self.worker.test_started.connect(self.test_started.emit)
        self.worker.test_progress.connect(self.test_progress.emit)
        self.worker.test_completed.connect(self.test_completed.emit)
        self.worker.all_completed.connect(self.on_all_completed)
        self.worker.log_message.connect(self.log_message.emit)
        self.worker.error_occurred.connect(self.on_error_occurred)
        
        # 스레드 시작
        self.worker_thread.start()
        
    def stop_tests(self):
        """테스트 중지"""
        if self.worker:
            self.worker.stop()
            
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait(5000)  # 5초 대기
            
    def on_all_completed(self, results: List[dict]):
        """모든 테스트 완료 처리"""
        self.results = results
        self.all_completed.emit(results)
        
        # 스레드 정리
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            
    def on_error_occurred(self, error_message: str):
        """에러 발생 처리"""
        self.log_message.emit(error_message, "ERROR")
        
        # 스레드 정리
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            
    def is_running(self) -> bool:
        """실행 중인지 확인"""
        return self.worker_thread and self.worker_thread.isRunning()
        
    def get_results(self) -> List[dict]:
        """결과 반환"""
        return self.results
        
    def get_summary(self) -> dict:
        """결과 요약 반환"""
        if not self.results:
            return {
                'total_tests': 0,
                'passed_tests': 0,
                'failed_tests': 0,
                'success_rate': 0.0
            }
            
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed
        success_rate = (passed / total * 100) if total > 0 else 0.0
        
        return {
            'total_tests': total,
            'passed_tests': passed,
            'failed_tests': failed,
            'success_rate': success_rate
        }