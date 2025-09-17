"""
Enhanced Content Extraction Module - Clean Implementation

This module provides advanced text extraction capabilities with file conversion,
proxy rotation, link extraction, and quality metrics support.

This is a clean, minimal implementation that addresses all historical problems
while incorporating proven enhancements from the original codebase.
"""

import asyncio
import gzip
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import py3langid as langid
import requests
import trafilatura
from trafilatura.settings import use_config

logger = logging.getLogger(__name__)

# Import MarkItDown converter and other modules
try:
    from .markitdown_converter import (
        MarkItDownConversionError,
        get_markitdown_converter,
        is_markitdown_available,
    )
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    MarkItDownConversionError = Exception  # type: ignore
    logger.warning("MarkItDown converter not available - file conversion disabled")

# Configure trafilatura for optimal extraction
config = use_config()
config.set("DEFAULT", "EXTRACTION_TIMEOUT", "30")


async def retry_with_backoff(
    func,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
):
    """Retry function with exponential backoff for transient errors."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            
            # Check if this is a retryable error
            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error on attempt {attempt + 1}: {e}")
                raise e
            
            if attempt == max_retries:
                logger.error(f"Max retries ({max_retries}) exceeded. Last error: {e}")
                raise e
            
            # Calculate delay with exponential backoff
            delay = min(base_delay * (backoff_factor ** attempt), max_delay)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f}s...")
            await asyncio.sleep(delay)
    
    # This should never be reached, but just in case
    raise last_exception


def is_retryable_error(error: Exception) -> bool:
    """Determine if an error is retryable (transient)."""
    # HTTP errors that are typically transient
    if hasattr(error, 'response') and hasattr(error.response, 'status_code'):
        status_code = error.response.status_code
        # Retry on server errors and some client errors
        if status_code in [500, 502, 503, 504, 408, 429]:
            return True
    
    # Network/connection errors
    error_str = str(error).lower()
    retryable_patterns = [
        'timeout', 'connection', 'network', 'dns', 'resolve',
        'temporary failure', 'service unavailable', 'bad gateway',
        'gateway timeout', 'too many requests'
    ]
    
    return any(pattern in error_str for pattern in retryable_patterns)


def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video URL."""
    youtube_domains = [
        # Main YouTube domains
        'youtube.com', 'www.youtube.com', 'm.youtube.com',
        'gaming.youtube.com', 'studio.youtube.com',
        'youtube-nocookie.com', 'youtu.be', 'www.youtu.be',
        
        # Regional YouTube domains (Europe)
        'youtube.at', 'youtube.be', 'youtube.bg', 'youtube.hr',
        'youtube.cy', 'youtube.cz', 'youtube.dk', 'youtube.ee',
        'youtube.es', 'youtube.fi', 'youtube.fr', 'youtube.gr',
        'youtube.hu', 'youtube.ie', 'youtube.it', 'youtube.lt',
        'youtube.lu', 'youtube.lv', 'youtube.mt', 'youtube.nl',
        'youtube.pl', 'youtube.pt', 'youtube.ro', 'youtube.se',
        'youtube.sk', 'youtube.si', 'youtube.de'
    ]
    
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url.lower())
        # Check if domain matches exactly or is a subdomain
        return any(parsed.netloc == domain or parsed.netloc.endswith('.' + domain) for domain in youtube_domains)
    except Exception:
        return False


async def convert_youtube_content(
    url: str,
    output_format: str = "markdown",
    max_file_size_mb: int = 50,
    timeout_seconds: int = 120
) -> Tuple[str, Dict[str, Any]]:
    """Convert YouTube URL to transcribed text using MarkItDown."""
    
    if not MARKITDOWN_AVAILABLE or not is_markitdown_available():
        raise Exception("MarkItDown not available for YouTube transcription")
    
    try:
        converter = get_markitdown_converter(
            max_file_size_mb=max_file_size_mb,
            timeout_seconds=timeout_seconds
        )
        
        # MarkItDown can handle YouTube URLs directly
        text, metadata = await converter.convert_youtube_to_markdown(url)
        
        conversion_meta = {
            'converted': metadata.get('converted', True),
            'original_format': metadata.get('original_format', 'YouTube Video'),
            'file_size_mb': 0.0,  # YouTube URLs don't have file size
            'conversion_method': 'markitdown_youtube'
        }
        
        return text, conversion_meta
        
    except Exception as e:
        logger.error(f"YouTube transcription failed: {e}")
        return "", {
            'converted': False,
            'original_format': 'YouTube Video',
            'file_size_mb': 0.0,
            'conversion_method': 'markitdown_youtube',
            'error': str(e)
        }


