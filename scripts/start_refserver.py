#!/usr/bin/env python3
"""
RefServer 자동 시작 스크립트
GPU 감지 후 적절한 구성으로 RefServer를 시작합니다.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from scripts.detect_gpu import determine_deployment_mode


def check_docker_compose():
    """Docker Compose 설치 확인"""
    try:
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # Try docker compose (new syntax)
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False


def run_docker_compose(compose_file: str, command: str = "up", additional_args: list = None):
    """Docker Compose 실행"""
    if additional_args is None:
        additional_args = ["--build"]
    
    # Try docker-compose first
    try:
        cmd = ["docker-compose", "-f", compose_file, command] + additional_args
        print(f"🚀 Running: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try docker compose (new syntax)
        try:
            cmd = ["docker", "compose", "-f", compose_file, command] + additional_args
            print(f"🚀 Running: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Docker Compose failed: {e}")
            return False


def check_prerequisites():
    """전제 조건 확인"""
    issues = []
    
    # Docker 확인
    if not check_docker_compose():
        issues.append("Docker Compose가 설치되지 않았거나 실행되지 않습니다.")
    
    # Docker Compose 파일 확인
    compose_files = ["docker-compose.yml", "docker-compose.cpu.yml"]
    for file in compose_files:
        if not os.path.exists(file):
            issues.append(f"Docker Compose 파일이 없습니다: {file}")
    
    return issues


def setup_environment_variables(deployment_info):
    """환경변수 설정"""
    env_vars = {}
    
    if not deployment_info['services']['ollama_llava']:
        env_vars['LLAVA_ENABLED'] = 'false'
    
    if not deployment_info['services']['huridocs']:
        env_vars['HURIDOCS_LAYOUT_URL'] = 'disabled'
    
    if deployment_info['deployment_mode'] == 'cpu':
        env_vars['CPU_ONLY_MODE'] = 'true'
    
    # 환경변수 설정
    for key, value in env_vars.items():
        os.environ[key] = value
        print(f"🔧 환경변수 설정: {key}={value}")
    
    return env_vars


def main():
    """메인 함수"""
    print("🎯 RefServer 자동 시작 스크립트")
    print("=" * 50)
    
    # 전제 조건 확인
    print("🔍 전제 조건 확인...")
    issues = check_prerequisites()
    if issues:
        print("❌ 다음 문제를 해결해주세요:")
        for issue in issues:
            print(f"  • {issue}")
        return 1
    
    # GPU 감지 및 배포 모드 결정
    print("🔍 GPU 감지 및 배포 모드 결정...")
    deployment_info = determine_deployment_mode()
    
    print(f"📊 배포 모드: {deployment_info['deployment_mode'].upper()}")
    print(f"📄 Docker Compose 파일: {deployment_info['compose_file']}")
    print()
    
    # 서비스 상태 출력
    print("🎯 서비스 활성화 상태:")
    for service, enabled in deployment_info['services'].items():
        status = "✅ 활성화" if enabled else "❌ 비활성화"
        print(f"  - {service}: {status}")
    print()
    
    # 권장사항 출력
    if deployment_info['recommendations']:
        print("💡 권장사항:")
        for rec in deployment_info['recommendations']:
            print(f"  • {rec}")
        print()
    
    # 환경변수 설정
    print("🔧 환경변수 설정...")
    env_vars = setup_environment_variables(deployment_info)
    
    # 사용자 확인
    if deployment_info['deployment_mode'] == 'cpu':
        print("⚠️  CPU 전용 모드로 실행됩니다.")
        print("   - OCR 품질 평가 (LLaVA) 비활성화")
        print("   - 레이아웃 분석 (Huridocs) 비활성화")
        print("   ✅ 메타데이터 추출 (Llama 3.2) 정상 작동")
        print("   ✅ 기본 기능은 정상적으로 작동합니다.")
        print()
    
    response = input("계속 진행하시겠습니까? (y/N): ").lower().strip()
    if response not in ['y', 'yes']:
        print("👋 실행을 취소했습니다.")
        return 0
    
    # RefServer 시작
    print("🚀 RefServer 시작...")
    compose_file = deployment_info['compose_file']
    
    success = run_docker_compose(compose_file, "up", ["--build", "-d"])
    
    if success:
        print("✅ RefServer가 성공적으로 시작되었습니다!")
        print()
        print("🌐 접속 정보:")
        print("  - API 서버: http://localhost:8000")
        print("  - 관리자 인터페이스: http://localhost:8000/admin")
        print("  - API 문서: http://localhost:8000/docs")
        print()
        print("📝 로그 확인: docker-compose logs -f")
        print("🛑 중지: docker-compose down")
        return 0
    else:
        print("❌ RefServer 시작에 실패했습니다.")
        return 1


if __name__ == "__main__":
    sys.exit(main())