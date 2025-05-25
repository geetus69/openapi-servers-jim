# URL Access API Server

A FastAPI-based OpenAPI tool server that provides URL content retrieval and processing capabilities for LLMs. This tool allows AI agents to fetch, analyze, and extract content from URLs shared by users.

## Features

- **URL Content Fetching**: Retrieve and extract readable text content from web pages
- **Content Analysis**: Analyze URLs without downloading full content (HEAD requests)
- **HTML Processing**: Extract clean text content, titles, and metadata from HTML pages
- **JSON Support**: Pretty-print and analyze JSON responses
- **Security Features**: Content size limits, timeout controls, and safe content handling
- **Metadata Extraction**: Extract page titles, descriptions, Open Graph data, and more

## API Endpoints

### `GET /fetch`
Fetches content from a URL and extracts readable text.

**Parameters:**
- `url` (required): The URL to fetch content from
- `extract_text` (optional, default: true): Whether to extract text content from HTML
- `follow_redirects` (optional, default: true): Whether to follow HTTP redirects
- `timeout` (optional, default: 30): Request timeout in seconds (1-120)

**Response:**
```json
{
  "url": "https://example.com",
  "title": "Page Title",
  "content": "Extracted text content...",
  "content_type": "text/html; charset=utf-8",
  "status_code": 200,
  "word_count": 150,
  "metadata": {
    "description": "Page description",
    "keywords": "keyword1, keyword2",
    "og_title": "Open Graph title"
  }
}
```

### `GET /analyze`
Analyzes a URL without fetching full content (HEAD request only).

**Parameters:**
- `url` (required): The URL to analyze
- `timeout` (optional, default: 10): Request timeout in seconds (1-60)

**Response:**
```json
{
  "url": "https://example.com",
  "is_accessible": true,
  "content_type": "text/html; charset=utf-8",
  "content_length": 12345,
  "status_code": 200,
  "error_message": null
}
```

### `GET /health`
Health check endpoint.

## Installation & Usage

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker

1. Build and run with Docker Compose:
```bash
docker compose up
```

The API will be available at `http://localhost:8000` with interactive documentation at `http://localhost:8000/docs`.

## Security Considerations

- **Content Size Limit**: Maximum 10MB per request to prevent memory issues
- **Timeout Controls**: Configurable timeouts to prevent hanging requests
- **User Agent**: Uses a proper user agent string for respectful web scraping
- **Error Handling**: Comprehensive error handling for various failure scenarios

## Use Cases

- **Research Assistance**: Help LLMs access and analyze web content shared by users
- **Content Summarization**: Extract clean text for summarization tasks
- **Link Validation**: Check if URLs are accessible before processing
- **Metadata Extraction**: Get structured information about web pages

## Example Usage

```python
import requests

# Fetch content from a URL
response = requests.get("http://localhost:8000/fetch", params={
    "url": "https://example.com",
    "extract_text": True
})

content_data = response.json()
print(f"Title: {content_data['title']}")
print(f"Content: {content_data['content'][:200]}...")
```

## Integration with LLMs

This tool is designed to be automatically triggered when users share URLs in their messages. The LLM can:

1. Detect URLs in user messages
2. Use the `/analyze` endpoint to check accessibility
3. Use the `/fetch` endpoint to retrieve and process content
4. Provide summaries, answer questions, or perform analysis on the content

## Error Handling

The API provides detailed error responses for various scenarios:
- **408**: Request timeout
- **413**: Content too large (>10MB)
- **422**: Unable to decode content as text
- **503**: Unable to connect to URL
- **500**: Internal server errors

## Contributing

This server follows the OpenAPI Tool Server pattern used throughout this repository. Feel free to extend functionality or improve existing features. 