"""
Circuit breaker pattern implementation for RefServer services
Prevents unnecessary repeated failed connections to external services
"""

import time
import logging
import threading
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Service disabled due to failures
    HALF_OPEN = "half_open" # Testing if service is back


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 3           # Number of failures before opening
    recovery_timeout: int = 300          # Seconds before attempting recovery (5 minutes)
    success_threshold: int = 2           # Successful calls needed to close circuit
    timeout: int = 10                    # Default timeout for service calls
    manual_override: bool = False        # Manual override from admin


@dataclass
class CircuitStats:
    """Circuit breaker statistics"""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    last_success_time: float = 0
    total_calls: int = 0
    total_failures: int = 0
    last_error: Optional[str] = None
    opened_at: Optional[float] = None
    closed_at: Optional[float] = None


class ServiceCircuitBreaker:
    """Circuit breaker for external service calls"""
    
    def __init__(self, service_name: str, config: CircuitBreakerConfig):
        self.service_name = service_name
        self.config = config
        self.stats = CircuitStats()
        self._lock = threading.RLock()
        
        logger.info(f"Initialized circuit breaker for {service_name}")
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection
        
        Args:
            func: Function to execute
            *args, **kwargs: Arguments for the function
            
        Returns:
            Function result or raises CircuitBreakerOpenError
            
        Raises:
            CircuitBreakerOpenError: When circuit is open
        """
        with self._lock:
            self.stats.total_calls += 1
            
            # Check if circuit is open
            if self._is_circuit_open():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN for {self.service_name}. "
                    f"Last error: {self.stats.last_error}"
                )
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                self._on_success()
                return result
                
            except Exception as e:
                self._on_failure(str(e))
                raise
    
    def _is_circuit_open(self) -> bool:
        """Check if circuit should be open"""
        # Manual override takes precedence
        if self.config.manual_override:
            return True
            
        if self.stats.state == CircuitState.CLOSED:
            return False
            
        elif self.stats.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self.stats.last_failure_time >= self.config.recovery_timeout:
                self.stats.state = CircuitState.HALF_OPEN
                self.stats.success_count = 0
                logger.info(f"Circuit breaker for {self.service_name} entering HALF_OPEN state")
                return False
            return True
            
        elif self.stats.state == CircuitState.HALF_OPEN:
            return False
            
        return False
    
    def _on_success(self):
        """Handle successful call"""
        with self._lock:
            self.stats.success_count += 1
            self.stats.last_success_time = time.time()
            
            if self.stats.state == CircuitState.HALF_OPEN:
                if self.stats.success_count >= self.config.success_threshold:
                    self._close_circuit()
            elif self.stats.state == CircuitState.OPEN:
                # Should not happen, but handle it
                self.stats.state = CircuitState.HALF_OPEN
                self.stats.success_count = 1
    
    def _on_failure(self, error_message: str):
        """Handle failed call"""
        with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()
            self.stats.last_error = error_message
            
            if self.stats.state == CircuitState.CLOSED:
                if self.stats.failure_count >= self.config.failure_threshold:
                    self._open_circuit()
            elif self.stats.state == CircuitState.HALF_OPEN:
                # Failed during testing, go back to open
                self._open_circuit()
    
    def _open_circuit(self):
        """Open the circuit"""
        self.stats.state = CircuitState.OPEN
        self.stats.opened_at = time.time()
        self.stats.failure_count = 0  # Reset for next cycle
        logger.warning(f"Circuit breaker OPENED for {self.service_name}. "
                      f"Error: {self.stats.last_error}")
    
    def _close_circuit(self):
        """Close the circuit"""
        self.stats.state = CircuitState.CLOSED
        self.stats.closed_at = time.time()
        self.stats.failure_count = 0
        self.stats.success_count = 0
        logger.info(f"Circuit breaker CLOSED for {self.service_name}")
    
    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        with self._lock:
            return {
                "service_name": self.service_name,
                "state": self.stats.state.value,
                "failure_count": self.stats.failure_count,
                "success_count": self.stats.success_count,
                "total_calls": self.stats.total_calls,
                "total_failures": self.stats.total_failures,
                "last_error": self.stats.last_error,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "opened_at": self.stats.opened_at,
                "closed_at": self.stats.closed_at,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "success_threshold": self.config.success_threshold,
                    "manual_override": self.config.manual_override
                },
                "next_attempt_allowed": self._get_next_attempt_time()
            }
    
    def _get_next_attempt_time(self) -> Optional[float]:
        """Get timestamp when next attempt is allowed"""
        if self.stats.state == CircuitState.OPEN and not self.config.manual_override:
            return self.stats.last_failure_time + self.config.recovery_timeout
        return None
    
    def force_open(self, reason: str = "Manual override"):
        """Manually open the circuit"""
        with self._lock:
            self.config.manual_override = True
            self.stats.state = CircuitState.OPEN
            self.stats.last_error = reason
            self.stats.opened_at = time.time()
            logger.warning(f"Circuit breaker manually OPENED for {self.service_name}: {reason}")
    
    def force_close(self):
        """Manually close the circuit"""
        with self._lock:
            self.config.manual_override = False
            self._close_circuit()
            logger.info(f"Circuit breaker manually CLOSED for {self.service_name}")
    
    def reset_stats(self):
        """Reset all statistics"""
        with self._lock:
            self.stats = CircuitStats()
            self.config.manual_override = False
            logger.info(f"Circuit breaker statistics reset for {self.service_name}")


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class ServiceCircuitBreakerManager:
    """Manager for all service circuit breakers"""
    
    def __init__(self):
        self._breakers: Dict[str, ServiceCircuitBreaker] = {}
        self._lock = threading.RLock()
        
        # Initialize default circuit breakers for known services
        self._initialize_default_breakers()
    
    def _initialize_default_breakers(self):
        """Initialize circuit breakers for known services"""
        services = {
            "ollama_llava": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=300,  # 5 minutes
                success_threshold=2,
                timeout=10
            ),
            "ollama_metadata": CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=300,  # 5 minutes
                success_threshold=2,
                timeout=30
            ),
            "huridocs_layout": CircuitBreakerConfig(
                failure_threshold=2,
                recovery_timeout=180,  # 3 minutes
                success_threshold=1,
                timeout=15
            )
        }
        
        for service_name, config in services.items():
            self._breakers[service_name] = ServiceCircuitBreaker(service_name, config)
    
    def get_breaker(self, service_name: str) -> ServiceCircuitBreaker:
        """Get circuit breaker for a service"""
        with self._lock:
            if service_name not in self._breakers:
                # Create default breaker for unknown service
                config = CircuitBreakerConfig()
                self._breakers[service_name] = ServiceCircuitBreaker(service_name, config)
            
            return self._breakers[service_name]
    
    def get_all_status(self) -> Dict[str, Dict]:
        """Get status of all circuit breakers"""
        with self._lock:
            return {
                name: breaker.get_status() 
                for name, breaker in self._breakers.items()
            }
    
    def force_open_service(self, service_name: str, reason: str = "Manual override"):
        """Manually disable a service"""
        breaker = self.get_breaker(service_name)
        breaker.force_open(reason)
    
    def force_close_service(self, service_name: str):
        """Manually enable a service"""
        breaker = self.get_breaker(service_name)
        breaker.force_close()
    
    def reset_service_stats(self, service_name: str):
        """Reset statistics for a service"""
        breaker = self.get_breaker(service_name)
        breaker.reset_stats()
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if service is available (circuit not open)"""
        try:
            breaker = self.get_breaker(service_name)
            # Try a dummy call to check if circuit would allow it
            breaker.call(lambda: True)
            return True
        except CircuitBreakerOpenError:
            return False
        except Exception:
            # If dummy call fails, circuit will handle it
            return False


# Global circuit breaker manager
_circuit_breaker_manager = None


def get_circuit_breaker_manager() -> ServiceCircuitBreakerManager:
    """Get global circuit breaker manager instance"""
    global _circuit_breaker_manager
    
    if _circuit_breaker_manager is None:
        _circuit_breaker_manager = ServiceCircuitBreakerManager()
    
    return _circuit_breaker_manager


def with_circuit_breaker(service_name: str):
    """Decorator to add circuit breaker to a function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            manager = get_circuit_breaker_manager()
            breaker = manager.get_breaker(service_name)
            return breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator