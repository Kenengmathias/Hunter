#!/usr/bin/env python3
import requests
import time
import os
from dotenv import load_dotenv
import concurrent.futures
from typing import List, Dict

load_dotenv()

def test_single_proxy(proxy_string: str) -> Dict:
    """Test a single proxy and return results"""
    try:
        parts = proxy_string.strip().split(':')
        if len(parts) == 4:
            ip, port, username, password = parts
            proxy_dict = {
                'http': f'http://{username}:{password}@{ip}:{port}',
                'https': f'http://{username}:{password}@{ip}:{port}'
            }
            proxy_name = f"{ip}:{port}"
        else:
            return {'proxy': proxy_string, 'status': 'invalid_format', 'response_time': None, 'ip': None}
        
        # Test the proxy
        start_time = time.time()
        response = requests.get(
            'http://httpbin.org/ip',
            proxies=proxy_dict,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            return {
                'proxy': proxy_name,
                'status': 'working',
                'response_time': round(response_time, 2),
                'ip': data.get('origin', 'unknown'),
                'full_config': proxy_dict
            }
        else:
            return {'proxy': proxy_name, 'status': f'error_{response.status_code}', 'response_time': None, 'ip': None}
            
    except requests.exceptions.Timeout:
        return {'proxy': proxy_string, 'status': 'timeout', 'response_time': None, 'ip': None}
    except requests.exceptions.ProxyError as e:
        return {'proxy': proxy_string, 'status': f'proxy_error: {str(e)[:50]}', 'response_time': None, 'ip': None}
    except Exception as e:
        return {'proxy': proxy_string, 'status': f'error: {str(e)[:50]}', 'response_time': None, 'ip': None}

def test_all_proxies():
    """Test all proxies from environment"""
    proxy_list = os.getenv('PROXY_LIST', '')
    if not proxy_list:
        print("❌ No PROXY_LIST found in .env file")
        return
    
    proxies = [proxy.strip() for proxy in proxy_list.split(',') if proxy.strip()]
    print(f"🧪 Testing {len(proxies)} proxies...")
    print("=" * 60)
    
    # Test proxies in parallel
    working_proxies = []
    failed_proxies = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_proxy = {executor.submit(test_single_proxy, proxy): proxy for proxy in proxies}
        
        for future in concurrent.futures.as_completed(future_to_proxy):
            result = future.result()
            
            if result['status'] == 'working':
                working_proxies.append(result)
                print(f"✅ {result['proxy']} - {result['response_time']}s - IP: {result['ip']}")
            else:
                failed_proxies.append(result)
                print(f"❌ {result['proxy']} - {result['status']}")
    
    print("=" * 60)
    print(f"✅ Working proxies: {len(working_proxies)}")
    print(f"❌ Failed proxies: {len(failed_proxies)}")
    
    if working_proxies:
        print("\n🔧 Working proxy configurations:")
        for proxy in working_proxies:
            print(f"   • {proxy['proxy']} ({proxy['response_time']}s)")
        
        # Create filtered proxy list
        working_proxy_strings = []
        original_proxies = [proxy.strip() for proxy in proxy_list.split(',') if proxy.strip()]
        
        for working in working_proxies:
            for original in original_proxies:
                if working['proxy'] in original:
                    working_proxy_strings.append(original)
                    break
        
        print(f"\n📋 Updated PROXY_LIST for .env (only working proxies):")
        print("PROXY_LIST=" + ",".join(working_proxy_strings))
        
        # Save to file
        with open('working_proxies.txt', 'w') as f:
            f.write("PROXY_LIST=" + ",".join(working_proxy_strings))
        print("\n💾 Saved working proxies to 'working_proxies.txt'")
    else:
        print("\n⚠️  No working proxies found!")
        print("Consider:")
        print("   • Check your Webshare account status")
        print("   • Verify proxy credentials")
        print("   • Try without proxies temporarily")

if __name__ == "__main__":
    test_all_proxies()
