"""
MarkItDown-based file converter module.

This module provides async file conversion capabilities using Microsoft's MarkItDown library,
replacing the previous Pandoc and pymupdf4llm dependencies with a pure Python solution.

Supports 25+ file formats including:
- Documents: PDF, DOCX, PPTX, XLSX, ODT, RTF
- Images: JPG, PNG, GIF, BMP, TIFF, SVG, WebP
- Audio/Video: MP3, WAV, MP4, AVI, MOV (with transcription)
- Web: HTML, Markdown, XML
- YouTube videos (with transcription)
- Email formats: EML, MSG
"""

import asyncio
import io
import logging
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

# Global variable to track MarkItDown availability
_markitdown_available = None

def is_markitdown_available() -> bool:
    """Check if MarkItDown is available for import."""
    global _markitdown_available
    
    if _markitdown_available is None:
        try:
            import markitdown
            _markitdown_available = True
        except ImportError:
            _markitdown_available = False
            
    return _markitdown_available

# MarkItDown supported formats mapping
MARKITDOWN_SUPPORTED_FORMATS = {
    # Documents
    'pdf': 'PDF Document',
    'docx': 'Microsoft Word Document',
    'doc': 'Microsoft Word Document (Legacy)',
    'pptx': 'Microsoft PowerPoint Presentation',
    'ppt': 'Microsoft PowerPoint Presentation (Legacy)',
    'xlsx': 'Microsoft Excel Spreadsheet',
    'xls': 'Microsoft Excel Spreadsheet (Legacy)',
    'odt': 'OpenDocument Text',
    'ods': 'OpenDocument Spreadsheet',
    'odp': 'OpenDocument Presentation',
    'rtf': 'Rich Text Format',
    'txt': 'Plain Text',
    
    # Images
    'jpg': 'JPEG Image',
    'jpeg': 'JPEG Image',
    'png': 'PNG Image',
    'gif': 'GIF Image',
    'bmp': 'Bitmap Image',
    'tiff': 'TIFF Image',
    'tif': 'TIFF Image',
    'svg': 'SVG Vector Image',
    'webp': 'WebP Image',
    
    # Audio/Video (with transcription)
    'mp3': 'MP3 Audio',
    'wav': 'WAV Audio',
    'mp4': 'MP4 Video',
    'avi': 'AVI Video',
    'mov': 'QuickTime Video',
    'mkv': 'Matroska Video',
    'wmv': 'Windows Media Video',
    'flv': 'Flash Video',
    'webm': 'WebM Video',
    'm4a': 'M4A Audio',
    'aac': 'AAC Audio',
    'ogg': 'OGG Audio',
    'flac': 'FLAC Audio',
    
    # Web formats
    'html': 'HTML Document',
    'htm': 'HTML Document',
    'xml': 'XML Document',
    'md': 'Markdown Document',
    'markdown': 'Markdown Document',
    
    # Email formats
    'eml': 'Email Message',
    'msg': 'Outlook Message',
    
    # Archives (limited support)
    'zip': 'ZIP Archive'
}

class MarkItDownConversionError(Exception):
    """Custom exception for MarkItDown conversion errors."""
    pass

