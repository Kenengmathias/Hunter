import os
import logging
import traceback
import asyncio
import aiohttp
import random
import time
from flask import Flask, request, render_template, flash, jsonify
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from urllib.parse import urljoin, quote_plus
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    load_dotenv()
    
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hunter_secret_key_fallback')
    
    class Config:
        JOOBLE_KEY = os.getenv('JOOBLE_API_KEY')
        ADZUNA_APP_ID = os.getenv('ADZUNA_APP_ID')
        ADZUNA_APP_KEY = os.getenv('ADZUNA_APP_KEY')
        JSEARCH_API_KEY = os.getenv('JSEARCH_API_KEY')
        
        # Proxy settings
        PROXY_USERNAME = os.getenv('PROXY_USERNAME')
        PROXY_PASSWORD = os.getenv('PROXY_PASSWORD')
        PROXY_ENDPOINT = os.getenv('PROXY_ENDPOINT')
        PROXY_PORT = os.getenv('PROXY_PORT')
    
    config = Config()
    ua = UserAgent()

    class ProxyRotator:
        def __init__(self):
            self.proxies = self._load_proxies()
            self.current_index = 0
        
        def _load_proxies(self):
            if not all([config.PROXY_USERNAME, config.PROXY_PASSWORD, config.PROXY_ENDPOINT, config.PROXY_PORT]):
                logger.warning("Proxy configuration incomplete, running without proxies")
                return []
            
            proxy_auth = f"{config.PROXY_USERNAME}:{config.PROXY_PASSWORD}"
            proxy_url = f"http://{proxy_auth}@{config.PROXY_ENDPOINT}:{config.PROXY_PORT}"
            
            return [
                {'http': proxy_url, 'https': proxy_url}
            ]
        
        def get_proxy(self):
            if not self.proxies:
                return None
            proxy = self.proxies[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.proxies)
            return proxy

    proxy_rotator = ProxyRotator()

    class JobScraper:
        def __init__(self):
            self.session = requests.Session()
            self.headers = self._get_headers()
        
        def _get_headers(self):
            return {
                'User-Agent': ua.random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0'
            }
        
        def _make_request(self, url, params=None):
            try:
                proxy = proxy_rotator.get_proxy()
                self.headers['User-Agent'] = ua.random
                
                response = self.session.get(
                    url, 
                    params=params,
                    headers=self.headers,
                    proxies=proxy,
                    timeout=15,
                    verify=True
                )
                
                # Add random delay to avoid detection
                time.sleep(random.uniform(1, 3))
                
                return response
            except Exception as e:
                logger.error(f"Request failed: {str(e)}")
                return None
        
        def scrape_indeed(self, keywords, location="", max_results=10):
            jobs = []
            try:
                base_url = "https://indeed.com/jobs"
                params = {
                    'q': keywords,
                    'l': location,
                    'start': 0
                }
                
                response = self._make_request(base_url, params)
                if not response or response.status_code != 200:
                    logger.error(f"Indeed request failed: {response.status_code if response else 'No response'}")
                    return jobs
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Indeed job cards selector (may need updates)
                job_cards = soup.find_all('div', class_='job_seen_beacon') or soup.find_all('a', {'data-jk': True})
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find('span', {'title': True}) or card.find('h2', class_='jobTitle')
                        company_elem = card.find('span', class_='companyName') or card.find('data-testid', 'company-name')
                        location_elem = card.find('div', {'data-testid': 'job-location'}) or card.find('div', class_='companyLocation')
                        
                        if title_elem:
                            title = title_elem.get('title') or title_elem.get_text(strip=True)
                            company = company_elem.get_text(strip=True) if company_elem else 'Unknown Company'
                            job_location = location_elem.get_text(strip=True) if location_elem else location
                            
                            # Try to get job URL
                            link_elem = card.find('a', href=True)
                            job_url = urljoin('https://indeed.com', link_elem['href']) if link_elem else '#'
                            
                            jobs.append({
                                'title': title,
                                'company': company,
                                'location': job_location,
                                'link': job_url,
                                'source': 'Indeed',
                                'job_type': 'Not specified',
                                'salary': 'Not specified'
                            })
                    except Exception as e:
                        logger.error(f"Error parsing Indeed job card: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Indeed scraping error: {str(e)}")
            
            return jobs
        
        def scrape_jobberman(self, keywords, location="nigeria", max_results=10):
            jobs = []
            try:
                base_url = "https://www.jobberman.com/jobs"
                params = {
                    'q': keywords,
                    'location': location
                }
                
                response = self._make_request(base_url, params)
                if not response or response.status_code != 200:
                    logger.error(f"Jobberman request failed: {response.status_code if response else 'No response'}")
                    return jobs
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Jobberman job cards selector
                job_cards = soup.find_all('div', class_='job-item') or soup.find_all('article', class_='job-item')
                
                for card in job_cards[:max_results]:
                    try:
                        title_elem = card.find('h3') or card.find('h2') or card.find('a', class_='job-title')
                        company_elem = card.find('p', class_='company-name') or card.find('span', class_='company')
                        location_elem = card.find('span', class_='job-location') or card.find('p', class_='location')
                        
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            company = company_elem.get_text(strip=True) if company_elem else 'Unknown Company'
                            job_location = location_elem.get_text(strip=True) if location_elem else location
                            
                            # Try to get job URL
                            link_elem = card.find('a', href=True)
                            job_url = urljoin('https://www.jobberman.com', link_elem['href']) if link_elem else '#'
                            
                            jobs.append({
                                'title': title,
                                'company': company,
                                'location': job_location,
                                'link': job_url,
                                'source': 'Jobberman',
                                'job_type': 'Not specified',
                                'salary': 'Not specified'
                            })
                    except Exception as e:
                        logger.error(f"Error parsing Jobberman job card: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Jobberman scraping error: {str(e)}")
            
            return jobs

    job_scraper = JobScraper()

    def search_jsearch_api(keywords, location="", job_type="", max_results=10):
        jobs = []
        if not config.JSEARCH_API_KEY:
            logger.warning("JSEARCH_API_KEY not configured")
            return jobs
        
        try:
            url = "https://jsearch.p.rapidapi.com/search"
            
            querystring = {
                "query": f"{keywords} in {location}" if location else keywords,
                "page": "1",
                "num_pages": "1"
            }
            
            if job_type and job_type != "all":
                querystring["employment_types"] = job_type.upper()
            
            headers = {
                "X-RapidAPI-Key": config.JSEARCH_API_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
            
            response = requests.get(url, headers=headers, params=querystring, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('data', [])[:max_results]:
                    jobs.append({
                        'title': job.get('job_title', 'No title'),
                        'company': job.get('employer_name', 'Unknown'),
                        'location': job.get('job_city', 'Remote'),
                        'link': job.get('job_apply_link', '#'),
                        'source': 'JSearch',
                        'job_type': job.get('job_employment_type', 'Not specified'),
                        'salary': job.get('job_salary', 'Not specified')
                    })
            else:
                logger.error(f"JSearch API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f'Error searching JSearch: {str(e)}')
        
        return jobs

    def search_jooble(keywords, location="remote", max_results=5):
        jobs = []
        if not config.JOOBLE_KEY:
            logger.warning("JOOBLE_API_KEY not configured")
            return jobs
        
        try:
            jooble_url = f"https://jooble.org/api/{config.JOOBLE_KEY}"
            jooble_params = {"keywords": keywords, "location": location, "page": 1}
            response = requests.post(jooble_url, json=jooble_params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('jobs', [])[:max_results]:
                    jobs.append({
                        'title': job.get('title', 'No title'),
                        'company': job.get('company', 'Unknown'),
                        'link': job.get('link', '#'),
                        'location': job.get('location', 'Remote'),
                        'source': 'Jooble',
                        'job_type': 'Not specified',
                        'salary': 'Not specified'
                    })
            else:
                logger.error(f"Jooble API error: {response.status_code}")
        except Exception as e:
            logger.error(f'Error searching Jooble: {str(e)}')
        
        return jobs

    def search_adzuna(keywords, location="remote", max_results=5):
        jobs = []
        if not config.ADZUNA_APP_ID or not config.ADZUNA_APP_KEY:
            logger.warning("Adzuna credentials not configured")
            return jobs
        
        try:
            location_map = {'remote': 'us', 'new york, ny': 'us', 'san francisco, ca': 'us', 'london, uk': 'gb', 'nigeria': 'ng', 'lagos': 'ng', 'abuja': 'ng', 'calabar': 'ng'}
            country = location_map.get(location.lower(), 'ng')
            base_url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            params = {'app_id': config.ADZUNA_APP_ID, 'app_key': config.ADZUNA_APP_KEY, 'what': keywords, 'results_per_page': max_results}
            response = requests.get(base_url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                for job in data.get('results', [])[:max_results]:
                    salary = job.get('salary_min', 0)
                    salary_display = f"₦{salary:,.0f}" if country == 'ng' and salary else 'Not specified'
                    
                    jobs.append({
                        'title': job.get('title', 'No title'),
                        'company': job.get('company', {}).get('display_name', 'Unknown'),
                        'link': job.get('redirect_url', '#'),
                        'location': job.get('location', {}).get('display_name', 'Remote'),
                        'source': 'Adzuna',
                        'job_type': job.get('contract_time', 'Not specified'),
                        'salary': salary_display
                    })
            else:
                logger.error(f"Adzuna API error: {response.status_code}")
        except Exception as e:
            logger.error(f'Error searching Adzuna: {str(e)}')
        
        return jobs

    def aggregate_all_jobs(keywords, location="", job_type="", local_jobs=False):
        all_jobs = []
        
        # Determine search strategy
        if local_jobs and location.lower() in ['calabar', 'nigeria', 'lagos', 'abuja', 'port harcourt']:
            # Focus on local Nigerian sources
            all_jobs.extend(job_scraper.scrape_jobberman(keywords, location, 15))
            all_jobs.extend(search_adzuna(keywords, location, 10))
        else:
            # Global search
            all_jobs.extend(search_jsearch_api(keywords, location, job_type, 15))
            all_jobs.extend(job_scraper.scrape_indeed(keywords, location, 10))
            all_jobs.extend(search_jooble(keywords, location, 10))
            all_jobs.extend(search_adzuna(keywords, location, 10))
            
            # Add Nigerian jobs if not specified location
            if not location:
                all_jobs.extend(job_scraper.scrape_jobberman(keywords, "nigeria", 5))
        
        # Remove duplicates based on title and company
        unique_jobs = []
        seen_jobs = set()
        
        for job in all_jobs:
            job_signature = f"{job['title'].lower()}_{job['company'].lower()}"
            if job_signature not in seen_jobs:
                seen_jobs.add(job_signature)
                unique_jobs.append(job)
        
        return unique_jobs

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/search', methods=['POST'])
    def search_jobs():
        try:
            keywords = request.form.get('keywords', '').strip()
            location = request.form.get('location', '').strip()
            job_type = request.form.get('job_type', 'all')
            local_jobs = 'local_jobs' in request.form
            
            if not keywords:
                flash('Please enter job keywords')
                return render_template('index.html')
            
            jobs = aggregate_all_jobs(keywords, location, job_type, local_jobs)
            
            return render_template('results.html', jobs=jobs, query={
                'keywords': keywords,
                'location': location,
                'job_type': job_type,
                'local_jobs': local_jobs,
                'total_jobs': len(jobs)
            })
            
        except Exception as e:
            logger.error(f"Search error: {str(e)}")
            flash(f'Search error: {str(e)}')
            return render_template('index.html')

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('index.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 Error: {traceback.format_exc()}")
        flash('An internal error occurred. Please try again.')
        return render_template('index.html'), 500

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=8000)
