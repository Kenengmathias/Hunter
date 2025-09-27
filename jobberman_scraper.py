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
        """Search jobs on Jobberman"""
        jobs = []
        try:
            search_params = {
                'q': keywords,
                'l': location or 'Nigeria'
            }
            
            search_url = f"{self.base_url}/jobs?" + urlencode(search_params)
            logger.info(f"Searching Jobberman: {search_url}")
            
            # Get page content
            html_content = self._fetch_page(search_url)
            if not html_content:
                logger.error("Failed to fetch Jobberman search page")
                return jobs
            
            # Parse jobs
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for job cards with various possible selectors
            job_cards = soup.find_all(['div', 'article', 'li'], class_=lambda x: x and any(
                keyword in x.lower() for keyword in ['job', 'listing', 'card', 'item'] if x
            ))
            
            jobs_found = 0
            for card in job_cards:
                if jobs_found >= max_results:
                    break
                    
                job_data = self._extract_job_data(card)
                if job_data and self._is_valid_job(job_data):
                    jobs.append(job_data)
                    jobs_found += 1
                    
        except Exception as e:
            logger.error(f"Error scraping Jobberman: {str(e)}")
        
        logger.info(f"Jobberman scraper found {len(jobs)} jobs")
        return jobs
    
    def _fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch page content with proxy and anti-detection"""
        for attempt in range(max_retries):
            try:
                # Get working proxy
                proxy = self.proxy_manager.get_working_proxy() if self.proxy_manager.proxies else None
                
                # Get headers with Nigerian context
                headers = self.ua_manager.get_headers()
                headers.update({
                    'Accept-Language': 'en-NG,en;q=0.9,en-US;q=0.8',
                    'Cache-Control': 'no-cache'
                })
                
                # Random delay
                time.sleep(random.uniform(1, 4))
                
                response = self.session.get(
                    url,
                    headers=headers,
                    proxies=proxy,
                    timeout=20,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code == 429:  # Rate limited
                    wait_time = random.uniform(15, 30)
                    logger.warning(f"Rate limited, waiting {wait_time:.1f}s")
                    time.sleep(wait_time)
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(3, 6))
        
        return None
    
    def _extract_job_data(self, card) -> Optional[Dict]:
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
                'source': 'Jobberman'
            }
            
            # Title selectors
            title_selectors = [
                'h3 a',
                'h2 a', 
                '.job-title a',
                '.title a',
                'a[href*="/job/"]'
            ]
            
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    job_data['title'] = title_elem.get_text(strip=True)
                    # Also get the link
                    href = title_elem.get('href')
                    if href:
                        job_data['link'] = urljoin(self.base_url, href)
                    break
            
            # Company name
            company_selectors = [
                '.company-name',
                '.employer',
                '.company a',
                'p.company',
                '[class*="company"]'
            ]
            
            for selector in company_selectors:
                company_elem = card.select_one(selector)
                if company_elem:
                    job_data['company'] = company_elem.get_text(strip=True)
                    break
            
            # Location
            location_selectors = [
                '.location',
                '.job-location',
                '[class*="location"]',
                'span[title*="Location"]'
            ]
            
            for selector in location_selectors:
                location_elem = card.select_one(selector)
                if location_elem:
                    job_data['location'] = location_elem.get_text(strip=True)
                    break
            
            # Salary
            salary_selectors = [
                '.salary',
                '.pay',
                '[class*="salary"]',
                '[class*="pay"]'
            ]
            
            for selector in salary_selectors:
                salary_elem = card.select_one(selector)
                if salary_elem:
                    salary_text = salary_elem.get_text(strip=True)
                    if any(char in salary_text for char in ['₦', 'NGN', 'Naira', '$']):
                        job_data['salary'] = salary_text
                        break
            
            # Job type
            type_selectors = [
                '.job-type',
                '.type',
                '[class*="type"]'
            ]
            
            for selector in type_selectors:
                type_elem = card.select_one(selector)
                if type_elem:
                    job_data['job_type'] = type_elem.get_text(strip=True)
                    break
            
            # Description
            desc_selectors = [
                '.description',
                '.summary',
                '.snippet',
                'p'
            ]
            
            for selector in desc_selectors:
                desc_elem = card.select_one(selector)
                if desc_elem:
                    desc_text = desc_elem.get_text(strip=True)
                    if len(desc_text) > 50:  # Only take substantial descriptions
                        job_data['description'] = desc_text[:200]
                        break
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.warning(f"Error extracting job data: {str(e)}")
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Check if job data is valid"""
        required_fields = ['title', 'company']
        return all(job_data.get(field, '').strip() for field in required_fields)
