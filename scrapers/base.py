"""
Base scraper class for all land record scrapers.
Provides common functionality and interface for specific scrapers.
"""

import random
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, AsyncGenerator, List, Tuple

from playwright.async_api import (
    async_playwright,
    Browser,
    Page,
    BrowserContext,
    Playwright,
    Error as PlaywrightError
)

from utils.logger import get_default_logger
from utils.retry import retry


# Realistic browser user agents for rotation
USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 OPR/105.0.0.0"
]

# Viewport sizes for rotation
VIEWPORTS: List[Tuple[int, int]] = [
    (1280, 800),
    (1366, 768),
    (1440, 900),
    (1920, 1080)
]


class BaseScraper(ABC):
    """
    Production-ready abstract base class for all scrapers.
    
    Features:
    - Async context manager support
    - User-Agent rotation
    - Viewport rotation
    - Proxy integration
    - Cache integration
    - Screenshot capture on errors
    - Comprehensive logging
    - Retry integration
    - Graceful cleanup
    - Strong typing
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        cache_service: Optional[Any] = None,
        proxy_service: Optional[Any] = None,
        captcha_service: Optional[Any] = None
    ) -> None:
        """
        Initialize the base scraper.
        
        Args:
            config: Configuration dictionary
            cache_service: Optional cache service instance
            proxy_service: Optional proxy service instance
            captcha_service: Optional captcha service instance
        """
        self.config: Dict[str, Any] = config
        self.cache_service: Optional[Any] = cache_service
        self.proxy_service: Optional[Any] = proxy_service
        self.captcha_service: Optional[Any] = captcha_service
        
        # Playwright components
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Configuration
        self.headless: bool = config.get('headless', True)
        self.screenshot_dir: Path = Path(config.get('screenshot_dir', 'logs/screenshots'))
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        # Logger
        self.logger = get_default_logger()
        
        # State tracking
        self._is_initialized: bool = False
        self._current_proxy: Optional[Dict[str, Any]] = None
    
    def _get_random_user_agent(self) -> str:
        """
        Get a random user agent from the list.
        
        Returns:
            Random user agent string
        """
        return random.choice(USER_AGENTS)
    
    def _get_random_viewport(self) -> Dict[str, int]:
        """
        Get a random viewport from the list.
        
        Returns:
            Dictionary with width and height
        """
        width, height = random.choice(VIEWPORTS)
        return {'width': width, 'height': height}
    
    def _get_proxy(self) -> Optional[Dict[str, Any]]:
        """
        Get a proxy from the proxy service if configured.
        
        Returns:
            Proxy dictionary or None
        """
        if self.proxy_service:
            proxy = self.proxy_service.get_proxy()
            if proxy:
                self._current_proxy = proxy
                self.logger.debug(f"Using proxy: {proxy.get('host')}:{proxy.get('port')}")
            return proxy
        return None
    
    def _get_proxy_server(self) -> Optional[str]:
        """
        Get proxy server string for Playwright.
        
        Returns:
            Proxy server string or None
        """
        if self._current_proxy:
            return f"http://{self._current_proxy.get('host')}:{self._current_proxy.get('port')}"
        return None
    
    async def get_cached(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        if self.cache_service:
            try:
                return await self.cache_service.get(key)
            except Exception as e:
                self.logger.error(f"Cache get error: {e}")
        return None
    
    async def set_cached(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        if self.cache_service:
            try:
                return await self.cache_service.set(key, value, ttl)
            except Exception as e:
                self.logger.error(f"Cache set error: {e}")
        return False
    
    async def create_page(self) -> Page:
        """
        Create a new page.
        
        Note: Viewport and user_agent are set on the context during initialization
        for newer Playwright versions.
        
        Returns:
            New Page instance
        """
        if not self.context:
            raise RuntimeError("Browser context not initialized")
        
        self.logger.debug("Creating new page...")
        
        page = await self.context.new_page()
        
        return page
    
    async def navigate(self, url: str, wait_until: str = 'networkidle') -> None:
        """
        Navigate to a URL with error handling and logging.
        
        Args:
            url: URL to navigate to
            wait_until: Navigation wait condition
        """
        if not self.page:
            raise RuntimeError("Page not initialized")
        
        self.logger.info(f"Navigating to: {url}")
        
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=self.config.get('page_load_timeout', 60000))
            self.logger.debug(f"Successfully navigated to: {url}")
        except PlaywrightError as e:
            self.logger.error(f"Navigation error for {url}: {e}")
            await self.capture_screenshot(f"nav_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            raise
    
    async def capture_screenshot(self, filename: str) -> Optional[str]:
        """
        Capture a screenshot of the current page.
        
        Args:
            filename: Screenshot filename
            
        Returns:
            Path to screenshot or None if failed
        """
        if not self.page:
            self.logger.warning("Cannot capture screenshot: page not initialized")
            return None
        
        try:
            screenshot_path = self.screenshot_dir / filename
            await self.page.screenshot(path=str(screenshot_path), full_page=True)
            self.logger.debug(f"Screenshot saved to: {screenshot_path}")
            return str(screenshot_path)
        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {e}")
            return None
    
    async def initialize(self) -> None:
        """Initialize browser and page with production-ready setup."""
        if self._is_initialized:
            self.logger.warning("Scraper already initialized")
            return
        
        try:
            self.logger.info("Initializing browser...")
            self.playwright = await async_playwright().start()
            
            launch_options: Dict[str, Any] = {
                'headless': self.headless,
                'args': [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            }
            
            self.browser = await self.playwright.chromium.launch(**launch_options)
            self.logger.info("Browser launched successfully")
            
            # Get proxy before creating context
            self._get_proxy()
            
            self.context = await self.browser.new_context(
                viewport=self._get_random_viewport(),
                user_agent=self._get_random_user_agent(),
                proxy={'server': self._get_proxy_server()} if self._get_proxy_server() else None,
                ignore_https_errors=True,
                java_script_enabled=True
            )
            self.logger.info("Browser context created")
            
            self.page = await self.create_page()
            self.logger.info("Page created successfully")
            
            self._is_initialized = True
            
        except Exception as e:
            self.logger.error(f"Browser initialization failed: {e}", exc_info=True)
            await self.close()
            raise
    
    async def close(self) -> None:
        """Gracefully close all browser resources with logging."""
        if not self._is_initialized:
            return
        
        self.logger.info("Closing browser resources...")
        
        try:
            if self.page:
                await self.page.close()
                self.logger.debug("Page closed")
                self.page = None
        except Exception as e:
            self.logger.error(f"Error closing page: {e}")
        
        try:
            if self.context:
                await self.context.close()
                self.logger.debug("Context closed")
                self.context = None
        except Exception as e:
            self.logger.error(f"Error closing context: {e}")
        
        try:
            if self.browser:
                await self.browser.close()
                self.logger.debug("Browser closed")
                self.browser = None
        except Exception as e:
            self.logger.error(f"Error closing browser: {e}")
        
        try:
            if self.playwright:
                await self.playwright.stop()
                self.logger.debug("Playwright stopped")
                self.playwright = None
        except Exception as e:
            self.logger.error(f"Error stopping playwright: {e}")
        
        # Mark proxy as successful if used
        if self._current_proxy and self.proxy_service:
            self.proxy_service.mark_proxy_success(self._current_proxy)
        
        self._is_initialized = False
        self.logger.info("Browser resources closed successfully")
    
    async def __aenter__(self) -> 'BaseScraper':
        """
        Async context manager entry.
        
        Returns:
            Self for use in async with block
        """
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """
        Async context manager exit with error handling.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if exc_type is not None:
            self.logger.error(f"Exception in context manager: {exc_val}", exc_info=True)
            await self.capture_screenshot(f"error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            
            # Mark proxy as failed if used
            if self._current_proxy and self.proxy_service:
                self.proxy_service.mark_proxy_failed(self._current_proxy)
        
        await self.close()
    
    @abstractmethod
    async def scrape(self, query_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scrape data based on query parameters.
        
        Args:
            query_params: Dictionary containing search parameters
            
        Returns:
            Dictionary containing scraped data
        """
        pass
    
    @abstractmethod
    async def verify_captcha(self) -> bool:
        """
        Verify and handle captcha if present.
        
        Returns:
            True if captcha handled successfully, False otherwise
        """
        pass
    
    @retry(max_attempts=3, delay=2.0, backoff=2.0, exceptions=(PlaywrightError, Exception))
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> bool:
        """
        Wait for a selector to appear on the page with retry logic.
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
            
        Returns:
            True if selector found, False otherwise
        """
        if not self.page:
            return False
        
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            self.logger.debug(f"Selector found: {selector}")
            return True
        except Exception as e:
            self.logger.warning(f"Selector not found: {selector}, error: {e}")
            return False
    
    async def take_screenshot(self, path: str) -> Optional[str]:
        """
        Take a screenshot of the current page.
        
        Args:
            path: Path to save the screenshot
            
        Returns:
            Path to screenshot or None if failed
        """
        return await self.capture_screenshot(Path(path).name)
