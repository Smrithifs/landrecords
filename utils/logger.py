"""
Logging configuration and utilities.
Provides structured logging for the application.
"""

import logging
import sys
from typing import Optional
from pathlib import Path
from datetime import datetime


class Logger:
    """Custom logger class for structured logging."""
    
    def __init__(self, name: str, config: dict):
        """
        Initialize logger.
        
        Args:
            name: Logger name
            config: Configuration dictionary
        """
        self.name = name
        self.config = config
        self.logger = logging.getLogger(name)
        self._setup_logger()
    
    def _setup_logger(self) -> None:
        """Configure logger with handlers and formatters."""
        self.logger.setLevel(self.config.get('log_level', 'INFO'))
        
        # Remove existing handlers
        self.logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.config.get('console_level', 'INFO'))
        console_handler.setFormatter(simple_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        log_dir = Path(self.config.get('log_dir', 'logs'))
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(self.config.get('file_level', 'DEBUG'))
        file_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(file_handler)
        
        # Error file handler
        error_file = log_dir / f"{self.name}_errors_{datetime.now().strftime('%Y%m%d')}.log"
        error_handler = logging.FileHandler(error_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        self.logger.addHandler(error_handler)
    
    def debug(self, message: str, extra: Optional[dict] = None) -> None:
        """
        Log debug message.
        
        Args:
            message: Log message
            extra: Additional context data
        """
        if extra:
            message = f"{message} | Context: {extra}"
        self.logger.debug(message)
    
    def info(self, message: str, extra: Optional[dict] = None) -> None:
        """
        Log info message.
        
        Args:
            message: Log message
            extra: Additional context data
        """
        if extra:
            message = f"{message} | Context: {extra}"
        self.logger.info(message)
    
    def warning(self, message: str, extra: Optional[dict] = None) -> None:
        """
        Log warning message.
        
        Args:
            message: Log message
            extra: Additional context data
        """
        if extra:
            message = f"{message} | Context: {extra}"
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False, extra: Optional[dict] = None) -> None:
        """
        Log error message.
        
        Args:
            message: Log message
            exc_info: Include exception info
            extra: Additional context data
        """
        if extra:
            message = f"{message} | Context: {extra}"
        self.logger.error(message, exc_info=exc_info)
    
    def critical(self, message: str, exc_info: bool = False, extra: Optional[dict] = None) -> None:
        """
        Log critical message.
        
        Args:
            message: Log message
            exc_info: Include exception info
            extra: Additional context data
        """
        if extra:
            message = f"{message} | Context: {extra}"
        self.logger.critical(message, exc_info=exc_info)


def get_logger(name: str, config: Optional[dict] = None) -> Logger:
    """
    Get or create logger instance.
    
    Args:
        name: Logger name
        config: Configuration dictionary (uses default if not provided)
        
    Returns:
        Logger instance
    """
    if config is None:
        config = {
            'log_level': 'INFO',
            'console_level': 'INFO',
            'file_level': 'DEBUG',
            'log_dir': 'logs'
        }
    return Logger(name, config)


# Default logger instance
default_logger: Optional[Logger] = None


def setup_default_logging(config: dict) -> None:
    """
    Setup default logging configuration.
    
    Args:
        config: Configuration dictionary
    """
    global default_logger
    default_logger = get_logger('land_records', config)


def get_default_logger() -> Logger:
    """
    Get default logger instance.
    
    Returns:
        Default logger instance
    """
    global default_logger
    if default_logger is None:
        default_logger = get_logger('land_records')
    return default_logger