def get_lang(text: str) -> str:
    """Detect language of text using py3langid."""
    try:
        lang, confidence = langid.classify(text)
        return lang if confidence > 0.5 else "unknown"
    except Exception:
        return "unknown"


def is_binary_content(content: bytes) -> bool:
    """Check if content is binary (e.g., gzipped)."""
    return content.startswith(b'\x1f\x8b') or b'\x00' in content[:1024]


def decompress_if_needed(content: bytes) -> str:
    """Decompress and decode content if needed."""
    try:
        # Check if content is gzipped
        if content.startswith(b'\x1f\x8b'):
            content = gzip.decompress(content)
        
        # Try UTF-8 first, then fallback encodings
        for encoding in ['utf-8', 'latin1', 'iso-8859-1', 'cp1252']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # Last resort: decode with errors='replace'
        return content.decode('utf-8', errors='replace')
    except Exception as e:
        logger.warning(f"Failed to decompress/decode content: {e}")
        return content.decode('utf-8', errors='replace')


def extract_text_from_html(
    html_content: str,
    output_format: str = "markdown",
    target_language: str = "auto",
    preference: str = "none"
) -> str:
    """Extract text from HTML content using trafilatura."""
    try:
        # Configure extraction parameters
        extract_kwargs = {
            "favor_precision": preference == "precision",
            "favor_recall": preference == "recall",
            "include_links": False,  # We handle links separately
            "include_images": False,
            "include_tables": True,
            "include_formatting": output_format in ["markdown", "raw_markdown"]
        }
        
        if output_format in ["text", "raw_text"]:
            # Use trafilatura.extract for clean text (no output_format param = plain text)
            text = trafilatura.extract(html_content, **extract_kwargs)
        elif output_format in ["markdown", "raw_markdown"]:
            # Use trafilatura.extract with markdown output
            text = trafilatura.extract(html_content, output_format="markdown", **extract_kwargs)
        else:
            # Default to markdown
            text = trafilatura.extract(html_content, output_format="markdown", **extract_kwargs)
        
        return text or ""
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        return ""


def extract_links_from_html(html_content: str, base_url: str) -> List[Dict[str, Any]]:
    """Extract and classify links from HTML content."""
    try:
        # Import link extraction if available
        try:
            from text_extraction.link_extraction import extract_links_from_html as extract_links
            return extract_links(html_content, base_url)
        except ImportError:
            logger.warning("Link extraction module not available")
            return []
    except Exception as e:
        logger.error(f"Link extraction failed: {e}")
        return []


def calculate_quality_metrics(text: str) -> Optional[Dict[str, Any]]:
    """Calculate lightweight quality indicators for extracted text."""
    try:
        from text_extraction.quality import calculate_quality_metrics as _calculate

        return _calculate(text)
    except ImportError:
        logger.warning("Quality metrics module not available")
        return None
    except Exception as e:
        logger.error(f"Quality metrics calculation failed: {e}")
        return None


async def convert_file_content(
    url: str,
    content: bytes,
    output_format: str = "markdown",
    max_file_size_mb: int = 50,
    timeout_seconds: int = 60
) -> Tuple[str, Dict[str, Any]]:
    """Convert file content using MarkItDown if available."""
    try:
        # Import MarkItDown converter if available
        try:
            from text_extraction.markitdown_converter import get_markitdown_converter, is_markitdown_available
            
            if not is_markitdown_available():
                logger.warning("MarkItDown not available")
                return "", {"converted": False, "reason": "markitdown_not_available"}
            
            # Detect file format from URL
            from urllib.parse import urlparse
            parsed_url = urlparse(url)
            file_name = Path(parsed_url.path).name or None
            file_extension = (
                file_name.split('.')[-1].lower()
                if file_name and '.' in file_name
                else 'unknown'
            )

            # Get converter instance
            converter = get_markitdown_converter(
                max_file_size_mb=max_file_size_mb,
                timeout_seconds=timeout_seconds
            )

            # Convert file
            text, metadata = await converter.convert_file_to_markdown(
                content=content,
                file_format=file_extension,
                filename=file_name,
            )

            return text, metadata

        except ImportError as e:
            logger.warning(f"MarkItDown converter module not available: {e}")
            return "", {"converted": False, "reason": "converter_not_available"}
        except MarkItDownConversionError as conversion_error:
            logger.warning(f"MarkItDown conversion failed: {conversion_error}")
            return "", {"converted": False, "reason": str(conversion_error)}
    except Exception as e:
        logger.error(f"File conversion failed: {e}")
        return "", {"converted": False, "reason": f"conversion_error: {str(e)}"}


