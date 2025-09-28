import random
import requests
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, proxy_list: List[str] = None):
        """
        Initialize with proxy list in format: 'ip:port:username:password'
        """
        self.proxies = []
        self.working_proxies = []
        self.failed_proxies = []
        self.current_index = 0
        self.last_test_time = 0
        if proxy_list:
            self.load_proxies(proxy_list)
    
    def load_proxies(self, proxy_list: List[str]):
        """Load proxies from list"""
        for proxy_string in proxy_list:
            try:
                parts = proxy_string.strip().split(':')
                if len(parts) >= 2:
                    if len(parts) == 4:  # With auth
                        ip, port, username, password = parts
                        proxy_dict = {
                            'http': f'http://{username}:{password}@{ip}:{port}',
                            'https': f'http://{username}:{password}@{ip}:{port}',
                            'raw': proxy_string.strip()
                        }
                    else:  # Without auth
                        ip, port = parts[:2]
                        proxy_dict = {
                            'http': f'http://{ip}:{port}',
                            'https': f'http://{ip}:{port}',
                            'raw': proxy_string.strip()
                        }
                    self.proxies.append(proxy_dict)
            except Exception as e:
                logger.warning(f"Failed to parse proxy {proxy_string}: {e}")
        
        logger.info(f"Loaded {len(self.proxies)} proxies")
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from working proxies, fallback to all proxies"""
        if not self.proxies:
            return None
        
        # Use working proxies if available
        if self.working_proxies:
            return random.choice(self.working_proxies)
        
        return random.choice(self.proxies)
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        
        proxy_list = self.working_proxies if self.working_proxies else self.proxies
        proxy = proxy_list[self.current_index]
        self.current_index = (self.current_index + 1) % len(proxy_list)
        return proxy
    
    def test_proxy(self, proxy_dict: Dict[str, str], timeout: int = 10) -> bool:
        """Test if proxy is working"""
        try:
            response = requests.get(
                'http://httpbin.org/ip',
                proxies={'http': proxy_dict['http'], 'https': proxy_dict['https']},
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            return response.status_code == 200
        except:
            return False
    
    def get_working_proxy(self, max_attempts: int = 3) -> Optional[Dict[str, str]]:
        """Get a working proxy after testing, with caching"""
        current_time = time.time()
        
        # Re-test proxies every 5 minutes
        if current_time - self.last_test_time > 300:
            self._refresh_working_proxies()
            self.last_test_time = current_time
        
        # Try working proxies first
        if self.working_proxies:
            for _ in range(max_attempts):
                proxy = random.choice(self.working_proxies)
                # Quick test
                if self.test_proxy(proxy, timeout=5):
                    return proxy
                else:
                    # Remove from working list if failed
                    self.working_proxies.remove(proxy)
                    self.failed_proxies.append(proxy)
        
        # Fallback to testing random proxies
        for _ in range(max_attempts):
            proxy = self.get_random_proxy()
            if proxy and self.test_proxy(proxy, timeout=8):
                if proxy not in self.working_proxies:
                    self.working_proxies.append(proxy)
                return proxy
        
        logger.warning("No working proxy found")
        return None
    
    def _refresh_working_proxies(self):
        """Refresh the working proxies list"""
        logger.debug("Refreshing proxy list...")
        self.working_proxies = []
        self.failed_proxies = []
        
        # Test up to 5 proxies to avoid delays
        test_proxies = random.sample(self.proxies, min(5, len(self.proxies)))
        
        for proxy in test_proxies:
            if self.test_proxy(proxy, timeout=5):
                self.working_proxies.append(proxy)
            else:
                self.failed_proxies.append(proxy)
        
        logger.info(f"Proxy refresh: {len(self.working_proxies)} working, {len(self.failed_proxies)} failed")
    
    def get_proxy_stats(self) -> Dict:
        """Get proxy statistics"""
        return {
            'total': len(self.proxies),
            'working': len(self.working_proxies),
            'failed': len(self.failed_proxies)
        }
