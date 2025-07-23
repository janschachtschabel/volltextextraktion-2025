"""
Content Extraction Strategies Module

This module provides multiple content extraction strategies for different
types of web pages and content structures.
"""

import logging
from typing import Optional
from playwright.async_api import Page as async_api_Page

logger = logging.getLogger(__name__)


async def extract_with_multiple_strategies(page: async_api_Page) -> str:
    """
    Extract content using multiple strategies and return the best result.
    
    Tries different extraction methods:
    1. Trafilatura extraction from page HTML
    2. Direct text content extraction
    3. Readable content extraction
    4. Full page content as fallback
    
    Returns the first strategy that produces substantial content (>500 chars).
    """
    logger.debug("Starting multi-strategy content extraction")
    
    strategies = [
        ("trafilatura", extract_with_trafilatura),
        ("text_content", extract_text_content),
        ("readable_content", extract_readable_content),
        ("full_content", extract_full_content)
    ]
    
    for strategy_name, strategy_func in strategies:
        try:
            content = await strategy_func(page)
            if content and len(content.strip()) > 500:
                logger.debug(f"Strategy '{strategy_name}' successful: {len(content)} characters")
                return content.strip()
            else:
                logger.debug(f"Strategy '{strategy_name}' insufficient content: {len(content) if content else 0} characters")
        except Exception as e:
            logger.warning(f"Strategy '{strategy_name}' failed: {e}")
    
    # If no strategy produces substantial content, return the best we have
    logger.debug("No strategy produced substantial content, using fallback")
    try:
        return await extract_full_content(page)
    except Exception as e:
        logger.error(f"All extraction strategies failed: {e}")
        return ""


async def extract_with_trafilatura(page: async_api_Page) -> str:
    """
    Extract content using Trafilatura from page HTML.
    """
    try:
        import trafilatura
        
        html_content = await page.content()
        extracted = trafilatura.extract(html_content)
        return extracted or ""
        
    except ImportError:
        logger.warning("Trafilatura not available")
        return ""
    except Exception as e:
        logger.warning(f"Trafilatura extraction failed: {e}")
        return ""


async def extract_text_content(page: async_api_Page) -> str:
    """
    Extract text content directly from DOM.
    
    Focuses on main content areas and filters out navigation elements.
    """
    try:
        content = await page.evaluate("""
            () => {
                // Try to find main content areas first
                const mainSelectors = [
                    'main', 'article', '.content', '#content', 
                    '.main', '#main', '.post', '.entry'
                ];
                
                for (const selector of mainSelectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        return element.textContent || element.innerText || '';
                    }
                }
                
                // Fallback to body content
                return document.body.textContent || document.body.innerText || '';
            }
        """)
        
        return content.strip() if content else ""
        
    except Exception as e:
        logger.warning(f"Text content extraction failed: {e}")
        return ""


async def extract_readable_content(page: async_api_Page) -> str:
    """
    Extract readable content by filtering out navigation and ads.
    
    Uses DOM traversal to identify and extract only meaningful content.
    """
    try:
        content = await page.evaluate("""
            () => {
                // Elements to skip (navigation, ads, etc.)
                const skipSelectors = [
                    'nav', 'header', 'footer', 'aside', '.sidebar',
                    '.navigation', '.menu', '.ads', '.advertisement',
                    '.social', '.share', '.comments', '.comment'
                ];
                
                // Create a TreeWalker to traverse text nodes
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: function(node) {
                            // Skip if parent element is in skip list
                            let parent = node.parentElement;
                            while (parent) {
                                for (const selector of skipSelectors) {
                                    if (parent.matches && parent.matches(selector)) {
                                        return NodeFilter.FILTER_REJECT;
                                    }
                                }
                                parent = parent.parentElement;
                            }
                            
                            // Skip if text is too short or only whitespace
                            const text = node.textContent.trim();
                            if (text.length < 10) {
                                return NodeFilter.FILTER_REJECT;
                            }
                            
                            // Check if element is visible
                            const element = node.parentElement;
                            if (element) {
                                const style = window.getComputedStyle(element);
                                if (style.display === 'none' || style.visibility === 'hidden') {
                                    return NodeFilter.FILTER_REJECT;
                                }
                            }
                            
                            return NodeFilter.FILTER_ACCEPT;
                        }
                    }
                );
                
                const textParts = [];
                let node;
                while (node = walker.nextNode()) {
                    textParts.push(node.textContent.trim());
                }
                
                return textParts.join(' ');
            }
        """)
        
        return content.strip() if content else ""
        
    except Exception as e:
        logger.warning(f"Readable content extraction failed: {e}")
        return ""


async def extract_full_content(page: async_api_Page) -> str:
    """
    Extract full page content as fallback.
    
    Simply gets all text content from the page body.
    """
    try:
        content = await page.evaluate("() => document.body.textContent || document.body.innerText || ''")
        return content.strip() if content else ""
        
    except Exception as e:
        logger.warning(f"Full content extraction failed: {e}")
        return ""