async def extract_from_url(
    url: str,
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
    Enhanced text extraction from URL with comprehensive feature support.
    
    This function provides the core extraction logic for the enhanced API,
    including file conversion, proxy rotation, link extraction, and quality metrics.
    """
    start_time = time.time()
    
    try:
        logger.info(f"extract_from_url called with: url={url}, convert_files={convert_files}")
        
        # Check for YouTube URLs first (MarkItDown can transcribe these)
        is_youtube = is_youtube_url(url)
        logger.info(f"YouTube URL check: {is_youtube} for {url}")
        
        if convert_files and is_youtube:
            try:
                logger.info(f"Entering YouTube transcription branch for: {url}")
                converted_text, conversion_meta = await convert_youtube_content(
                    url=url,
                    output_format=output_format,
                    max_file_size_mb=max_file_size_mb,
                    timeout_seconds=conversion_timeout
                )
                
                if converted_text:
                    # Calculate quality metrics for transcribed content
                    quality_metrics = calculate_quality_metrics(converted_text) if calculate_quality else None
                    
                    return {
                        "text": converted_text,
                        "status": 200,
                        "reason": "success",
                        "message": "YouTube transcription successful",
                        "lang": get_lang(converted_text),
                        "method": "youtube_transcription",
                        "mode": "youtube_transcription",
                        "final_url": url,
                        "proxy_used": None,
                        "links": [] if include_links else None,
                        "quality_metrics": quality_metrics,
                        **conversion_meta
                    }
                else:
                    logger.warning(f"YouTube transcription failed, falling back to regular extraction: {url}")
            except Exception as e:
                logger.warning(f"YouTube transcription error: {e}, falling back to regular extraction")
        
        # Check for unsupported file formats
        if convert_files:
            # Try file conversion if enabled
            try:
                response = requests.head(url, timeout=10, allow_redirects=True)
                content_type = response.headers.get('content-type', '').lower()
                
                # Check if it's a convertible file format (comprehensive MIME type detection)
                office_mime_types = [
                    # PDF formats
                    'application/pdf',
                    # Word formats
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
                    'application/msword',  # .doc
                    # Excel formats
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
                    'application/vnd.ms-excel',  # .xls
                    # PowerPoint formats
                    'application/vnd.openxmlformats-officedocument.presentationml.presentation',  # .pptx
                    'application/vnd.ms-powerpoint',  # .ppt
                    # OpenDocument formats
                    'application/vnd.oasis.opendocument.text',  # .odt
                    'application/vnd.oasis.opendocument.presentation',  # .odp
                    'application/vnd.oasis.opendocument.spreadsheet',  # .ods
                    # RTF and other text formats
                    'application/rtf',
                    'text/rtf',
                    # Also check for simple format strings as fallback
                    'pdf', 'docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt'
                ]
                
                if any(mime_type in content_type for mime_type in office_mime_types):
                    # Download and convert file
                    response = requests.get(url, timeout=timeout, allow_redirects=True)
                    response.raise_for_status()
                    
                    converted_text, conversion_meta = await convert_file_content(
                        url=url,
                        content=response.content,
                        output_format=output_format,
                        max_file_size_mb=max_file_size_mb,
                        timeout_seconds=conversion_timeout
                    )
                    
                    if converted_text:
                        # Successful conversion
                        detected_lang = get_lang(converted_text) if target_language == "auto" else target_language
                        
                        result = {
                            "text": converted_text,
                            "status": 200,
                            "reason": "success",
                            "message": "File converted and extracted successfully",
                            "lang": detected_lang,
                            "mode": "simple",
                            "final_url": url,
                            "converted": conversion_meta.get("converted", True),
                            "original_format": conversion_meta.get("original_format", "unknown"),
                            "file_size_mb": conversion_meta.get("file_size_mb", 0),
                            "proxy_used": None,
                            "links": [] if include_links else None,
                            "quality_metrics": calculate_quality_metrics(converted_text) if calculate_quality else None
                        }
                        
                        return result
            except Exception as e:
                logger.warning(f"File conversion failed, falling back to HTML extraction: {e}")
        
        # Standard HTML extraction with proxy support
        # Initialize variables
        html_content = None
        final_url = url
        proxy_used = None
        http_status = 200  # Default status
        
        # Try with proxies if provided
        if proxies:
            # Randomize proxy order for better distribution
            proxy_list = proxies.copy()
            random.shuffle(proxy_list)
            
            for proxy in proxy_list:
                try:
                    logger.info(f"Trying proxy: {proxy}")
                    proxies_dict = {
                        'http': f'http://{proxy}',
                        'https': f'http://{proxy}'
                    }
                    
                    response = requests.get(
                        url,
                        proxies=proxies_dict,
                        timeout=timeout,
                        allow_redirects=True,
                        headers={
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                        }
                    )
                    
                    # Capture status code but don't raise for 4xx errors if content exists
                    http_status = response.status_code
                    if response.content and len(response.content) > 0:
                        # Success with proxy (even if 404/4xx, we have content)
                        html_content = response.content
                        final_url = response.url
                        proxy_used = proxy
                        logger.info(f"Successfully extracted using proxy: {proxy} (HTTP {http_status})")
                        break
                    else:
                        # No content, treat as failure
                        response.raise_for_status()
                    
                except Exception as e:
                    logger.warning(f"Proxy {proxy} failed: {e}")
                    continue
        
        # Fallback to direct connection if no proxy worked
        if html_content is None:
            try:
                logger.info("Trying direct connection (no proxy)")
                response = requests.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                
                # Capture status code but don't raise for 4xx errors if content exists
                http_status = response.status_code
                if response.content and len(response.content) > 0:
                    html_content = response.content
                    final_url = response.url
                    logger.info(f"Successfully extracted using direct connection (HTTP {http_status})")
                else:
                    # No content, treat as failure
                    response.raise_for_status()
            except Exception as e:
                logger.error(f"Direct connection failed: {e}")
                raise
        
        # Process HTML content
        if is_binary_content(html_content):
            html_text = decompress_if_needed(html_content)
        else:
            html_text = html_content.decode('utf-8', errors='replace')
        
        # Extract text using trafilatura
        extracted_text = extract_text_from_html(
            html_content=html_text,
            output_format=output_format,
            target_language=target_language,
            preference=preference
        )
        
        if not extracted_text:
            raise ValueError("No text content could be extracted")
        
        # Detect language
        detected_lang = get_lang(extracted_text) if target_language == "auto" else target_language
        
        # Extract links if requested
        extracted_links = []
        if include_links:
            extracted_links = extract_links_from_html(html_text, final_url)
        
        # Calculate quality metrics if requested
        quality_metrics = None
        if calculate_quality:
            quality_metrics = calculate_quality_metrics(extracted_text)
        
        # Determine appropriate message based on HTTP status and content quality
        if http_status == 404:
            status_message = f"HTTP 404 detected, but {len(extracted_text)} characters successfully extracted. This may be intentional anti-crawling behavior."
        elif http_status >= 400:
            status_message = f"HTTP {http_status} detected, but {len(extracted_text)} characters successfully extracted. Content appears valid despite error status."
        elif http_status == 200:
            status_message = "Text extracted successfully"
        else:
            status_message = f"HTTP {http_status} - Text extracted successfully ({len(extracted_text)} characters)"
        
        # Generate timestamp and origin information
        extraction_timestamp = datetime.now(timezone.utc).isoformat()
        extraction_origin = "realtime_crawl"  # This is a live extraction
        
        # Build result
        result = {
            "text": extracted_text,
            "status": http_status,  # Always show actual HTTP status code
            "reason": "success",
            "message": status_message,
            "lang": detected_lang,
            "mode": "simple",
            "final_url": final_url,
            "converted": False,
            "original_format": None,
            "file_size_mb": None,
            "proxy_used": proxy_used,
            "links": extracted_links if include_links else None,
            "quality_metrics": quality_metrics,
            "extraction_timestamp": extraction_timestamp,
            "extraction_origin": extraction_origin
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Extraction failed for {url}: {e}")
        
        return {
            "text": "",
            "status": 500,
            "reason": "extraction_error",
            "message": f"Extraction failed: {str(e)}",
            "lang": "unknown",
            "mode": "simple",
            "final_url": url,
            "converted": False,
            "original_format": None,
            "file_size_mb": None,
            "proxy_used": None,
            "links": [] if include_links else None,
            "quality_metrics": None
        }
