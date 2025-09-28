#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from api_manager import APIManager
from jobberman_scraper import JobbermanScraper
from proxy_manager import ProxyManager
from user_agent_manager import UserAgentManager

load_dotenv()

def test_apis():
    """Test all API sources individually"""
    print("🧪 Testing Individual Job Sources")
    print("=" * 40)
    
    # Initialize API Manager
    api_manager = APIManager(
        jooble_key=os.getenv('JOOBLE_API_KEY'),
        adzuna_app_id=os.getenv('ADZUNA_APP_ID'),
        adzuna_app_key=os.getenv('ADZUNA_APP_KEY'),
        jsearch_key=os.getenv('JSEARCH_API_KEY')
    )
    
    # Test queries
    test_cases = [
        ('Developer', 'Nigeria'),
        ('Developer', 'UK'),
        ('Marketing', 'Remote')
    ]
    
    for keywords, location in test_cases:
        print(f"\n🔍 Testing: '{keywords}' in '{location}'")
        print("-" * 30)
        
        # Test JSearch
        try:
            jsearch_jobs = api_manager.search_jsearch(keywords, location, 3)
            print(f"✅ JSearch: {len(jsearch_jobs)} jobs")
            if jsearch_jobs:
                print(f"   Sample: {jsearch_jobs[0]['title']} at {jsearch_jobs[0]['company']}")
        except Exception as e:
            print(f"❌ JSearch failed: {str(e)}")
        
        # Test Jooble
        try:
            jooble_jobs = api_manager.search_jooble(keywords, location, 3)
            print(f"✅ Jooble: {len(jooble_jobs)} jobs")
            if jooble_jobs:
                print(f"   Sample: {jooble_jobs[0]['title']} at {jooble_jobs[0]['company']}")
        except Exception as e:
            print(f"❌ Jooble failed: {str(e)}")
        
        # Test Adzuna
        try:
            adzuna_jobs = api_manager.search_adzuna(keywords, location, 3)
            print(f"✅ Adzuna: {len(adzuna_jobs)} jobs")
            if adzuna_jobs:
                print(f"   Sample: {adzuna_jobs[0]['title']} at {adzuna_jobs[0]['company']}")
        except Exception as e:
            print(f"❌ Adzuna failed: {str(e)}")

def test_jobberman():
    """Test Jobberman scraper"""
    print(f"\n🧪 Testing Jobberman Scraper")
    print("-" * 30)
    
    try:
        proxy_manager = ProxyManager()
        ua_manager = UserAgentManager()
        jobberman = JobbermanScraper(proxy_manager, ua_manager)
        
        jobs = jobberman.search_jobs("Developer", "Lagos", max_results=3)
        print(f"✅ Jobberman: {len(jobs)} jobs")
        if jobs:
            for i, job in enumerate(jobs[:2]):
                print(f"   {i+1}. {job['title']} at {job.get('company', 'Unknown')}")
    except Exception as e:
        print(f"❌ Jobberman failed: {str(e)}")

if __name__ == "__main__":
    test_apis()
    test_jobberman()
    print(f"\n✅ Individual testing complete!")
