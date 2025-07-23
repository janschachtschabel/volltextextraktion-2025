"""
File Conversion Module - Clean Implementation

This module provides file format conversion capabilities using MarkItDown
for converting various document formats (DOCX, PDF, XLSX, etc.) to text/markdown.

This is a clean, minimal implementation that addresses all historical problems
while providing robust file conversion with proper error handling.
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def convert_file_to_markdown(
    content: bytes,
    url: str,
    output_format: str = "markdown",
    max_file_size_mb: int = 50,
    timeout_seconds: int = 60
) -> Tuple[str, Dict[str, any]]:
    """
    Convert file content to markdown/text using MarkItDown.
    
    Args:
        content: Raw file content as bytes
        url: Original URL for context and format detection
        output_format: Desired output format (markdown, text, etc.)
        max_file_size_mb: Maximum file size limit
        timeout_seconds: Conversion timeout
    
    Returns:
        Tuple of (converted_text, metadata_dict)
    """
    try:
        # Check file size
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            return "", {
                "converted": False,
                "reason": f"file_too_large",
                "size_mb": round(file_size_mb, 2),
                "max_size_mb": max_file_size_mb
            }
        
        # Try MarkItDown conversion first
        try:
            converted_text, format_info = _convert_with_markitdown(
                content, url, output_format, timeout_seconds
            )
            
            if converted_text:
                return converted_text, {
                    "converted": True,
                    "format": format_info.get("format", "unknown"),
                    "size_mb": round(file_size_mb, 2),
                    "method": "markitdown"
                }
        except ImportError:
            logger.warning("MarkItDown not available, trying fallback conversion")
        except Exception as e:
            logger.warning(f"MarkItDown conversion failed: {e}")
        
        # Fallback to basic conversion methods
        converted_text, format_info = _convert_with_fallback(
            content, url, output_format, timeout_seconds
        )
        
        if converted_text:
            return converted_text, {
                "converted": True,
                "format": format_info.get("format", "unknown"),
                "size_mb": round(file_size_mb, 2),
                "method": "fallback"
            }
        
        # No conversion possible
        return "", {
            "converted": False,
            "reason": "conversion_failed",
            "size_mb": round(file_size_mb, 2)
        }
        
    except Exception as e:
        logger.error(f"File conversion failed: {e}")
        return "", {
            "converted": False,
            "reason": f"error: {str(e)}",
            "size_mb": 0
        }


def _convert_with_markitdown(
    content: bytes,
    url: str,
    output_format: str,
    timeout_seconds: int
) -> Tuple[str, Dict[str, str]]:
    """Convert using MarkItDown library."""
    try:
        # Try to import MarkItDown
        from markitdown import MarkItDown
        
        # Create converter instance
        md = MarkItDown()
        
        # Detect file format from URL
        file_format = _detect_file_format(url)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_format}") as temp_file:
            temp_file.write(content)
            temp_file.flush()
            
            try:
                # Convert file
                result = md.convert(temp_file.name)
                
                if result and result.text_content:
                    converted_text = result.text_content.strip()
                    
                    # Apply output format if needed
                    if output_format == "text":
                        # Strip markdown formatting for plain text
                        converted_text = _markdown_to_text(converted_text)
                    
                    return converted_text, {"format": file_format.upper()}
                else:
                    return "", {"format": file_format.upper()}
                    
            finally:
                # Cleanup temp file
                try:
                    Path(temp_file.name).unlink()
                except:
                    pass
        
    except ImportError:
        raise ImportError("MarkItDown not available")
    except Exception as e:
        logger.error(f"MarkItDown conversion error: {e}")
        return "", {"format": "unknown"}


def _convert_with_fallback(
    content: bytes,
    url: str,
    output_format: str,
    timeout_seconds: int
) -> Tuple[str, Dict[str, str]]:
    """Fallback conversion using basic methods."""
    try:
        file_format = _detect_file_format(url)
        
        # Basic text extraction for common formats
        if file_format.lower() in ['txt', 'csv']:
            # Try to decode as text
            for encoding in ['utf-8', 'latin1', 'cp1252']:
                try:
                    text = content.decode(encoding)
                    return text.strip(), {"format": file_format.upper()}
                except UnicodeDecodeError:
                    continue
        
        # For other formats, try external tools if available
        if file_format.lower() == 'pdf':
            return _convert_pdf_fallback(content, timeout_seconds)
        
        # No fallback available
        return "", {"format": file_format.upper()}
        
    except Exception as e:
        logger.error(f"Fallback conversion error: {e}")
        return "", {"format": "unknown"}


def _convert_pdf_fallback(content: bytes, timeout_seconds: int) -> Tuple[str, Dict[str, str]]:
    """Fallback PDF conversion using pdftotext if available."""
    try:
        # Check if pdftotext is available
        result = subprocess.run(
            ['pdftotext', '-v'],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode != 0:
            return "", {"format": "PDF"}
        
        # Use pdftotext for conversion
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
            temp_pdf.write(content)
            temp_pdf.flush()
            
            try:
                # Convert PDF to text
                result = subprocess.run(
                    ['pdftotext', temp_pdf.name, '-'],
                    capture_output=True,
                    timeout=timeout_seconds,
                    text=True
                )
                
                if result.returncode == 0 and result.stdout:
                    return result.stdout.strip(), {"format": "PDF"}
                else:
                    return "", {"format": "PDF"}
                    
            finally:
                try:
                    Path(temp_pdf.name).unlink()
                except:
                    pass
        
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("pdftotext not available or timed out")
        return "", {"format": "PDF"}
    except Exception as e:
        logger.error(f"PDF fallback conversion error: {e}")
        return "", {"format": "PDF"}


def _detect_file_format(url: str) -> str:
    """Detect file format from URL extension."""
    try:
        # Extract extension from URL
        url_lower = url.lower()
        
        # Common document formats
        format_map = {
            '.pdf': 'pdf',
            '.doc': 'doc',
            '.docx': 'docx',
            '.xls': 'xls',
            '.xlsx': 'xlsx',
            '.ppt': 'ppt',
            '.pptx': 'pptx',
            '.odt': 'odt',
            '.ods': 'ods',
            '.odp': 'odp',
            '.rtf': 'rtf',
            '.txt': 'txt',
            '.csv': 'csv',
            '.html': 'html',
            '.htm': 'html',
            '.xml': 'xml'
        }
        
        for ext, format_name in format_map.items():
            if ext in url_lower:
                return format_name
        
        return 'unknown'
        
    except Exception:
        return 'unknown'


def _markdown_to_text(markdown_text: str) -> str:
    """Convert markdown to plain text by removing formatting."""
    try:
        import re
        
        # Remove markdown formatting
        text = markdown_text
        
        # Remove headers
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
        
        # Remove bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        
        # Remove links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        
        # Remove code blocks
        text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        
        # Remove list markers
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        
        # Clean up whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()
        
        return text
        
    except Exception as e:
        logger.warning(f"Markdown to text conversion failed: {e}")
        return markdown_text


def is_convertible_format(url: str) -> bool:
    """Check if URL points to a convertible file format."""
    convertible_formats = [
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.odt', '.ods', '.odp', '.rtf', '.txt', '.csv', '.html', '.htm'
    ]
    
    url_lower = url.lower()
    return any(fmt in url_lower for fmt in convertible_formats)


def get_supported_formats() -> list:
    """Get list of supported file formats."""
    return [
        'PDF', 'DOC', 'DOCX', 'XLS', 'XLSX', 'PPT', 'PPTX',
        'ODT', 'ODS', 'ODP', 'RTF', 'TXT', 'CSV', 'HTML', 'HTM'
    ]
