"""Browser-Based Extraction Module - Refactored Implementation

This module provides browser-based text extraction using Playwright for
JavaScript-heavy websites and SPAs that require dynamic content rendering.

Refactored for better maintainability with modular architecture.
"""

import asyncio
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from playwright import async_api

# Windows-specific fix for Playwright/asyncio compatibility
if sys.platform.startswith('win'):
    try:
        # Set Windows-compatible event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# Import specialized modules
from .spa_extraction import enhanced_spa_extraction
from .error_detection import fallback_extraction_strategies

try:
    from .markitdown_converter import (
        MarkItDownConversionError,
        get_markitdown_converter,
        is_markitdown_available,
    )
    MARKITDOWN_CONVERTER_READY = True
except ImportError:
    MarkItDownConversionError = Exception  # type: ignore

    def get_markitdown_converter(*args, **kwargs):  # type: ignore
        raise ImportError("MarkItDown converter not available")

    def is_markitdown_available() -> bool:  # type: ignore
        return False

    MARKITDOWN_CONVERTER_READY = False

logger = logging.getLogger(__name__)


def _detect_language(text: str) -> str:
    """Detect language of text using py3langid."""
    try:
        import py3langid
        if text and len(text.strip()) > 10:
            return py3langid.classify(text[:1000])[0]
    except ImportError:
        pass
    return "en"


def _format_from_content_type(content_type: str) -> Optional[str]:
    """Map HTTP content types to file extensions understood by MarkItDown."""
    mapping = {
        "application/pdf": "pdf",
        "application/x-pdf": "pdf",
        "application/acrobat": "pdf",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-powerpoint": "ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "text/plain": "txt",
        "text/csv": "csv",
        "text/html": "html",
    }

    return mapping.get(content_type)


async def _wait_for_content_indicators(page: async_api.Page, timeout: int = 10000) -> None:
    """Wait for common content indicators that suggest the page has loaded."""
    try:
        # Wait for any of these common content indicators
        await page.wait_for_selector(
            'main, article, .content, #content, .post, .article, p',
            timeout=timeout
        )
    except Exception:
        # If no specific indicators found, just wait a bit
        await asyncio.sleep(2)


async def _progressive_content_wait(page: async_api.Page) -> None:
    """Progressive waiting strategy with content size monitoring."""
    previous_length = 0
    stable_count = 0
    
    for i in range(5):  # Max 5 iterations
        await asyncio.sleep(1)
        try:
            current_content = await page.content()
            current_length = len(current_content)
            
            if current_length == previous_length:
                stable_count += 1
                if stable_count >= 2:  # Content stable for 2 iterations
                    break
            else:
                stable_count = 0
                previous_length = current_length
        except Exception:
            break


async def wait_for_spa_stability(page: async_api.Page, network_idle_timeout=30000, stable_time=500, max_total_timeout=35000):
    """
    Wartet erst auf networkidle, dann darauf, dass das DOM für `stable_time` ms unverändert bleibt.
    
    Args:
        page: Playwright page instance
        network_idle_timeout: Timeout für Netzwerk-Ruhe in ms
        stable_time: Zeit ohne DOM-Mutationen in ms
        max_total_timeout: Maximaler Gesamt-Timeout in ms
    """
    try:
        # 1. Auf Netzwerkruhe warten
        logger.debug(f"Waiting for network idle (timeout: {network_idle_timeout}ms)")
        await page.wait_for_load_state('networkidle', timeout=network_idle_timeout)
        
        # 2. MutationObserver im Seitenkontext einrichten
        logger.debug("Setting up DOM mutation observer")
        await page.evaluate("""
            () => {
                // Letzte Mutation-Zeit merken
                window.__lastMutation = performance.now();
                // Observer, der Timestamp bei jeder Mutation updatet
                window.__mutationObserver = new MutationObserver(() => {
                    window.__lastMutation = performance.now();
                });
                window.__mutationObserver.observe(document, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    characterData: true
                });
            }
        """)

        # 3. Auf eine Periode ohne Änderungen warten
        remaining_timeout = max_total_timeout - network_idle_timeout
        logger.debug(f"Waiting for DOM stability ({stable_time}ms without mutations, timeout: {remaining_timeout}ms)")
        await page.wait_for_function(
            f"() => performance.now() - window.__lastMutation > {stable_time}",
            timeout=remaining_timeout
        )
        
        logger.debug("DOM stability achieved")
        
    except Exception as e:
        logger.warning(f"SPA stability wait failed: {e}")
    finally:
        # 4. Observer aufräumen (immer ausführen, auch bei Fehlern)
        try:
            await page.evaluate("""
                () => {
                    if (window.__mutationObserver) {
                        window.__mutationObserver.disconnect();
                        delete window.__mutationObserver;
                        delete window.__lastMutation;
                    }
                }
            """)
            logger.debug("Mutation observer cleaned up")
        except Exception as cleanup_error:
            logger.warning(f"Observer cleanup failed: {cleanup_error}")


