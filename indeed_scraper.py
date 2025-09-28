import asyncio
import random
import logging
import time
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Browser, Page
from playwright_stealth import stealth_async
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager
import concurrent.futures

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
        self.max_total_time = 45  # Maximum time for entire Indeed search
        
    def search_jobs(self, keywords: str, location: str = '', job_type: str = '', 
                   max_results: int = 10, country: str = 'global') -> List[Dict]:
        """Search jobs using Playwright with stealth and anti-detection"""
        start_time = time.time()
        
        try:
            # Run async playwright in thread
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._run_async_search, keywords, location, job_type, max_results, country)
                jobs = future.result(timeout=self.max_total_time)
                
            search_time = time.time() - start_time
            logger.info(f"Indeed scraper completed in {search_time:.1f}s, found {len(jobs)} jobs")
            return jobs
            
        except concurrent.futures.TimeoutError:
            logger.warning(f"Indeed search timed out after {self.max_total_time}s")
            return []
        except Exception as e:
            logger.error(f"Error in Indeed scraper: {str(e)}")
            return []
    
    def _run_async_search(self, keywords: str, location: str, job_type: str, max_results: int, country: str) -> List[Dict]:
        """Run the async search in sync context"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._async_search_jobs(keywords, location, job_type, max_results, country))
        finally:
            loop.close()
    
    async def _async_search_jobs(self, keywords: str, location: str, job_type: str, max_results: int, country: str) -> List[Dict]:
        """Async job search with Playwright"""
        jobs = []
        browser = None
        
        try:
            # Determine best Indeed domain
            if 'uk' in location.lower() or 'united kingdom' in location.lower():
                country = 'gb'
            elif any(nigerian_city in location.lower() for nigerian_city in ['nigeria', 'lagos', 'abuja', 'calabar']):
                country = 'ng'
            
            base_url = self.base_urls.get(country, self.base_urls['global'])
            
            # Build search URL
            search_url = self._build_search_url(base_url, keywords, location, job_type)
            logger.info(f"Searching Indeed: {search_url}")
            
            # Launch browser with stealth
            async with async_playwright() as p:
                browser = await self._launch_stealth_browser(p)
                page = await browser.new_page()
                
                # Apply stealth techniques
                await stealth_async(page)
                await self._configure_page(page)
                
                # Try multiple strategies
                strategies = [
                    self._strategy_direct_search,
                    self._strategy_mobile_search,
                    self._strategy_alternative_search
                ]
                
                for i, strategy in enumerate(strategies):
                    try:
                        jobs = await strategy(page, search_url, base_url, max_results)
                        if jobs:
                            logger.info(f"Indeed strategy {i+1} succeeded with {len(jobs)} jobs")
                            break
                    except Exception as e:
                        logger.warning(f"Indeed strategy {i+1} failed: {str(e)}")
                        continue
                        
        except Exception as e:
            logger.error(f"Error in async Indeed search: {str(e)}")
        finally:
            if browser:
                await browser.close()
        
        return jobs
    
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
    
    async def _launch_stealth_browser(self, p) -> Browser:
        """Launch browser with maximum stealth"""
        # Get proxy configuration
        proxy_config = None
        if self.proxy_manager.proxies:
            proxy_dict = self.proxy_manager.get_working_proxy()
            if proxy_dict:
                # Extract proxy details
                proxy_url = proxy_dict['http']
                if '@' in proxy_url:
                    # With authentication
                    auth_part = proxy_url.split('://')[1].split('@')[0]
                    server_part = proxy_url.split('@')[1]
                    username, password = auth_part.split(':')
                    server = f"http://{server_part}"
                    proxy_config = {
                        'server': server,
                        'username': username,
                        'password': password
                    }
                else:
                    # Without authentication
                    proxy_config = {'server': proxy_url}
        
        # Browser launch options with maximum stealth
        launch_options = {
            'headless': True,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-features=TranslateUI',
                '--disable-ipc-flooding-protection',
                '--window-size=1920,1080'
            ]
        }
        
        if proxy_config:
            launch_options['proxy'] = proxy_config
        
        return await p.chromium.launch(**launch_options)
    
    async def _configure_page(self, page: Page):
        """Configure page with human-like settings"""
        # Set realistic viewport
        await page.set_viewport_size({"width": 1366, "height": 768})
        
        # Set realistic user agent
        await page.set_user_agent(self.ua_manager.get_chrome_user_agent())
        
        # Set additional headers
        await page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
        
        # Block unnecessary resources for speed
        await page.route('**/*.{png,jpg,jpeg,gif,svg,css,font,woff,woff2}', lambda route: route.abort())
    
    async def _strategy_direct_search(self, page: Page, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Direct Indeed search strategy"""
        try:
            # Navigate with realistic timing
            await page.goto(search_url, wait_until='domcontentloaded', timeout=20000)
            
            # Human-like delay
            await page.wait_for_timeout(random.randint(2000, 4000))
            
            # Parse jobs
            return await self._parse_jobs_from_page(page, base_url, max_results)
            
        except Exception as e:
            logger.debug(f"Direct search strategy failed: {str(e)}")
            return []
    
    async def _strategy_mobile_search(self, page: Page, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Mobile Indeed search strategy"""
        try:
            # Convert to mobile URL
            mobile_url = search_url.replace('indeed.com', 'm.indeed.com')
            mobile_url = mobile_url.replace('ng.indeed.com', 'm.ng.indeed.com')
            mobile_url = mobile_url.replace('uk.indeed.com', 'm.uk.indeed.com')
            
            # Set mobile user agent
            await page.set_user_agent('Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1')
            await page.set_viewport_size({"width": 375, "height": 667})
            
            await page.goto(mobile_url, wait_until='domcontentloaded', timeout=15000)
            await page.wait_for_timeout(random.randint(1500, 3000))
            
            return await self._parse_jobs_from_page(page, base_url, max_results, mobile=True)
            
        except Exception as e:
            logger.debug(f"Mobile search strategy failed: {str(e)}")
            return []
    
    async def _strategy_alternative_search(self, page: Page, search_url: str, base_url: str, max_results: int) -> List[Dict]:
        """Alternative Indeed search with different approach"""
        try:
            # Try different URL patterns
            alt_url = search_url + '&radius=25&fromage=7'  # 25km radius, last 7 days
            
            await page.goto(alt_url, wait_until='networkidle', timeout=25000)
            await page.wait_for_timeout(random.randint(2000, 5000))
            
            # Try to handle any popups or overlays
            try:
                # Close common popups
                popup_selectors = ['[aria-label="close"]', '.icl-CloseButton', '.popover-x-button-close']
                for selector in popup_selectors:
                    if await page.locator(selector).count() > 0:
                        await page.click(selector)
                        await page.wait_for_timeout(500)
            except:
                pass
            
            return await self._parse_jobs_from_page(page, base_url, max_results)
            
        except Exception as e:
            logger.debug(f"Alternative search strategy failed: {str(e)}")
            return []
    
    async def _parse_jobs_from_page(self, page: Page, base_url: str, max_results: int, mobile: bool = False) -> List[Dict]:
        """Parse jobs from the current page"""
        jobs = []
        
        try:
            # Wait for job results to load
            await page.wait_for_timeout(3000)
            
            # Multiple selectors for job cards
            job_selectors = [
                '[data-jk]',  # Main Indeed job cards
                '.jobsearch-SerpJobCard',
                '.job_seen_beacon',
                '.slider_item',
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
                logger.warning("No job cards found on page")
                return []
            
            # Extract job data from cards
            for i, card in enumerate(job_cards[:max_results]):
                try:
                    job_data = await self._extract_job_data_from_card(card, base_url, mobile)
                    if job_data and self._is_valid_job(job_data):
                        jobs.append(job_data)
                except Exception as e:
                    logger.debug(f"Error extracting job {i}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error parsing jobs from page: {str(e)}")
        
        return jobs
    
    async def _extract_job_data_from_card(self, card, base_url: str, mobile: bool = False) -> Optional[Dict]:
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
                '[data-testid="job-title"] a',
                'a[data-jk]'
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
            salary_selectors = [
                '.salary-snippet',
                '[data-testid*="salary"]',
                '.estimated-salary'
            ]
            
            for selector in salary_selectors:
                try:
                    salary_elem = card.locator(selector).first
                    if await salary_elem.count() > 0:
                        salary = await salary_elem.inner_text()
                        if salary and any(currency in salary for currency in ['₦', '$', '€', '£', 'USD', 'NGN', 'GBP']):
                            job_data['salary'] = salary.strip()
                            break
                except:
                    continue
            
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
        spam_indicators = ['undefined', 'null', 'error', 'test job', 'advertisement']
        if any(spam in title for spam in spam_indicators):
            return False
        
        if len(job_data['title']) < 5:
            return False
        
        # Must have either company or location
        has_company = bool(job_data.get('company', '').strip())
        has_location = bool(job_data.get('location', '').strip())
        
        return has_company or has_location
