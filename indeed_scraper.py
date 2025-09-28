import asyncio
import random
import logging
import time
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager
import threading

logger = logging.getLogger(__name__)

class IndeedScraper:
    def __init__(self, proxy_manager: ProxyManager, user_agent_manager: UserAgentManager):
        self.proxy_manager = proxy_manager
        self.ua_manager = user_agent_manager
        self.base_urls = {
            'ng': 'https://ng.indeed.com',
            'gb': 'https://uk.indeed.com',
            'global': 'https://indeed.com'
        }
        self._lock = threading.Lock()
    
    def search_jobs(self, keywords: str, location: str = '', job_type: str = '', 
                   max_results: int = 10, country: str = 'global') -> List[Dict]:
        """Search jobs using Playwright with thread-safe execution"""
        try:
            # Determine best Indeed domain
            if 'uk' in location.lower() or 'united kingdom' in location.lower():
                country = 'gb'
            elif any(nigerian_city in location.lower() for nigerian_city in ['nigeria', 'lagos', 'abuja', 'calabar']):
                country = 'ng'
            
            base_url = self.base_urls.get(country, self.base_urls['global'])
            search_url = self._build_search_url(base_url, keywords, location, job_type)
            
            logger.info(f"Indeed scraper starting: {search_url}")
            
            # Run async search in a new event loop (thread-safe)
            with self._lock:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    jobs = loop.run_until_complete(
                        self._async_search_jobs(search_url, base_url, max_results)
                    )
                finally:
                    loop.close()
            
            logger.info(f"Indeed scraper found {len(jobs)} jobs")
            return jobs
            
        except Exception as e:
            logger.error(f"Error in Indeed scraper: {str(e)}")
            return []
    
    def _build_search_url(self, base_url: str, keywords: str, location: str, job_type: str) -> str:
        """Build Indeed search URL"""
        params = []
        params.append(f"q={keywords.replace(' ', '+')}")
        
        if location:
            params.append(f"l={location.replace(' ', '+')}")
        
        params.append("start=0")
        params.append("sort=relevance")
        
        if job_type and job_type != 'all':
            job_type_map = {
                'fulltime': 'fulltime',
                'parttime': 'parttime',
                'contract': 'contract',
                'freelance': 'contract'
            }
            if job_type.lower() in job_type_map:
                params.append(f"jt={job_type_map[job_type.lower()]}")
        
        return f"{base_url}/jobs?{'&'.join(params)}"
    
    async def _async_search_jobs(self, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Async job search with Playwright"""
        jobs = []
        browser = None
        
        try:
            async with async_playwright() as p:
                # Launch browser with simple configuration
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu'
                    ]
                )
                
                page = await browser.new_page()
                
                # Apply stealth
                await stealth_async(page)
                
                # Set realistic user agent
                await page.set_user_agent(self.ua_manager.get_chrome_user_agent())
                
                # Navigate to Indeed
                await page.goto(search_url, wait_until='domcontentloaded', timeout=20000)
                
                # Wait a bit for content to load
                await page.wait_for_timeout(3000)
                
                # Parse jobs from page
                jobs = await self._parse_jobs_from_page(page, base_url, max_results)
                
        except Exception as e:
            logger.warning(f"Playwright Indeed search failed: {str(e)}")
        finally:
            if browser:
                await browser.close()
        
        return jobs
    
    async def _parse_jobs_from_page(self, page, base_url: str, max_results: int) -> List[Dict]:
        """Parse jobs from the current page"""
        jobs = []
        
        try:
            # Multiple selectors for job cards
            job_selectors = [
                '[data-jk]',
                '.jobsearch-SerpJobCard',
                '.job_seen_beacon',
                'td.resultContent'
            ]
            
            job_cards = []
            for selector in job_selectors:
                try:
                    cards = await page.locator(selector).all()
                    if cards:
                        job_cards = cards
                        logger.debug(f"Found {len(cards)} job cards with selector: {selector}")
                        break
                except:
                    continue
            
            if not job_cards:
                logger.warning("No job cards found on Indeed page")
                return []
            
            # Extract job data from cards
            for i, card in enumerate(job_cards[:max_results]):
                try:
                    job_data = await self._extract_job_data_from_card(card, base_url)
                    if job_data and self._is_valid_job(job_data):
                        jobs.append(job_data)
                except Exception as e:
                    logger.debug(f"Error extracting job {i}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing jobs from Indeed page: {str(e)}")
        
        return jobs
    
    async def _extract_job_data_from_card(self, card, base_url: str) -> Optional[Dict]:
        """Extract job data from a single job card"""
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
            
            # Extract title
            title_selectors = [
                'h2 a span[title]',
                'h2 a',
                '.jobTitle a',
                '[data-testid="job-title"] a'
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = card.locator(selector).first
                    if await title_elem.count() > 0:
                        title = await title_elem.get_attribute('title')
                        if not title:
                            title = await title_elem.inner_text()
                        if title and title.strip():
                            job_data['title'] = title.strip()
                            break
                except:
                    continue
            
            # Extract company
            company_selectors = [
                '[data-testid="company-name"]',
                '.companyName',
                'span.companyName'
            ]
            
            for selector in company_selectors:
                try:
                    company_elem = card.locator(selector).first
                    if await company_elem.count() > 0:
                        company = await company_elem.inner_text()
                        if company and company.strip():
                            job_data['company'] = company.strip()
                            break
                except:
                    continue
            
            # Extract location
            location_selectors = [
                '[data-testid="job-location"]',
                '.companyLocation'
            ]
            
            for selector in location_selectors:
                try:
                    location_elem = card.locator(selector).first
                    if await location_elem.count() > 0:
                        location = await location_elem.inner_text()
                        if location and location.strip():
                            job_data['location'] = location.strip()
                            break
                except:
                    continue
            
            # Extract salary
            try:
                salary_elem = card.locator('.salary-snippet, [data-testid*="salary"]').first
                if await salary_elem.count() > 0:
                    salary = await salary_elem.inner_text()
                    if salary and any(currency in salary for currency in ['₦', '$', '€', '£', 'USD', 'NGN', 'GBP']):
                        job_data['salary'] = salary.strip()
            except:
                pass
            
            # Extract job link
            try:
                link_elem = card.locator('h2 a[href]').first
                if await link_elem.count() > 0:
                    href = await link_elem.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            job_data['link'] = base_url + href
                        else:
                            job_data['link'] = href
                else:
                    # Try data-jk attribute
                    jk = await card.get_attribute('data-jk')
                    if jk:
                        job_data['link'] = f"{base_url}/viewjob?jk={jk}"
            except:
                pass
            
            # Extract description
            try:
                desc_elem = card.locator('.job-snippet, .summary').first
                if await desc_elem.count() > 0:
                    description = await desc_elem.inner_text()
                    if description:
                        job_data['description'] = description.strip()[:200]
            except:
                pass
            
            return job_data if job_data['title'] else None
            
        except Exception as e:
            logger.debug(f"Error extracting job data: {str(e)}")
            return None
    
    def _is_valid_job(self, job_data: Dict) -> bool:
        """Check if job data is valid"""
        if not job_data.get('title'):
            return False
        
        title = job_data['title'].lower()
        
        # Filter out spam
        spam_indicators = ['undefined', 'null', 'error', 'test job']
        if any(spam in title for spam in spam_indicators):
            return False
        
        if len(job_data['title']) < 5:
            return False
        
        # Must have either company or location
        has_company = bool(job_data.get('company', '').strip())
        has_location = bool(job_data.get('location', '').strip())
        
        return has_company or has_location
