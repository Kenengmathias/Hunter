import asyncio
import concurrent.futures
import logging
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
    
    def search_all_sources(self, keywords: str, location: str = '', job_type: str = '', 
                          max_results_per_source: int = 10, include_local: bool = False) -> List[Dict]:
        """Search jobs from all configured sources"""
        all_jobs = []
        
        # Determine which country/region we're searching
        is_nigerian_search = self._is_nigerian_location(location)
        
        # Define search tasks
        search_tasks = []
        
        # API sources (always include)
        search_tasks.extend([
            ('Jooble API', self.api_manager.search_jooble, keywords, location, max_results_per_source),
            ('Adzuna API', self.api_manager.search_adzuna, keywords, location, max_results_per_source),
            ('JSearch API', self.api_manager.search_jsearch, keywords, location, max_results_per_source)
        ])
        
        # Web scraping sources
        if is_nigerian_search or include_local:
            search_tasks.append(
                ('Jobberman', self.jobberman_scraper.search_jobs, keywords, location, job_type, max_results_per_source)
            )
        
        # Always include Indeed (global)
        indeed_country = 'ng' if is_nigerian_search else 'global'
        search_tasks.append(
            ('Indeed', self.indeed_scraper.search_jobs, keywords, location, job_type, max_results_per_source, indeed_country)
        )
        
        # Execute searches
        all_jobs = self._execute_searches(search_tasks)
        
        # Deduplicate and process
        unique_jobs = self._deduplicate_jobs(all_jobs)
        processed_jobs = self._process_jobs(unique_jobs, location)
        
        logger.info(f"Total jobs found: {len(all_jobs)}, Unique jobs: {len(unique_jobs)}")
        return processed_jobs
    
    def _execute_searches(self, search_tasks: List) -> List[Dict]:
        """Execute all search tasks concurrently"""
        all_jobs = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_source = {}
            for task in search_tasks:
                source_name = task[0]
                search_func = task[1]
                args = task[2:]
                
                future = executor.submit(self._safe_search, search_func, *args)
                future_to_source[future] = source_name
            
            # Collect results
            for future in concurrent.futures.as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    jobs = future.result(timeout=30)  # 30 second timeout per source
                    all_jobs.extend(jobs)
                    logger.info(f"{source_name}: Found {len(jobs)} jobs")
                except Exception as e:
                    logger.error(f"{source_name} failed: {str(e)}")
        
        return all_jobs
    
    def _safe_search(self, search_func, *args):
        """Safely execute search function with error handling"""
        try:
            return search_func(*args)
        except Exception as e:
            logger.error(f"Search function error: {str(e)}")
            return []
    
    def _is_nigerian_location(self, location: str) -> bool:
        """Check if location is in Nigeria"""
        nigerian_keywords = [
            'nigeria', 'lagos', 'abuja', 'kano', 'ibadan', 'calabar', 
            'port harcourt', 'benin city', 'jos', 'ilorin', 'owerri',
            'enugu', 'abeokuta', 'onitsha', 'warri', 'sokoto'
        ]
        return any(keyword in location.lower() for keyword in nigerian_keywords)
    
    def _deduplicate_jobs(self, jobs: List[Dict]) -> List[Dict]:
        """Remove duplicate jobs based on title and company"""
        seen_jobs: Set[str] = set()
        unique_jobs = []
        
        for job in jobs:
            # Create hash based on title, company, and location
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
            # Remove extra whitespace and normalize
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
        score = 0.0
        
        # Base score
        score += 1.0
        
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
        
        # Description length bonus (more detailed jobs)
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
