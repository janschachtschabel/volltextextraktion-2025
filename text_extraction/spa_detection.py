"""
SPA Detection Module

This module provides functionality to detect Single Page Applications (SPAs)
and identify JavaScript frameworks used on web pages.
"""

import logging
from typing import Dict, Any
from playwright.async_api import Page as async_api_Page

logger = logging.getLogger(__name__)


async def detect_spa_characteristics(page: async_api_Page) -> bool:
    """
    Detect if the current page is likely a Single Page Application.
    
    Uses multiple heuristics to identify SPA characteristics:
    - JavaScript framework detection (React, Vue, Angular, etc.)
    - History API usage
    - Dynamic content indicators
    - DOM structure analysis
    
    Returns:
        bool: True if page appears to be an SPA
    """
    logger.debug("Detecting SPA characteristics")
    
    try:
        # JavaScript evaluation to detect SPA indicators
        spa_indicators = await page.evaluate("""
            () => {
                let score = 0;
                const indicators = {};
                
                // Check for common SPA frameworks
                if (window.React || document.querySelector('[data-reactroot]') || document.querySelector('#root')) {
                    score += 2;
                    indicators.react = true;
                }
                
                if (window.Vue || document.querySelector('[data-v-]')) {
                    score += 2;
                    indicators.vue = true;
                }
                
                if (window.angular || document.querySelector('[ng-app]') || document.querySelector('app-root')) {
                    score += 2;
                    indicators.angular = true;
                }
                
                if (window.Ember) {
                    score += 2;
                    indicators.ember = true;
                }
                
                if (window.__SVELTE__) {
                    score += 2;
                    indicators.svelte = true;
                }
                
                // Check for History API usage
                if (window.history && window.history.pushState) {
                    score += 1;
                    indicators.historyApi = true;
                }
                
                // Check for dynamic content indicators
                if (document.querySelector('[data-testid]') || 
                    document.querySelector('[data-cy]') ||
                    document.querySelector('.loading') ||
                    document.querySelector('.spinner')) {
                    score += 1;
                    indicators.dynamicContent = true;
                }
                
                // Check for single-page structure
                const mainContent = document.querySelector('#app') || 
                                  document.querySelector('#root') ||
                                  document.querySelector('.app');
                if (mainContent) {
                    score += 1;
                    indicators.spaStructure = true;
                }
                
                return {
                    score: score,
                    indicators: indicators,
                    isSpa: score >= 2
                };
            }
        """)
        
        logger.debug(f"SPA detection score: {spa_indicators['score']}, indicators: {spa_indicators['indicators']}")
        return spa_indicators['isSpa']
        
    except Exception as e:
        logger.warning(f"Error during SPA detection: {e}")
        return False


def detect_spa_indicators(html_content: str) -> Dict[str, Any]:
    """
    Detect indicators that suggest this is a Single Page Application.
    
    This function analyzes HTML content for SPA framework indicators
    and returns information about detected frameworks and characteristics.
    
    Args:
        html_content: Raw HTML content to analyze
        
    Returns:
        Dict containing SPA detection results and framework information
    """
    indicators = {
        'frameworks': [],
        'score': 0,
        'is_spa': False,
        'characteristics': []
    }
    
    html_lower = html_content.lower()
    
    # React indicators
    if any(indicator in html_lower for indicator in [
        'data-reactroot', 'react.js', 'reactdom', '__react', '_reactinternalinstance'
    ]):
        indicators['frameworks'].append('React')
        indicators['score'] += 2
        indicators['characteristics'].append('React framework detected')
    
    # Vue indicators
    if any(indicator in html_lower for indicator in [
        'vue.js', 'data-v-', '__vue__', 'v-if', 'v-for', 'v-model'
    ]):
        indicators['frameworks'].append('Vue')
        indicators['score'] += 2
        indicators['characteristics'].append('Vue framework detected')
    
    # Angular indicators
    if any(indicator in html_lower for indicator in [
        'ng-app', 'ng-controller', 'angular.js', 'app-root', '[ng-'
    ]):
        indicators['frameworks'].append('Angular')
        indicators['score'] += 2
        indicators['characteristics'].append('Angular framework detected')
    
    # Ember indicators
    if any(indicator in html_lower for indicator in [
        'ember.js', 'ember-application', 'data-ember-'
    ]):
        indicators['frameworks'].append('Ember')
        indicators['score'] += 2
        indicators['characteristics'].append('Ember framework detected')
    
    # Svelte indicators
    if any(indicator in html_lower for indicator in [
        'svelte', '__svelte__'
    ]):
        indicators['frameworks'].append('Svelte')
        indicators['score'] += 2
        indicators['characteristics'].append('Svelte framework detected')
    
    # General SPA indicators
    if any(indicator in html_lower for indicator in [
        'single-page', 'spa-', '#app', '#root', 'data-testid', 'data-cy'
    ]):
        indicators['score'] += 1
        indicators['characteristics'].append('SPA structure indicators found')
    
    # Dynamic loading indicators
    if any(indicator in html_lower for indicator in [
        'loading', 'spinner', 'skeleton', 'lazy-load'
    ]):
        indicators['score'] += 1
        indicators['characteristics'].append('Dynamic loading indicators found')
    
    # Determine if this is likely an SPA
    indicators['is_spa'] = indicators['score'] >= 2
    
    return indicators
