"""
SPA Extraction Module

This module provides specialized extraction strategies for Single Page Applications
and dynamic content loading scenarios.
"""

import logging
import asyncio
from typing import Dict, Any
from playwright.async_api import Page as async_api_Page
from .spa_detection import detect_spa_characteristics

logger = logging.getLogger(__name__)


async def enhanced_spa_extraction(page: async_api_Page, url: str) -> Dict[str, Any]:
    """
    Advanced SPA and JavaScript content extraction with intelligent detection.
    
    This function implements sophisticated strategies for handling:
    - Single Page Applications (SPAs)
    - Dynamic content loading
    - JavaScript-rendered content
    - Error page detection
    - Content stability monitoring
    - Ultra-complex SPAs like kmap.eu
    """
    logger.debug("Starting enhanced SPA extraction")
    
    # Step 1: Enhanced SPA detection with more aggressive heuristics
    is_spa = await detect_spa_characteristics(page)
    
    # Step 2: Check for ultra-complex SPAs that need special handling
    is_ultra_complex = await detect_ultra_complex_spa(page, url)
    
    # Step 3: Choose appropriate waiting strategy
    if is_ultra_complex:
        logger.debug("Ultra-complex SPA detected - using maximum aggressive strategies")
        await ultra_complex_spa_wait(page)
        extraction_method = "ultra_complex_spa"
    elif is_spa:
        logger.debug("SPA detected - using advanced waiting strategies")
        await spa_content_wait(page)
        extraction_method = "spa_optimized"
    else:
        logger.debug("Regular site detected - using standard waiting")
        await standard_content_wait(page)
        extraction_method = "standard_optimized"
    
    # Step 4: Monitor content stability with extended patience for complex SPAs
    content_stable = await monitor_content_stability(page, max_wait=15 if is_ultra_complex else 8)
    if content_stable:
        logger.debug("Content stability achieved")
    else:
        logger.debug("Content may still be loading - proceeding anyway")
    
    # Import here to avoid circular imports
    from .content_extraction_strategies import extract_with_multiple_strategies
    from .error_detection import detect_error_page
    
    # Step 5: Extract content with enhanced strategies for complex SPAs
    # Always try embedded JSON extraction first for kmap.eu
    if 'kmap.eu' in url:
        logger.debug("kmap.eu detected - trying embedded JSON extraction first")
        content = await extract_embedded_json_content(page)
        if len(content) > 500:
            logger.debug(f"Embedded JSON extraction successful: {len(content)} chars")
            extraction_method = "embedded_json_extraction"
        else:
            logger.debug("Embedded JSON extraction failed, falling back to ultra-complex strategies")
            content = await extract_ultra_complex_spa_content(page)
    elif is_ultra_complex:
        content = await extract_ultra_complex_spa_content(page)
    else:
        content = await extract_with_multiple_strategies(page)
    
    # Step 6: Detect if this is an error page
    is_error_page, error_type = await detect_error_page(page, content)
    
    return {
        'content': content,
        'extraction_method': extraction_method,
        'is_spa': is_spa,
        'is_ultra_complex': is_ultra_complex,
        'is_error_page': is_error_page,
        'error_type': error_type,
        'content_stable': content_stable
    }


async def spa_content_wait(page: async_api_Page):
    """
    Specialized waiting strategy for SPAs using robust DOM stability monitoring.
    
    Uses the advanced wait_for_spa_stability approach:
    - Network idle waiting
    - DOM mutation monitoring with timestamps
    - Automatic observer cleanup
    - Configurable stability periods
    """
    logger.debug("Starting SPA content waiting strategy with DOM stability monitoring")
    
    try:
        # Use the robust wait_for_spa_stability function
        await wait_for_spa_stability(
            page, 
            network_idle_timeout=30000,  # 30s for network idle
            stable_time=500,             # 500ms without DOM mutations
            max_total_timeout=35000      # 35s total timeout
        )
        
        # Additional SPA-specific checks
        await wait_for_spa_indicators(page)
        await check_framework_readiness(page)
        
        logger.debug("SPA content waiting completed successfully")
        
    except Exception as e:
        logger.warning(f"SPA content wait failed: {e}")
        # Fallback to basic wait
        await asyncio.sleep(3)


async def wait_for_spa_stability(page: async_api_Page, network_idle_timeout=30000, stable_time=500, max_total_timeout=35000):
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


async def wait_for_spa_indicators(page: async_api_Page):
    """Wait for common SPA loading indicators to disappear."""
    loading_selectors = [
        '.loading', '.spinner', '.loader', '[data-loading]',
        '.loading-spinner', '.loading-overlay', '.preloader',
        '[aria-label*="loading"]', '[aria-label*="Loading"]'
    ]
    
    for selector in loading_selectors:
        try:
            # Wait for loading indicator to be hidden (if it exists)
            await page.wait_for_selector(selector, state='hidden', timeout=5000)
            logger.debug(f"Loading indicator {selector} disappeared")
        except Exception:
            # Selector not found or timeout - that's fine
            continue


