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

class IndeedScraper:
    def __init__(self, proxy_manager: ProxyManager, user_agent_manager: UserAgentManager):
        self.proxy_manager = proxy_manager
        self.ua_manager = user_agent_manager
        self.base_urls = {
            'ng': 'https://ng.indeed.com',  # Nigeria
            'gb': 'https://uk.indeed.com',  # UK  
            'global': 'https://indeed.com'  # Global
        }
        self.session = requests.Session()
    
    def search_jobs(self, keywords: str, location: str = '', job_type: str = '', 
                   max_results: int = 10, country: str = 'global') -> List[Dict]:
        """Enhanced Indeed job search with better anti-detection"""
        jobs = []
        try:
            # Determine best Indeed domain
            if 'uk' in location.lower() or 'united kingdom' in location.lower():
                country = 'gb'
            elif any(nigerian_city in location.lower() for nigerian_city in ['nigeria', 'lagos', 'abuja', 'calabar']):
                country = 'ng'
            
            base_url = self.base_urls.get(country, self.base_urls['global'])
            
            search_params = {
                'q': keywords,
                'l': location,
                'start': 0,
                'sort': 'relevance'
            }
            
            if job_type and job_type != 'all':
                job_type_map = {
                    'fulltime': 'fulltime',
                    'parttime': 'parttime', 
                    'contract': 'contract',
                    'freelance': 'contract'
                }
                if job_type.lower() in job_type_map:
                    search_params['jt'] = job_type_map[job_type.lower()]
            
            search_url = f"{base_url}/jobs?" + urlencode(search_params)
            logger.info(f"Searching Indeed: {search_url}")
            
            # Try multiple strategies
            strategies = [
                self._strategy_mobile_indeed,
                self._strategy_regular_indeed,
                self._strategy_alternative_indeed
            ]
            
            for strategy in strategies:
                try:
                    jobs = strategy(search_url, base_url, max_results)
                    if jobs:
                        logger.info(f"Indeed strategy succeeded with {len(jobs)} jobs")
                        break
                except Exception as e:
                    logger.warning(f"Indeed strategy failed: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error scraping Indeed: {str(e)}")
        
        logger.info(f"Indeed scraper found {len(jobs)} jobs")
        return jobs
    
    def _strategy_mobile_indeed(self, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Try mobile version of Indeed (often less protected)"""
        mobile_url = search_url.replace('indeed.com', 'm.indeed.com').replace('ng.indeed.com', 'm.ng.indeed.com').replace('uk.indeed.com', 'm.uk.indeed.com')
        
        html_content = self._fetch_page_enhanced(mobile_url, mobile=True)
        if html_content:
            return self._parse_jobs_enhanced(html_content, base_url, max_results, mobile=True)
        return []
    
    def _strategy_regular_indeed(self, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Regular Indeed scraping with enhanced headers"""
        html_content = self._fetch_page_enhanced(search_url, mobile=False)
        if html_content:
            return self._parse_jobs_enhanced(html_content, base_url, max_results, mobile=False)
        return []
    
    def _strategy_alternative_indeed(self, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Alternative Indeed URL patterns"""
        # Try different URL patterns
        alt_urls = [
            search_url.replace('/jobs?', '/q-'),  # Alternative URL structure
            search_url + '&radius=50',  # Add radius
            search_url.replace('indeed.com', 'indeed.co.uk') if 'uk' in search_url else search_url
        ]
        
        for url in alt_urls:
            html_content = self._fetch_page_enhanced(url)
            if html_content:
                jobs = self._parse_jobs_enhanced(html_content, base_url, max_results)
                if jobs:
                    return jobs
        return []
    
    def _fetch_page_enhanced(self, url: str, max_retries: int = 3, mobile: bool = False) -> Optional[str]:
        """Enhanced page fetching with multiple anti-detection techniques"""
        for attempt in range(max_retries):
            try:
                # Get a working proxy
                proxy = self.proxy_manager.get_working_proxy() if self.proxy_manager.proxies else None
                
                # Enhanced headers based on mobile vs desktop
                if mobile:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                else:
                    headers = self.ua_manager.get_headers()
                    headers.update({
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'Cache-Control': 'max-age=0'
                    })
                
                # Random delay with jitter
                time.sleep(random.uniform(2, 6))
                
                # Add some randomization to avoid patterns
                if random.random() < 0.3:
                    headers['DNT'] = '1'
                
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                    allow_redirects=True,
                    verify=True
                )
                
                if response.status_code == 200:
                    # Check if we got blocked (Indeed sometimes returns 200 but with block page)
                    if 'blocked' in response.text.lower() or 'captcha' in response.text.lower():
                        logger.warning(f"Indeed returned block page - attempt {attempt + 1}")
                        time.sleep(random.uniform(10, 20))
                        continue
                    
                    return response.text
                    
                elif response.status_code == 403:
                    logger.warning(f"Indeed blocked request (403) - attempt {attempt + 1}")
                    time.sleep(random.uniform(5, 15))
                    
                elif response.status_code == 429:  # Rate limited
                    wait_time = random.uniform(20, 40)
                    logger.warning(f"Indeed rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    
                elif response.status_code == 503:  # Service unavailable
                    wait_time = random.uniform(10, 20)
                    logger.warning(f"Indeed service unavailable, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                    
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(5, 10))
        
        return None
    
    def _parse_jobs_enhanced(self, html_content: str, base_url: str, max_results: int, mobile: bool = False) -> List[Dict]:
        """Enhanced job parsing with multiple selector strategies"""
        jobs = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Multiple selector strategies for different Indeed layouts
        if mobile:
            selectors_to_try = [
                'div[data-jk]',  # Mobile job cards
                '.job',
                '.jobsearch-SerpJobCard',
                '[class*="job"]'
            ]
        else:
            selectors_to_try = [
                'div[data-jk]',  # Current Indeed job cards
                '.jobsearch-SerpJobCard',
                '.job_seen_beacon',
                '.slider_container .slider_item',
                'td.resultContent',
                '[class*="job"]',
                '[data-testid*="job"]'
            ]
        
        job_cards = []
        for selector in selectors_to_try:
            job_cards = soup.select(selector)
            if job_cards:
                logger.debug(f"Found {len(job_cards)} job cards with selector: {selector}")
                break
        
        if not job_cards:
            logger.warning("No job cards found with any selector")
            return jobs
        
        jobs_found = 0
        for card in job_cards:
            if jobs_found >= max_results:
                break
                
            job_data = self._extract_job_data_enhanced(card, base_url, mobile)
            if job_data and self._is_valid_job(job_data):
                jobs.append(job_data)
                jobs_found += 1
        
        return jobs
    
    def _extract_job_data_enhanced(self, card, base_url: str, mobile: bool = False) -> Optional[Dict]:
        """Enhanced job data extraction"""
        try:
            job_data = {
                'title': '',
                'company': '',
                'location': '',
                'salary': '',
                'link': '',
                'description': '',
                'job_type': '',
                'source': 'Indeed'
            }
            
            if mobile:
                # Mobile selectors
                title_selectors = [
                    'h2 a span[title]',
                    'h2 a',
                    '.jobTitle a',
                    '[data-testid="job-title"] a'
                ]
                
                company_selectors = [
                    '[data-testid="company-name"]',
                    '.companyName'
                ]
                
                location_selectors = [
                    '[data-testid="job-location"]',
                    '.companyLocation'
                ]
            else:
                # Desktop selectors
                title_selectors = [
                    '[data-jk] h2 a span[title]',
                    '[data-jk] h2 span[title]',
                    'h2 a span[title]',
                    '.jobTitle a span[title]',
                    'h2.jobTitle span[title]',
                    '[data-testid="job-title"] a'
                ]
                
                company_selectors = [
                    '[data-testid="company-name"]',
                    '.companyName a',
                    '.companyName span',
                    'span.companyName'
                ]
                
                location_selectors = [
                    '[data-testid="job-location"]',
                    '.companyLocation',
                    'div.companyLocation'
                ]
            
            # Extract title
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    job_data['title'] = title_elem.get('title') or title_elem.get_text(strip=True)
                    if job_data['title']:
                        break
            
            # Extract company
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    job_data['company'] = company_elem.get_text(strip=True)
                    if job_data['company']:
                        break
            
            # Extract location
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    job_data['location'] = location_elem.get_text(strip=True)
                    if job_data['location']:
                        break
            
            # Extract salary
            salary_selectors = [
                '.salary-snippet',
                '[data-testid*="salary"]',
                '.estimated-salary',
                '.salaryText'
            ]
            
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if any(currency in salary_text for currency in ['₦', ', '€', '£', 'USD', 'NGN', 'GBP']):
                        job_data['salary'] = salary_text
                        break
            
            # Extract job link
            link_elem = card.select_one('h2 a[href], [data-jk]')
            if link_elem:
                if link_elem.name == 'a':
                    href = link_elem.get('href')
                else:
                    # For data-jk elements, construct the link
                    jk = link_elem.get('data-jk')
                    href = f"/viewjob?jk={jk}" if jk else None
                
                if href:
                    job_data['link'] = urljoin(base_url, href)
            
            # Extract description
            desc_selectors = [
                '.job-snippet',
                '.summary',
                '[data-testid="job-snippet"]',
                '.jobSnippet'
            ]
            
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    job_data['description'] = desc_elem.get_text(strip=True)[:200]
                    if job_data['description']:
                        break
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.warning(f"Error extracting Indeed job data: {str(e)}")
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Check if job data is valid"""
        required_fields = ['title', 'company']
        is_valid = all(job_data.get(field, '').strip() for field in required_fields)
        
        # Additional validation
        if is_valid and job_data['title']:
            title = job_data['title'].lower()
            # Filter out obvious spam or invalid titles
            spam_indicators = ['undefined', 'null', 'error', 'test job']
            if any(spam in title for spam in spam_indicators):
                return False
            if len(job_data['title']) < 5:  # Title too short
                return False
        
        return is_valid
