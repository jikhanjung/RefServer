#!/usr/bin/env python3
"""
GPU 감지 스크립트
GPU 사용 가능성을 체크하고 적절한 Docker Compose 설정을 결정합니다.
"""

import subprocess
import sys
import os
import platform
from typing import Dict, Any


def check_nvidia_gpu() -> Dict[str, Any]:
    """
    NVIDIA GPU 사용 가능성 확인
    
    Returns:
        dict: GPU 정보 및 사용 가능성
    """
    result = {
        "available": False,
        "driver_version": None,
        "gpu_count": 0,
        "gpu_names": [],
        "cuda_available": False,
        "docker_runtime": False
    }
    
    try:
        # nvidia-smi 명령어로 GPU 확인
        nvidia_smi_result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if nvidia_smi_result.returncode == 0:
            lines = nvidia_smi_result.stdout.strip().split('\n')
            result["available"] = True
            result["gpu_count"] = len(lines)
            
            for line in lines:
                if line.strip():
                    parts = line.split(', ')
                    if len(parts) >= 2:
                        gpu_name = parts[0].strip()
                        driver_version = parts[1].strip()
                        result["gpu_names"].append(gpu_name)
                        if not result["driver_version"]:
                            result["driver_version"] = driver_version
                            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    # CUDA 사용 가능성 확인
    try:
        import torch
        result["cuda_available"] = torch.cuda.is_available()
    except ImportError:
        # PyTorch가 설치되지 않은 경우 nvidia-ml-py로 확인
        try:
            import pynvml
            pynvml.nvmlInit()
            result["cuda_available"] = True
        except ImportError:
            pass
    
    # Docker GPU 런타임 확인
    try:
        docker_info = subprocess.run(
            ["docker", "info", "--format", "{{.Runtimes}}"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if docker_info.returncode == 0 and "nvidia" in docker_info.stdout:
            result["docker_runtime"] = True
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return result


def check_amd_gpu() -> Dict[str, Any]:
    """
    AMD GPU 사용 가능성 확인 (ROCm)
    
    Returns:
        dict: AMD GPU 정보
    """
    result = {
        "available": False,
        "gpu_count": 0,
        "rocm_available": False
    }
    
    try:
        # rocm-smi 확인
        rocm_result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if rocm_result.returncode == 0:
            result["available"] = True
            # GPU 개수 계산 (간단한 방법)
            gpu_lines = [line for line in rocm_result.stdout.split('\n') if 'GPU' in line]
            result["gpu_count"] = len(gpu_lines)
            result["rocm_available"] = True
            
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass
    
    return result


def get_system_info() -> Dict[str, Any]:
    """
    시스템 정보 수집
    
    Returns:
        dict: 시스템 정보
    """
    return {
        "platform": platform.system(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
        "docker_available": check_docker_available()
    }


def check_docker_available() -> bool:
    """
    Docker 설치 및 실행 상태 확인
    
    Returns:
        bool: Docker 사용 가능 여부
    """
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False


def determine_deployment_mode() -> Dict[str, Any]:
    """
    배포 모드 결정
    
    Returns:
        dict: 배포 설정 정보
    """
    nvidia_info = check_nvidia_gpu()
    amd_info = check_amd_gpu()
    system_info = get_system_info()
    
    # GPU 사용 가능성 종합 판단
    gpu_available = nvidia_info["available"] or amd_info["available"]
    
    # 서비스별 활성화 여부 결정
    services = {
        "ollama_llama": True,  # Llama 3.2는 CPU에서도 실행 가능 (메타데이터 추출용)
        "ollama_llava": gpu_available and nvidia_info["docker_runtime"],  # LLaVA는 GPU 필요 (이미지 처리)
        "huridocs": gpu_available,  # Huridocs는 GPU 가속 권장
        "refserver": True  # RefServer는 항상 실행
    }
    
    # Docker Compose 파일 선택
    if gpu_available:
        compose_file = "docker-compose.yml"
        deployment_mode = "gpu"
    else:
        compose_file = "docker-compose.cpu.yml"
        deployment_mode = "cpu"
    
    return {
        "deployment_mode": deployment_mode,
        "compose_file": compose_file,
        "services": services,
        "nvidia_info": nvidia_info,
        "amd_info": amd_info,
        "system_info": system_info,
        "recommendations": get_recommendations(nvidia_info, amd_info, system_info)
    }


def get_recommendations(nvidia_info: Dict, amd_info: Dict, system_info: Dict) -> list:
    """
    사용자를 위한 권장사항 생성
    
    Returns:
        list: 권장사항 목록
    """
    recommendations = []
    
    if not nvidia_info["available"] and not amd_info["available"]:
        recommendations.append("GPU가 감지되지 않았습니다. CPU 전용 모드로 실행됩니다.")
        recommendations.append("LLaVA (OCR 품질 평가)와 Huridocs (레이아웃 분석) 서비스가 비활성화됩니다.")
        recommendations.append("메타데이터 추출 (Llama 3.2)은 CPU에서 정상 작동합니다.")
        
    elif nvidia_info["available"] and not nvidia_info["docker_runtime"]:
        recommendations.append("NVIDIA GPU가 감지되었지만 Docker GPU 런타임이 설치되지 않았습니다.")
        recommendations.append("nvidia-docker2를 설치하여 GPU 가속을 활용하세요.")
        recommendations.append("현재는 CPU 모드로 실행됩니다 (메타데이터 추출은 정상 작동).")
        
    elif nvidia_info["available"] and nvidia_info["docker_runtime"]:
        recommendations.append(f"NVIDIA GPU가 사용 가능합니다. ({nvidia_info['gpu_count']}개 GPU 감지)")
        recommendations.append("모든 서비스가 GPU 가속으로 실행됩니다.")
        
    if not system_info["docker_available"]:
        recommendations.append("Docker가 설치되지 않았거나 실행되지 않고 있습니다.")
        
    return recommendations


def main():
    """메인 함수"""
    print("🔍 RefServer GPU 감지 및 배포 모드 결정\n")
    
    deployment_info = determine_deployment_mode()
    
    print(f"📊 배포 모드: {deployment_info['deployment_mode'].upper()}")
    print(f"📄 Docker Compose 파일: {deployment_info['compose_file']}")
    print()
    
    print("🎯 서비스 활성화 상태:")
    for service, enabled in deployment_info['services'].items():
        status = "✅ 활성화" if enabled else "❌ 비활성화"
        print(f"  - {service}: {status}")
    print()
    
    print("💡 권장사항:")
    for rec in deployment_info['recommendations']:
        print(f"  • {rec}")
    print()
    
    # 환경변수 설정 제안
    env_vars = []
    if not deployment_info['services']['ollama_llava']:
        env_vars.append("LLAVA_ENABLED=false")
    if not deployment_info['services']['huridocs']:
        env_vars.append("HURIDOCS_LAYOUT_URL=disabled")
    
    if env_vars:
        print("🔧 권장 환경변수:")
        for var in env_vars:
            print(f"  export {var}")
        print()
    
    # 실행 명령어 제안
    print("🚀 실행 명령어:")
    if deployment_info['deployment_mode'] == 'gpu':
        print(f"  docker-compose up --build")
    else:
        print(f"  docker-compose -f {deployment_info['compose_file']} up --build")
    
    return deployment_info


if __name__ == "__main__":
    import json
    deployment_info = main()
    
    # JSON 파일로 결과 저장 (다른 스크립트에서 사용 가능)
    with open('.deployment_info.json', 'w') as f:
        json.dump(deployment_info, f, indent=2)