async def check_framework_readiness(page: async_api_Page):
    """Check if common SPA frameworks are ready."""
    try:
        # Check React readiness
        react_ready = await page.evaluate("""
            () => {
                if (window.React && window.ReactDOM) {
                    return document.readyState === 'complete';
                }
                return true; // Not a React app
            }
        """)
        
        # Check Vue readiness
        vue_ready = await page.evaluate("""
            () => {
                if (window.Vue) {
                    return document.readyState === 'complete';
                }
                return true; // Not a Vue app
            }
        """)
        
        if react_ready and vue_ready:
            logger.debug("Framework readiness confirmed")
        else:
            logger.debug("Framework not fully ready, but proceeding")
            
    except Exception as e:
        logger.debug(f"Framework readiness check failed: {e}")


async def standard_content_wait(page: async_api_Page):
    """
    Standard waiting strategy for regular websites.
    """
    logger.debug("Starting standard content wait")
    
    try:
        await page.wait_for_load_state("networkidle", timeout=8000)
        logger.debug("Standard content wait completed")
    except Exception as e:
        logger.warning(f"Standard content wait failed: {e}")


async def monitor_content_stability(page: async_api_Page, max_wait: int = 8):
    """
    Monitor content stability by checking DOM changes over time.
    
    Returns True if content appears stable, False if still changing.
    """
    logger.debug("Starting content stability monitoring")
    
    previous_content_hash = None
    stable_count = 0
    
    for i in range(max_wait):
        try:
            # Get current page content hash
            current_content = await page.content()
            current_hash = hash(current_content)
            
            if current_hash == previous_content_hash:
                stable_count += 1
                if stable_count >= 3:  # Stable for 3 seconds
                    logger.debug(f"Content stable after {i+1} seconds")
                    return True
            else:
                stable_count = 0
                previous_content_hash = current_hash
            
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.warning(f"Error during stability monitoring: {e}")
            break
    
    logger.debug("Content stability timeout reached")
    return False


async def detect_ultra_complex_spa(page: async_api_Page, url: str) -> bool:
    """
    Detect ultra-complex SPAs that require special handling.
    
    These are SPAs that:
    - Show placeholder messages like "JavaScript wird benötigt!"
    - Have complex React/Vue component trees
    - Require extensive waiting and interaction
    - Use advanced routing and state management
    """
    logger.debug("Detecting ultra-complex SPA characteristics")
    
    try:
        # Check for known ultra-complex SPA patterns
        ultra_complex_indicators = await page.evaluate("""
            () => {
                let score = 0;
                const indicators = {};
                
                // Check for placeholder messages indicating JS requirement
                const placeholderTexts = [
                    'JavaScript wird benötigt',
                    'JavaScript is required',
                    'Please enable JavaScript',
                    'This app requires JavaScript',
                    'Loading...',
                    'Wird geladen...'
                ];
                
                const bodyText = document.body.textContent || '';
                for (const placeholder of placeholderTexts) {
                    if (bodyText.includes(placeholder)) {
                        score += 3;
                        indicators.hasPlaceholder = true;
                        break;
                    }
                }
                
                // Check for complex React patterns
                if (window.React && (window.__REACT_DEVTOOLS_GLOBAL_HOOK__ || document.querySelector('[data-reactroot]'))) {
                    score += 2;
                    indicators.complexReact = true;
                }
                
                // Check for Vue with complex routing
                if (window.Vue && window.VueRouter) {
                    score += 2;
                    indicators.complexVue = true;
                }
                
                // Check for service workers (often used in complex SPAs)
                if ('serviceWorker' in navigator) {
                    score += 1;
                    indicators.hasServiceWorker = true;
                }
                
                // Check for complex state management
                if (window.Redux || window.Vuex || window.MobX) {
                    score += 2;
                    indicators.hasStateManagement = true;
                }
                
                // Check for minimal DOM content (sign of heavy JS rendering)
                const textLength = bodyText.trim().length;
                if (textLength < 500 && textLength > 0) {
                    score += 2;
                    indicators.minimalContent = true;
                }
                
                // Check for specific ultra-complex SPA domains
                const complexDomains = ['kmap.eu', 'app.', 'dashboard.', 'admin.'];
                const currentDomain = window.location.hostname;
                for (const domain of complexDomains) {
                    if (currentDomain.includes(domain)) {
                        score += 1;
                        indicators.complexDomain = true;
                        break;
                    }
                }
                
                return {
                    score: score,
                    indicators: indicators,
                    isUltraComplex: score >= 4
                };
            }
        """)
        
        logger.debug(f"Ultra-complex SPA detection score: {ultra_complex_indicators['score']}, indicators: {ultra_complex_indicators['indicators']}")
        return ultra_complex_indicators['isUltraComplex']
        
    except Exception as e:
        logger.warning(f"Error during ultra-complex SPA detection: {e}")
        return False