class MarkItDownConverter:
    """Async MarkItDown-based file converter.
    
    Provides in-memory file conversion with configurable size limits and timeouts.
    Supports all MarkItDown-compatible formats including YouTube video transcription.
    """
    
    def __init__(self, max_file_size_mb: int = 5, timeout_seconds: int = 60, 
                 enable_transcription: bool = True):
        """
        Initialize the MarkItDown converter.
        
        Args:
            max_file_size_mb: Maximum file size in MB (1-100)
            timeout_seconds: Conversion timeout in seconds (10-300)
            enable_transcription: Enable audio/video transcription
        """
        if not is_markitdown_available():
            raise ImportError("MarkItDown is not available. Install with: pip install 'markitdown[all]'")
        
        # Validate parameters
        self.max_file_size_mb = max(1, min(100, max_file_size_mb))
        self.timeout_seconds = max(10, min(300, timeout_seconds))
        self.enable_transcription = enable_transcription
        
        # Setup logging first
        self.logger = logging.getLogger(__name__)
        
        # Initialize MarkItDown
        self._init_markitdown()
    
    def _init_markitdown(self):
        """Initialize the MarkItDown instance."""
        try:
            import markitdown
            self.markitdown = markitdown.MarkItDown()
            self.logger.info("MarkItDown converter initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize MarkItDown: {e}")
            raise MarkItDownConversionError(f"MarkItDown initialization failed: {e}")

    @staticmethod
    def _guess_file_format(content: bytes) -> Optional[str]:
        """Attempt to guess the file format from the binary signature."""
        if not content:
            return None

        # PDF header
        if content.startswith(b"%PDF"):
            return "pdf"

        # RTF documents start with "{\rtf"
        if content.startswith(b"{\\rtf"):
            return "rtf"

        # OpenXML-based formats (docx, xlsx, pptx) are zipped containers
        if content.startswith(b"PK"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as archive:
                    names = archive.namelist()
                    if any(name.startswith("word/") for name in names):
                        return "docx"
                    if any(name.startswith("xl/") for name in names):
                        return "xlsx"
                    if any(name.startswith("ppt/") for name in names):
                        return "pptx"
            except zipfile.BadZipFile:
                return None

        # Fallback: try to decode as text – treat as plain text if successful
        try:
            content[:1024].decode("utf-8")
            return "txt"
        except Exception:
            return None

        return None

    def _normalise_format(
        self,
        file_format: Optional[str],
        filename: Optional[str],
        content: bytes,
    ) -> str:
        """Determine the most likely file format for conversion."""

        candidate = (file_format or "").lower().lstrip(".")

        if not candidate or candidate == "unknown":
            if filename:
                candidate = Path(filename).suffix.lstrip(".").lower()

        if not candidate or candidate == "unknown":
            guessed = self._guess_file_format(content)
            if guessed:
                candidate = guessed

        if not candidate:
            raise MarkItDownConversionError("Unable to determine file format for conversion")

        if not self.is_convertible_format(candidate):
            raise MarkItDownConversionError(f"Unsupported format: {candidate}")

        return candidate
    
    def get_supported_formats(self) -> Dict[str, str]:
        """Get dictionary of supported formats."""
        return MARKITDOWN_SUPPORTED_FORMATS.copy()
    
    def is_convertible_format(self, file_extension: str) -> bool:
        """Check if a file extension is supported for conversion."""
        return file_extension.lower().lstrip('.') in MARKITDOWN_SUPPORTED_FORMATS
    
    def is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube video."""
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^&\n?#]+)',
            r'(?:https?://)?(?:www\.)?youtu\.be/([^&\n?#]+)',
            r'(?:https?://)?(?:www\.)?youtube\.com/embed/([^&\n?#]+)',
            r'(?:https?://)?(?:m\.)?youtube\.com/watch\?v=([^&\n?#]+)'
        ]
        
        for pattern in youtube_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def _validate_file_size(self, content: bytes) -> None:
        """Validate file size against limits."""
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > self.max_file_size_mb:
            raise MarkItDownConversionError(
                f"File size ({file_size_mb:.2f}MB) exceeds limit ({self.max_file_size_mb}MB)"
            )
    
    async def convert_file_to_markdown(
        self,
        content: bytes,
        file_format: str,
        filename: Optional[str] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Convert file content to markdown using MarkItDown.
        
        Args:
            content: File content as bytes
            file_format: File extension (e.g., 'pdf', 'docx')
            filename: Optional original filename
            
        Returns:
            Tuple of (converted_text, metadata)
            
        Raises:
            MarkItDownConversionError: If conversion fails
        """
        normalised_format = self._normalise_format(file_format, filename, content)

        # Validate file size
        self._validate_file_size(content)

        file_size_mb = len(content) / (1024 * 1024)
        self.logger.info(
            "Converting %s file (%.2fMB) to markdown",
            normalised_format.upper(),
            file_size_mb,
        )

        try:
            # Convert using async wrapper
            result_text = await self._convert_file_async(content, normalised_format)

            metadata = {
                "converted": True,
                "original_format": normalised_format.upper(),
                "file_size_mb": round(file_size_mb, 3),
                "conversion_method": "markitdown",
                "character_length": len(result_text),
            }

            self.logger.info(
                "Successfully converted %s file (%d characters)",
                normalised_format.upper(),
                len(result_text),
            )
            return result_text, metadata

        except Exception as e:
            self.logger.error(f"MarkItDown conversion failed: {e}")
            raise MarkItDownConversionError(f"Conversion failed: {e}")

    async def _convert_file_async(self, content: bytes, file_format: str) -> str:
        """Async wrapper for MarkItDown conversion."""
        def _convert() -> str:
            stream = io.BytesIO(content)
            stream.seek(0)

            try:
                result = self.markitdown.convert(stream, file_extension=f".{file_format}")
            except TypeError:
                # Some converters expect a path on disk – fall back to a temp file
                with tempfile.NamedTemporaryFile(suffix=f".{file_format}", delete=False) as temp_file:
                    temp_file.write(content)
                    temp_file.flush()
                    temp_path = Path(temp_file.name)

                try:
                    result = self.markitdown.convert(str(temp_path))
                finally:
                    try:
                        temp_path.unlink()
                    except Exception:
                        pass
            except Exception as exc:  # pragma: no cover - defensive
                raise MarkItDownConversionError(f"MarkItDown conversion error: {exc}") from exc

            markdown = getattr(result, "markdown", None) or getattr(result, "text_content", None)
            if not markdown:
                raise MarkItDownConversionError("MarkItDown returned no textual content")

            return markdown.strip()

        # Run conversion in thread pool with timeout
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_convert),
                timeout=self.timeout_seconds,
            )
        except asyncio.TimeoutError:
            raise MarkItDownConversionError(f"Conversion timed out after {self.timeout_seconds}s")

    async def convert_youtube_to_markdown(self, youtube_url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Convert YouTube video to markdown with transcription.
        
        Args:
            youtube_url: YouTube video URL
            
        Returns:
            Tuple of (converted_text, metadata)
            
        Raises:
            MarkItDownConversionError: If conversion fails
        """
        if not self.enable_transcription:
            raise MarkItDownConversionError("YouTube transcription is disabled")
        
        if not self.is_youtube_url(youtube_url):
            raise MarkItDownConversionError("Invalid YouTube URL")
        
        self.logger.info(f"Converting YouTube video: {youtube_url}")
        
        try:
            result = await self._convert_youtube_async(youtube_url)
            
            metadata = {
                'converted': True,
                'original_format': 'YOUTUBE',
                'source_url': youtube_url,
                'conversion_method': 'markitdown_youtube'
            }
            
            self.logger.info(f"Successfully converted YouTube video ({len(result)} characters)")
            return result, metadata
            
        except Exception as e:
            self.logger.error(f"YouTube conversion failed: {e}")
            raise MarkItDownConversionError(f"YouTube conversion failed: {e}")
    
    async def _convert_youtube_async(self, youtube_url: str) -> str:
        """Async wrapper for YouTube conversion."""
        def _convert() -> str:
            try:
                result = self.markitdown.convert(youtube_url)
            except Exception as exc:  # pragma: no cover - defensive
                raise MarkItDownConversionError(f"YouTube conversion error: {exc}") from exc

            markdown = getattr(result, "markdown", None) or getattr(result, "text_content", None)
            if not markdown:
                raise MarkItDownConversionError("MarkItDown returned no textual content for the video")

            return markdown.strip()

        # Run conversion in thread pool with timeout (longer for videos)
        video_timeout = max(self.timeout_seconds * 2, 120)  # At least 2 minutes for videos
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_convert),
                timeout=video_timeout,
            )
        except asyncio.TimeoutError:
            raise MarkItDownConversionError(f"YouTube conversion timed out after {video_timeout}s")

# Global converter instance
_global_converter = None

def get_markitdown_converter(max_file_size_mb: int = 5, timeout_seconds: int = 60) -> MarkItDownConverter:
    """
    Get a global MarkItDown converter instance.
    
    Args:
        max_file_size_mb: Maximum file size in MB
        timeout_seconds: Conversion timeout in seconds
        
    Returns:
        MarkItDownConverter instance
    """
    global _global_converter
    
    if _global_converter is None:
        _global_converter = MarkItDownConverter(
            max_file_size_mb=max_file_size_mb,
            timeout_seconds=timeout_seconds
        )
    
    return _global_converter

# Convenience functions
def get_supported_formats() -> Dict[str, str]:
    """Get dictionary of supported file formats."""
    return MARKITDOWN_SUPPORTED_FORMATS.copy()

def is_convertible_format(file_extension: str) -> bool:
    """Check if a file extension is supported for conversion."""
    return file_extension.lower().lstrip('.') in MARKITDOWN_SUPPORTED_FORMATS

def is_youtube_url(url: str) -> bool:
    """Check if URL is a YouTube video."""
    converter = get_markitdown_converter()
    return converter.is_youtube_url(url)
