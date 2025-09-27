import os
import logging
import traceback
from flask import Flask, request, render_template, flash, g
from dotenv import load_dotenv
from job_aggregator import JobAggregator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    load_dotenv()
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'hunter_secret_key_fallback')
    app.config['DEBUG'] = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # API Keys from environment
    API_KEYS = {
        'jooble_key': os.getenv('JOOBLE_API_KEY'),
        'adzuna_app_id': os.getenv('ADZUNA_APP_ID'),
        'adzuna_app_key': os.getenv('ADZUNA_APP_KEY'),
        'jsearch_key': os.getenv('JSEARCH_API_KEY')
    }
    
    # Proxy configuration (add your Webshare proxies here)
    PROXY_LIST = []
    proxy_string = os.getenv('PROXY_LIST', '')
    if proxy_string:
        PROXY_LIST = [proxy.strip() for proxy in proxy_string.split(',') if proxy.strip()]
    
    def get_job_aggregator():
        """Get or create job aggregator instance"""
        if 'job_aggregator' not in g:
            g.job_aggregator = JobAggregator(
                proxy_list=PROXY_LIST,
                **API_KEYS
            )
        return g.job_aggregator
    
    @app.route('/', methods=['GET', 'POST'])
    def index():
        """Main job search page"""
        jobs = []
        search_performed = False
        
        if request.method == 'POST':
            try:
                # Get form data
                job_title = request.form.get('job_title', '').strip()
                location = request.form.get('location', '').strip()
                job_type = request.form.get('job_type', 'all')
                include_local = request.form.get('include_local') == 'on'
                max_results = int(request.form.get('max_results', 20))
                
                # Validate input
                if not job_title:
                    flash('Please enter a job title or keywords.')
                    return render_template('index.html')
                
                # Log search attempt
                logger.info(f"Job search: '{job_title}' in '{location}' type:'{job_type}' local:{include_local}")
                
                # Get aggregator and search
                aggregator = get_job_aggregator()
                jobs = aggregator.search_all_sources(
                    keywords=job_title,
                    location=location,
                    job_type=job_type,
                    max_results_per_source=max_results // 4,  # Distribute across sources
                    include_local=include_local
                )
                
                search_performed = True
                
                if jobs:
                    flash(f'Found {len(jobs)} jobs matching your search.')
                else:
                    flash('No jobs found. Try different keywords or location.')
                    
            except Exception as e:
                logger.error(f"Search error: {traceback.format_exc()}")
                flash(f'Search error: {str(e)}. Please try again.')
        
        return render_template('index.html', 
                             jobs=jobs, 
                             search_performed=search_performed)
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {'status': 'ok', 'message': 'Hunter job search is running'}
    
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 Error: {request.url}")
        flash('Page not found.')
        return render_template('index.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 Error: {traceback.format_exc()}")
        flash('An internal error occurred. Please try again.')
        return render_template('index.html'), 500
    
    @app.before_request
    def before_request():
        """Log each request"""
        logger.info(f"{request.method} {request.path} - {request.remote_addr}")
    
    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv('PORT', 8000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Starting Hunter Job Search on {host}:{port}")
    app.run(debug=debug, host=host, port=port)
