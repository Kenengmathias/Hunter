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
            'global': 'https://indeed.com'  # Global
        }
        self.session = requests.Session()
    
    def search_jobs(self, keywords: str, location: str = '', job_type: str = '', 
                   max_results: int = 10, country: str = 'ng') -> List[Dict]:
        """Search jobs on Indeed"""
        jobs = []
        try:
            base_url = self.base_urls.get(country, self.base_urls['global'])
            search_params = {
                'q': keywords,
                'l': location,
                'start': 0
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
            
            # Get page content
            html_content = self._fetch_page(search_url)
            if not html_content:
                logger.error("Failed to fetch Indeed search page")
                return jobs
            
            # Parse jobs
            soup = BeautifulSoup(html_content, 'html.parser')
            job_cards = soup.find_all(['div', 'a'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['job', 'result', 'card'] if x
            ))
            
            jobs_found = 0
            for card in job_cards:
                if jobs_found >= max_results:
                    break
                    
                job_data = self._extract_job_data(card, base_url)
                if job_data and self._is_valid_job(job_data):
                    jobs.append(job_data)
                    jobs_found += 1
                    
        except Exception as e:
            logger.error(f"Error scraping Indeed: {str(e)}")
        
        logger.info(f"Indeed scraper found {len(jobs)} jobs")
        return jobs
    
    def _fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch page content with proxy and anti-detection"""
        for attempt in range(max_retries):
            try:
                # Get working proxy
                proxy = self.proxy_manager.get_working_proxy() if self.proxy_manager.proxies else None
                
                # Get headers
                headers = self.ua_manager.get_headers()
                
                # Random delay
                time.sleep(random.uniform(1, 3))
                
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=15,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:  # Rate limited
                    wait_time = random.uniform(10, 20)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 5))
        
        return None
    
    def _extract_job_data(self, card, base_url: str) -> Optional[Dict]:
        """Extract job data from job card element"""
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
            
            # Try multiple selectors for title
            title_selectors = [
                '[data-jk] h2 a span',
                '[data-jk] h2 span',
                'h2 a span[title]',
                '.jobTitle a span',
                'h2.jobTitle span'
            ]
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    job_data['title'] = title_elem.get('title') or title_elem.get_text(strip=True)
                    break
            
            # Company name
            company_selectors = [
                '[data-testid="company-name"]',
                '.companyName',
                'span.companyName a',
                'span.companyName span'
            ]
            
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    job_data['company'] = company_elem.get_text(strip=True)
                    break
            
            # Location
            location_selectors = [
                '[data-testid="job-location"]',
                '.companyLocation',
                'div.companyLocation'
            ]
            
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    job_data['location'] = location_elem.get_text(strip=True)
                    break
            
            # Salary
            salary_selectors = [
                '.salary-snippet',
                '[data-testid="attribute_snippet_testid"]',
                '.estimated-salary'
            ]
            
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem and any(char in salary_elem.get_text() for char in ['₦', '$', '€', '£']):
                    job_data['salary'] = salary_elem.get_text(strip=True)
                    break
            
            # Job link
            link_elem = card.select_one('h2 a[href], [data-jk]')
            if link_elem:
                href = link_elem.get('href') or f"/job?jk={link_elem.get('data-jk')}"
                if href:
                    job_data['link'] = urljoin(base_url, href)
            
            # Job description snippet
            desc_elem = card.select_one('.job-snippet, .summary')
            if desc_elem:
                job_data['description'] = desc_elem.get_text(strip=True)[:200]
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.warning(f"Error extracting job data: {str(e)}")
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Check if job data is valid"""
        required_fields = ['title', 'company']
        return all(job_data.get(field, '').strip() for field in required_fields)
