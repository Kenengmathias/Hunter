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
        """Search jobs on Jobberman with improved real job parsing"""
        jobs = []
        try:
            # Enhanced Nigerian location handling
            search_location = self._format_nigerian_location(location)
            
            # Try multiple URL patterns
            search_urls = [
                f"{self.base_url}/jobs?q={keywords.replace(' ', '+')}",
                f"{self.base_url}/jobs?search={keywords.replace(' ', '+')}",
            ]
            
            logger.info(f"Searching Jobberman for: {keywords} in {search_location}")
            
            # Try each URL pattern
            for search_url in search_urls:
                html_content = self._fetch_page(search_url)
                
                if html_content and self._is_valid_html(html_content):
                    jobs = self._parse_real_jobs(html_content, max_results)
                    if jobs:
                        logger.info(f"Success with URL: {search_url}")
                        break
                                
        except Exception as e:
            logger.error(f"Error scraping Jobberman: {str(e)}")
        
        logger.info(f"Jobberman scraper found {len(jobs)} jobs")
        return jobs
    
    def _format_nigerian_location(self, location: str) -> str:
        """Format Nigerian locations properly"""
        if not location:
            return 'Nigeria'
        
        nigerian_cities = {
            'lagos': 'Lagos',
            'abuja': 'Abuja',
            'calabar': 'Calabar',
            'port harcourt': 'Port Harcourt',
            'kano': 'Kano',
            'ibadan': 'Ibadan',
            'nigeria': 'Nigeria'
        }
        
        location_lower = location.lower().strip()
        for key, formatted in nigerian_cities.items():
            if key in location_lower:
                return formatted
        
        return location
    
    def _is_valid_html(self, html_content: str) -> bool:
        """Check if HTML contains actual job content"""
        if not html_content or len(html_content) < 1000:
            return False
        
        # Check for job-related keywords
        job_indicators = ['salary', 'apply', 'company', 'position', 'experience', 'qualification']
        content_lower = html_content.lower()
        
        indicator_count = sum(1 for indicator in job_indicators if indicator in content_lower)
        return indicator_count >= 3
    
    def _fetch_page(self, url: str, max_retries: int = 2) -> Optional[str]:
        """Fetch page with minimal retries"""
        for attempt in range(max_retries):
            try:
                # Simple request without proxy for speed
                headers = {
                    'User-Agent': self.ua_manager.get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache'
                }
                
                time.sleep(random.uniform(1, 2))
                
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=15,
                    allow_redirects=True
                )
                
                if response.status_code == 200:
                    return response.text
                elif response.status_code in [404, 410]:
                    logger.debug(f"URL not found ({response.status_code}): {url}")
                    return None
                else:
                    logger.debug(f"HTTP {response.status_code} for {url}")
                    
            except Exception as e:
                logger.debug(f"Fetch attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(2, 4))
        
        return None
    
    def _parse_real_jobs(self, html_content: str, max_results: int) -> List[Dict]:
        """Parse only real jobs, filtering out navigation and UI elements"""
        jobs = []
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove navigation, headers, footers, and sidebars first
        for unwanted in soup.select('nav, header, footer, aside, .sidebar, .nav, .menu, .filter'):
            unwanted.decompose()
        
        # Look for job-specific containers with stricter rules
        job_selectors = [
            'article[class*="job"]',
            'div[class*="job-card"]',
            'div[class*="search-result"]',
            'li[class*="job"]',
            '.job-item',
            '.listing'
        ]
        
        potential_jobs = []
        for selector in job_selectors:
            elements = soup.select(selector)
            if elements:
                logger.debug(f"Found {len(elements)} potential jobs with: {selector}")
                potential_jobs.extend(elements)
                break
        
        # If no specific job containers, look for divs with job-like content
        if not potential_jobs:
            all_divs = soup.find_all(['div', 'article', 'li'])
            potential_jobs = [div for div in all_divs if self._looks_like_job(div)]
        
        # Extract and validate jobs
        for element in potential_jobs[:max_results * 3]:  # Check more elements
            job_data = self._extract_job_data_strict(element)
            
            if job_data and self._is_real_job(job_data):
                jobs.append(job_data)
                
                if len(jobs) >= max_results:
                    break
        
        return jobs
    
    def _looks_like_job(self, element) -> bool:
        """Check if element looks like a job posting"""
        try:
            text = element.get_text().lower()
            
            # Must have reasonable length
            if len(text) < 50 or len(text) > 2000:
                return False
            
            # Must have job-related keywords
            job_keywords = ['apply', 'salary', 'experience', 'qualification', 'job', 'position', 'role']
            keyword_count = sum(1 for keyword in job_keywords if keyword in text)
            
            if keyword_count < 2:
                return False
            
            # Must NOT be navigation or UI elements
            navigation_keywords = [
                'search filter', 'homepage', 'find a job', 'jobs found',
                'filter applied', 'sort by', 'view all', 'load more',
                'sign in', 'register', 'login', 'create account',
                'terms', 'privacy', 'cookie', 'contact us'
            ]
            
            if any(nav_keyword in text for nav_keyword in navigation_keywords):
                return False
            
            # Must have links (job postings have apply links)
            links = element.find_all('a', href=True)
            if len(links) < 1:
                return False
            
            return True
            
        except Exception:
            return False
    
    def _extract_job_data_strict(self, element) -> Optional[Dict]:
        """Extract job data with strict validation to avoid UI elements"""
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
            
            # Extract title - must be substantial and not a UI element
            title_selectors = [
                'h1 a', 'h2 a', 'h3 a', 'h4 a',
                'a[href*="/job/"]',
                'a[href*="/jobs/"]',
                '.job-title a',
                '.title a'
            ]
            
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title_text = title_elem.get_text(strip=True)
                    
                    # Validate title
                    if self._is_valid_job_title(title_text):
                        job_data['title'] = title_text
                        
                        # Get link
                        href = title_elem.get('href')
                        if href:
                            if href.startswith('http'):
                                job_data['link'] = href
                            else:
                                job_data['link'] = urljoin(self.base_url, href)
                        break
            
            # If no valid title found, skip this element
            if not job_data['title']:
                return None
            
            # Extract company - look for company-specific patterns
            company_selectors = [
                '.company-name',
                '.employer',
                '.company',
                '[class*="company"]',
                'span.company'
            ]
            
            for selector in company_selectors:
                company_elem = element.select_one(selector)
                if company_elem:
                    company_text = company_elem.get_text(strip=True)
                    if company_text and len(company_text) > 1 and len(company_text) < 100:
                        # Skip if it's a UI element
                        if not any(ui_word in company_text.lower() for ui_word in ['filter', 'search', 'homepage', 'jobs found']):
                            job_data['company'] = company_text
                            break
            
            # Extract location
            location_selectors = [
                '.location',
                '.job-location',
                '[class*="location"]'
            ]
            
            for selector in location_selectors:
                location_elem = element.select_one(selector)
                if location_elem:
                    location_text = location_elem.get_text(strip=True)
                    if location_text and any(nigerian_city in location_text.lower() for nigerian_city in ['lagos', 'abuja', 'nigeria', 'calabar', 'kano', 'ibadan', 'port harcourt']):
                        job_data['location'] = location_text
                        break
            
            # Extract salary
            salary_keywords = ['₦', 'NGN', 'naira', 'salary', '$', 'per month', 'per annum']
            text_content = element.get_text()
            
            for line in text_content.split('\n'):
                if any(keyword in line for keyword in salary_keywords):
                    cleaned_line = line.strip()
                    if len(cleaned_line) < 50 and any(char.isdigit() for char in cleaned_line):
                        job_data['salary'] = cleaned_line
                        break
            
            # Extract description - get meaningful text
            paragraphs = element.find_all('p')
            for p in paragraphs:
                desc_text = p.get_text(strip=True)
                if len(desc_text) > 50 and len(desc_text) < 500:
                    job_data['description'] = desc_text[:200]
                    break
            
            return job_data
            
        except Exception as e:
            logger.debug(f"Error extracting job data: {str(e)}")
            return None
    
    def _is_valid_job_title(self, title: str) -> bool:
        """Validate that title is a real job title, not UI element"""
        if not title or len(title) < 5:
            return False
        
        if len(title) > 150:  # Too long to be a title
            return False
        
        title_lower = title.lower()
        
        # Reject obvious UI elements
        ui_elements = [
            'search filter', 'homepage', 'find a job', 'jobs found',
            'filter applied', 'filters applied', 'sort by', 'view all',
            'load more', 'sign in', 'register', 'login', 'create account',
            'jobs in nigeria', 'any job function', 'refine search',
            'browse', 'categories', 'popular searches'
        ]
        
        if any(ui_elem in title_lower for ui_elem in ui_elements):
            return False
        
        # Must contain job-related words or industry terms
        job_indicators = [
            'manager', 'officer', 'executive', 'assistant', 'specialist',
            'engineer', 'developer', 'analyst', 'coordinator', 'supervisor',
            'director', 'consultant', 'representative', 'administrator',
            'accountant', 'designer', 'marketer', 'sales', 'hr', 'it',
            'intern', 'graduate', 'senior', 'junior', 'lead'
        ]
        
        has_job_indicator = any(indicator in title_lower for indicator in job_indicators)
        
        # If no specific indicator, at least check it's not pure navigation
        if not has_job_indicator:
            # Allow if it has normal sentence structure and reasonable length
            words = title_lower.split()
            if len(words) < 2 or len(words) > 20:
                return False
        
        return True
    
    def _is_real_job(self, job_data: Dict) -> bool:
        """Final validation that this is a real job posting"""
        if not job_data.get('title'):
            return False
        
        # Must have valid title
        if not self._is_valid_job_title(job_data['title']):
            return False
        
        # Should have at least company OR location
        has_company = bool(job_data.get('company', '').strip())
        has_location = bool(job_data.get('location', '').strip())
        
        if not (has_company or has_location):
            return False
        
        # Should have a valid link
        link = job_data.get('link', '')
        if link and ('#' in link or 'javascript:' in link.lower()):
            return False
        
        return True
