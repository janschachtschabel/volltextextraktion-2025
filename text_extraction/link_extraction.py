"""
Link Extraction Module - Clean Implementation

This module provides link extraction and classification capabilities
for web content analysis and navigation structure understanding.

This is a clean, minimal implementation that addresses all historical problems
while providing comprehensive link analysis features.
"""

import logging
import re
from typing import Any, Dict, List
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def extract_links_from_html(html_content: str, base_url: str) -> List[Dict[str, Any]]:
    """
    Extract and classify links from HTML content.
    
    Returns a list of link dictionaries with URL, text, and classification info.
    Always returns a list (never None) to prevent null issues in API responses.
    """
    try:
        if not html_content or not base_url:
            return []
        
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        base_domain = urlparse(base_url).netloc.lower()
        
        # Find all anchor tags with href attributes
        for anchor in soup.find_all('a', href=True):
            try:
                href = anchor.get('href', '').strip()
                if not href or href.startswith('#') or href.startswith('javascript:'):
                    continue
                
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                
                # Get link text
                link_text = anchor.get_text(strip=True)
                if not link_text:
                    link_text = anchor.get('title', '').strip()
                if not link_text:
                    link_text = href
                
                # Classify link as internal or external
                link_domain = urlparse(absolute_url).netloc.lower()
                is_internal = link_domain == base_domain or link_domain == '' or link_domain.endswith('.' + base_domain)
                
                # Determine link type
                link_type = classify_link_type(absolute_url, link_text, anchor)
                
                link_info = {
                    "url": absolute_url,
                    "text": link_text[:200],  # Limit text length
                    "is_internal": is_internal,
                    "link_type": link_type
                }
                
                links.append(link_info)
                
            except Exception as e:
                logger.warning(f"Failed to process link {anchor}: {e}")
                continue
        
        # Remove duplicates while preserving order
        seen_urls = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen_urls:
                seen_urls.add(link["url"])
                unique_links.append(link)
        
        logger.info(f"Extracted {len(unique_links)} unique links from HTML content")
        return unique_links
        
    except Exception as e:
        logger.error(f"Link extraction failed: {e}")
        return []  # Always return empty list instead of None


def classify_link_type(url: str, text: str, anchor_element) -> str:
    """
    Classify the type of link based on URL, text, and HTML attributes.
    
    Returns classification like 'navigation', 'content', 'external', 'download', etc.
    """
    try:
        url_lower = url.lower()
        text_lower = text.lower()
        
        # Check for download links
        download_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                              '.zip', '.rar', '.tar', '.gz', '.mp3', '.mp4', '.avi']
        if any(ext in url_lower for ext in download_extensions):
            return 'download'
        
        # Check for media links
        media_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp', '.mp4', '.avi', '.mov']
        if any(ext in url_lower for ext in media_extensions):
            return 'media'
        
        # Check for email links
        if url_lower.startswith('mailto:'):
            return 'email'
        
        # Check for phone links
        if url_lower.startswith('tel:'):
            return 'phone'
        
        # Check for social media
        social_domains = ['facebook.com', 'twitter.com', 'linkedin.com', 'instagram.com', 
                         'youtube.com', 'github.com', 'reddit.com']
        if any(domain in url_lower for domain in social_domains):
            return 'social'
        
        # Check for navigation indicators
        nav_indicators = ['menu', 'nav', 'home', 'about', 'contact', 'services', 
                         'products', 'blog', 'news', 'help', 'support']
        if any(indicator in text_lower for indicator in nav_indicators):
            return 'navigation'
        
        # Check for content indicators
        content_indicators = ['read more', 'continue reading', 'full article', 'details', 
                             'learn more', 'view', 'see']
        if any(indicator in text_lower for indicator in content_indicators):
            return 'content'
        
        # Check HTML attributes for additional context
        if anchor_element:
            classes = ' '.join(anchor_element.get('class', [])).lower()
            if 'button' in classes or 'btn' in classes:
                return 'button'
            if 'nav' in classes or 'menu' in classes:
                return 'navigation'
        
        # Default classification
        return 'content'
        
    except Exception as e:
        logger.warning(f"Link classification failed: {e}")
        return 'unknown'


def filter_and_deduplicate_links(links: List[Dict[str, Any]], max_links: int = 100) -> List[Dict[str, Any]]:
    """
    Filter and deduplicate links, keeping the most relevant ones.
    
    This function helps manage large numbers of links by prioritizing
    internal links and removing low-quality duplicates.
    """
    try:
        if not links:
            return []
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_links = []
        for link in links:
            if link["url"] not in seen_urls:
                seen_urls.add(link["url"])
                unique_links.append(link)
        
        # Sort by relevance (internal links first, then by type)
        type_priority = {
            'content': 1,
            'navigation': 2,
            'download': 3,
            'button': 4,
            'social': 5,
            'media': 6,
            'email': 7,
            'phone': 8,
            'unknown': 9
        }
        
        def link_priority(link):
            internal_priority = 0 if link.get('is_internal', False) else 1
            type_priority_value = type_priority.get(link.get('link_type', 'unknown'), 9)
            return (internal_priority, type_priority_value)
        
        sorted_links = sorted(unique_links, key=link_priority)
        
        # Limit to max_links
        if len(sorted_links) > max_links:
            sorted_links = sorted_links[:max_links]
            logger.info(f"Limited links to {max_links} most relevant ones")
        
        return sorted_links
        
    except Exception as e:
        logger.error(f"Link filtering failed: {e}")
        return links[:max_links] if links else []


def analyze_link_patterns(links: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Analyze patterns in extracted links to provide insights about the page structure.
    
    Returns statistics about link types, internal vs external ratio, etc.
    """
    try:
        if not links:
            return {
                "total_links": 0,
                "internal_links": 0,
                "external_links": 0,
                "link_types": {},
                "internal_ratio": 0.0
            }
        
        total_links = len(links)
        internal_count = sum(1 for link in links if link.get('is_internal', False))
        external_count = total_links - internal_count
        
        # Count link types
        link_types = {}
        for link in links:
            link_type = link.get('link_type', 'unknown')
            link_types[link_type] = link_types.get(link_type, 0) + 1
        
        internal_ratio = internal_count / total_links if total_links > 0 else 0.0
        
        analysis = {
            "total_links": total_links,
            "internal_links": internal_count,
            "external_links": external_count,
            "link_types": link_types,
            "internal_ratio": round(internal_ratio, 2)
        }
        
        return analysis
        
    except Exception as e:
        logger.error(f"Link pattern analysis failed: {e}")
        return {
            "total_links": 0,
            "internal_links": 0,
            "external_links": 0,
            "link_types": {},
            "internal_ratio": 0.0
        }


def extract_and_classify_links(html_content: str, base_url: str) -> List[Dict[str, Any]]:
    """
    Extract and classify links from HTML content - compatibility function for browser_helpers.
    
    This is a wrapper around extract_links_from_html for backward compatibility.
    
    Args:
        html_content: Raw HTML content
        base_url: Base URL for resolving relative links
        
    Returns:
        List of link dictionaries with metadata
    """
    return extract_links_from_html(html_content, base_url)
