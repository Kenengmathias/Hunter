import concurrent.futures
import logging
import time
from typing import List, Dict, Set
from api_manager import APIManager
from indeed_scraper import IndeedScraper
from jobberman_scraper import JobbermanScraper
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager
import hashlib

logger = logging.getLogger(__name__)

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
        
        # Timeout settings (thread-safe)
        self.max_total_time = 60  # Maximum time for entire search
        self.api_timeout = 12     # Timeout per API call
        self.scraper_timeout = 25 # Timeout per scraper
    
    def search_all_sources(self, keywords: str, location: str = '', job_type: str = '', 
                          max_results_per_source: int = 10, include_local: bool = False) -> List[Dict]:
        """Search jobs from all sources with thread-safe timeout control"""
        start_time = time.time()
        all_jobs = []
        
        try:
            logger.info(f"Starting job search: '{keywords}' in '{location}'")
            
            # Determine search strategy
            is_nigerian_search = self._is_nigerian_location(location)
            
            # Define search tasks
            search_tasks = self._build_search_tasks(
                keywords, location, job_type, max_results_per_source, 
                is_nigerian_search, include_local
            )
            
            # Execute searches with thread-safe timeout control
            all_jobs = self._execute_searches_thread_safe(search_tasks)
            
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
        """Build list of search tasks"""
        tasks = []
        
        # API tasks (high priority - fast and reliable)
        api_tasks = [
            ('JSearch API', self.api_manager.search_jsearch, self.api_timeout, keywords, location, max_results_per_source),
            ('Jooble API', self.api_manager.search_jooble, self.api_timeout, keywords, location, max_results_per_source),
            ('Adzuna API', self.api_manager.search_adzuna, self.api_timeout, keywords, location, max_results_per_source)
        ]
        
        # Scraper tasks
        scraper_tasks = []
        
        # Add Jobberman for Nigerian searches or when local is requested
        if is_nigerian_search or include_local:
            scraper_tasks.append(
                ('Jobberman', self.jobberman_scraper.search_jobs, self.scraper_timeout, keywords, location, job_type, max_results_per_source)
            )
        
        # Add Indeed (with Playwright)
        indeed_country = 'ng' if is_nigerian_search else 'global'
        scraper_tasks.append(
            ('Indeed', self.indeed_scraper.search_jobs, self.scraper_timeout, keywords, location, job_type, max_results_per_source, indeed_country)
        )
        
        return api_tasks + scraper_tasks
    
    def _execute_searches_thread_safe(self, search_tasks: List) -> List[Dict]:
        """Execute searches with thread-safe timeout control"""
        all_jobs = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_source = {}
            for task in search_tasks:
                source_name, search_func, timeout, *args = task
                
                future = executor.submit(self._safe_search, search_func, *args)
                future_to_source[future] = (source_name, timeout)
            
            # Collect results with individual timeouts
            for future in concurrent.futures.as_completed(future_to_source, timeout=self.max_total_time):
                source_name, timeout = future_to_source[future]
                try:
                    source_jobs = future.result(timeout=timeout)
                    if source_jobs:
                        all_jobs.extend(source_jobs)
                        logger.info(f"{source_name}: Found {len(source_jobs)} jobs")
                    else:
                        logger.info(f"{source_name}: Found 0 jobs")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{source_name} timed out after {timeout}s")
                except Exception as e:
                    logger.error(f"{source_name} failed: {str(e)}")
        
        return all_jobs
    
    def _safe_search(self, search_func, *args):
        """Execute search function with error handling"""
        try:
            result = search_func(*args)
            return result if result else []
        except Exception as e:
            logger.error(f"Search function {search_func.__name__} error: {str(e)}")
            return []
    
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
            job.get('location', '').lower().strip()[:20]
        ]
        key_string = '|'.join(key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _process_jobs(self, jobs: List[Dict], search_location: str) -> List[Dict]:
        """Process and rank jobs"""
        processed_jobs = []
        
        for job in jobs:
            # Clean up job data
            processed_job = self._clean_job_data(job)
            
            # Add relevance score
            processed_job['relevance_score'] = self._calculate_relevance(processed_job, search_location)
            
            processed_jobs.append(processed_job)
        
        # Sort by relevance score (highest first)
        processed_jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return processed_jobs
    
    def _clean_job_data(self, job: Dict) -> Dict:
        """Clean and standardize job data"""
        cleaned = job.copy()
        
        # Clean title
        if cleaned.get('title'):
            cleaned['title'] = cleaned['title'].strip()
        
        # Clean company
        if cleaned.get('company'):
            cleaned['company'] = cleaned['company'].strip()
        
        # Clean location
        if cleaned.get('location'):
            location = cleaned['location'].strip()
            location = ' '.join(location.split())
            cleaned['location'] = location
        
        # Ensure all required fields exist
        required_fields = ['title', 'company', 'location', 'salary', 'link', 'description', 'job_type', 'source']
        for field in required_fields:
            if field not in cleaned:
                cleaned[field] = ''
        
        return cleaned
    
    def _calculate_relevance(self, job: Dict, search_location: str) -> float:
        """Calculate job relevance score"""
        score = 1.0
        
        # Location matching bonus
        if search_location and job.get('location'):
            job_location = job['location'].lower()
            search_location_lower = search_location.lower()
            
            if search_location_lower in job_location:
                score += 2.0
            elif any(word in job_location for word in search_location_lower.split()):
                score += 1.0
        
        # Salary information bonus
        if job.get('salary') and job['salary'].strip():
            score += 1.5
        
        # Description length bonus
        if job.get('description'):
            desc_len = len(job['description'])
            if desc_len > 100:
                score += 1.0
            elif desc_len > 50:
                score += 0.5
        
        # Nigerian job bonus if searching in Nigeria
        if self._is_nigerian_location(search_location) and job.get('source') == 'Jobberman':
            score += 1.0
        
        return score
