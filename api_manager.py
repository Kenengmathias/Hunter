import requests
import logging
import time
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import threading

logger = logging.getLogger(__name__)

class APIManager:
    def __init__(self, jooble_key: str = None, adzuna_app_id: str = None, 
                 adzuna_app_key: str = None, jsearch_key: str = None):
        self.jooble_key = jooble_key
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        self.jsearch_key = jsearch_key
        
        # Rate limiting
        self.last_request_times = {}
        self.request_lock = threading.Lock()
    
    def _rate_limit(self, api_name: str, min_interval: float = 0.5):
        """Simple rate limiting to avoid API abuse"""
        with self.request_lock:
            now = time.time()
            last_time = self.last_request_times.get(api_name, 0)
            elapsed = now - last_time
            
            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)
            
            self.last_request_times[api_name] = time.time()
    
    def search_jooble(self, keywords: str, location: str = "remote", max_results: int = 5) -> List[Dict]:
        """Enhanced Jooble API with better Nigerian support"""
        jobs = []
        if not self.jooble_key:
            logger.warning("JOOBLE_API_KEY not configured")
            return jobs
        
        try:
            self._rate_limit('jooble')
            
            jooble_url = f"https://jooble.org/api/{self.jooble_key}"
            
            # Enhanced Nigerian location handling
            search_location = self._optimize_location_for_jooble(location)
            
            jooble_params = {
                "keywords": keywords,
                "location": search_location,
                "page": 1
            }
            
            response = requests.post(jooble_url, json=jooble_params, timeout=12)
            
            if response.status_code == 200:
                data = response.json()
                jobs_data = data.get('jobs', [])
                
                for job in jobs_data[:max_results]:
                    processed_job = self._process_jooble_job(job, location)
                    if processed_job:
                        jobs.append(processed_job)
                        
                logger.info(f"Jooble found {len(jobs)} jobs for '{keywords}' in '{location}'")
            else:
                logger.error(f"Jooble API error: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Jooble: {str(e)}')
        except Exception as e:
            logger.error(f'Unexpected Jooble error: {str(e)}')
        
        return jobs
    
    def _optimize_location_for_jooble(self, location: str) -> str:
        """Optimize location query for Jooble API"""
        if not location:
            return "remote"
        
        location_lower = location.lower().strip()
        
        # Nigerian city mapping for better results
        nigerian_cities = {
            'lagos': 'Lagos, Nigeria',
            'abuja': 'Abuja, Nigeria', 
            'calabar': 'Calabar, Nigeria',
            'port harcourt': 'Port Harcourt, Nigeria',
            'kano': 'Kano, Nigeria',
            'ibadan': 'Ibadan, Nigeria',
            'benin city': 'Benin City, Nigeria',
            'jos': 'Jos, Nigeria',
            'ilorin': 'Ilorin, Nigeria',
            'nigeria': 'Nigeria'
        }
        
        # Check for Nigerian cities
        for city_key, city_full in nigerian_cities.items():
            if city_key in location_lower:
                return city_full
        
        # International locations
        international_mapping = {
            'uk': 'United Kingdom',
            'united kingdom': 'United Kingdom',
            'london': 'London, UK',
            'canada': 'Canada',
            'toronto': 'Toronto, Canada',
            'vancouver': 'Vancouver, Canada',
            'usa': 'United States',
            'united states': 'United States',
            'new york': 'New York, USA',
            'san francisco': 'San Francisco, USA',
            'remote': 'remote'
        }
        
        for key, mapped in international_mapping.items():
            if key in location_lower:
                return mapped
        
        return location  # Return as-is if no mapping found
    
    def _process_jooble_job(self, job: Dict, original_location: str) -> Optional[Dict]:
        """Process and enhance Jooble job data"""
        try:
            title = job.get('title', '').strip()
            company = job.get('company', '').strip()
            
            if not title or not company:
                return None
            
            # Clean and enhance job data
            processed = {
                'title': title,
                'company': company,
                'link': job.get('link', '#'),
                'location': job.get('location', original_location),
                'salary': self._clean_salary(job.get('salary', '')),
                'description': job.get('snippet', ''),
                'job_type': self._extract_job_type_from_text(title + ' ' + job.get('snippet', '')),
                'source': 'Jooble'
            }
            
            return processed
            
        except Exception as e:
            logger.debug(f"Error processing Jooble job: {e}")
            return None
    
    def search_adzuna(self, keywords: str, location: str = "remote", max_results: int = 5) -> List[Dict]:
        """Enhanced Adzuna API with better Nigerian and international support"""
        jobs = []
        if not self.adzuna_app_id or not self.adzuna_app_key:
            logger.warning("Adzuna credentials not configured")
            return jobs
        
        try:
            self._rate_limit('adzuna')
            
            # Enhanced location and query optimization
            country_code, optimized_query, location_query = self._optimize_adzuna_search(keywords, location)
            
            base_url = f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
            
            params = {
                'app_id': self.adzuna_app_id,
                'app_key': self.adzuna_app_key,
                'what': optimized_query,
                'results_per_page': max_results,
                'sort_by': 'relevance'
            }
            
            if location_query:
                params['where'] = location_query
            
            response = requests.get(base_url, params=params, timeout=12)
            
            if response.status_code == 200:
                data = response.json()
                jobs_data = data.get('results', [])
                
                for job in jobs_data[:max_results]:
                    processed_job = self._process_adzuna_job(job, location, country_code)
                    if processed_job:
                        jobs.append(processed_job)
                        
                logger.info(f"Adzuna found {len(jobs)} jobs for '{keywords}' in '{location}'")
            else:
                logger.error(f"Adzuna API error: {response.status_code} - {response.text[:200]}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Adzuna: {str(e)}')
        except Exception as e:
            logger.error(f'Unexpected Adzuna error: {str(e)}')
        
        return jobs
    
    def _optimize_adzuna_search(self, keywords: str, location: str) -> tuple:
        """Optimize Adzuna search parameters"""
        location_lower = location.lower().strip()
        
        # Country code mapping
        country_mapping = {
            'uk': 'gb',
            'united kingdom': 'gb',
            'london': 'gb',
            'canada': 'ca',
            'toronto': 'ca',
            'vancouver': 'ca',
            'usa': 'us',
            'united states': 'us',
            'new york': 'us',
            'san francisco': 'us',
            'remote': 'us'
        }
        
        # Default to US API for Nigerian searches (better results)
        country_code = 'us'
        location_query = ''
        optimized_query = keywords
        
        # Check for international locations
        for location_key, code in country_mapping.items():
            if location_key in location_lower:
                country_code = code
                if location_key not in ['usa', 'united states', 'remote']:
                    location_query = location
                break
        
        # Handle Nigerian locations specially
        nigerian_indicators = ['nigeria', 'lagos', 'abuja', 'calabar', 'port harcourt', 'kano', 'ibadan']
        if any(indicator in location_lower for indicator in nigerian_indicators):
            country_code = 'us'  # Use US API for broader results
            optimized_query = f"{keywords} Nigeria"  # Include Nigeria in query
            location_query = location  # Keep original location
        
        return country_code, optimized_query, location_query
    
    def _process_adzuna_job(self, job: Dict, original_location: str, country_code: str) -> Optional[Dict]:
        """Process and enhance Adzuna job data"""
        try:
            title = job.get('title', '').strip()
            if not title:
                return None
            
            # Extract salary
            salary = self._extract_adzuna_salary(job, country_code)
            
            # Clean description
            description = job.get('description', '')
            if isinstance(description, str) and len(description) > 300:
                description = description[:200] + '...'
            
            processed = {
                'title': title,
                'company': job.get('company', {}).get('display_name', 'Unknown'),
                'link': job.get('redirect_url', '#'),
                'location': job.get('location', {}).get('display_name', original_location),
                'salary': salary,
                'description': description,
                'job_type': job.get('contract_time', ''),
                'source': 'Adzuna'
            }
            
            return processed
            
        except Exception as e:
            logger.debug(f"Error processing Adzuna job: {e}")
            return None
    
    def _extract_adzuna_salary(self, job: Dict, country_code: str) -> str:
        """Extract and format Adzuna salary information"""
        try:
            salary_min = job.get('salary_min', 0)
            salary_max = job.get('salary_max', 0)
            
            if not salary_min or not salary_max:
                return ''
            
            # Currency mapping
            currency_map = {
                'us': '$',
                'ca': 'CAD $',
                'gb': '£',
                'de': '€'
            }
            
            currency = currency_map.get(country_code, '$')
            
            # Format salary range
            if salary_min == salary_max:
                return f"{currency}{salary_min:,.0f}"
            else:
                return f"{currency}{salary_min:,.0f} - {currency}{salary_max:,.0f}"
                
        except Exception:
            return ''
    
    def search_jsearch(self, keywords: str, location: str = "", max_results: int = 5) -> List[Dict]:
        """Enhanced JSearch API with perfect Nigerian support"""
        jobs = []
        if not self.jsearch_key:
            logger.warning("JSEARCH_API_KEY not configured")
            return jobs
        
        try:
            self._rate_limit('jsearch', 1.0)  # Longer rate limit for JSearch
            
            url = "https://jsearch.p.rapidapi.com/search"
            
            # Build optimized query
            query = self._build_jsearch_query(keywords, location)
            
            params = {
                "query": query,
                "page": 1,
                "num_pages": 1,
                "date_posted": "all"
            }
            
            headers = {
                "X-RapidAPI-Key": self.jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                jobs_data = data.get('data', [])
                
                if not jobs_data:
                    logger.info("JSearch returned no job data")
                    return jobs
                
                for job in jobs_data[:max_results]:
                    processed_job = self._process_jsearch_job(job)
                    if processed_job:
                        jobs.append(processed_job)
                        
                logger.info(f"JSearch found {len(jobs)} jobs for '{keywords}' in '{location}'")
                
            elif response.status_code == 403:
                logger.error("JSearch API 403 Forbidden - Check API key validity")
            elif response.status_code == 429:
                logger.warning("JSearch API rate limited (429)")
            else:
                logger.error(f"JSearch API error: {response.status_code} - {response.text[:200]}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching JSearch: {str(e)}')
        except Exception as e:
            logger.error(f'Unexpected JSearch error: {str(e)}')
        
        return jobs
    
    def _build_jsearch_query(self, keywords: str, location: str) -> str:
        """Build optimized JSearch query"""
        if not location or location.lower() in ['remote', '']:
            return keywords
        
        location_lower = location.lower().strip()
        
        # Nigerian locations - include country for better results
        nigerian_cities = ['nigeria', 'lagos', 'abuja', 'calabar', 'port harcourt', 'kano', 'ibadan']
        if any(city in location_lower for city in nigerian_cities):
            if 'nigeria' not in location_lower:
                return f"{keywords} {location} Nigeria"
            else:
                return f"{keywords} {location}"
        
        # International locations
        return f"{keywords} {location}"
    
    def _process_jsearch_job(self, job: Dict) -> Optional[Dict]:
        """Process and enhance JSearch job data"""
        try:
            title = job.get('job_title', '').strip()
            if not title:
                return None
            
            # Extract salary
            salary = self._extract_jsearch_salary(job)
            
            # Build location
            location_parts = [
                job.get('job_city', ''),
                job.get('job_state', ''),
                job.get('job_country', '')
            ]
            location = ', '.join(filter(None, location_parts)) or 'Remote'
            
            # Clean description
            description = job.get('job_description', '') or ''
            if len(description) > 200:
                description = description[:200] + '...'
            
            processed = {
                'title': title,
                'company': job.get('employer_name', 'Unknown'),
                'link': job.get('job_apply_link', '#'),
                'location': location,
                'salary': salary,
                'description': description,
                'job_type': job.get('job_employment_type', ''),
                'source': 'JSearch'
            }
            
            return processed
            
        except Exception as e:
            logger.debug(f"Error processing JSearch job: {e}")
            return None
    
    def _extract_jsearch_salary(self, job: Dict) -> str:
        """Extract and format JSearch salary"""
        try:
            salary_min = job.get('job_salary_min')
            salary_max = job.get('job_salary_max')
            salary_currency = job.get('job_salary_currency', 'USD')
            salary_period = job.get('job_salary_period', 'YEAR')
            
            if not salary_min or not salary_max:
                return ''
            
            # Currency symbol mapping
            currency_symbols = {
                'USD': '$',
                'NGN': '₦',
                'GBP': '£',
                'EUR': '€',
                'CAD': 'CAD $'
            }
            
            symbol = currency_symbols.get(salary_currency, salary_currency)
            
            # Period mapping
            period_map = {
                'YEAR': '/year',
                'MONTH': '/month', 
                'HOUR': '/hour'
            }
            
            period = period_map.get(salary_period, '')
            
            if salary_min == salary_max:
                return f"{symbol}{salary_min:,}{period}"
            else:
                return f"{symbol}{salary_min:,} - {symbol}{salary_max:,}{period}"
                
        except Exception:
            return ''
    
    def _clean_salary(self, salary: str) -> str:
        """Clean and standardize salary strings"""
        if not salary:
            return ''
        
        # Remove extra whitespace
        salary = ' '.join(salary.split())
        
        # Common cleaning patterns
        salary = salary.replace('Salary:', '').strip()
        
        return salary
    
    def _extract_job_type_from_text(self, text: str) -> str:
        """Extract job type from title and description"""
        if not text:
            return ''
        
        text_lower = text.lower()
        
        # Job type indicators
        if any(indicator in text_lower for indicator in ['full-time', 'full time', 'permanent']):
            return 'Full-time'
        elif any(indicator in text_lower for indicator in ['part-time', 'part time']):
            return 'Part-time'
        elif any(indicator in text_lower for indicator in ['contract', 'contractor']):
            return 'Contract'
        elif any(indicator in text_lower for indicator in ['freelance', 'freelancer']):
            return 'Freelance'
        elif any(indicator in text_lower for indicator in ['internship', 'intern']):
            return 'Internship'
        elif any(indicator in text_lower for indicator in ['remote']):
            return 'Remote'
        
        return ''
