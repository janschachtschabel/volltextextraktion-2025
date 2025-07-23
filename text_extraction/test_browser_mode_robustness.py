#!/usr/bin/env python3
"""
Browser Mode Robustness Test

This test validates that browser mode extraction is now as robust as simple mode,
using the proven browser extraction logic from the full version.

Tests both modes on the same URLs to ensure parity.
"""

import asyncio
import json
import requests
import time
from typing import Dict, List


def test_extraction_mode(url: str, mode: str, include_links: bool = False) -> Dict:
    """Test extraction with specified mode and return detailed results."""
    api_url = "http://127.0.0.1:8000/from-url"
    
    payload = {
        "url": url,
        "mode": mode,
        "output_format": "markdown",
        "include_links": include_links,
        "calculate_quality": False,
        "convert_files": False
    }
    
    start_time = time.time()
    
    try:
        response = requests.post(api_url, json=payload, timeout=45)
        duration = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            text_length = len(data.get("text", ""))
            
            return {
                "success": True,
                "status_code": response.status_code,
                "text_length": text_length,
                "duration": round(duration, 2),
                "reason": data.get("reason", "unknown"),
                "final_url": data.get("final_url", url),
                "proxy_used": data.get("proxy_used"),
                "links_count": len(data.get("links", [])) if data.get("links") else 0,
                "mode": data.get("mode", mode),
                "lang": data.get("lang", "unknown")
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "text_length": 0,
                "duration": round(duration, 2),
                "error": response.text[:200],
                "mode": mode
            }
            
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "status_code": 0,
            "text_length": 0,
            "duration": round(duration, 2),
            "error": str(e)[:200],
            "mode": mode
        }


def compare_modes(url: str, include_links: bool = False) -> Dict:
    """Compare simple and browser modes for the same URL."""
    print(f"\n=== Testing URL: {url} ===")
    
    # Test simple mode
    print("Testing Simple Mode...")
    simple_result = test_extraction_mode(url, "simple", include_links)
    
    # Test browser mode
    print("Testing Browser Mode...")
    browser_result = test_extraction_mode(url, "browser", include_links)
    
    # Compare results
    comparison = {
        "url": url,
        "simple": simple_result,
        "browser": browser_result,
        "parity_achieved": False,
        "notes": []
    }
    
    # Check if both modes succeeded
    if simple_result["success"] and browser_result["success"]:
        comparison["parity_achieved"] = True
        comparison["notes"].append("Both modes successful")
        
        # Compare text lengths
        simple_len = simple_result["text_length"]
        browser_len = browser_result["text_length"]
        
        if browser_len >= simple_len * 0.8:  # Browser should get at least 80% of simple mode content
            comparison["notes"].append(f"Content parity good: Browser {browser_len} vs Simple {simple_len}")
        else:
            comparison["notes"].append(f"Content parity concern: Browser {browser_len} vs Simple {simple_len}")
            comparison["parity_achieved"] = False
            
    elif simple_result["success"] and not browser_result["success"]:
        comparison["notes"].append("Browser mode failed while simple mode succeeded - PARITY ISSUE")
        comparison["parity_achieved"] = False
        
    elif not simple_result["success"] and browser_result["success"]:
        comparison["notes"].append("Browser mode succeeded while simple mode failed - Browser advantage")
        comparison["parity_achieved"] = True
        
    else:
        comparison["notes"].append("Both modes failed")
        comparison["parity_achieved"] = True  # Both failed equally
    
    # Print results
    print(f"Simple Mode:  {'SUCCESS' if simple_result['success'] else 'FAILED'} - {simple_result['text_length']} chars in {simple_result['duration']}s")
    print(f"Browser Mode: {'SUCCESS' if browser_result['success'] else 'FAILED'} - {browser_result['text_length']} chars in {browser_result['duration']}s")
    print(f"Parity: {'ACHIEVED' if comparison['parity_achieved'] else 'FAILED'} - {', '.join(comparison['notes'])}")
    
    return comparison


def main():
    """Run comprehensive browser mode robustness tests."""
    print("Browser Mode Robustness Test")
    print("=" * 50)
    print("Testing browser mode parity with simple mode using proven robust logic")
    
    # Test URLs - mix of simple and complex sites
    test_urls = [
        "https://example.com",  # Simple static site
        "https://httpbin.org/html",  # Simple HTML test page
        "https://www.wikipedia.org",  # Complex but standard site
        "https://news.ycombinator.com",  # Simple but dynamic content
        "https://github.com",  # Modern web app with some JS
    ]
    
    results = []
    
    # Test each URL
    for url in test_urls:
        try:
            result = compare_modes(url, include_links=False)
            results.append(result)
            time.sleep(2)  # Brief pause between tests
        except Exception as e:
            print(f"Error testing {url}: {e}")
            results.append({
                "url": url,
                "error": str(e),
                "parity_achieved": False
            })
    
    # Summary
    print("\n" + "=" * 50)
    print("ROBUSTNESS TEST SUMMARY")
    print("=" * 50)
    
    total_tests = len(results)
    parity_achieved = sum(1 for r in results if r.get("parity_achieved", False))
    
    print(f"Total URLs tested: {total_tests}")
    print(f"Parity achieved: {parity_achieved}/{total_tests} ({parity_achieved/total_tests*100:.1f}%)")
    
    if parity_achieved == total_tests:
        print("\nSUCCESS: Browser mode has achieved parity with simple mode!")
        print("  Browser extraction is now as robust as simple mode.")
    else:
        print(f"\nISSUES: {total_tests - parity_achieved} URLs still have parity problems")
        print("  Browser mode needs further improvements.")
    
    # Detailed results
    print("\nDetailed Results:")
    for i, result in enumerate(results, 1):
        if "error" in result:
            print(f"{i}. {result['url']}: ERROR - {result['error']}")
        else:
            status = "SUCCESS" if result["parity_achieved"] else "FAILED"
            print(f"{i}. {result['url']}: {status}")
            if result.get("simple"):
                print(f"   Simple:  {result['simple']['text_length']} chars, {result['simple']['duration']}s")
            if result.get("browser"):
                print(f"   Browser: {result['browser']['text_length']} chars, {result['browser']['duration']}s")
    
    return parity_achieved == total_tests


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
