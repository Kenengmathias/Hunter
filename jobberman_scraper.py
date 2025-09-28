import requests
from bs4 import BeautifulSoup
import time
import random
import logging
from urllib.parse import urlencode, urljoin
from typing import List, Dict, Optional
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager

logger = logging.getLogger(__name__)

class JobbermanScraper:
    def __init__(self, proxy_manager: ProxyManager, user_agent_manager: UserAgentManager):
        self.proxy_manager = proxy_manager
        self.ua_manager = user_agent_manager
        self.base_url = 'https://www.jobberman.com'
        self.session = requests.Session()
    
    def search_jobs(self, keywords: str, location: str = '', job_type: str = '', 
                   max_results: int = 10) -> List[Dict]:
        """Search jobs on Jobberman with updated URL structure"""
        jobs = []
        try:
            # Updated Jobberman URL patterns (2025)
            search_urls = [
                # Try different URL structures that might work
                f"{self.base_url}/search?q={keywords}",
                f"{self.base_url}/jobs?search={keywords}",
                f"{self.base_url}/find-jobs?keywords={keywords}",
                f"{self.base_url}/job-search?query={keywords}",
                # Legacy patterns
                f"{self.base_url}/jobs?" + urlencode({'q': keywords, 'location': location}) if location else f"{self.base_url}/jobs?" + urlencode({'q': keywords})
            ]
            
            logger.info(f"Searching Jobberman for: {keywords} in {location}")
            
            # Try each URL pattern
            for search_url in search_urls:
                logger.debug(f"Trying URL: {search_url}")
                html_content = self._fetch_page(search_url)
                
                if html_content and 'blocked' not in html_content.lower():
                    jobs = self._parse_jobs(html_content, max_results)
                    if jobs:
                        logger.info(f"Success with URL: {search_url}")
                        break
                    else:
                        # Even if no jobs found, if we got valid HTML, try to parse it
                        if len(html_content) > 1000:  # Got substantial content
                            jobs = self._parse_jobs_flexible(html_content, max_results)
                            if jobs:
                                logger.info(f"Found jobs with flexible parsing")
                                break
                                
        except Exception as e:
            logger.error(f"Error scraping Jobberman: {str(e)}")
        
        logger.info(f"Jobberman scraper found {len(jobs)} jobs")
        return jobs
    
    def _fetch_page(self, url: str, max_retries: int = 2) -> Optional[str]:
        """Simplified page fetching with better error handling"""
        for attempt in range(max_retries):
            try:
                # Use proxy if available, otherwise go direct
                proxy = None
                if self.proxy_manager.proxies:
                    # Test and get a working proxy
                    for _ in range(3):  # Try up to 3 proxies
                        test_proxy = self.proxy_manager.get_random_proxy()
                        if test_proxy and self.proxy_manager.test_proxy(test_proxy, timeout=5):
                            proxy = test_proxy
                            break
                
                # Simple, clean headers
                headers = {
                    'User-Agent': self.ua_manager.get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                # Random delay
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=15,
                    allow_redirects=True,
                    verify=True
                )
                
                logger.debug(f"Response status: {response.status_code} for {url}")
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 404:
                    logger.warning(f"URL not found (404): {url}")
                    return None  # Don't retry 404s
                elif response.status_code == 410:
                    logger.warning(f"URL gone (410): {url}")
                    return None  # Don't retry 410s
                elif response.status_code in [403, 429]:
                    logger.warning(f"Blocked/Rate limited ({response.status_code}): {url}")
                    time.sleep(random.uniform(5, 10))
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout for {url} - attempt {attempt + 1}")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Connection error for {url}: {str(e)[:100]}")
            except Exception as e:
                logger.warning(f"Request error for {url}: {str(e)[:100]}")
                
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2, 5))
        
        return None
    
    def _parse_jobs(self, html_content: str, max_results: int) -> List[Dict]:
        """Parse jobs from HTML with multiple strategies"""
        jobs = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for common job listing patterns
        job_selectors = [
            # Modern Jobberman selectors
            '[data-test="job-card"]',
            '.job-card',
            '.search-result-item',
            '.job-listing',
            '.job-item',
            # Generic selectors
            '.card[class*="job"]',
            '[class*="job-card"]',
            '[class*="job-item"]',
            '[class*="search-result"]'
        ]
        
        job_cards = []
        for selector in job_selectors:
            job_cards = soup.select(selector)
            if job_cards:
                logger.debug(f"Found {len(job_cards)} cards with: {selector}")
                break
        
        # Fallback: look for any structure that might contain jobs
        if not job_cards:
            job_cards = self._find_job_cards_flexible(soup)
        
        # Parse found cards
        for card in job_cards[:max_results]:
            job_data = self._extract_job_data(card)
            if job_data and self._is_valid_job(job_data):
                jobs.append(job_data)
        
        return jobs
    
    def _parse_jobs_flexible(self, html_content: str, max_results: int) -> List[Dict]:
        """Flexible parsing when standard selectors don't work"""
        jobs = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Look for job-related keywords in the HTML
        job_indicators = ['apply', 'salary', 'company', 'location', 'full-time', 'part-time']
        potential_jobs = []
        
        # Find all divs/articles with job-related content
        all_elements = soup.find_all(['div', 'article', 'section', 'li'])
        
        for element in all_elements:
            text = element.get_text().lower()
            if any(indicator in text for indicator in job_indicators) and len(text) > 50:
                potential_jobs.append(element)
        
        # Try to extract job data from potential elements
        for element in potential_jobs[:max_results * 2]:  # Check more elements
            job_data = self._extract_job_data_flexible(element)
            if job_data and self._is_valid_job(job_data):
                jobs.append(job_data)
                if len(jobs) >= max_results:
                    break
        
        return jobs
    
    def _find_job_cards_flexible(self, soup) -> List:
        """Find job cards using flexible patterns"""
        potential_cards = []
        
        # Look for repeated structures (likely job listings)
        all_divs = soup.find_all('div')
        class_counts = {}
        
        # Count occurrences of class names
        for div in all_divs:
            classes = div.get('class', [])
            for cls in classes:
                if len(cls) > 3:  # Skip very short class names
                    class_counts[cls] = class_counts.get(cls, 0) + 1
        
        # Find classes that appear multiple times (likely job cards)
        repeated_classes = [cls for cls, count in class_counts.items() if count >= 3 and count <= 50]
        
        # Get elements with these repeated classes
        for cls in repeated_classes[:5]:  # Limit to top 5 candidates
            elements = soup.find_all(class_=cls)
            if elements and len(elements) >= 3:
                potential_cards.extend(elements)
        
        return potential_cards[:20]  # Limit to reasonable number
    
    def _extract_job_data(self, card) -> Optional[Dict]:
        """Extract job data with multiple fallback strategies"""
        try:
            job_data = {
                'title': '',
                'company': '',
                'location': '',
                'salary': '',
                'link': '',
                'description': '',
                'job_type': '',
                'source': 'Jobberman'
            }
            
            # Title extraction with multiple strategies
            title_selectors = [
                'h1 a', 'h2 a', 'h3 a', 'h4 a',
                '.job-title', '.title', '[class*="title"]',
                'a[href*="job"]', 'a[href*="/jobs/"]'
            ]
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    if title_text and len(title_text) > 3:
                        job_data['title'] = title_text
                        # Get link if it's an anchor
                        if title_elem.name == 'a':
                            href = title_elem.get('href')
                            if href:
                                job_data['link'] = urljoin(self.base_url, href)
                        break
            
            # Company extraction
            company_selectors = [
                '.company', '.employer', '[class*="company"]',
                '[class*="employer"]'
            ]
            
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    company_text = company_elem.get_text(strip=True)
                    if company_text and len(company_text) > 1:
                        job_data['company'] = company_text
                        break
            
            # Location extraction
            location_selectors = [
                '.location', '[class*="location"]',
                '.address', '[class*="address"]'
            ]
            
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    if location_text and len(location_text) > 2:
                        job_data['location'] = location_text
                        break
            
            # If no link found yet, try to find any link in the card
            if not job_data['link']:
                link_elem = card.select_one('a[href]')
                if link_elem:
                    href = link_elem.get('href')
                    if href and any(keyword in href for keyword in ['job', 'position', 'vacancy']):
                        job_data['link'] = urljoin(self.base_url, href)
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.debug(f"Error extracting job data: {str(e)}")
            return None
    
    def _extract_job_data_flexible(self, element) -> Optional[Dict]:
        """Flexible job data extraction for unknown structures"""
        try:
            text = element.get_text()
            
            # Look for job title patterns
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            job_data = {
                'title': '',
                'company': '',
                'location': '',
                'salary': '',
                'link': '',
                'description': '',
                'job_type': '',
                'source': 'Jobberman'
            }
            
            # Try to identify title (usually first substantial line)
            for line in lines[:3]:
                if len(line) > 10 and not any(skip in line.lower() for skip in ['apply', 'view', 'click']):
                    job_data['title'] = line
                    break
            
            # Look for links
            link_elem = element.select_one('a[href]')
            if link_elem:
                href = link_elem.get('href')
                if href:
                    job_data['link'] = urljoin(self.base_url, href)
            
            # Simple company/location detection
            for line in lines[1:5]:
                if any(location_word in line.lower() for location_word in ['lagos', 'abuja', 'nigeria', 'remote']):
                    job_data['location'] = line
                elif not job_data['company'] and len(line) < 50:
                    job_data['company'] = line
            
            return job_data if job_data['title'] else None
            
        except Exception:
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Enhanced job validation"""
        if not job_data.get('title'):
            return False
        
        title = job_data['title'].lower()
        
        # Filter out obvious non-jobs
        spam_indicators = [
            'click here', 'visit', 'http', 'www.', 'apply now only',
            'advertisement', 'sponsored', 'banner'
        ]
        
        if any(spam in title for spam in spam_indicators):
            return False
        
        # Title should be reasonable length
        if len(job_data['title']) < 3 or len(job_data['title']) > 200:
            return False
        
        # Should have either company or location
        has_company = bool(job_data.get('company', '').strip())
        has_location = bool(job_data.get('location', '').strip())
        
        return has_company or has_location
