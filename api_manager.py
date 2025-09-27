import requests
import logging
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
            else:
                logger.error(f"Jooble API error: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Jooble: {str(e)}')
        
        return jobs
    
    def search_adzuna(self, keywords: str, location: str = "remote", max_results: int = 5) -> List[Dict]:
        """Search jobs using Adzuna API"""
        jobs = []
        if not self.adzuna_app_id or not self.adzuna_app_key:
            logger.warning("Adzuna credentials not configured")
            return jobs
        
        try:
            location_map = {
                'remote': 'us',
                'new york, ny': 'us', 
                'san francisco, ca': 'us',
                'london, uk': 'gb',
                'berlin, de': 'de',
                'toronto, on': 'ca',
                'nigeria': 'ng',
                'lagos': 'ng',
                'abuja': 'ng',
                'calabar': 'ng'
            }
            
            country = location_map.get(location.lower(), 'us')
            base_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            params = {
                'app_id': self.adzuna_app_id,
                'app_key': self.adzuna_app_key,
                'what': keywords,
                'results_per_page': max_results
            }
            
            response = requests.get(base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('results', [])[:max_results]:
                    salary_min = job.get('salary_min', 0)
                    salary_max = job.get('salary_max', 0)
                    salary = ''
                    if salary_min and salary_max:
                        currency = '$' if country == 'us' else '₦' if country == 'ng' else '$'
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
            else:
                logger.error(f"Adzuna API error: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching Adzuna: {str(e)}')
        
        return jobs
    
    def search_jsearch(self, keywords: str, location: str = "", max_results: int = 5) -> List[Dict]:
        """Search jobs using JSearch API"""
        jobs = []
        if not self.jsearch_key:
            logger.warning("JSEARCH_API_KEY not configured")
            return jobs
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            query = f"{keywords} in {location}" if location else keywords
            querystring = {
                "query": query,
                "page": "1",
                "num_pages": "1",
                "date_posted": "all"
            }
            
            headers = {
                "X-RapidAPI-Key": self.jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('data', [])[:max_results]:
                    # Extract salary information
                    salary = ""
                    salary_min = job.get('job_salary_min')
                    salary_max = job.get('job_salary_max')
                    salary_currency = job.get('job_salary_currency', 'USD')
                    
                    if salary_min and salary_max:
                        currency_symbol = ' if salary_currency == 'USD' else '₦' if salary_currency == 'NGN' else salary_currency
                        salary = f"{currency_symbol}{salary_min:,} - {currency_symbol}{salary_max:,}"
                    
                    jobs.append({
                        'title': job.get('job_title', 'No title'),
                        'company': job.get('employer_name', 'Unknown'),
                        'link': job.get('job_apply_link', '#'),
                        'location': job.get('job_city', '') + ', ' + job.get('job_country', ''),
                        'salary': salary,
                        'description': job.get('job_description', '')[:200],
                        'job_type': job.get('job_employment_type', ''),
                        'source': 'JSearch'
                    })
            else:
                logger.error(f"JSearch API error: {response.status_code}")
                
        except requests.RequestException as e:
            logger.error(f'Error searching JSearch: {str(e)}')
        
        return jobs
