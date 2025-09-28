import asyncio
import concurrent.futures
import logging
import time
import signal
from typing import List, Dict, Set
from api_manager import APIManager
from indeed_scraper import IndeedScraper
from jobberman_scraper import JobbermanScraper
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager
import hashlib

logger = logging.getLogger(__name__)

class TimeoutError(Exception):
    pass

class JobAggregator:
    def __init__(self, proxy_list: List[str] = None, **api_keys):
        # Initialize managers
        self.proxy_manager = ProxyManager(proxy_list) if proxy_list else ProxyManager()
        self.ua_manager = UserAgentManager()
        
        # Initialize API manager
        self.api_manager = APIManager(
            jooble_key=api_keys.get('jooble_key'),
            adzuna_app_id=api_keys.get('adzuna_app_id'),
            adzuna_app_key=api_keys.get('adzuna_app_key'),
            jsearch_key=api_keys.get('jsearch_key')
        )
        
        # Initialize scrapers
        self.indeed_scraper = IndeedScraper(self.proxy_manager, self.ua_manager)
        self.jobberman_scraper = JobbermanScraper(self.proxy_manager, self.ua_manager)
        
        # Timeout settings
        self.max_total_time = 75  # Maximum time for entire search
        self.api_timeout = 15     # Timeout per API call
        self.scraper_timeout = 30 # Timeout per scraper
    
    def search_all_sources(self, keywords: str, location: str = '', job_type: str = '', 
                          max_results_per_source: int = 10, include_local: bool = False) -> List[Dict]:
        """Search jobs from all sources with strict timeout control"""
        start_time = time.time()
        all_jobs = []
        
        try:
            logger.info(f"Starting comprehensive job search: '{keywords}' in '{location}'")
            
            # Determine search strategy
            is_nigerian_search = self._is_nigerian_location(location)
            
            # Define search tasks with timeouts
            search_tasks = self._build_search_tasks(
                keywords, location, job_type, max_results_per_source, 
                is_nigerian_search, include_local
            )
            
            # Execute searches with timeout control
            all_jobs = self._execute_searches_with_timeout(search_tasks)
            
            # Process results
            unique_jobs = self._deduplicate_jobs(all_jobs)
            processed_jobs = self._process_jobs(unique_jobs, location)
            
            total_time = time.time() - start_time
            logger.info(f"Search completed in {total_time:.1f}s: {len(all_jobs)} total, {len(unique_jobs)} unique jobs")
            
            return processed_jobs
            
        except Exception as e:
            logger.error(f"Error in job aggregation: {str(e)}")
            total_time = time.time() - start_time
            logger.info(f"Search failed after {total_time:.1f}s, returning {len(all_jobs)} jobs found so far")
            
            # Return what we have so far
            if all_jobs:
                unique_jobs = self._deduplicate_jobs(all_jobs)
                return self._process_jobs(unique_jobs, location)
            return []
    
    def _build_search_tasks(self, keywords: str, location: str, job_type: str, 
                           max_results_per_source: int, is_nigerian_search: bool, include_local: bool) -> List:
        """Build list of search tasks with priorities"""
        tasks = []
        
        # API tasks (high priority - fast and reliable)
        api_tasks = [
            ('JSearch API', self.api_manager.search_jsearch, 'api', self.api_timeout, keywords, location, max_results_per_source),
            ('Jooble API', self.api_manager.search_jooble, 'api', self.api_timeout, keywords, location, max_results_per_source),
            ('Adzuna API', self.api_manager.search_adzuna, 'api', self.api_timeout, keywords, location, max_results_per_source)
        ]
        
        # Scraper tasks (medium priority - can be slower)
        scraper_tasks = []
        
        # Add Jobberman for Nigerian searches
        if is_nigerian_search or include_local:
            scraper_tasks.append(
                ('Jobberman', self.jobberman_scraper.search_jobs, 'scraper', 25, keywords, location, job_type, max_results_per_source)
            )
        
        # Add Indeed (lowest priority due to blocking issues, but now with Playwright)
        indeed_country = 'ng' if is_nigerian_search else 'global'
        scraper_tasks.append(
            ('Indeed', self.indeed_scraper.search_jobs, 'scraper', self.scraper_timeout, keywords, location, job_type, max_results_per_source, indeed_country)
        )
        
        # Return APIs first (for speed), then scrapers
        return api_tasks + scraper_tasks
    
    def _execute_searches_with_timeout(self, search_tasks: List) -> List[Dict]:
        """Execute searches with strict timeout control"""
        all_jobs = []
        start_time = time.time()
        
        # Separate fast APIs from slower scrapers
        api_tasks = [task for task in search_tasks if task[2] == 'api']
        scraper_tasks = [task for task in search_tasks if task[2] == 'scraper']
        
        # Execute APIs first (parallel, fast)
        logger.info("Starting API searches...")
        api_jobs = self._execute_task_group(api_tasks, max_workers=3, group_timeout=20)
        all_jobs.extend(api_jobs)
        
        # Check remaining time
        elapsed = time.time() - start_time
        remaining_time = self.max_total_time - elapsed
        
        if remaining_time > 10:  # If we have at least 10 seconds left
            logger.info("Starting scraper searches...")
            scraper_jobs = self._execute_task_group(scraper_tasks, max_workers=2, group_timeout=remaining_time)
            all_jobs.extend(scraper_jobs)
        else:
            logger.warning("Insufficient time remaining for scrapers, returning API results only")
        
        return all_jobs
    
    def _execute_task_group(self, tasks: List, max_workers: int, group_timeout: float) -> List[Dict]:
        """Execute a group of tasks with timeout"""
        jobs = []
        
        if not tasks:
            return jobs
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks
            future_to_source = {}
            for task in tasks:
                source_name, search_func, task_type, task_timeout, *args = task
                
                future = executor.submit(self._safe_search_with_timeout, search_func, task_timeout, *args)
                future_to_source[future] = source_name
            
            # Collect results with group timeout
            try:
                for future in concurrent.futures.as_completed(future_to_source, timeout=group_timeout):
                    source_name = future_to_source[future]
                    try:
                        source_jobs = future.result(timeout=1)  # Quick retrieval
                        jobs.extend(source_jobs)
                        logger.info(f"{source_name}: Found {len(source_jobs)} jobs")
                    except Exception as e:
                        logger.warning(f"{source_name} failed: {str(e)}")
                        
            except concurrent.futures.TimeoutError:
                logger.warning(f"Task group timed out after {group_timeout:.1f}s")
                
                # Cancel remaining futures
                for future in future_to_source:
                    if not future.done():
                        future.cancel()
        
        return jobs
    
    def _safe_search_with_timeout(self, search_func, timeout: float, *args):
        """Execute search function with timeout protection"""
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Search timed out after {timeout}s")
        
        try:
            # Set timeout for non-Windows systems
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(timeout))
            
            result = search_func(*args)
            
            # Clear timeout
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            
            return result if result else []
            
        except TimeoutError:
            logger.warning(f"Function {search_func.__name__} timed out")
            return []
        except Exception as e:
            logger.error(f"Function {search_func.__name__} error: {str(e)}")
            return []
        finally:
            # Ensure timeout is cleared
            if hasattr(signal, 'SIGALRM'):
                signal.alarm(0)
    
    def _is_nigerian_location(self, location: str) -> bool:
        """Check if location is in Nigeria"""
        nigerian_keywords = [
            'nigeria', 'lagos', 'abuja', 'kano', 'ibadan', 'calabar', 
            'port harcourt', 'benin city', 'jos', 'ilorin', 'owerri',
            'enugu', 'abeokuta', 'onitsha', 'warri', 'sokoto', 'kaduna',
            'maiduguri', 'zaria', 'katsina', 'bauchi'
        ]
        return any(keyword in location.lower() for keyword in nigerian_keywords)
    
    def _deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs based on title and company"""
        seen_jobs: Set[str] = set()
        unique_jobs = []
        
        for job in jobs:
            job_key = self._create_job_hash(job)
            
            if job_key not in seen_jobs:
                seen_jobs.add(job_key)
                unique_jobs.append(job)
        
        return unique_jobs
    
    def _create_job_hash(self, job: Dict) -> str:
        """Create unique hash for job deduplication"""
        key_parts = [
            job.get('title', '').lower().strip(),
            job.get('company', '').lower().strip(),
            job.get('location', '').lower().strip()[:20]  # First 20 chars of location
        ]
        key_string = '|'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _process_jobs(self, jobs: List[Dict], search_location: str) -> List[Dict]:
        """Process and rank jobs with enhanced scoring"""
        processed_jobs = []
        
        for job in jobs:
            # Clean up job data
            processed_job = self._clean_job_data(job)
            
            # Add relevance score
            processed_job['relevance_score'] = self._calculate_relevance(processed_job, search_location)
            
            # Add source reliability score
            processed_job['source_score'] = self._get_source_reliability_score(processed_job.get('source', ''))
            
            processed_jobs.append(processed_job)
        
        # Sort by combined score (relevance + source reliability)
        processed_jobs.sort(key=lambda x: (x.get('relevance_score', 0) + x.get('source_score', 0)), reverse=True)
        
        return processed_jobs
    
    def _clean_job_data(self, job: Dict) -> Dict:
        """Clean and standardize job data"""
        cleaned = job.copy()
        
        # Clean title
        if cleaned.get('title'):
            title = cleaned['title'].strip()
            # Remove common prefixes/suffixes
            title = title.replace('Job Title:', '').replace('Position:', '').strip()
            cleaned['title'] = title
        
        # Clean company
        if cleaned.get('company'):
            company = cleaned['company'].strip()
            # Remove common suffixes
            company = company.replace(' - Company', '').replace('Company:', '').strip()
            cleaned['company'] = company
        
        # Clean location
        if cleaned.get('location'):
            location = cleaned['location'].strip()
            # Normalize location format
            location = ' '.join(location.split())
            cleaned['location'] = location
        
        # Clean salary
        if cleaned.get('salary'):
            salary = cleaned['salary'].strip()
            # Standardize salary format
            cleaned['salary'] = salary
        
        # Ensure all required fields exist
        required_fields = ['title', 'company', 'location', 'salary', 'link', 'description', 'job_type', 'source']
        for field in required_fields:
            if field not in cleaned:
                cleaned[field] = ''
        
        return cleaned
    
    def _calculate_relevance(self, job: Dict, search_location: str) -> float:
        """Calculate job relevance score with enhanced factors"""
        score = 1.0  # Base score
        
        # Location matching bonus
        if search_location and job.get('location'):
            job_location = job['location'].lower()
            search_location_lower = search_location.lower()
            
            # Exact location match
            if search_location_lower in job_location:
                score += 3.0
            # Partial location match
            elif any(word in job_location for word in search_location_lower.split() if len(word) > 2):
                score += 1.5
            
            # Nigerian location bonus
            if self._is_nigerian_location(search_location) and self._is_nigerian_location(job_location):
                score += 2.0
        
        # Salary information bonus
        if job.get('salary') and job['salary'].strip():
            score += 1.5
            # Higher salary ranges get slight bonus
            salary_text = job['salary'].lower()
            if any(high_indicator in salary_text for high_indicator in ['senior', 'lead', 'manager', 'director']):
                score += 0.5
        
        # Job description quality bonus
        if job.get('description'):
            desc_len = len(job['description'])
            if desc_len > 150:
                score += 1.2
            elif desc_len > 75:
                score += 0.8
            elif desc_len > 25:
                score += 0.4
        
        # Job link availability bonus
        if job.get('link') and job['link'] != '#' and 'http' in job['link']:
            score += 1.0
        
        # Company name quality bonus
        if job.get('company') and len(job['company']) > 3:
            score += 0.5
        
        # Title quality bonus (avoid spam-like titles)
        if job.get('title'):
            title = job['title'].lower()
            if len(title) > 10 and len(title) < 100:  # Reasonable length
                score += 0.5
            # Avoid spammy titles
            spam_indicators = ['click here', 'apply now!', 'urgent!!!', 'immediate start']
            if any(spam in title for spam in spam_indicators):
                score -= 2.0
        
        return max(score, 0.1)  # Minimum score
    
    def _get_source_reliability_score(self, source: str) -> float:
        """Get reliability score for job source"""
        reliability_scores = {
            'JSearch': 3.0,    # AI-powered, usually high quality
            'Indeed': 2.5,     # Large database, good quality when accessible
            'Jooble': 2.0,     # Good aggregation
            'Adzuna': 2.0,     # Reliable API
            'Jobberman': 1.5   # Nigerian focus, but sometimes inconsistent
        }
        return reliability_scores.get(source, 1.0)
    
    def get_search_stats(self) -> Dict:
        """Get aggregator statistics"""
        proxy_stats = self.proxy_manager.get_proxy_stats() if self.proxy_manager else {}
        
        return {
            'proxy_stats': proxy_stats,
            'max_search_time': self.max_total_time,
            'api_timeout': self.api_timeout,
            'scraper_timeout': self.scraper_timeout
        }
