"""
Retry utility for handling transient failures.
Provides retry decorators and functions with exponential backoff.
"""

import asyncio
import functools
from typing import Callable, Optional, Type, Tuple, Any
from datetime import datetime, timedelta


class RetryError(Exception):
    """Exception raised when all retry attempts are exhausted."""
    pass


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback function called on each retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        if on_retry:
                            await on_retry(attempt + 1, e)
                        
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Last error: {str(last_exception)}"
                        ) from last_exception
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            import time
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        if on_retry:
                            on_retry(attempt + 1, e)
                        
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_attempts} attempts. "
                            f"Last error: {str(last_exception)}"
                        ) from last_exception
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


async def retry_async(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
) -> Any:
    """
    Retry an async function with exponential backoff.
    
    Args:
        func: Async function to retry
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch
        on_retry: Optional callback function called on each retry
        
    Returns:
        Result of the function call
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_attempts):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            
            if attempt < max_attempts - 1:
                if on_retry:
                    await on_retry(attempt + 1, e)
                
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                raise RetryError(
                    f"Function failed after {max_attempts} attempts. "
                    f"Last error: {str(last_exception)}"
                ) from last_exception


class RetryTracker:
    """Track retry statistics for monitoring and debugging."""
    
    def __init__(self):
        """Initialize retry tracker."""
        self.attempts: dict = {}
        self.successes: dict = {}
        self.failures: dict = {}
    
    def record_attempt(self, func_name: str) -> None:
        """
        Record a retry attempt.
        
        Args:
            func_name: Name of the function being retried
        """
        if func_name not in self.attempts:
            self.attempts[func_name] = 0
        self.attempts[func_name] += 1
    
    def record_success(self, func_name: str) -> None:
        """
        Record a successful retry.
        
        Args:
            func_name: Name of the function
        """
        if func_name not in self.successes:
            self.successes[func_name] = 0
        self.successes[func_name] += 1
    
    def record_failure(self, func_name: str) -> None:
        """
        Record a failed retry.
        
        Args:
            func_name: Name of the function
        """
        if func_name not in self.failures:
            self.failures[func_name] = 0
        self.failures[func_name] += 1
    
    def get_stats(self, func_name: str) -> dict:
        """
        Get retry statistics for a function.
        
        Args:
            func_name: Name of the function
            
        Returns:
            Dictionary with statistics
        """
        return {
            'attempts': self.attempts.get(func_name, 0),
            'successes': self.successes.get(func_name, 0),
            'failures': self.failures.get(func_name, 0),
            'success_rate': (
                self.successes.get(func_name, 0) / self.attempts.get(func_name, 1)
                if self.attempts.get(func_name, 0) > 0 else 0
            )
        }
    
    def get_all_stats(self) -> dict:
        """
        Get statistics for all tracked functions.
        
        Returns:
            Dictionary with all statistics
        """
        all_funcs = set(self.attempts.keys()) | set(self.successes.keys()) | set(self.failures.keys())
        return {func: self.get_stats(func) for func in all_funcs}


# Global retry tracker
retry_tracker = RetryTracker()
