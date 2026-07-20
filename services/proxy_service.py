"""
Proxy service for managing proxy rotations.
Handles proxy pool management and rotation.
"""

from typing import List, Optional, Dict, Any
import asyncio
import random


class ProxyService:
    """Service for managing proxy rotations."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize proxy service.
        
        Args:
            config: Configuration dictionary containing proxy settings
        """
        self.config = config
        self.proxies: List[Dict[str, Any]] = config.get('proxy_list', [])
        self.current_index = 0
        self.failed_attempts: Dict[str, int] = {}
        self.max_failures = config.get('max_proxy_failures', 3)
    
    def get_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get next available proxy from the pool.
        
        Returns:
            Proxy dictionary or None if no proxies available
        """
        if not self.proxies:
            return None
        
        # Try to find a working proxy
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_index]
            proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
            
            # Check if proxy has failed too many times
            if self.failed_attempts.get(proxy_key, 0) < self.max_failures:
                self.current_index = (self.current_index + 1) % len(self.proxies)
                return proxy
            
            self.current_index = (self.current_index + 1) % len(self.proxies)
        
        return None
    
    def mark_proxy_failed(self, proxy: Dict[str, Any]) -> None:
        """
        Mark a proxy as failed.
        
        Args:
            proxy: Proxy dictionary that failed
        """
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        self.failed_attempts[proxy_key] = self.failed_attempts.get(proxy_key, 0) + 1
    
    def mark_proxy_success(self, proxy: Dict[str, Any]) -> None:
        """
        Mark a proxy as successful (reset failure count).
        
        Args:
            proxy: Proxy dictionary that succeeded
        """
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        self.failed_attempts[proxy_key] = 0
    
    def add_proxy(self, proxy: Dict[str, Any]) -> None:
        """
        Add a new proxy to the pool.
        
        Args:
            proxy: Proxy dictionary with host, port, username, password
        """
        self.proxies.append(proxy)
    
    def remove_proxy(self, proxy: Dict[str, Any]) -> None:
        """
        Remove a proxy from the pool.
        
        Args:
            proxy: Proxy dictionary to remove
        """
        proxy_key = f"{proxy.get('host')}:{proxy.get('port')}"
        self.proxies = [p for p in self.proxies 
                       if f"{p.get('host')}:{p.get('port')}" != proxy_key]
        if proxy_key in self.failed_attempts:
            del self.failed_attempts[proxy_key]
    
    def get_proxy_count(self) -> int:
        """
        Get the number of available proxies.
        
        Returns:
            Number of proxies
        """
        return len(self.proxies)
    
    async def test_proxy(self, proxy: Dict[str, Any], timeout: int = 10) -> bool:
        """
        Test if a proxy is working.
        
        Args:
            proxy: Proxy dictionary to test
            timeout: Timeout in seconds
            
        Returns:
            True if proxy is working, False otherwise
        """
        # Placeholder for proxy testing logic
        await asyncio.sleep(1)
        return True
