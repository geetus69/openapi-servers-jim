import requests
import re
from urllib.parse import urlparse, urljoin
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
import mimetypes
import json

app = FastAPI(
    title="URL Access API",
    version="1.0.0",
    description="Provides URL content retrieval and processing for LLMs. Fetches web pages, extracts text content, and handles various content types.",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Pydantic models
# -------------------------------

class URLContentResponse(BaseModel):
    url: str = Field(..., description="The original URL that was accessed")
    title: Optional[str] = Field(None, description="Page title if available")
    content: str = Field(..., description="Extracted text content from the URL")
    content_type: str = Field(..., description="MIME type of the content")
    status_code: int = Field(..., description="HTTP status code of the response")
    word_count: int = Field(..., description="Number of words in the extracted content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the content")

class URLAnalysisResponse(BaseModel):
    url: str = Field(..., description="The URL that was analyzed")
    is_accessible: bool = Field(..., description="Whether the URL is accessible")
    content_type: Optional[str] = Field(None, description="MIME type of the content")
    content_length: Optional[int] = Field(None, description="Content length in bytes")
    status_code: Optional[int] = Field(None, description="HTTP status code")
    error_message: Optional[str] = Field(None, description="Error message if URL is not accessible")

# -------------------------------
# Helper functions
# -------------------------------

def extract_text_from_html(html_content: str, url: str) -> Tuple[str, str, dict]:
    """Extract text content and metadata from HTML."""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Extract title
    title = None
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text().strip()
    
    # Extract metadata
    metadata = {}
    
    # Meta description
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        metadata['description'] = meta_desc.get('content', '')
    
    # Meta keywords
    meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
    if meta_keywords:
        metadata['keywords'] = meta_keywords.get('content', '')
    
    # Open Graph data
    og_tags = soup.find_all('meta', property=re.compile(r'^og:'))
    for tag in og_tags:
        property_name = tag.get('property', '').replace('og:', '')
        content = tag.get('content', '')
        if property_name and content:
            metadata[f'og_{property_name}'] = content
    
    # Extract main content
    # Try to find main content areas first
    main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile(r'content|main|article'))
    
    if main_content:
        text = main_content.get_text()
    else:
        # Fall back to body content
        body = soup.find('body')
        text = body.get_text() if body else soup.get_text()
    
    # Clean up text
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text, title, metadata

def get_user_agent():
    """Return a reasonable user agent string."""
    return "Mozilla/5.0 (compatible; URL-Access-Tool/1.0; +https://github.com/open-webui/openapi-servers)"

# -------------------------------
# Routes
# -------------------------------

@app.get("/fetch", response_model=URLContentResponse, summary="Fetch and extract content from a URL")
def fetch_url_content(
    url: HttpUrl = Query(..., description="The URL to fetch content from"),
    extract_text: bool = Query(True, description="Whether to extract text content from HTML"),
    follow_redirects: bool = Query(True, description="Whether to follow HTTP redirects"),
    timeout: int = Query(30, description="Request timeout in seconds", ge=1, le=120)
):
    """
    Fetches content from the specified URL and extracts readable text.
    Supports various content types including HTML, plain text, and JSON.
    For HTML content, extracts the main text content and metadata.
    """
    url_str = str(url)
    
    headers = {
        'User-Agent': get_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
    }
    
    try:
        response = requests.get(
            url_str,
            headers=headers,
            timeout=timeout,
            allow_redirects=follow_redirects,
            stream=True
        )
        response.raise_for_status()
        
        # Get content type
        content_type = response.headers.get('content-type', '').lower()
        
        # Read content with size limit (10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > max_size:
                raise HTTPException(status_code=413, detail="Content too large (max 10MB)")
        
        # Decode content
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text_content = content.decode('latin-1')
            except UnicodeDecodeError:
                raise HTTPException(status_code=422, detail="Unable to decode content as text")
        
        title = None
        metadata = {}
        
        # Process based on content type
        if 'text/html' in content_type and extract_text:
            text_content, title, metadata = extract_text_from_html(text_content, url_str)
        elif 'application/json' in content_type:
            try:
                # Pretty print JSON
                json_data = json.loads(text_content)
                text_content = json.dumps(json_data, indent=2)
                metadata['json_keys'] = list(json_data.keys()) if isinstance(json_data, dict) else []
            except json.JSONDecodeError:
                pass  # Keep original content if JSON parsing fails
        
        # Count words
        word_count = len(text_content.split())
        
        return URLContentResponse(
            url=url_str,
            title=title,
            content=text_content,
            content_type=content_type,
            status_code=response.status_code,
            word_count=word_count,
            metadata=metadata
        )
        
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=408, detail="Request timeout")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Unable to connect to the URL")
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"HTTP error: {e}")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An internal error occurred: {str(e)}")

@app.get("/analyze", response_model=URLAnalysisResponse, summary="Analyze a URL without fetching full content")
def analyze_url(
    url: HttpUrl = Query(..., description="The URL to analyze"),
    timeout: int = Query(10, description="Request timeout in seconds", ge=1, le=60)
):
    """
    Analyzes a URL by making a HEAD request to check accessibility,
    content type, and size without downloading the full content.
    """
    url_str = str(url)
    
    headers = {
        'User-Agent': get_user_agent(),
    }
    
    try:
        response = requests.head(
            url_str,
            headers=headers,
            timeout=timeout,
            allow_redirects=True
        )
        
        content_type = response.headers.get('content-type', '')
        content_length = response.headers.get('content-length')
        content_length = int(content_length) if content_length and content_length.isdigit() else None
        
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=True,
            content_type=content_type,
            content_length=content_length,
            status_code=response.status_code,
            error_message=None
        )
        
    except requests.exceptions.Timeout:
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=False,
            error_message="Request timeout"
        )
    except requests.exceptions.ConnectionError:
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=False,
            error_message="Unable to connect to the URL"
        )
    except requests.exceptions.HTTPError as e:
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=False,
            status_code=e.response.status_code,
            error_message=f"HTTP error: {e}"
        )
    except requests.exceptions.RequestException as e:
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=False,
            error_message=f"Request error: {str(e)}"
        )
    except Exception as e:
        return URLAnalysisResponse(
            url=url_str,
            is_accessible=False,
            error_message=f"An internal error occurred: {str(e)}"
        )

@app.get("/health", summary="Health check endpoint")
def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "service": "url-access-api"} 