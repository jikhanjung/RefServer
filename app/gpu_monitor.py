"""
GPU Memory Monitoring for Ollama and other services
"""

import logging
import subprocess
import re
import requests
from typing import Dict, Optional, List, Tuple
import json

logger = logging.getLogger(__name__)


class GPUMonitor:
    """Monitor GPU memory usage and Ollama status"""
    
    def __init__(self):
        self.ollama_host = "http://localhost:11434"
    
    def get_gpu_memory_info(self) -> Dict:
        """Get GPU memory information using nvidia-smi"""
        try:
            # Run nvidia-smi command
            result = subprocess.run([
                'nvidia-smi', '--query-gpu=index,name,memory.total,memory.used,memory.free,utilization.gpu',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                logger.warning("nvidia-smi not available or failed")
                return {"available": False, "error": "nvidia-smi not available"}
            
            gpus = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 6:
                        gpus.append({
                            "index": int(parts[0]),
                            "name": parts[1],
                            "total_memory": int(parts[2]),  # MB
                            "used_memory": int(parts[3]),   # MB
                            "free_memory": int(parts[4]),   # MB
                            "utilization": int(parts[5])    # %
                        })
            
            return {
                "available": True,
                "gpus": gpus,
                "total_gpus": len(gpus)
            }
            
        except Exception as e:
            logger.error(f"Error getting GPU info: {e}")
            return {"available": False, "error": str(e)}
    
    def get_ollama_status(self) -> Dict:
        """Get Ollama service status and loaded models"""
        try:
            # Check if Ollama is running
            response = requests.get(f"{self.ollama_host}/api/tags", timeout=5)
            
            if response.status_code != 200:
                return {
                    "running": False,
                    "error": f"HTTP {response.status_code}"
                }
            
            # Get loaded models
            models_data = response.json()
            models = models_data.get('models', [])
            
            # Try to get running models (ps command)
            running_models = []
            try:
                ps_response = requests.get(f"{self.ollama_host}/api/ps", timeout=3)
                if ps_response.status_code == 200:
                    ps_data = ps_response.json()
                    running_models = ps_data.get('models', [])
            except:
                pass
            
            return {
                "running": True,
                "total_models": len(models),
                "running_models": len(running_models),
                "models": [
                    {
                        "name": model.get('name', 'unknown'),
                        "size": model.get('size', 0),
                        "modified_at": model.get('modified_at', '')
                    }
                    for model in models
                ],
                "active_models": [
                    {
                        "name": model.get('name', 'unknown'),
                        "size": model.get('size', 0)
                    }
                    for model in running_models
                ]
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "running": False,
                "error": f"Connection failed: {str(e)}"
            }
        except Exception as e:
            return {
                "running": False,
                "error": str(e)
    
    def get_gpu_processes(self) -> List[Dict]:
        """Get processes using GPU"""
        try:
            result = subprocess.run([
                'nvidia-smi', '--query-compute-apps=pid,used_memory,process_name',
                '--format=csv,noheader,nounits'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            processes = []
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 3:
                        processes.append({
                            "pid": int(parts[0]),
                            "memory_usage": int(parts[1]),  # MB
                            "name": parts[2]
                        })
            
            return processes
            
        except Exception as e:
            logger.error(f"Error getting GPU processes: {e}")
            return []
    
    def estimate_ollama_memory_usage(self, ollama_status: Dict) -> int:
        """Estimate Ollama GPU memory usage based on loaded models"""
        if not ollama_status.get("running"):
            return 0
        
        # Rough estimates for common models (in MB)
        model_memory_estimates = {
            "llama3.2": 4000,    # ~4GB for 3B model
            "llama3.2:1b": 1500,  # ~1.5GB for 1B model
            "llama3.2:3b": 4000,  # ~4GB for 3B model
            "llava": 3000,       # ~3GB for vision model
            "llava:7b": 5000,    # ~5GB for 7B vision model
            "llava:13b": 8000,   # ~8GB for 13B vision model
            "codellama": 4000,   # ~4GB
            "mistral": 4000,     # ~4GB
        }
        
        total_estimated = 0
        active_models = ollama_status.get("active_models", [])
        
        for model in active_models:
            model_name = model.get("name", "").lower()
            
            # Try to match model name with estimates
            estimated_memory = 2000  # Default 2GB
            for known_model, memory in model_memory_estimates.items():
                if known_model in model_name:
                    estimated_memory = memory
                    break
            
            total_estimated += estimated_memory
        
        # Add base Ollama overhead (~500MB)
        if active_models:
            total_estimated += 500
        
        return total_estimated
    
    def get_comprehensive_status(self) -> Dict:
        """Get comprehensive GPU and Ollama status"""
        gpu_info = self.get_gpu_memory_info()
        ollama_status = self.get_ollama_status()
        gpu_processes = self.get_gpu_processes()
        
        # Estimate Ollama memory usage
        ollama_memory_estimate = self.estimate_ollama_memory_usage(ollama_status)
        
        # Find Ollama processes in GPU process list
        ollama_processes = []
        for proc in gpu_processes:
            if 'ollama' in proc['name'].lower() or 'llama' in proc['name'].lower():
                ollama_processes.append(proc)
        
        # Calculate actual Ollama memory usage if found
        actual_ollama_memory = sum(proc['memory_usage'] for proc in ollama_processes)
        
        return {
            "gpu": gpu_info,
            "ollama": {
                **ollama_status,
                "estimated_memory_mb": ollama_memory_estimate,
                "actual_memory_mb": actual_ollama_memory if ollama_processes else None,
                "processes": ollama_processes
            },
            "gpu_processes": gpu_processes,
            "summary": {
                "gpu_available": gpu_info.get("available", False),
                "ollama_running": ollama_status.get("running", False),
                "total_gpu_memory": sum(gpu.get("total_memory", 0) for gpu in gpu_info.get("gpus", [])),
                "used_gpu_memory": sum(gpu.get("used_memory", 0) for gpu in gpu_info.get("gpus", [])),
                "free_gpu_memory": sum(gpu.get("free_memory", 0) for gpu in gpu_info.get("gpus", [])),
                "ollama_memory_usage": actual_ollama_memory if ollama_processes else ollama_memory_estimate
            }
        }


# Global instance
_gpu_monitor = None

def get_gpu_monitor() -> GPUMonitor:
    """Get global GPU monitor instance"""
    global _gpu_monitor
    if _gpu_monitor is None:
        _gpu_monitor = GPUMonitor()
    return _gpu_monitor