async def _extract_page_content(page: async_api.Page) -> str:
    """Extract page content with multiple fallback strategies."""
    try:
        # Primary: Get full HTML content
        content = await page.content()
        if content and len(content) > 100:
            return content
    except Exception:
        pass
    
    try:
        # Fallback: Get visible text content
        visible_text = await page.evaluate("""
            () => {
                // Remove script and style elements
                const scripts = document.querySelectorAll('script, style');
                scripts.forEach(el => el.remove());
                
                // Get text content
                return document.body.innerText || document.body.textContent || '';
            }
        """)
        
        if visible_text and len(visible_text.strip()) > 50:
            # Wrap in basic HTML structure
            return f"<html><body>{visible_text}</body></html>"
    except Exception:
        pass
    
    return ""


async def extract_with_browser(
    url: str,
    browser: Optional[async_api.Browser] = None,
    output_format: str = "markdown",
    target_language: str = "auto",
    preference: str = "none",
    convert_files: bool = False,
    max_file_size_mb: int = 50,
    conversion_timeout: int = 60,
    include_links: bool = False,
    proxies: Optional[List[str]] = None,
    timeout: int = 30,
    calculate_quality: bool = False
) -> Dict[str, Any]:
    """
    Extract text from URL using browser automation with Playwright.
    
    This function provides robust browser-based extraction with multiple
    fallback strategies for JavaScript-heavy sites and SPAs. Uses fresh
    browser instances for maximum stability.
    
    Args:
        browser: Optional browser instance (if None, creates fresh instance)
    """
    logger.error(f"DEBUG: extract_with_browser called with output_format='{output_format}'")
    logger.info(f"Starting robust browser extraction for URL: {url}")
    
    # Prepare MarkItDown converter for file downloads when requested
    converter = None
    if convert_files:
        if MARKITDOWN_CONVERTER_READY and is_markitdown_available():
            try:
                converter = get_markitdown_converter(
                    max_file_size_mb=max_file_size_mb,
                    timeout_seconds=conversion_timeout,
                )
            except Exception as converter_error:  # pragma: no cover - defensive
                logger.warning(f"Could not initialize MarkItDown converter: {converter_error}")
                converter = None
        else:
            logger.info("MarkItDown converter not available in browser mode")

    # Create fresh browser instance if none provided
    fresh_browser = None
    fresh_playwright = None
    if browser is None:
        try:
            from playwright.async_api import async_playwright
            fresh_playwright = await async_playwright().start()

            # Enhanced browser launch configuration for stability
            primary_args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--hide-scrollbars',
                '--mute-audio',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-logging',
                '--disable-permissions-api',
                '--disable-presentation-api',
                '--disable-speech-api',
                '--disable-file-system',
                '--disable-sensors',
                '--disable-geolocation',
                '--disable-notifications',
                '--disable-features=TranslateUI',
                '--disable-hang-monitor',
                '--disable-prompt-on-repost',
                '--disable-domain-reliability',
            ]

            if sys.platform.startswith('win'):
                primary_args = [
                    '--disable-gpu',
                    '--disable-extensions',
                    '--disable-background-timer-throttling',
                    '--mute-audio',
                    '--disable-notifications',
                ]

            launch_options: Dict[str, Any] = {
                'headless': True,
                'args': primary_args,
                'timeout': 60000,
            }

            if not sys.platform.startswith('win'):
                launch_options['slow_mo'] = 50

            try:
                fresh_browser = await fresh_playwright.chromium.launch(**launch_options)
            except Exception as launch_error:
                logger.warning(f"Primary Chromium launch configuration failed: {launch_error}")
                fallback_args = ['--disable-gpu']
                if not sys.platform.startswith('win'):
                    fallback_args.insert(0, '--no-sandbox')

                launch_options.pop('slow_mo', None)
                launch_options['args'] = fallback_args

                fresh_browser = await fresh_playwright.chromium.launch(**launch_options)
            browser = fresh_browser
            logger.debug("Created fresh browser instance with enhanced stability configuration")
        except Exception as e:
            logger.error(f"Failed to create fresh browser instance: {e}")
            return {
                "text": "",
                "status": 500,
                "reason": "browser_creation_failed",
                "message": str(e),
                "lang": "en",
                "mode": "browser",
                "final_url": url,
                "converted": False,
                "proxy_used": None,
                "links": [] if include_links else None,
                "quality_metrics": None
            }
    
    # Proxy rotation logic for browser mode
    proxy_list = list(proxies) if proxies else [None]
    if proxies:
        random.shuffle(proxy_list)  # Random proxy selection
        logger.info(f"Using random proxy selection from {len(proxy_list)} available proxies")
    else:
        proxy_list = [None]  # None means direct connection
        logger.info("No proxies provided, using direct connection")
    
    content = None
    status_code = 500
    final_url = url
    extraction_method = "unknown"
    proxy_used = None
    
    for proxy in proxy_list:
        context = None
        page = None
        
        try:
            # Create browser context with or without proxy
            if proxy:
                proxy_used = proxy
                logger.info(f"Attempting browser request with proxy: {proxy}")
                try:
                    # Create context with proxy configuration
                    context = await browser.new_context(
                        proxy={"server": f"http://{proxy}"},
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    )
                    page = await context.new_page()
                except Exception as proxy_error:
                    logger.error(f"Error creating browser context with proxy {proxy}: {proxy_error}")
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass
                    continue
            else:
                proxy_used = None
                logger.info("Attempting browser request without proxy")
                try:
                    # Create context without proxy
                    context = await browser.new_context(
                        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    )
                    page = await context.new_page()
                except Exception as direct_error:
                    logger.error(f"Error creating browser context without proxy: {direct_error}")
                    if context:
                        try:
                            await context.close()
                        except Exception:
                            pass
                    continue
            
            # Enhanced browser configuration for better JS/SPA support
            try:
                # Set realistic headers
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9,de;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                })
                
                # Set viewport for consistent rendering
                await page.set_viewport_size({"width": 1920, "height": 1080})
                
            except Exception as config_error:
                logger.warning(f"Could not set browser configuration: {config_error}")
            
            # Navigate to the page with enhanced error handling
            navigation_successful = False
            try:
                logger.debug(f"Navigating to {url} with browser (timeout: {timeout}s)")
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=max(60000, timeout * 1000)  # At least 60 seconds for navigation
                )
        
                if response:
                    status_code = response.status
                    final_url = response.url
                    
                    # Check Content-Type for unsupported formats
                    content_type = None
                    if response.headers:
                        content_type = response.headers.get('content-type', '').lower().strip()
                        if content_type and ';' in content_type:
                            content_type = content_type.split(';')[0].strip()
                    
                    # Handle file conversion if enabled
                    if convert_files and converter:
                        try:
                            filename: Optional[str] = None
                            file_format = _format_from_content_type(content_type or "") if content_type else None

                            try:
                                parsed_final = urlparse(final_url)
                                filename = Path(parsed_final.path).name or None
                                if not file_format and filename and '.' in filename:
                                    file_format = filename.split('.')[-1].lower()
                            except Exception:
                                filename = None

                            if not file_format:
                                file_format = 'unknown'

                            if file_format and (
                                file_format == 'unknown'
                                or converter.is_convertible_format(file_format)
                            ):
                                logger.info(
                                    "Attempting file conversion for %s in browser mode: %s",
                                    file_format,
                                    final_url,
                                )
                                file_content = await response.body()
                                converted_text, conversion_metadata = await converter.convert_file_to_markdown(
                                    content=file_content,
                                    file_format=file_format,
                                    filename=filename,
                                )

                                if converted_text:
                                    result = {
                                        "text": converted_text,
                                        "status": status_code,
                                        "reason": "success",
                                        "lang": _detect_language(converted_text),
                                        "mode": "browser",
                                        "final_url": final_url,
                                        "proxy_used": proxy_used,
                                        "converted": conversion_metadata.get("converted", True),
                                        "original_format": conversion_metadata.get("original_format"),
                                        "file_size_mb": conversion_metadata.get("file_size_mb"),
                                        "links": [] if include_links else None,
                                        "quality_metrics": None,
                                    }

                                    if context:
                                        await context.close()

                                    logger.info(
                                        "Successfully converted file in browser mode (%d chars)",
                                        len(converted_text),
                                    )
                                    return result
                        except MarkItDownConversionError as conversion_error:
                            logger.warning(
                                f"File conversion failed in browser mode for {final_url}: {conversion_error}"
                            )
                        except Exception as conversion_error:  # pragma: no cover - defensive
                            logger.error(
                                f"Unexpected error during file conversion for {final_url}: {conversion_error}"
                            )
                        # Continue with normal extraction when conversion fails

                    navigation_successful = True
                    logger.debug(f"Navigation successful: {status_code} - {final_url}")
                
            except Exception as goto_error:
                logger.warning(f"Navigation error for {url}: {goto_error}")
                # Try alternative navigation approach
                try:
                    logger.debug("Trying alternative navigation with networkidle")
                    response = await page.goto(
                        url,
                        wait_until="networkidle",
                        timeout=max(90000, timeout * 1500)  # Even longer timeout for networkidle
                    )
                    if response:
                        status_code = response.status
                        final_url = response.url
                        navigation_successful = True
                        logger.debug(f"Alternative navigation successful: {status_code}")
                except Exception as alt_error:
                    logger.warning(f"Alternative navigation also failed: {alt_error}")
                    # Continue anyway - page might be partially loaded
    
            # Enhanced waiting strategy for JS/SPA content with advanced detection
            if navigation_successful:
                try:
                    # Advanced SPA and JavaScript content handling using modular approach
                    extraction_result = await enhanced_spa_extraction(page, url)
                    
                    if extraction_result.get('content'):
                        content = extraction_result['content']
                        extraction_method = extraction_result.get('extraction_method', 'enhanced_spa')
                        
                        # Check if it's an error page but still has content
                        if extraction_result.get('is_error_page'):
                            logger.info(f"Error page detected and processed: {extraction_result.get('error_type', 'unknown')}")
                        else:
                            logger.info(f"Enhanced SPA extraction successful: {len(content)} chars")
                    else:
                        # Fallback to original strategies with improvements
                        content, extraction_method = await fallback_extraction_strategies(page)
                        
                except Exception as spa_error:
                    logger.warning(f"Enhanced SPA extraction failed: {spa_error}")
                    # Fallback to basic extraction
                    content, extraction_method = await fallback_extraction_strategies(page)
            
            if content:
                logger.info(f"Browser extraction successful via {extraction_method}: {len(content)} chars")
                # Close context and break out of proxy loop on success
                if context:
                    try:
                        await context.close()
                        logger.debug("Browser context closed successfully")
                    except Exception as close_error:
                        logger.warning(f"Error closing browser context: {close_error}")
                break
            else:
                logger.warning(f"Browser extraction failed - no content retrieved")
                if context:
                    try:
                        await context.close()
                        logger.debug("Browser context closed after failure")
                    except Exception as close_error:
                        logger.warning(f"Error closing browser context after failure: {close_error}")
                if proxy:
                    continue  # Try next proxy
                else:
                    break  # No more options
            
        except Exception as page_error:
            logger.error(f"Error creating/using page with proxy {proxy}: {page_error}")
            if context:
                try:
                    await context.close()
                    logger.debug("Browser context closed after page error")
                except Exception as close_error:
                    logger.warning(f"Error closing browser context after page error: {close_error}")
            if proxy:
                continue  # Try next proxy
            else:
                break  # No more options
    
    # If we reach here and have no content, return error
    if not content:
        logger.error(f"All browser extraction attempts failed for {url}")
        
        # Cleanup fresh browser instances on failure
        if fresh_browser:
            try:
                await fresh_browser.close()
            except Exception:
                pass
        
        if fresh_playwright:
            try:
                await fresh_playwright.stop()
            except Exception:
                pass
        
        return {
            "text": "",
            "status": 500,
            "reason": "browser_extraction_failed",
            "message": "All browser extraction attempts failed",
            "lang": "en",
            "mode": "browser",
            "final_url": url,
            "converted": False,
            "proxy_used": proxy_used,
            "links": [] if include_links else None,
            "quality_metrics": None
        }
    
    # Process extracted content
    logger.error(f"DEBUG: Starting content processing with output_format='{output_format}', content length={len(content)}")
    try:
        # Use trafilatura to extract clean text from HTML
        import trafilatura
        
        # Map our output formats to trafilatura-compatible formats
        trafilatura_format_map = {
            "text": "txt",
            "markdown": "markdown",
            "raw_text": "txt"
        }
        trafilatura_format = trafilatura_format_map.get(output_format, "txt")
        
        logger.error(f"DEBUG: Output format mapping: {output_format} -> {trafilatura_format}")
        
        try:
            extracted_text = trafilatura.extract(
                content,
                output_format=trafilatura_format,
                target_language=target_language if target_language != "auto" else None,
                include_comments=False,
                include_tables=True
            )
        except Exception as e:
            logger.error(f"DEBUG: trafilatura.extract failed with format '{trafilatura_format}': {e}")
            # Try without output_format parameter
            try:
                extracted_text = trafilatura.extract(
                    content,
                    target_language=target_language if target_language != "auto" else None,
                    include_comments=False,
                    include_tables=True
                )
                logger.error(f"DEBUG: trafilatura.extract succeeded without output_format")
            except Exception as e2:
                logger.error(f"DEBUG: trafilatura.extract failed even without output_format: {e2}")
                extracted_text = None
        
        if not extracted_text:
            # Fallback: extract from raw HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, 'html.parser')
            extracted_text = soup.get_text(strip=True)
        
        # Extract links if requested
        links = []
        if include_links and content:
            try:
                from .link_extraction import extract_and_classify_links
                links = extract_and_classify_links(content, final_url)
            except Exception as e:
                logger.warning(f"Link extraction failed: {e}")
                links = []
        
        # Calculate quality metrics if requested
        quality_metrics = None
        if calculate_quality and extracted_text:
            try:
                from .quality import calculate_quality_metrics as _calculate_quality

                quality_metrics = _calculate_quality(extracted_text)
            except Exception as e:
                logger.warning(f"Quality calculation failed: {e}")
        
        # Detect language
        detected_language = _detect_language(extracted_text or "")
        
        # Determine appropriate message based on HTTP status and content quality
        text_length = len(extracted_text or "")
        if status_code == 404:
            status_message = f"HTTP 404 detected, but {text_length} characters successfully extracted. This may be intentional anti-crawling behavior."
        elif status_code >= 400:
            status_message = f"HTTP {status_code} detected, but {text_length} characters successfully extracted. Content appears valid despite error status."
        elif status_code == 200:
            status_message = "Text extracted successfully"
        else:
            status_message = f"HTTP {status_code} - Text extracted successfully ({text_length} characters)"
        
        # Generate timestamp and origin information
        extraction_timestamp = datetime.now(timezone.utc).isoformat()
        extraction_origin = "realtime_crawl"  # This is a live extraction
        
        result = {
            "text": extracted_text or "",
            "status": status_code,
            "reason": "success",
            "message": status_message,
            "lang": detected_language,
            "mode": "browser",
            "final_url": final_url,
            "converted": False,
            "original_format": None,
            "file_size_mb": None,
            "proxy_used": proxy_used,
            "links": links if include_links else None,
            "quality_metrics": quality_metrics,
            "extraction_timestamp": extraction_timestamp,
            "extraction_origin": extraction_origin
        }
        
        logger.info(f"Browser extraction completed successfully: {len(extracted_text or '')} characters")
        
        # Cleanup fresh browser instances
        if fresh_browser:
            try:
                await fresh_browser.close()
                logger.debug("Fresh browser instance closed")
            except Exception as cleanup_error:
                logger.warning(f"Error closing fresh browser: {cleanup_error}")
        
        if fresh_playwright:
            try:
                await fresh_playwright.stop()
                logger.debug("Fresh playwright instance stopped")
            except Exception as cleanup_error:
                logger.warning(f"Error stopping fresh playwright: {cleanup_error}")
        
        return result
        
    except Exception as e:
        logger.error(f"Content processing failed for {url}: {e}")
        
        # Cleanup fresh browser instances on error
        if fresh_browser:
            try:
                await fresh_browser.close()
            except Exception:
                pass
        
        if fresh_playwright:
            try:
                await fresh_playwright.stop()
            except Exception:
                pass
        
        return {
            "text": "",
            "status": 500,
            "reason": "content_processing_failed",
            "message": str(e),
            "lang": "en",
            "mode": "browser",
            "final_url": final_url,
            "converted": False,
            "proxy_used": proxy_used,
            "links": [] if include_links else None,
            "quality_metrics": None
        }


# All SPA extraction functions moved to spa_extraction.py module


# SPA detection functions moved to spa_detection.py module


# SPA waiting and monitoring functions moved to spa_extraction.py module


# Content extraction strategies moved to content_extraction_strategies.py module


# Error detection and fallback strategies moved to error_detection.py module


# Fallback extraction functions moved to error_detection.py module


# SPA indicators detection function moved to spa_detection.py module
