#!/usr/bin/env python3
"""Enhanced Text Extraction Web Service - Clean Implementation

This module provides a FastAPI-based web service for text extraction with comprehensive
feature support including file conversion, proxy rotation, link extraction, and quality metrics.

This is a clean, minimal, and effective rewrite that addresses all historical problems
from the original codebase while incorporating all recent improvements.
"""

import argparse
import asyncio
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from enum import StrEnum, auto
from typing import Any, Dict, List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from playwright import async_api
from pydantic import BaseModel, Field, field_validator

# Import modules - with fallback to basic implementation
try:
    import text_extraction.content_extraction as content_extraction
    import text_extraction.browser_helpers as browser_helpers
    ENHANCED_MODULES_AVAILABLE = True
except ImportError:
    # Fallback to basic implementation if enhanced modules don't exist yet
    import text_extraction.grab_content as grab_content
    ENHANCED_MODULES_AVAILABLE = False

from text_extraction._version import __version__

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for FastAPI application."""
    # Startup
    logger.info(f"Starting Text Extraction API - Smart v{__version__}")
    if ENHANCED_MODULES_AVAILABLE:
        logger.info("Enhanced modules available: File conversion, Proxy rotation, Link extraction, Quality metrics")
    else:
        logger.info("Basic mode: Enhanced modules not available, using fallback implementation")
    
    yield
    
    # Shutdown
    global browser_instance, playwright_instance
    
    # Close browser instance
    if browser_instance:
        try:
            await browser_instance.close()
            logger.info("Browser instance closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
    
    # Stop playwright instance
    if playwright_instance:
        try:
            await playwright_instance.stop()
            logger.info("Playwright instance stopped")
        except Exception as e:
            logger.warning(f"Error stopping playwright: {e}")
    
    logger.info("Text Extraction API - Smart shutdown complete")


# FastAPI application with enhanced configuration
app = FastAPI(
    title="Text Extraction API - Smart",
    description="""Clean, minimal, and effective text extraction service with comprehensive features:

**Features:**
- Multiple output formats (text, markdown, raw_text)
- File format conversion (25+ formats via MarkItDown/Pandoc)
- Proxy rotation with transparency
- Link extraction and classification
- Content quality assessment with normalized scores (0-1)
- Browser-based extraction for JavaScript-heavy sites and SPAs
- Robust error handling with fallback mechanisms

**Main Endpoints:**
- `POST /extract` - Extract text from URLs with full feature support
- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (this page)
- `GET /redoc` - Alternative API documentation

**Extraction Methods:**
- `simple` - Fast extraction using trafilatura (default)
- `browser` - JavaScript-aware extraction using Playwright

