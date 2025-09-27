import random
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class ProxyManager:
    def __init__(self, proxy_list: List[str] = None):
        """
        Initialize with proxy list in format: 'ip:port:username:password'
        """
        self.proxies = []
        self.current_index = 0
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
                            'https': f'http://{username}:{password}@{ip}:{port}'
                        }
                    else:  # Without auth
                        ip, port = parts[:2]
                        proxy_dict = {
                            'http': f'http://{ip}:{port}',
                            'https': f'http://{ip}:{port}'
                        }
                    self.proxies.append(proxy_dict)
            except Exception as e:
                logger.warning(f"Failed to parse proxy {proxy_string}: {e}")
    
    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """Get a random proxy from the list"""
        if not self.proxies:
            return None
        return random.choice(self.proxies)
    
    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy
    
    def test_proxy(self, proxy_dict: Dict[str, str], timeout: int = 10) -> bool:
        """Test if proxy is working"""
        try:
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxy_dict,
                timeout=timeout,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            return response.status_code == 200
        except:
            return False
    
    def get_working_proxy(self, max_attempts: int = 5) -> Optional[Dict[str, str]]:
        """Get a working proxy after testing"""
        for _ in range(max_attempts):
            proxy = self.get_random_proxy()
            if proxy and self.test_proxy(proxy):
                return proxy
        return None
