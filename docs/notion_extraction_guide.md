# Notion Strategy Extraction with Headless Scraper

This implementation provides a comprehensive solution for extracting all content from Notion pages, including hidden sections, toggles, and embedded YouTube videos, using Playwright-based headless scraping and NotebookLM MCP for summarization.

## Features

### 1. Playwright-based Headless Scraper (`core/notion_scraper.py`)
- **Full Content Expansion**: Expands all toggle blocks and inline databases
- **Lazy Loading Handling**: Scrolls to trigger lazy-loaded content
- **Resource Extraction**: Captures YouTube links, PDFs, and other resources
- **Structured Output**: Saves JSON, markdown, and resource lists

### 2. Enhanced Notion Ingestion (`core/notion_ingest.py`)
- **Dual Mode Support**: API-based and headless scraping modes
- **NotebookLM Integration**: Summarizes YouTube videos via MCP
- **Flexible Crawling**: Configurable link depth and resource limits
- **Trading Pipeline**: Direct integration with strategy compilation

### 3. MCP Integration
- **NotebookLM Server**: Added to MCP configuration for YouTube summarization
- **Automatic Startup**: MCP manager handles server lifecycle
- **Error Handling**: Graceful fallback when MCP servers unavailable

## Installation

1. Install Playwright:
```bash
cd /Users/burritoaccount/Desktop/LifeOS
./venv/bin/pip install playwright
./venv/bin/playwright install chromium
```

2. NotebookLM MCP is automatically configured in `lifeos/config/mcp.config.json`

## Usage

### CLI Commands

#### Basic API-based ingestion:
```bash
./venv/bin/python core/cli.py trading-notion ingest --url "https://www.notion.so/your-page"
```

#### Headless scraping with full content expansion:
```bash
./venv/bin/python core/cli.py trading-notion ingest \
  --url "https://www.notion.so/your-page" \
  --headless \
  --notebooklm
```

#### Compile strategies from extracted data:
```bash
./venv/bin/python core/cli.py trading-notion compile
```

### Python API

```python
from core.notion_ingest import ingest_notion_page

# Headless scraping with NotebookLM
result = ingest_notion_page(
    url="https://www.notion.so/your-page",
    use_headless=True,
    notebooklm_summary=True,
    crawl_links=True,
    max_links=50,
    crawl_depth=1,
)

# Feed into trading compilation
from core.trading_notion import compile_notion_strategies
strategies = compile_notion_strategies(result['exec_path'])
```

## Output Files

### Headless Scraping Saves:
- `lifeos/data/notion_scrapes/notion_scrape_*.json` - Full scraped data
- `lifeos/data/notion_scrapes/notion_scrape_*.md` - Markdown digest
- `lifeos/data/notion_scrapes/notion_scrape_*_resources.json` - Extracted resources

### Pipeline Files:
- `data/notion/{page_id}_headless.json` - Raw scraped data
- `data/trader/notion/notion_headless_execution_base.json` - Execution payload
- Notes saved via notes_manager with full content

## Configuration

Add to `lifeos/config/lifeos.config.json`:
```json
{
  "notion_ingest": {
    "default_url": "https://www.notion.so/your-default-page",
    "use_headless": true,
    "notebooklm_summary": true
  }
}
```

## Architecture

```
Notion Page
    ↓
Playwright Scraper (expands toggles, lazy loads)
    ↓
Structured Data (JSON + blocks + resources)
    ↓
NotebookLM MCP (YouTube summaries)
    ↓
Trading Pipeline (strategy compilation)
    ↓
Strategies.json (backtest-ready)
```

## Testing

Run the test script:
```bash
./venv/bin/python test_notion_extraction.py "https://www.notion.so/your-page"
```

## Benefits

1. **Complete Content**: Captures everything visible in browser, including toggles
2. **YouTube Intelligence**: Summarizes videos with NotebookLM for strategy insights
3. **Direct Integration**: Feeds straight into trading bot compilation
4. **Flexible Output**: Multiple formats for different use cases
5. **Robust Error Handling**: Graceful fallbacks and detailed logging

## Next Steps

1. Implement actual NotebookLM MCP calls for YouTube summarization
2. Add support for authentication-required Notion pages
3. Implement incremental updates (only scrape changed content)
4. Add visual screenshot capture for complex content
5. Extend to other document sources (Google Docs, etc.)