**Quality Metrics:**
When enabled, returns normalized scores (0-1) for:
- Overall quality score
- Readability assessment
- Content structure analysis
- Error page detection
- Text diversity measurement
""",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global browser and playwright instances for reuse
playwright_instance: Optional[Any] = None
browser_instance: Optional[async_api.Browser] = None


class ExtractionMethod(StrEnum):
    """Available extraction methods"""
    simple = auto()
    browser = auto()


class OutputFormat(StrEnum):
    """Available output formats"""
    text = auto()
    markdown = auto()
    raw_text = auto()


class Preference(StrEnum):
    """Extraction preferences for trafilatura"""
    none = auto()
    recall = auto()
    precision = auto()


class LinkInfo(BaseModel):
    """Information about extracted links"""
    url: str
    text: str
    is_internal: bool
    link_type: str = "unknown"


class QualityMetrics(BaseModel):
    """Lightweight signals describing the extracted content."""

    character_length: int = Field(
        default=0,
        ge=0,
        description="Number of characters in the extracted text",
    )
    content_category: str = Field(
        default="other",
        description="Detected content category (educational_content, educational_metadata, error_page, other)",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence for the detected content category",
    )
    matched_keywords: Dict[str, int] = Field(
        default_factory=dict,
        description="Counts of matched keyword groups used for classification",
    )


class ExtractionData(BaseModel):
    """Request data model for text extraction"""
    url: str = Field(..., description="URL to extract text from")
    method: ExtractionMethod = Field(default=ExtractionMethod.simple, description="Extraction method")
    output_format: OutputFormat = Field(default=OutputFormat.markdown, description="Output format")
    target_language: str = Field(default="auto", description="Target language for extraction")
    preference: Preference = Field(default=Preference.none, description="Extraction preference")
    
    # File conversion parameters
    convert_files: bool = Field(default=False, description="Enable file format conversion")
    max_file_size_mb: int = Field(default=50, ge=1, le=100, description="Maximum file size for conversion")
    conversion_timeout: int = Field(default=60, ge=10, le=300, description="Conversion timeout in seconds")
    
    # Link extraction
    include_links: bool = Field(default=False, description="Extract and classify links")
    
    # Proxy configuration
    proxies: Optional[Union[str, List[str]]] = Field(default=None, description="Proxy servers (single string or list)")
    
    # Browser-specific options
    browser_location: Optional[str] = Field(default=None, description="Custom browser executable path")
    timeout: int = Field(default=30, ge=5, le=120, description="Request timeout in seconds")
    
    # Quality assessment
    calculate_quality: bool = Field(default=False, description="Calculate content quality metrics")

    @field_validator('proxies')
    @classmethod
    def validate_proxies(cls, v):
        # Handle None case
        if v is None:
            return None
        
        # Convert single string to list for uniform processing
        if isinstance(v, str):
            v = [v]
        
        # Handle empty list
        if not v or v == []:
            return None
        
        # Handle "no proxy" cases - various ways users might indicate no proxy
        if isinstance(v, list):
            # Check for common "no proxy" indicators
            no_proxy_indicators = [
                "",           # Empty string
                "string",     # Literal "string" 
                "none",       # "none"
                "null",       # "null"
                "false",      # "false"
                "0",          # "0"
            ]
            
            # Filter out empty/whitespace strings and no-proxy indicators
            filtered_proxies = []
            for proxy in v:
                if proxy is None:
                    continue
                proxy_str = str(proxy).strip().lower()
                if proxy_str and proxy_str not in no_proxy_indicators:
                    filtered_proxies.append(str(proxy).strip())
            
            # If no valid proxies remain, return None
            if not filtered_proxies:
                return None
            
            # Validate remaining proxy entries
            valid_proxies = []
            for proxy in filtered_proxies:
                if ':' not in proxy:
                    raise ValueError(f"Invalid proxy format: {proxy}. Expected 'host:port'")
                # Basic validation of host:port format
                try:
                    host, port = proxy.split(':', 1)
                    if not host.strip() or not port.strip():
                        raise ValueError(f"Invalid proxy format: {proxy}. Host and port cannot be empty")
                    # Try to convert port to int to validate it's numeric
                    int(port)
                    valid_proxies.append(proxy)
                except ValueError as e:
                    if "Invalid proxy format" in str(e):
                        raise e
                    raise ValueError(f"Invalid proxy format: {proxy}. Port must be numeric")
            
            return valid_proxies if valid_proxies else None
        
        return None


class ExtractionResult(BaseModel):
    """Response model for text extraction results"""
    # Core content
    text: str = Field(..., description="Extracted text content")
    
    # Status information
    status: int = Field(..., description="HTTP status code")
    reason: str = Field(..., description="Extraction status reason")
    message: str = Field(default="", description="Additional status message")
    
    # Metadata
    lang: str = Field(..., description="Detected language")
    mode: str = Field(..., description="Extraction method used")
    final_url: str = Field(..., description="Final URL after redirects")
    version: str = Field(default=__version__, description="API version")
    
    # File conversion metadata
    converted: bool = Field(default=False, description="Whether file conversion was performed")
    original_format: Optional[str] = Field(default=None, description="Original file format")
    file_size_mb: Optional[float] = Field(default=None, description="File size in MB")
    
    # Proxy information
    proxy_used: Optional[str] = Field(default=None, description="Proxy server used")
    
    # Links (when requested)
    links: Optional[List[LinkInfo]] = Field(default=None, description="Extracted links")
    
    # Quality metrics (when requested)
    quality_metrics: Optional[QualityMetrics] = Field(default=None, description="Content quality assessment")
    
    # Performance metrics
    extraction_time: float = Field(..., description="Extraction time in seconds")
    
    # Provenance and freshness information
    extraction_timestamp: Optional[str] = Field(default=None, description="ISO 8601 timestamp when extraction was performed")
    extraction_origin: Optional[str] = Field(default=None, description="Origin of extraction (realtime_crawl, backfill, cache, etc.)")


@app.get("/_ping")
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "version": __version__, 
        "timestamp": time.time(),
        "enhanced_modules_available": ENHANCED_MODULES_AVAILABLE,
        "features": [
            "file_conversion",
            "proxy_rotation", 
            "link_extraction",
            "quality_metrics",
            "browser_mode"
        ] if ENHANCED_MODULES_AVAILABLE else ["browser_mode"]
    }





@app.post(
    "/from-url",
    response_model=ExtractionResult,
    summary="Extract text from URL",
    description="""
    Extract text content from web pages and files with comprehensive feature support.
    
    This endpoint provides robust text extraction with multiple fallback mechanisms,
    file format conversion, proxy rotation, link extraction, and quality assessment.
    
    **Key Features:**
    - Multiple extraction methods (simple HTTP vs browser-based)
    - File format conversion for 25+ formats (DOCX, PDF, XLSX, etc.) [if enhanced modules available]
    - Proxy rotation with transparent usage reporting [if enhanced modules available]
    - Link extraction with internal/external classification [if enhanced modules available]
    - Content quality metrics and assessment [if enhanced modules available]
    - Robust error handling with graceful fallbacks
    """
)
async def extract_from_url(data: ExtractionData, response: Response) -> ExtractionResult:
    """Extract text content from a URL with comprehensive feature support."""
    start_time = time.time()
    
    try:
        logger.info(f"Starting extraction for URL: {data.url}")
        
        if ENHANCED_MODULES_AVAILABLE:
            # Use enhanced modules if available
            result = await enhanced_extraction(data)
        else:
            # Fallback to basic implementation
            logger.info("Using basic implementation (enhanced modules not available)")
            result = await basic_extraction_fallback(data)
        
        # Calculate extraction time
        extraction_time = time.time() - start_time
        
        # Add rate limit headers for transparency
        response.headers["X-RateLimit-Limit-Per-Minute"] = "45"
        response.headers["X-RateLimit-Limit-Per-Second"] = "1"
        response.headers["X-RateLimit-Window"] = "60"
        response.headers["X-RateLimit-Policy"] = "sliding-window"
        response.headers["X-API-Version"] = __version__
        
        # Ensure result has extraction_time
        if isinstance(result, dict):
            result['extraction_time'] = extraction_time
            result['version'] = __version__
            return ExtractionResult(**result)
        else:
            # Handle unexpected result format
            # Generate timestamp and origin for unexpected format case
            extraction_timestamp = datetime.now(timezone.utc).isoformat()
            extraction_origin = "realtime_crawl_fallback"  # This is a fallback format handling
            
            return ExtractionResult(
                text=result if isinstance(result, str) else "",
                status=200,
                reason="success",
                message="Extraction completed",
                lang="auto",
                mode=data.method.value,
                final_url=data.url,
                extraction_time=extraction_time,
                extraction_timestamp=extraction_timestamp,
                extraction_origin=extraction_origin
            )
            
    except Exception as e:
        extraction_time = time.time() - start_time
        logger.error(f"Extraction failed for {data.url}: {str(e)}")
        
        # Generate timestamp and origin for error case
        extraction_timestamp = datetime.now(timezone.utc).isoformat()
        extraction_origin = "realtime_crawl_error"  # This is a failed extraction attempt
        
        return ExtractionResult(
            text="",
            status=500,
            reason="extraction_error",
            message=f"Extraction failed: {str(e)}",
            lang="unknown",
            mode=data.method.value,
            final_url=data.url,
            extraction_time=extraction_time,
            extraction_timestamp=extraction_timestamp,
            extraction_origin=extraction_origin
        )


async def enhanced_extraction(data: ExtractionData) -> Dict[str, Any]:
    """Enhanced extraction using full feature modules."""
    # Determine extraction method
    if data.method == ExtractionMethod.browser:
        # Use fresh browser strategy - no browser instance passed
        # browser_helpers will create its own fresh instance
        result = await browser_helpers.extract_with_browser(
            url=data.url,
            browser=None,  # Force fresh browser creation
            output_format=data.output_format.value,
            target_language=data.target_language,
            preference=data.preference.value,
            convert_files=data.convert_files,
            max_file_size_mb=data.max_file_size_mb,
            conversion_timeout=data.conversion_timeout,
            include_links=data.include_links,
            proxies=data.proxies,
            timeout=data.timeout,
            calculate_quality=data.calculate_quality
        )
    else:
        # Use simple extraction
        result = await content_extraction.extract_from_url(
            url=data.url,
            output_format=data.output_format.value,
            target_language=data.target_language,
            preference=data.preference.value,
            convert_files=data.convert_files,
            max_file_size_mb=data.max_file_size_mb,
            conversion_timeout=data.conversion_timeout,
            include_links=data.include_links,
            proxies=data.proxies,
            timeout=data.timeout,
            calculate_quality=data.calculate_quality
        )
    
    return result


async def basic_extraction_fallback(data: ExtractionData) -> Dict[str, Any]:
    """Fallback to basic extraction when enhanced modules are not available."""
    lang = data.target_language
    
    # Use basic grab_content module
    if data.method == ExtractionMethod.simple:
        text = grab_content.from_html(
            data.url,
            preference=data.preference.value,
            target_language=lang,
        )
    else:
        # Browser mode fallback
        if data.browser_location is None:
            get_browser_fun = lambda x: x.chromium.launch(
                args=["--single-process"]
            )
        else:
            get_browser_fun = lambda x: x.chromium.connect_over_cdp(
                endpoint_url=data.browser_location
            )
            
        async with (
            async_api.async_playwright() as p,
            await get_browser_fun(p) as browser,
        ):
            text = await grab_content.from_headless_browser(
                data.url,
                browser=browser,
                preference=data.preference.value,
                target_language=lang,
            )
    
    # Handle no content
    if text is None:
        raise HTTPException(
            status_code=500,
            detail="No content was extracted. This could be due to no text being present on the page, the website relying on JavaScript, or language detection issues.",
        )
    
    # Detect language
    detected_lang = lang if lang != "auto" else grab_content.get_lang(text)
    
    # Generate timestamp and origin information
    extraction_timestamp = datetime.now(timezone.utc).isoformat()
    extraction_origin = "realtime_crawl_fallback"  # This is a live extraction using fallback
    
    return {
        "text": text,
        "status": 200,
        "reason": "success",
        "message": "Extraction completed using basic fallback",
        "lang": detected_lang,
        "mode": data.method.value,
        "final_url": data.url,
        "converted": False,
        "original_format": None,
        "file_size_mb": None,
        "proxy_used": None,
        "links": [] if data.include_links else None,
        "quality_metrics": None,
        "extraction_timestamp": extraction_timestamp,
        "extraction_origin": extraction_origin
    }


async def create_fresh_browser_instance() -> tuple[async_api.Browser, Any]:
    """Create a fresh browser instance for a single request.
    
    Returns tuple of (browser, playwright) for proper cleanup.
    This approach avoids browser instance reuse issues.
    """
    try:
        from playwright.async_api import async_playwright
        
        # Create fresh playwright and browser instances
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--single-process',  # Helps with Docker compatibility
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        )
        logger.debug("Fresh browser instance created successfully")
        return browser, playwright
    except Exception as e:
        logger.error(f"Failed to create fresh browser instance: {e}")
        raise HTTPException(status_code=500, detail="Browser initialization failed")


async def get_browser_instance() -> async_api.Browser:
    """Get or create browser instance for browser-based extraction.
    
    DEPRECATED: This function is kept for backward compatibility but now
    creates fresh instances to avoid stability issues.
    """
    browser, _ = await create_fresh_browser_instance()
    return browser





def main():
    """Main function to run the web service."""
    parser = argparse.ArgumentParser(description="Text Extraction API - Smart")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="Log level (default: info)"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting Text Extraction API - Smart v{__version__}")
    logger.info(f"Server will be available at: http://{args.host}:{args.port}")
    logger.info(f"API documentation: http://{args.host}:{args.port}/docs")
    
    uvicorn.run(
        "text_extraction.webservice:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level
    )


if __name__ == "__main__":
    main()