async def ultra_complex_spa_wait(page: async_api_Page):
    """
    Ultra-aggressive waiting strategy for complex SPAs.
    
    Uses maximum patience and multiple techniques:
    - Extended network idle waiting
    - Deep DOM mutation monitoring
    - Framework-specific initialization waiting
    - Progressive content checking
    - Interaction simulation
    """
    logger.debug("Starting ultra-complex SPA wait")
    
    try:
        # Step 1: Extended network idle wait
        logger.debug("  - Extended network idle wait...")
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except:
            pass
        
        # Step 2: Wait for framework initialization
        logger.debug("  - Waiting for framework initialization...")
        await page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    let attempts = 0;
                    const maxAttempts = 100;  // 20 seconds max
                    
                    const checkFrameworks = () => {
                        attempts++;
                        
                        // Check for React readiness
                        if (window.React && window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
                            const reactFiber = document.querySelector('[data-reactroot]');
                            if (reactFiber && reactFiber._reactInternalFiber) {
                                console.log('React fully initialized');
                                resolve();
                                return;
                            }
                        }
                        
                        // Check for Vue readiness
                        if (window.Vue && window.Vue.version) {
                            const vueApp = document.querySelector('[data-v-]');
                            if (vueApp) {
                                console.log('Vue fully initialized');
                                resolve();
                                return;
                            }
                        }
                        
                        // Check for any app-specific readiness indicators
                        if (window.app && window.app.ready) {
                            console.log('App ready state detected');
                            resolve();
                            return;
                        }
                        
                        if (attempts >= maxAttempts) {
                            console.log('Framework initialization timeout');
                            resolve();
                        } else {
                            setTimeout(checkFrameworks, 200);
                        }
                    };
                    
                    checkFrameworks();
                });
            }
        """)
        
        # Step 3: Deep DOM mutation monitoring
        logger.debug("  - Deep DOM mutation monitoring...")
        await page.evaluate("""
            () => {
                return new Promise((resolve) => {
                    let mutationCount = 0;
                    let lastMutationTime = Date.now();
                    let significantChanges = 0;
                    
                    const observer = new MutationObserver((mutations) => {
                        mutations.forEach((mutation) => {
                            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                                // Check if added nodes contain significant content
                                for (const node of mutation.addedNodes) {
                                    if (node.nodeType === Node.ELEMENT_NODE) {
                                        const text = node.textContent || '';
                                        if (text.length > 50 && !text.includes('JavaScript wird benötigt')) {
                                            significantChanges++;
                                        }
                                    }
                                }
                            }
                        });
                        
                        mutationCount++;
                        lastMutationTime = Date.now();
                    });
                    
                    observer.observe(document.body, {
                        childList: true,
                        subtree: true,
                        attributes: true,
                        attributeOldValue: true
                    });
                    
                    // Check every 500ms for stability or significant changes
                    const checkStability = () => {
                        const now = Date.now();
                        if (significantChanges >= 3) {
                            console.log('Significant content changes detected');
                            observer.disconnect();
                            resolve();
                        } else if (now - lastMutationTime > 3000) {  // 3 seconds of stability
                            console.log('DOM mutations stabilized');
                            observer.disconnect();
                            resolve();
                        } else {
                            setTimeout(checkStability, 500);
                        }
                    };
                    
                    setTimeout(checkStability, 500);
                    
                    // Maximum wait time of 15 seconds
                    setTimeout(() => {
                        observer.disconnect();
                        resolve();
                    }, 15000);
                });
            }
        """)
        
        # Step 4: Simulate user interactions to trigger content loading
        logger.debug("  - Simulating user interactions...")
        try:
            # Try clicking on potential navigation elements
            await page.evaluate("""
                () => {
                    const clickableElements = document.querySelectorAll('button, [role="button"], a[href="#"], .nav-item, .menu-item');
                    if (clickableElements.length > 0) {
                        clickableElements[0].click();
                    }
                }
            """)
            await asyncio.sleep(2)
        except:
            pass
        
        # Step 5: Force rendering through scrolling
        logger.debug("  - Force rendering through scrolling...")
        try:
            await page.evaluate("""
                () => {
                    return new Promise((resolve) => {
                        let scrollTop = 0;
                        const scrollStep = 300;
                        const maxScroll = Math.max(document.body.scrollHeight, 2000);
                        
                        const scroll = () => {
                            window.scrollTo(0, scrollTop);
                            scrollTop += scrollStep;
                            
                            if (scrollTop >= maxScroll) {
                                // Scroll back to top
                                window.scrollTo(0, 0);
                                setTimeout(resolve, 1000);
                            } else {
                                setTimeout(scroll, 200);
                            }
                        };
                        
                        scroll();
                    });
                }
            """)
        except:
            pass
        
        # Step 6: Final wait for any remaining async operations
        logger.debug("  - Final stabilization wait...")
        await asyncio.sleep(3)
        
        logger.debug("Ultra-complex SPA wait completed")
        
    except Exception as e:
        logger.warning(f"Error during ultra-complex SPA wait: {e}")


async def extract_embedded_json_content(page: async_api_Page) -> str:
    """Extract educational content from embedded JSON script tags (e.g., kmap.eu)."""
    try:
        # Get the raw HTML content
        html_content = await page.content()
        
        # Look for embedded JSON content in script tags using regex
        import re
        import json
        
        # Find script tags with embedded educational content
        script_patterns = [
            r'<script id="embedded-topic"[^>]*>(.*?)</script>',
            r'<script[^>]*type="json"[^>]*>(.*?)</script>',
            r'<script[^>]*id="[^"]*topic[^"]*"[^>]*>(.*?)</script>'
        ]
        
        extracted_content = ""
        
        for pattern in script_patterns:
            script_matches = re.findall(pattern, html_content, re.DOTALL)
            
            for script_content in script_matches:
                try:
                    # Clean up the script content
                    clean_content = script_content
                    
                    # Remove CDATA wrappers and HTML comments
                    clean_content = re.sub(r'<!--//--><!\[CDATA\[//>', '', clean_content)
                    clean_content = re.sub(r'//--><!\]\]>', '', clean_content)
                    clean_content = re.sub(r'<!--', '', clean_content)
                    clean_content = re.sub(r'-->', '', clean_content)
                    
                    # Find the JSON content between the first { and last }
                    start_brace = clean_content.find('{')
                    end_brace = clean_content.rfind('}')
                    
                    if start_brace != -1 and end_brace != -1 and end_brace > start_brace:
                        clean_content = clean_content[start_brace:end_brace + 1]
                    
                    clean_content = clean_content.strip()
                    
                    # Try to parse as JSON
                    json_data = json.loads(clean_content)
                    
                    # Extract educational content from the JSON structure
                    if json_data.get('description'):
                        # Remove HTML tags from description
                        description = re.sub(r'<[^>]*>', ' ', json_data['description'])
                        description = re.sub(r'\s+', ' ', description).strip()
                        extracted_content += f"Beschreibung:\n{description}\n\n"
                    
                    if json_data.get('summary'):
                        extracted_content += f"Zusammenfassung: {json_data['summary']}\n\n"
                    
                    if json_data.get('keywords'):
                        extracted_content += f"Schlüsselwörter: {json_data['keywords']}\n\n"
                    
                    if json_data.get('subject') and json_data.get('topic'):
                        extracted_content += f"Fach: {json_data['subject']} - Thema: {json_data['topic']}\n\n"
                    
                    if json_data.get('educationalLevel'):
                        extracted_content += f"Bildungsstufe: {json_data['educationalLevel']}\n\n"
                    
                    if json_data.get('typicalAgeRange'):
                        extracted_content += f"Altersbereich: {json_data['typicalAgeRange']}\n\n"
                    
                    # Extract attachment information
                    if json_data.get('attachments') and isinstance(json_data['attachments'], list):
                        extracted_content += "Anhänge und Ressourcen:\n"
                        for attachment in json_data['attachments']:
                            if attachment.get('name'):
                                tag_info = f" ({attachment['tag']})" if attachment.get('tag') else ""
                                extracted_content += f"- {attachment['name']}{tag_info}\n"
                        extracted_content += "\n"
                    
                    # If we found content, break out of the loop
                    if extracted_content.strip():
                        break
                        
                except (json.JSONDecodeError, Exception) as parse_error:
                    logger.debug(f"Failed to parse embedded JSON: {parse_error}")
                    continue
        
        return extracted_content.strip()
        
    except Exception as e:
        logger.warning(f"Embedded JSON extraction failed: {e}")
        return ""


async def extract_svg_interactive_content(page: async_api_Page) -> str:
    """Extract content from SVG elements and interactive educational components."""
    try:
        # Simple approach: get all text content from SVG and canvas elements
        svg_content = await page.evaluate("""
            () => {
                let content = '';
                
                // Extract from SVG elements
                const svgs = document.querySelectorAll('svg');
                for (const svg of svgs) {
                    const textElements = svg.querySelectorAll('text, tspan, title, desc');
                    for (const textEl of textElements) {
                        const text = textEl.textContent || '';
                        if (text.trim().length > 2) {
                            content += text.trim() + ' ';
                        }
                    }
                }
                
                return content.trim();
            }
        """)
        
        # Get content from elements that might contain educational material
        educational_content = await page.evaluate("""
            () => {
                let content = '';
                
                // Look for educational content containers
                const selectors = [
                    '[class*="content"]', '[class*="lesson"]', '[class*="concept"]',
                    '[class*="definition"]', '[class*="explanation"]', '[class*="description"]',
                    '[id*="content"]', '[id*="main"]', '[id*="lesson"]'
                ];
                
                for (const selector of selectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const element of elements) {
                        const text = element.textContent || '';
                        if (text.length > 50 && text.length < 2000) {
                            // Check if it contains educational keywords
                            const lowerText = text.toLowerCase();
                            if (lowerText.includes('koordinaten') || 
                                lowerText.includes('achse') || 
                                lowerText.includes('punkt') ||
                                lowerText.includes('raum') ||
                                lowerText.includes('dimension')) {
                                content += text + ' ';
                            }
                        }
                    }
                }
                
                return content.trim();
            }
        """)
        
        # Combine results
        combined_content = f"{svg_content} {educational_content}".strip()
        return combined_content
        
    except Exception as e:
        logger.warning(f"SVG/interactive extraction failed: {e}")
        return ""


async def extract_main_content_targeted(page: async_api_Page) -> str:
    """Extract content by targeting main content areas and excluding navigation."""
    return await page.evaluate("""
        () => {
            try {
                let content = '';
                
                // Target main content selectors (common patterns)
                const mainSelectors = [
                    'main', '[role="main"]', '.main-content', '.content-area',
                    '.main-container', '.page-content', '.article-content',
                    '.content-wrapper', '.primary-content', '.main-section',
                    '.content-body', '.page-body', '.article-body',
                    // Educational content specific selectors
                    '.lesson-content', '.course-content', '.educational-content',
                    '.learning-content', '.tutorial-content', '.chapter-content',
                    // kmap.eu specific patterns
                    '.knowledge-map', '.concept-content', '.topic-content',
                    '[data-content]', '[data-main]', '.app-content'
                ];
                
                // Try each main content selector
                for (const selector of mainSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const element of elements) {
                        const text = element.textContent || '';
                        if (text.length > 100) {
                            content += text + ' ';
                        }
                    }
                }
                
                // If no main content found, look for content containers
                if (content.length < 100) {
                    const contentContainers = document.querySelectorAll(
                        'div[class*="content"], div[id*="content"], ' +
                        'section[class*="content"], article, ' +
                        'div[class*="main"], div[id*="main"]'
                    );
                    
                    for (const container of contentContainers) {
                        // Skip navigation and header elements
                        if (container.closest('nav, header, .nav, .navigation, .menu')) {
                            continue;
                        }
                        
                        const text = container.textContent || '';
                        if (text.length > 50) {
                            content += text + ' ';
                        }
                    }
                }
                
                return content.trim();
            } catch (e) {
                return '';
            }
        }
    """)


async def extract_educational_content(page: async_api_Page) -> str:
    """Extract educational content by looking for specific patterns and structures."""
    return await page.evaluate("""
        () => {
            try {
                let content = '';
                
                // Wait for potential dynamic content loading
                const waitForContent = () => {
                    return new Promise((resolve) => {
                        let attempts = 0;
                        const checkContent = () => {
                            attempts++;
                            
                            // Look for educational content indicators
                            const educationalSelectors = [
                                // Text content areas
                                'p', 'div[class*="text"]', 'div[class*="description"]',
                                'div[class*="explanation"]', 'div[class*="definition"]',
                                // Lists and structured content
                                'ul', 'ol', 'dl', 'table',
                                // Headings that might indicate content sections
                                'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                                // Canvas or interactive elements (common in educational apps)
                                'canvas', 'svg', '[data-interactive]',
                                // Form elements that might contain content
                                'textarea', 'input[type="text"]'
                            ];
                            
                            let foundContent = '';
                            
                            for (const selector of educationalSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (const element of elements) {
                                    // Skip navigation and menu elements
                                    if (element.closest('nav, .nav, .navigation, .menu, header, footer, .sidebar')) {
                                        continue;
                                    }
                                    
                                    const text = element.textContent || '';
                                    
                                    // Look for substantial content
                                    if (text.length > 20 && !text.match(/^(Home|Menu|Navigation|Login|Register|Search)$/i)) {
                                        foundContent += text + ' ';
                                    }
                                }
                            }
                            
                            // If we found substantial content or reached max attempts, resolve
                            if (foundContent.length > 200 || attempts >= 10) {
                                resolve(foundContent);
                            } else {
                                setTimeout(checkContent, 500);
                            }
                        };
                        
                        checkContent();
                    });
                };
                
                // Wait for content to load (remove await since we're not in async context)
                content = '';
                
                // Immediate content extraction
                const educationalSelectors = [
                    // Text content areas
                    'p', 'div[class*="text"]', 'div[class*="description"]',
                    'div[class*="explanation"]', 'div[class*="definition"]',
                    // Lists and structured content
                    'ul', 'ol', 'dl', 'table',
                    // Headings that might indicate content sections
                    'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
                    // Canvas or interactive elements (common in educational apps)
                    'canvas', 'svg', '[data-interactive]',
                    // Form elements that might contain content
                    'textarea', 'input[type="text"]'
                ];
                
                for (const selector of educationalSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const element of elements) {
                        // Skip navigation and menu elements
                        if (element.closest('nav, .nav, .navigation, .menu, header, footer, .sidebar')) {
                            continue;
                        }
                        
                        const text = element.textContent || '';
                        
                        // Look for substantial content
                        if (text.length > 20 && !text.match(/^(Home|Menu|Navigation|Login|Register|Search)$/i)) {
                            content += text + ' ';
                        }
                    }
                }
                
                // Additional extraction for kmap.eu specific content
                if (content.length < 200) {
                    // Look for canvas or SVG content that might contain educational material
                    const canvasElements = document.querySelectorAll('canvas, svg');
                    for (const canvas of canvasElements) {
                        const parent = canvas.parentElement;
                        if (parent) {
                            const parentText = parent.textContent || '';
                            if (parentText.length > 50) {
                                content += parentText + ' ';
                            }
                        }
                    }
                    
                    // Look for data attributes that might contain content
                    const dataElements = document.querySelectorAll('[data-content], [data-text], [data-description]');
                    for (const element of dataElements) {
                        const dataContent = element.getAttribute('data-content') || 
                                          element.getAttribute('data-text') || 
                                          element.getAttribute('data-description') || '';
                        if (dataContent.length > 20) {
                            content += dataContent + ' ';
                        }
                    }
                }
                
                return content.trim();
            } catch (e) {
                return '';
            }
        }
    """)


async def wait_for_dynamic_educational_content(page: async_api_Page, timeout: int = 45) -> None:
    """Wait specifically for educational content to load dynamically."""
    try:
        # First, standard network idle wait
        await page.wait_for_load_state('networkidle', timeout=15000)
        
        # Wait for educational keywords to appear in the DOM
        educational_keywords = ['koordinaten', 'achse', 'punkt', 'raum', 'dimension']
        
        for attempt in range(3):
            await page.wait_for_timeout(5000)  # Wait 5 seconds between attempts
            
            # Check if educational content has appeared
            content_found = await page.evaluate(f"""
                () => {{
                    const keywords = {educational_keywords};
                    const bodyText = document.body.textContent.toLowerCase();
                    
                    // Count how many educational keywords are found
                    let keywordCount = 0;
                    keywords.forEach(keyword => {{
                        if (bodyText.includes(keyword)) {{
                            keywordCount++;
                        }}
                    }});
                    
                    // Also check for SVG elements with content
                    const svgCount = document.querySelectorAll('svg').length;
                    
                    return {{
                        keywordCount: keywordCount,
                        svgCount: svgCount,
                        bodyLength: bodyText.length,
                        hasEducationalContent: keywordCount >= 2 || svgCount >= 5
                    }};
                }}
            """)
            
            logger.info(f"Dynamic content check attempt {attempt + 1}: {content_found}")
            
            if content_found.get('hasEducationalContent', False):
                logger.info("Educational content detected, proceeding with extraction")
                break
                
            # Try to trigger content loading by scrolling or interaction
            if attempt < 2:
                await page.evaluate("""
                    () => {
                        // Scroll to trigger lazy loading
                        window.scrollTo(0, document.body.scrollHeight);
                        window.scrollTo(0, 0);
                        
                        // Try to click on any content areas that might trigger loading
                        const contentAreas = document.querySelectorAll('main, [role="main"], .content, .app-content');
                        contentAreas.forEach(area => {
                            if (area.click) {
                                area.click();
                            }
                        });
                    }
                """)  
        
        # Final wait for any remaining async operations
        await page.wait_for_timeout(5000)
        
    except Exception as e:
        logger.warning(f"Error waiting for dynamic educational content: {e}")


async def extract_ultra_complex_spa_content(page: async_api_Page) -> str:
    """
    Extract content from ultra-complex SPAs using aggressive strategies.
    
    Uses multiple extraction approaches specifically designed for
    complex React/Vue applications that resist normal extraction.
    """
    logger.debug("Starting ultra-complex SPA content extraction")
    
    # First, wait for dynamic educational content to load
    await wait_for_dynamic_educational_content(page)
    
    strategies = [
        ("embedded_json_extraction", extract_embedded_json_content),
        ("svg_interactive_extraction", extract_svg_interactive_content),
        ("main_content_targeting", extract_main_content_targeted),
        ("educational_content_extraction", extract_educational_content),
        ("react_fiber_extraction", extract_react_fiber_content),
        ("vue_component_extraction", extract_vue_component_content),
        ("shadow_dom_extraction", extract_shadow_dom_content),
        ("iframe_content_extraction", extract_iframe_content),
        ("dynamic_content_polling", extract_dynamic_content_polling),
        ("javascript_state_extraction", extract_javascript_state),
        ("aggressive_text_mining", extract_aggressive_text_mining)
    ]
    
    best_content = ""
    
    for strategy_name, strategy_func in strategies:
        try:
            content = await strategy_func(page)
            logger.debug(f"  {strategy_name}: {len(content)} characters")
            
            # Use the first strategy that produces substantial content
            if len(content) > 500:
                logger.debug(f"Strategy '{strategy_name}' successful with {len(content)} characters")
                return content
            
            # Keep track of the best content so far
            if len(content) > len(best_content):
                best_content = content
                
        except Exception as e:
            logger.warning(f"Strategy '{strategy_name}' failed: {e}")
    
    logger.debug(f"All strategies completed, best content: {len(best_content)} characters")
    return best_content


async def extract_react_fiber_content(page: async_api_Page) -> str:
    """Extract content from React Fiber trees."""
    return await page.evaluate("""
        () => {
            try {
                // Try to access React Fiber
                const reactRoot = document.querySelector('[data-reactroot]') || document.querySelector('#root');
                if (reactRoot && reactRoot._reactInternalFiber) {
                    const fiber = reactRoot._reactInternalFiber;
                    
                    // Traverse the fiber tree to extract text content
                    const extractFiberText = (node) => {
                        if (!node) return '';
                        
                        let text = '';
                        
                        // Check if this node has text content
                        if (node.memoizedProps && typeof node.memoizedProps.children === 'string') {
                            text += node.memoizedProps.children + ' ';
                        }
                        
                        // Recursively check child fibers
                        if (node.child) {
                            text += extractFiberText(node.child);
                        }
                        
                        // Check sibling fibers
                        if (node.sibling) {
                            text += extractFiberText(node.sibling);
                        }
                        
                        return text;
                    };
                    
                    return extractFiberText(fiber);
                }
                
                return '';
            } catch (e) {
                return '';
            }
        }
    """)


async def extract_vue_component_content(page: async_api_Page) -> str:
    """Extract content from Vue component trees."""
    return await page.evaluate("""
        () => {
            try {
                // Try to access Vue instances
                const vueElements = document.querySelectorAll('[data-v-]');
                let content = '';
                
                for (const element of vueElements) {
                    if (element.__vue__) {
                        const vue = element.__vue__;
                        
                        // Extract data from Vue instance
                        if (vue.$data) {
                            const dataStr = JSON.stringify(vue.$data);
                            // Extract readable text from data
                            const textMatches = dataStr.match(/"[^"]*"/g);
                            if (textMatches) {
                                content += textMatches.join(' ').replace(/"/g, '') + ' ';
                            }
                        }
                        
                        // Extract computed properties
                        if (vue.$options.computed) {
                            for (const key in vue.$options.computed) {
                                try {
                                    const value = vue[key];
                                    if (typeof value === 'string' && value.length > 10) {
                                        content += value + ' ';
                                    }
                                } catch (e) {}
                            }
                        }
                    }
                }
                
                return content;
            } catch (e) {
                return '';
            }
        }
    """)


async def extract_shadow_dom_content(page: async_api_Page) -> str:
    """Extract content from Shadow DOM elements."""
    return await page.evaluate("""
        () => {
            try {
                let content = '';
                
                // Find all elements with shadow roots
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_ELEMENT,
                    {
                        acceptNode: function(node) {
                            return node.shadowRoot ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
                        }
                    }
                );
                
                let node;
                while (node = walker.nextNode()) {
                    if (node.shadowRoot) {
                        const shadowContent = node.shadowRoot.textContent || '';
                        if (shadowContent.length > 10) {
                            content += shadowContent + ' ';
                        }
                    }
                }
                
                return content;
            } catch (e) {
                return '';
            }
        }
    """)


async def extract_iframe_content(page: async_api_Page) -> str:
    """Extract content from iframes."""
    try:
        iframes = await page.query_selector_all('iframe')
        content = ''
        
        for iframe in iframes:
            try:
                iframe_content = await iframe.content_frame()
                if iframe_content:
                    iframe_text = await iframe_content.text_content('body')
                    if iframe_text and len(iframe_text) > 50:
                        content += iframe_text + ' '
            except:
                continue
        
        return content
    except:
        return ''


async def extract_dynamic_content_polling(page: async_api_Page) -> str:
    """Poll for dynamic content changes over time."""
    return await page.evaluate("""
        () => {
            return new Promise((resolve) => {
                let bestContent = '';
                let attempts = 0;
                const maxAttempts = 20;  // 4 seconds of polling
                
                const pollContent = () => {
                    attempts++;
                    
                    // Get current content
                    const currentContent = document.body.textContent || '';
                    
                    // Filter out placeholder messages
                    if (currentContent.length > bestContent.length && 
                        !currentContent.includes('JavaScript wird benötigt') &&
                        !currentContent.includes('Loading...')) {
                        bestContent = currentContent;
                    }
                    
                    if (attempts >= maxAttempts || bestContent.length > 1000) {
                        resolve(bestContent);
                    } else {
                        setTimeout(pollContent, 200);
                    }
                };
                
                pollContent();
            });
        }
    """)


async def extract_javascript_state(page: async_api_Page) -> str:
    """Extract content from JavaScript application state."""
    return await page.evaluate("""
        () => {
            try {
                let content = '';
                
                // Check for Redux store
                if (window.__REDUX_STORE__) {
                    const state = window.__REDUX_STORE__.getState();
                    const stateStr = JSON.stringify(state);
                    // Extract readable text from state
                    const textMatches = stateStr.match(/"[^"]*"/g);
                    if (textMatches) {
                        content += textMatches.join(' ').replace(/"/g, '') + ' ';
                    }
                }
                
                // Check for Vuex store
                if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__ && window.__VUE_DEVTOOLS_GLOBAL_HOOK__.store) {
                    const store = window.__VUE_DEVTOOLS_GLOBAL_HOOK__.store;
                    if (store.state) {
                        const stateStr = JSON.stringify(store.state);
                        const textMatches = stateStr.match(/"[^"]*"/g);
                        if (textMatches) {
                            content += textMatches.join(' ').replace(/"/g, '') + ' ';
                        }
                    }
                }
                
                // Check for any global app state
                const globalKeys = ['appState', 'applicationState', 'state', 'store', 'data'];
                for (const key of globalKeys) {
                    if (window[key] && typeof window[key] === 'object') {
                        try {
                            const stateStr = JSON.stringify(window[key]);
                            const textMatches = stateStr.match(/"[^"]*"/g);
                            if (textMatches) {
                                content += textMatches.join(' ').replace(/"/g, '') + ' ';
                            }
                        } catch (e) {}
                    }
                }
                
                return content;
            } catch (e) {
                return '';
            }
        }
    """)


async def extract_aggressive_text_mining(page: async_api_Page) -> str:
    """Aggressively mine text from all possible sources."""
    return await page.evaluate(r"""
        () => {
            try {
                let content = '';
                
                // Extract from all script tags (looking for JSON data)
                const scripts = document.querySelectorAll('script');
                for (const script of scripts) {
                    const scriptContent = script.textContent || '';
                    
                    // Look for JSON data in scripts
                    const jsonMatches = scriptContent.match(/\{[^}]*"[^"]*"[^}]*\}/g);
                    if (jsonMatches) {
                        for (const match of jsonMatches) {
                            try {
                                const obj = JSON.parse(match);
                                const objStr = JSON.stringify(obj);
                                const textMatches = objStr.match(/"[^"]*"/g);
                                if (textMatches) {
                                    content += textMatches.join(' ').replace(/"/g, '') + ' ';
                                }
                            } catch (e) {}
                        }
                    }
                }
                
                // Extract from data attributes
                const elementsWithData = document.querySelectorAll('[data-*]');
                for (const element of elementsWithData) {
                    for (const attr of element.attributes) {
                        if (attr.name.startsWith('data-') && attr.value.length > 10) {
                            content += attr.value + ' ';
                        }
                    }
                }
                
                // Extract from comments (sometimes contains data)
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_COMMENT,
                    null,
                    false
                );
                
                let node;
                while (node = walker.nextNode()) {
                    const commentText = node.textContent || '';
                    if (commentText.length > 20 && !commentText.includes('<!--')) {
                        content += commentText + ' ';
                    }
                }
                
                return content;
            } catch (e) {
                return '';
            }
        }
    """)
