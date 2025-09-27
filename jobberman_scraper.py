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
        """Search jobs on Jobberman with improved selectors"""
        jobs = []
        try:
            # Build search URL - Jobberman uses different URL structure
            search_params = {
                'q': keywords,
            }
            
            # Handle Nigerian locations better
            if location:
                nigerian_locations = {
                    'lagos': 'Lagos',
                    'abuja': 'Abuja',
                    'calabar': 'Calabar',
                    'port harcourt': 'Port Harcourt',
                    'kano': 'Kano',
                    'ibadan': 'Ibadan',
                    'nigeria': 'Nigeria'
                }
                location_formatted = nigerian_locations.get(location.lower(), location)
                search_params['location'] = location_formatted
            
            search_url = f"{self.base_url}/jobs?" + urlencode(search_params)
            logger.info(f"Searching Jobberman: {search_url}")
            
            # Try multiple search approaches
            job_urls = [
                search_url,
                f"{self.base_url}/search-jobs?q={keywords}",  # Alternative URL structure
                f"{self.base_url}/jobs/search?keywords={keywords}"  # Another possible structure
            ]
            
            for url in job_urls:
                html_content = self._fetch_page(url)
                if html_content:
                    jobs = self._parse_jobs(html_content, max_results)
                    if jobs:
                        break
                    
        except Exception as e:
            logger.error(f"Error scraping Jobberman: {str(e)}")
        
        logger.info(f"Jobberman scraper found {len(jobs)} jobs")
        return jobs
    
    def _fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch page content with enhanced anti-detection"""
        for attempt in range(max_retries):
            try:
                # Get working proxy
                proxy = self.proxy_manager.get_working_proxy() if self.proxy_manager.proxies else None
                
                # Enhanced headers for Nigerian context
                headers = self.ua_manager.get_headers()
                headers.update({
                    'Accept-Language': 'en-NG,en;q=0.9,en-US;q=0.8',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                })
                
                # Random delay between requests
                time.sleep(random.uniform(2, 5))
                
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=25,
                    allow_redirects=True,
                    verify=True
                )
                
                if response.status_code == 200:
                    logger.debug(f"Successfully fetched {url}")
                    return response.text
                elif response.status_code == 403:
                    logger.warning(f"Blocked by Jobberman (403) - attempt {attempt + 1}")
                    time.sleep(random.uniform(5, 10))
                elif response.status_code == 429:  # Rate limited
                    wait_time = random.uniform(15, 30)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 8))
        
        return None
    
    def _parse_jobs(self, html_content: str, max_results: int) -> List[Dict]:
        """Parse jobs from HTML with multiple selector strategies"""
        jobs = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Multiple selector strategies for different Jobberman layouts
        selectors_to_try = [
            # Current Jobberman selectors (2024/2025)
            'div[data-testid="job-card"]',
            '.job-card',
            '.search-result',
            '.job-item',
            '.job-listing',
            # Legacy selectors
            'article.job',
            'div.job',
            '.job-result',
            # Generic selectors
            '[class*="job-"]',
            '[class*="search-result"]',
            '[class*="listing"]'
        ]
        
        job_cards = []
        for selector in selectors_to_try:
            job_cards = soup.select(selector)
            if job_cards:
                logger.debug(f"Found {len(job_cards)} job cards with selector: {selector}")
                break
        
        if not job_cards:
            # Fallback: look for any div containing job-related keywords
            all_divs = soup.find_all(['div', 'article', 'li'])
            job_cards = [div for div in all_divs if self._has_job_indicators(div)]
            logger.debug(f"Fallback found {len(job_cards)} potential job cards")
        
        jobs_found = 0
        for card in job_cards:
            if jobs_found >= max_results:
                break
                
            job_data = self._extract_job_data_enhanced(card)
            if job_data and self._is_valid_job(job_data):
                jobs.append(job_data)
                jobs_found += 1
        
        return jobs
    
    def _has_job_indicators(self, element) -> bool:
        """Check if element contains job-related content"""
        text = element.get_text().lower()
        job_indicators = ['apply', 'salary', 'location', 'company', 'job', 'position', 'role']
        class_str = ' '.join(element.get('class', [])).lower()
        
        return (any(indicator in text for indicator in job_indicators) and
                len(text) > 50 and  # Must have substantial content
                any(indicator in class_str for indicator in ['job', 'card', 'result', 'listing']))
    
    def _extract_job_data_enhanced(self, card) -> Optional[Dict]:
        """Enhanced job data extraction with multiple fallback strategies"""
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
            
            # Enhanced title extraction
            title_selectors = [
                '[data-testid="job-title"]',
                'h3 a', 'h2 a', 'h4 a',
                '.job-title a', '.job-title',
                '.title a', '.title',
                'a[href*="/job"]',
                'a[href*="/jobs/"]',
                '[class*="title"] a',
                '[class*="job-title"]'
            ]
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    if len(title_text) > 3:  # Valid title should be longer than 3 chars
                        job_data['title'] = title_text
                        # Get link if available
                        if title_elem.name == 'a':
                            href = title_elem.get('href')
                            if href:
                                job_data['link'] = urljoin(self.base_url, href)
                        break
            
            # Enhanced company extraction
            company_selectors = [
                '[data-testid="company-name"]',
                '.company-name', '.company', '.employer',
                '[class*="company"] a', '[class*="company"]',
                '[class*="employer"]'
            ]
            
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    company_text = company_elem.get_text(strip=True)
                    if len(company_text) > 1:
                        job_data['company'] = company_text
                        break
            
            # Enhanced location extraction
            location_selectors = [
                '[data-testid="job-location"]',
                '.location', '.job-location',
                '[class*="location"]',
                '.address', '[class*="address"]'
            ]
            
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    if len(location_text) > 2:
                        job_data['location'] = location_text
                        break
            
            # Enhanced salary extraction
            salary_selectors = [
                '[data-testid="salary"]',
                '.salary', '.pay', '.wage',
                '[class*="salary"]', '[class*="pay"]'
            ]
            
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if any(currency in salary_text for currency in ['₦', 'NGN', 'Naira', '$', 'USD']):
                        job_data['salary'] = salary_text
                        break
            
            # Enhanced description extraction
            desc_selectors = [
                '.description', '.summary', '.snippet',
                '[class*="description"]', '[class*="summary"]',
                'p'
            ]
            
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if len(desc_text) > 20:  # Substantial description
                        job_data['description'] = desc_text[:200]
                        break
            
            # Job type extraction
            type_selectors = [
                '.job-type', '.type', '[class*="type"]',
                '[data-testid="job-type"]'
            ]
            
            for selector in type_selectors:
                type_elem = card.select_one(selector)
                if type_elem:
                    type_text = type_elem.get_text(strip=True)
                    if type_text.lower() in ['full-time', 'part-time', 'contract', 'freelance', 'temporary']:
                        job_data['job_type'] = type_text
                        break
            
            # If no link found yet, try to find any link in the card
            if not job_data['link']:
                link_elem = card.select_one('a[href]')
                if link_elem:
                    href = link_elem.get('href')
                    if href and ('job' in href or 'position' in href):
                        job_data['link'] = urljoin(self.base_url, href)
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.warning(f"Error extracting job data: {str(e)}")
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Enhanced job validation"""
        # Must have title and either company or location
        has_title = job_data.get('title', '').strip() != ''
        has_company = job_data.get('company', '').strip() != ''
        has_location = job_data.get('location', '').strip() != ''
        
        # Title should be reasonable length and not contain spam indicators
        if has_title:
            title = job_data['title'].lower()
            spam_indicators = ['click here', 'visit', 'http', 'www.', 'apply now only']
            if any(spam in title for spam in spam_indicators):
                return False
            if len(job_data['title']) < 3 or len(job_data['title']) > 200:
                return False
        
        return has_title and (has_company or has_location)
