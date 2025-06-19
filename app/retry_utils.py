"""
Retry utilities for handling network timeouts and service failures
Implements exponential backoff with jitter for robust error handling
"""

import asyncio
import logging
import time
import random
from typing import Callable, Any, Optional, List, Union
from functools import wraps

logger = logging.getLogger(__name__)

class RetryError(Exception):
    """Exception raised when all retry attempts fail"""
    
    def __init__(self, message: str, attempts: int, last_error: Exception):
        self.message = message
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(f"{message} (after {attempts} attempts): {last_error}")

class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
        retriable_exceptions: Optional[List[type]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
        self.retriable_exceptions = retriable_exceptions or [
            ConnectionError,
            TimeoutError,
            OSError,
            asyncio.TimeoutError
        ]

def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """Calculate delay for exponential backoff with jitter"""
    delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # Add random jitter to prevent thundering herd
        jitter_range = delay * 0.1
        delay += random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)

def is_retriable_error(error: Exception, config: RetryConfig) -> bool:
    """Check if an error is retriable based on configuration"""
    return any(isinstance(error, exc_type) for exc_type in config.retriable_exceptions)

async def async_retry(func: Callable, *args, config: RetryConfig = None, **kwargs) -> Any:
    """
    Async retry wrapper with exponential backoff
    
    Args:
        func: Async function to retry
        *args: Function arguments
        config: Retry configuration
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all attempts fail
    """
    if config is None:
        config = RetryConfig()
    
    last_error = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            logger.debug(f"Attempt {attempt}/{config.max_attempts} for {func.__name__}")
            result = await func(*args, **kwargs)
            
            if attempt > 1:
                logger.info(f"Function {func.__name__} succeeded on attempt {attempt}")
            
            return result
            
        except Exception as e:
            last_error = e
            
            if not is_retriable_error(e, config):
                logger.error(f"Non-retriable error in {func.__name__}: {e}")
                raise e
            
            if attempt == config.max_attempts:
                logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
                break
            
            delay = calculate_delay(attempt, config)
            logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
            
            await asyncio.sleep(delay)
    
    raise RetryError(f"Function {func.__name__} failed", config.max_attempts, last_error)

def sync_retry(func: Callable, *args, config: RetryConfig = None, **kwargs) -> Any:
    """
    Sync retry wrapper with exponential backoff
    
    Args:
        func: Function to retry
        *args: Function arguments
        config: Retry configuration
        **kwargs: Function keyword arguments
        
    Returns:
        Function result
        
    Raises:
        RetryError: If all attempts fail
    """
    if config is None:
        config = RetryConfig()
    
    last_error = None
    
    for attempt in range(1, config.max_attempts + 1):
        try:
            logger.debug(f"Attempt {attempt}/{config.max_attempts} for {func.__name__}")
            result = func(*args, **kwargs)
            
            if attempt > 1:
                logger.info(f"Function {func.__name__} succeeded on attempt {attempt}")
            
            return result
            
        except Exception as e:
            last_error = e
            
            if not is_retriable_error(e, config):
                logger.error(f"Non-retriable error in {func.__name__}: {e}")
                raise e
            
            if attempt == config.max_attempts:
                logger.error(f"All {config.max_attempts} attempts failed for {func.__name__}")
                break
            
            delay = calculate_delay(attempt, config)
            logger.warning(f"Attempt {attempt} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s")
            
            time.sleep(delay)
    
    raise RetryError(f"Function {func.__name__} failed", config.max_attempts, last_error)

def retry_on_failure(config: RetryConfig = None):
    """
    Decorator for automatic retry with exponential backoff
    
    Args:
        config: Retry configuration
        
    Usage:
        @retry_on_failure(RetryConfig(max_attempts=5))
        async def network_call():
            # Function that might fail
            pass
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await async_retry(func, *args, config=config, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                return sync_retry(func, *args, config=config, **kwargs)
            return sync_wrapper
    
    return decorator

# Predefined retry configurations for common scenarios
NETWORK_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    backoff_multiplier=2.0,
    jitter=True
)

OLLAMA_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    backoff_multiplier=1.5,
    jitter=True
)

HURIDOCS_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=5.0,
    max_delay=120.0,
    backoff_multiplier=2.0,
    jitter=True
)

class CircuitBreaker:
    """
    Circuit breaker pattern implementation
    Prevents cascading failures by temporarily disabling failing services
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def _can_attempt(self) -> bool:
        """Check if we can attempt the operation"""
        if self.state == "CLOSED":
            return True
        elif self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.reset_timeout:
                self.state = "HALF_OPEN"
                return True
            return False
        else:  # HALF_OPEN
            return True
    
    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
    
    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if not self._can_attempt():
            raise Exception(f"Circuit breaker is OPEN. Service unavailable.")
        
        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e