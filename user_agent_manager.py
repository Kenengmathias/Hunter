import random
from fake_useragent import UserAgent
import logging

logger = logging.getLogger(__name__)

class UserAgentManager:
    def __init__(self):
        try:
            self.ua = UserAgent()
        except Exception as e:
            logger.warning(f"Failed to initialize UserAgent: {e}")
            self.ua = None
        
        # Fallback user agents
        self.fallback_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
    
    def get_random_user_agent(self) -> str:
        """Get a random user agent"""
        try:
            if self.ua:
                return self.ua.random
        except Exception as e:
            logger.warning(f"Error getting user agent from fake_useragent: {e}")
        
        return random.choice(self.fallback_agents)
    
    def get_chrome_user_agent(self) -> str:
        """Get a Chrome user agent"""
        try:
            if self.ua:
                return self.ua.chrome
        except Exception as e:
            logger.warning(f"Error getting Chrome user agent: {e}")
        
        chrome_agents = [ua for ua in self.fallback_agents if 'Chrome' in ua]
        return random.choice(chrome_agents) if chrome_agents else self.fallback_agents[0]
    
    def get_firefox_user_agent(self) -> str:
        """Get a Firefox user agent"""
        try:
            if self.ua:
                return self.ua.firefox
        except Exception as e:
            logger.warning(f"Error getting Firefox user agent: {e}")
        
        firefox_agents = [ua for ua in self.fallback_agents if 'Firefox' in ua]
        return random.choice(firefox_agents) if firefox_agents else self.fallback_agents[-1]
    
    def get_headers(self, referer: str = None) -> dict:
        """Get complete headers with random user agent"""
        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        if referer:
            headers['Referer'] = referer
            
        return headers
