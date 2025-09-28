import requests
import logging
import time
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class APIManager:
    def __init__(self, jooble_key: str = None, adzuna_app_id: str = None, 
                 adzuna_app_key: str = None, jsearch_key: str = None):
        self.jooble_key = jooble_key
        self.adzuna_app_id = adzuna_app_id
        self.adzuna_app_key = adzuna_app_key
        self.jsearch_key = jsearch_key
    
    def search_jooble(self, keywords: str, location: str = "remote", max_results: int = 5) -> List[Dict]:
        """Search jobs using Jooble API"""
        jobs = []
        if not self.jooble_key:
            logger.warning("JOOBLE_API_KEY not configured")
            return jobs
        
        try:
            jooble_url = f"https://jooble.org/api/{self.jooble_key}"
            
            # Enhanced location mapping for Nigerian searches
            if any(nigerian_term in location.lower() for nigerian_term in ['nigeria', 'lagos', 'abuja', 'calabar']):
                location = 'Nigeria'
            
            jooble_params = {
                "keywords": keywords,
                "location": location,
                "page": 1
            }
            
            response = requests.post(jooble_url, json=jooble_params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('jobs', [])[:max_results]:
                    jobs.append({
                        'title': job.get('title', 'No title'),
                        'company': job.get('company', 'Unknown'),
                        'link': job.get('link', '#'),
                        'location': job.get('location', 'Remote'),
                        'salary': job.get('salary', ''),
                        'description': job.get('snippet', ''),
                        'job_type': '',
                        'source': 'Jooble'
                    })
                logger.info(f"Jooble found {len(jobs)} jobs")
            else:
                logger.error(f"Jooble API error: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Jooble: {str(e)}')
        
        return jobs
    
    def search_adzuna(self, keywords: str, location: str = "remote", max_results: int = 5) -> List[Dict]:
        """Search jobs using Adzuna API with enhanced Nigerian support"""
        jobs = []
        if not self.adzuna_app_id or not self.adzuna_app_key:
            logger.warning("Adzuna credentials not configured")
            return jobs
        
        try:
            # Enhanced location mapping
            location_map = {
                'remote': 'us',
                'new york, ny': 'us', 
                'san francisco, ca': 'us',
                'london, uk': 'gb',
                'berlin, de': 'de',
                'toronto, on': 'ca',
                'uk': 'gb',
                'united kingdom': 'gb',
                'usa': 'us',
                'united states': 'us',
                # Nigerian locations - use US API but with location-specific search
                'nigeria': 'us',
                'lagos': 'us',
                'abuja': 'us',
                'calabar': 'us',
                'port harcourt': 'us',
                'kano': 'us',
                'ibadan': 'us'
            }
            
            country = location_map.get(location.lower(), 'us')
            base_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            
            # Enhanced query building for Nigerian locations
            what_query = keywords
            where_query = ''
            
            if any(nigerian_city in location.lower() for nigerian_city in ['nigeria', 'lagos', 'abuja', 'calabar', 'port harcourt', 'kano', 'ibadan']):
                what_query = f"{keywords} Nigeria"
                where_query = location
            elif location and location.lower() != 'remote':
                where_query = location
            
            params = {
                'app_id': self.adzuna_app_id,
                'app_key': self.adzuna_app_key,
                'what': what_query,
                'results_per_page': max_results,
                'sort_by': 'relevance'
            }
            
            if where_query:
                params['where'] = where_query
            
            response = requests.get(base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('results', [])[:max_results]:
                    salary_min = job.get('salary_min', 0)
                    salary_max = job.get('salary_max', 0)
                    salary = ''
                    if salary_min and salary_max:
                        currency = '$' if country in ['us', 'ca'] else '£' if country == 'gb' else '€' if country == 'de' else '$'
                        salary = f"{currency}{salary_min:,.0f} - {currency}{salary_max:,.0f}"
                    
                    jobs.append({
                        'title': job.get('title', 'No title'),
                        'company': job.get('company', {}).get('display_name', 'Unknown'),
                        'link': job.get('redirect_url', '#'),
                        'location': job.get('location', {}).get('display_name', 'Remote'),
                        'salary': salary,
                        'description': job.get('description', '')[:200],
                        'job_type': job.get('contract_time', ''),
                        'source': 'Adzuna'
                    })
                logger.info(f"Adzuna found {len(jobs)} jobs")
            else:
                logger.error(f"Adzuna API error: {response.status_code} - {response.text}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Adzuna: {str(e)}')
        
        return jobs
    
    def search_jsearch(self, keywords: str, location: str = "", max_results: int = 5) -> List[Dict]:
        """Search jobs using JSearch API with fixed headers (following Grok's recommendation)"""
        jobs = []
        if not self.jsearch_key:
            logger.warning("JSEARCH_API_KEY not configured")
            return jobs
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            
            # Enhanced query building for Nigerian searches
            if location and location.lower() != 'remote':
                if any(nigerian_city in location.lower() for nigerian_city in ['nigeria', 'lagos', 'abuja', 'calabar', 'port harcourt']):
                    query = f"{keywords} {location} Nigeria"
                else:
                    query = f"{keywords} {location}"
            else:
                query = keywords
            
            # Parameters as recommended by Grok
            params = {
                "query": query,
                "page": 1,
                "num_pages": 1
            }
            
            # Headers exactly as recommended by Grok
            headers = {
                "X-RapidAPI-Key": self.jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            # Small delay to avoid rate limiting
            time.sleep(0.5)
            
            response = requests.get(url, headers=headers, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                job_data = data.get('data', [])
                
                if not job_data:
                    logger.info("JSearch returned no job data")
                    return jobs
                
                for job in job_data[:max_results]:
                    # Extract salary information
                    salary = ""
                    salary_min = job.get('job_salary_min')
                    salary_max = job.get('job_salary_max')
                    salary_currency = job.get('job_salary_currency', 'USD')
                    salary_period = job.get('job_salary_period', 'YEAR')
                    
                    if salary_min and salary_max:
                        currency_symbol = '$' if salary_currency == 'USD' else '₦' if salary_currency == 'NGN' else '£' if salary_currency == 'GBP' else salary_currency
                        period = '/year' if salary_period == 'YEAR' else '/month' if salary_period == 'MONTH' else '/hour' if salary_period == 'HOUR' else ''
                        salary = f"{currency_symbol}{salary_min:,} - {currency_symbol}{salary_max:,}{period}"
                    
                    # Build location string
                    job_city = job.get('job_city', '')
                    job_state = job.get('job_state', '')
                    job_country = job.get('job_country', '')
                    
                    job_location = ', '.join(filter(None, [job_city, job_state, job_country]))
                    
                    jobs.append({
                        'title': job.get('job_title', 'No title'),
                        'company': job.get('employer_name', 'Unknown'),
                        'link': job.get('job_apply_link', '#'),
                        'location': job_location or 'Remote',
                        'salary': salary,
                        'description': (job.get('job_description', '') or '')[:200],
                        'job_type': job.get('job_employment_type', ''),
                        'source': 'JSearch'
                    })
                    
                logger.info(f"JSearch found {len(jobs)} jobs")
                
            elif response.status_code == 403:
                logger.error(f"JSearch API 403 Forbidden - Check API key validity")
            elif response.status_code == 429:
                logger.warning(f"JSearch API rate limited (429)")
            else:
                logger.error(f"JSearch API error: {response.status_code} - {response.text[:200]}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching JSearch: {str(e)}')
        except Exception as e:
            logger.error(f'Unexpected error in JSearch: {str(e)}')
        
        return jobs
