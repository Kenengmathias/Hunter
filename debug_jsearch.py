#!/usr/bin/env python3
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

def debug_jsearch_api():
    """Debug JSearch API issues"""
    jsearch_key = os.getenv('JSEARCH_API_KEY')
    
    if not jsearch_key:
        print("❌ JSEARCH_API_KEY not found in .env file")
        return
    
    print("🔍 Debugging JSearch API...")
    print(f"API Key: {jsearch_key[:10]}...{jsearch_key[-5:]}")
    print("=" * 50)
    
    # Test different header combinations
    test_cases = [
        {
            'name': 'Standard Headers',
            'headers': {
                "X-RapidAPI-Key": jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            }
        },
        {
            'name': 'Lowercase Headers',
            'headers': {
                "x-rapidapi-key": jsearch_key,
                "x-rapidapi-host": "jsearch.p.rapidapi.com"
            }
        },
        {
            'name': 'With User-Agent',
            'headers': {
                "X-RapidAPI-Key": jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
    ]
    
    url = "https://jsearch.p.rapidapi.com/search"
    querystring = {
        "query": "python developer",
        "page": "1",
        "num_pages": "1"
    }
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: {test_case['name']}")
        try:
            response = requests.get(
                url, 
                headers=test_case['headers'], 
                params=querystring, 
                timeout=15
            )
            
            print(f"   Status Code: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                job_count = len(data.get('data', []))
                print(f"   ✅ SUCCESS - Found {job_count} jobs")
                
                if job_count > 0:
                    sample_job = data['data'][0]
                    print(f"   Sample Job: {sample_job.get('job_title', 'N/A')}")
                    print(f"   Company: {sample_job.get('employer_name', 'N/A')}")
                break
                
            elif response.status_code == 403:
                print(f"   ❌ 403 FORBIDDEN")
                print(f"   Response: {response.text[:200]}")
                
                # Check if it's rate limit or auth issue
                if 'rate limit' in response.text.lower():
                    print("   Reason: Rate limit exceeded")
                elif 'invalid' in response.text.lower() or 'unauthorized' in response.text.lower():
                    print("   Reason: Invalid API key")
                else:
                    print("   Reason: Unknown authorization issue")
                    
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except requests.RequestException as e:
            print(f"   ❌ Request failed: {str(e)}")
    
    # Test API key validity with a simple endpoint
    print(f"\n🔑 Testing API Key Validity...")
    try:
        # Try a simpler endpoint or direct API test
        test_response = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key": jsearch_key,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            },
            params={"query": "test", "page": "1", "num_pages": "1"},
            timeout=10
        )
        
        print(f"Direct test status: {test_response.status_code}")
        
        if test_response.status_code == 200:
            print("✅ API key is valid and working!")
        elif test_response.status_code == 403:
            print("❌ API key is invalid or exceeded limits")
            print("Solutions:")
            print("   1. Check your RapidAPI dashboard")
            print("   2. Verify subscription status")
            print("   3. Check usage limits")
            print("   4. Try generating a new API key")
        else:
            print(f"⚠️  Unexpected response: {test_response.text[:300]}")
            
    except Exception as e:
        print(f"❌ API key test failed: {str(e)}")
    
    print(f"\n💡 Recommendations:")
    print("   • Check RapidAPI dashboard: https://rapidapi.com/dashboard")
    print("   • Verify JSearch subscription is active")
    print("   • Check monthly usage limits")
    print("   • Consider getting a new API key if expired")

if __name__ == "__main__":
    debug_jsearch_api()
