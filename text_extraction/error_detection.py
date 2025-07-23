"""
Error Detection Module

This module provides functionality to detect error pages and implement
fallback extraction strategies when primary methods fail.
"""

import logging
from typing import Tuple, Optional
from playwright.async_api import Page as async_api_Page

logger = logging.getLogger(__name__)


async def detect_error_page(page: async_api_Page, content: str) -> Tuple[bool, Optional[str]]:
    """
    Detect if the current page is an error page.
    
    Analyzes page title, content, and status indicators to identify:
    - HTTP error pages (404, 403, 500, etc.)
    - Cloudflare challenge pages
    - CAPTCHA pages
    - Blocked/restricted access pages
    
    Args:
        page: Playwright page object
        content: Extracted page content
        
    Returns:
        tuple: (is_error_page, error_type)
    """
    try:
        # Get page title and URL for analysis
        title = await page.title()
        url = page.url
        
        # Check for common error indicators in title
        error_titles = [
            '404', '403', '500', '502', '503', 'not found', 'access denied',
            'forbidden', 'error', 'blocked', 'captcha', 'challenge'
        ]
        
        title_lower = title.lower()
        for error_indicator in error_titles:
            if error_indicator in title_lower:
                logger.debug(f"Error page detected via title: {error_indicator}")
                return True, f"error_title_{error_indicator}"
        
        # Check for error indicators in content
        if content:
            content_lower = content.lower()
            
            # HTTP error indicators
            http_errors = [
                'page not found', '404 error', 'not found',
                'access denied', '403 forbidden', 'forbidden',
                'internal server error', '500 error', 'server error',
                'bad gateway', '502 error', '503 error'
            ]
            
            for error_indicator in http_errors:
                if error_indicator in content_lower:
                    logger.debug(f"Error page detected via content: {error_indicator}")
                    return True, f"http_error_{error_indicator.replace(' ', '_')}"
            
            # Cloudflare/security challenge indicators
            security_indicators = [
                'cloudflare', 'checking your browser', 'ddos protection',
                'security check', 'captcha', 'verify you are human',
                'ray id', 'blocked by', 'access restricted'
            ]
            
            for security_indicator in security_indicators:
                if security_indicator in content_lower:
                    logger.debug(f"Security challenge detected: {security_indicator}")
                    return True, f"security_challenge_{security_indicator.replace(' ', '_')}"
        
        # Check if content is suspiciously short (might be an error page)
        if content and len(content.strip()) < 100:
            # Additional checks for short content
            short_content_errors = [
                'error', 'not found', 'forbidden', 'denied', 'blocked'
            ]
            
            content_lower = content.lower()
            for error_indicator in short_content_errors:
                if error_indicator in content_lower:
                    logger.debug(f"Short error content detected: {error_indicator}")
                    return True, f"short_error_{error_indicator}"
        
        # Check page status via JavaScript if possible
        try:
            page_status = await page.evaluate("""
                () => {
                    // Check for common error page indicators in DOM
                    const errorSelectors = [
                        '.error', '#error', '.not-found', '.forbidden',
                        '.blocked', '.captcha', '.challenge'
                    ];
                    
                    for (const selector of errorSelectors) {
                        if (document.querySelector(selector)) {
                            return selector;
                        }
                    }
                    
                    return null;
                }
            """)
            
            if page_status:
                logger.debug(f"Error page detected via DOM selector: {page_status}")
                return True, f"dom_error_{page_status.replace('.', '').replace('#', '')}"
                
        except Exception as e:
            logger.debug(f"Could not check page status via JavaScript: {e}")
        
        return False, None
        
    except Exception as e:
        logger.warning(f"Error page detection failed: {e}")
        return False, None


async def fallback_extraction_strategies(page: async_api_Page) -> Tuple[str, str]:
    """
    Fallback extraction strategies when enhanced SPA extraction fails.
    
    Tries multiple basic extraction methods as a last resort:
    1. Network idle wait + basic extraction
    2. Content indicators wait + extraction
    3. Progressive wait + extraction
    4. Basic extraction without waiting
    
    Returns:
        tuple: (content, extraction_method)
    """
    logger.debug("Starting fallback extraction strategies")
    
    strategies = [
        ("networkidle_wait", networkidle_extraction),
        ("content_indicators", content_indicators_extraction),
        ("progressive_wait", progressive_extraction),
        ("basic_extraction", basic_extraction)
    ]
    
    for strategy_name, strategy_func in strategies:
        try:
            content = await strategy_func(page)
            if content and len(content.strip()) > 50:  # Minimum threshold
                logger.debug(f"Fallback strategy '{strategy_name}' successful: {len(content)} characters")
                return content.strip(), strategy_name
        except Exception as e:
            logger.warning(f"Fallback strategy '{strategy_name}' failed: {e}")
    
    logger.warning("All fallback strategies failed")
    return "", "fallback_failed"


async def networkidle_extraction(page: async_api_Page) -> str:
    """
    Extract content after waiting for network idle.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
        return await page.evaluate("() => document.body.textContent || ''")
    except Exception as e:
        logger.warning(f"Network idle extraction failed: {e}")
        return ""


async def content_indicators_extraction(page: async_api_Page) -> str:
    """
    Extract content after waiting for content indicators.
    """
    try:
        # Wait for common content indicators
        await page.wait_for_selector("main, article, .content, #content", timeout=10000)
        return await page.evaluate("() => document.body.textContent || ''")
    except Exception as e:
        logger.warning(f"Content indicators extraction failed: {e}")
        return ""


async def progressive_extraction(page: async_api_Page) -> str:
    """
    Extract content using progressive waiting.
    """
    try:
        import asyncio
        
        # Progressive waiting with content monitoring
        for i in range(5):
            await asyncio.sleep(1)
            content = await page.evaluate("() => document.body.textContent || ''")
            if content and len(content.strip()) > 100:
                return content
        
        # Return whatever we have
        return await page.evaluate("() => document.body.textContent || ''")
        
    except Exception as e:
        logger.warning(f"Progressive extraction failed: {e}")
        return ""


async def basic_extraction(page: async_api_Page) -> str:
    """
    Basic content extraction without special waiting.
    """
    try:
        return await page.evaluate("() => document.body.textContent || ''")
    except Exception as e:
        logger.warning(f"Basic extraction failed: {e}")
        return ""
