"""
Enhanced Browser Automation for Jarvis.
Performs useful actions after opening browsers.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import base64
import re
import logging

from core import config, providers, research_engine
from core.window_interaction import get_window_interactor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
BROWSER_PATH = ROOT / "data" / "browser_automation"
BROWSER_LOG_PATH = ROOT / "data" / "browser.log"


class BrowserAutomation:
    """Manages enhanced browser automation with useful actions."""
    
    def __init__(self):
        self.automation_db = BROWSER_PATH / "automation_data.json"
        self.window_interactor = get_window_interactor()
        self._ensure_directories()
        self._load_automation_data()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        BROWSER_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_automation_data(self):
        """Load automation data and patterns."""
        if self.automation_db.exists():
            with open(self.automation_db, "r") as f:
                self.automation_data = json.load(f)
        else:
            self.automation_data = {
                "scraped_data": [],
                "interactions": [],
                "screenshots": [],
                "forms_filled": [],
                "data_extracted": []
            }
    
    def _save_automation_data(self):
        """Save automation data."""
        with open(self.automation_db, "w") as f:
            json.dump(self.automation_data, f, indent=2)
    
    def _log_browser(self, action: str, details: Dict[str, Any]):
        """Log browser activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(BROWSER_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def extract_data_from_page(self, url: str, selectors: Optional[List[str]] = None) -> Dict[str, Any]:
        """Extract useful data from a web page."""
        if not selectors:
            # Default useful selectors
            selectors = [
                "title",
                "h1", "h2", "h3",
                "p",
                "a[href]",
                "img[src]",
                "table",
                "ul", "ol",
                ".price", ".cost",
                ".title", ".name",
                ".description",
                "[data-price]",
                "[data-name]"
            ]
        
        extraction_prompt = f"""Extract structured data from this webpage: {url}

For each of these CSS selectors, extract all matching content:
{json.dumps(selectors, indent=2)}

Focus on:
- Product names and prices
- Article titles and summaries
- Contact information
- Links and their text
- Key data points
- Tables and lists

Return as structured JSON with selector names as keys."""
        
        try:
            response = providers.ask_llm(extraction_prompt, max_output_tokens=800)
            
            extracted_data = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "selectors_used": selectors,
                "data": response,
                "success": True
            }
            
            self.automation_data["data_extracted"].append(extracted_data)
            self._save_automation_data()
            
            self._log_browser("data_extracted", {
                "url": url,
                "selectors": len(selectors)
            })
            
            return extracted_data
            
        except Exception as e:
            self._log_browser("data_extraction_error", {
                "url": url,
                "error": str(e)
            })
            return {"error": str(e)}
    
    def fill_forms_automatically(self, url: str, form_data: Dict[str, str]) -> Dict[str, Any]:
        """Automatically fill forms on a webpage."""
        fill_prompt = f"""Analyze forms on this webpage: {url}

And provide JavaScript code to automatically fill these forms:
{json.dumps(form_data, indent=2)}

Requirements:
1. Identify all form elements (input, textarea, select)
2. Match form data to appropriate fields
3. Generate safe JavaScript for filling
4. Include proper selectors and field identification
5. Add validation checks

Return the JavaScript code and field mapping."""
        
        try:
            response = providers.ask_llm(fill_prompt, max_output_tokens=600)
            
            form_fill_data = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "form_data": form_data,
                "javascript_code": response,
                "success": True
            }
            
            self.automation_data["forms_filled"].append(form_fill_data)
            self._save_automation_data()
            
            self._log_browser("form_fill_prepared", {
                "url": url,
                "fields": len(form_data)
            })
            
            return form_fill_data
            
        except Exception as e:
            self._log_browser("form_fill_error", {
                "url": url,
                "error": str(e)
            })
            return {"error": str(e)}
    
    def scrape_crypto_prices(self) -> Dict[str, Any]:
        """Scrape crypto prices from major exchanges."""
        crypto_sites = [
            {"name": "CoinGecko", "url": "https://www.coingecko.com", "selectors": ["table tbody tr", ".price", ".tw-text-lg"]},
            {"name": "CoinMarketCap", "url": "https://coinmarketcap.com", "selectors": ["table tbody tr", ".price", ".cmc-table-row"]},
            {"name": "Binance", "url": "https://www.binance.com/en/markets", "selectors": ["table tbody tr", ".price", ".css-1b7t8kb"]}
        ]
        
        scraped_data = []
        
        for site in crypto_sites:
            try:
                data = self.extract_data_from_page(site["url"], site["selectors"])
                if "error" not in data:
                    data["exchange"] = site["name"]
                    scraped_data.append(data)
                    
                    # Extract specific price information
                    price_analysis_prompt = f"""From this scraped data, extract cryptocurrency prices and market data:

{data.get('data', '')}

Focus on:
- Top 10 cryptocurrencies by market cap
- Current prices
- 24h changes
- Volume data

Return as structured JSON with symbol, price, change, volume."""
                    
                    price_response = providers.ask_llm(price_analysis_prompt, max_output_tokens=400)
                    
                    price_data = {
                        "exchange": site["name"],
                        "timestamp": datetime.now().isoformat(),
                        "price_data": price_response
                    }
                    
                    self.automation_data["scraped_data"].append(price_data)
                    
            except Exception as e:
                self._log_browser("crypto_scrape_error", {
                    "site": site["name"],
                    "error": str(e)
                })
        
        self._save_automation_data()
        
        return {
            "scraped_exchanges": len(scraped_data),
            "timestamp": datetime.now().isoformat(),
            "data": scraped_data
        }
    
    def research_topic_automatically(self, topic: str, depth: int = 3) -> Dict[str, Any]:
        """Automatically research a topic by visiting multiple sources."""
        # Get search results
        engine = research_engine.get_research_engine()
        search_results = engine.search_web(topic, max_results=depth * 2)
        
        researched_data = []
        
        for i, result in enumerate(search_results[:depth]):
            try:
                # Extract data from each page
                page_data = self.extract_data_from_page(result["url"])
                
                if "error" not in page_data:
                    # Summarize the content
                    summary_prompt = f"""Summarize this webpage content about {topic}:

URL: {result['url']}
Title: {result['title']}
Extracted Data: {page_data.get('data', '')}

Provide:
1. Key points (3-5 bullet points)
2. Important facts or data
3. Relevant quotes or statistics
4. Source credibility assessment

Focus on information relevant to {topic}."""
                    
                    summary = providers.ask_llm(summary_prompt, max_output_tokens=500)
                    
                    research_item = {
                        "url": result["url"],
                        "title": result["title"],
                        "summary": summary,
                        "extracted_data": page_data.get("data", ""),
                        "researched_at": datetime.now().isoformat()
                    }
                    
                    researched_data.append(research_item)
                    
            except Exception as e:
                self._log_browser("research_error", {
                    "url": result["url"],
                    "error": str(e)
                })
        
        # Create comprehensive summary
        if researched_data:
            summary_prompt = f"""Create a comprehensive research summary about {topic} from these sources:

{json.dumps([{'title': r['title'], 'summary': r['summary']} for r in researched_data], indent=2)}

Provide:
1. Executive summary (2-3 paragraphs)
2. Key findings (5-7 bullet points)
3. Important statistics or data
4. Source synthesis and contradictions
5. Further research recommendations"""
            
            comprehensive_summary = providers.ask_llm(summary_prompt, max_output_tokens=600)
            
            research_result = {
                "topic": topic,
                "timestamp": datetime.now().isoformat(),
                "sources_visited": len(researched_data),
                "research_data": researched_data,
                "comprehensive_summary": comprehensive_summary
            }
            
            self.automation_data["scraped_data"].append(research_result)
            self._save_automation_data()
            
            return research_result
        
        return {"error": "No data successfully scraped"}
    
    def monitor_website_changes(self, url: str, check_interval: int = 60) -> Dict[str, Any]:
        """Monitor a website for changes."""
        # Get current content
        current_data = self.extract_data_from_page(url)
        
        if "error" in current_data:
            return current_data
        
        # Check for previous data
        previous_data = None
        for item in self.automation_data["scraped_data"]:
            if item.get("url") == url:
                previous_data = item
                break
        
        if previous_data:
            # Compare for changes
            comparison_prompt = f"""Compare these two versions of webpage content:

Previous: {previous_data.get('data', '')[:1000]}
Current: {current_data.get('data', '')[:1000]}

Identify:
1. New content added
2. Content removed
3. Modified content
4. Structural changes
5. Price or data changes

Return as structured change report."""
            
            change_analysis = providers.ask_llm(comparison_prompt, max_output_tokens=500)
            
            monitoring_result = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "changes_detected": True,
                "change_analysis": change_analysis,
                "previous_timestamp": previous_data.get("timestamp"),
                "current_timestamp": current_data["timestamp"]
            }
        else:
            monitoring_result = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "changes_detected": False,
                "note": "First time monitoring this URL"
            }
        
        self.automation_data["scraped_data"].append({
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "monitoring_data": monitoring_result
        })
        
        self._save_automation_data()
        
        return monitoring_result
    
    def capture_and_analyze_screenshot(self, url: str) -> Dict[str, Any]:
        """Capture and analyze a screenshot of a webpage."""
        analysis_prompt = f"""Analyze the visual content and layout of this webpage: {url}

Provide analysis of:
1. Visual design and layout
2. Color scheme and branding
3. User interface elements
4. Call-to-action buttons
5. Navigation structure
6. Content organization
7. Mobile vs desktop optimization
8. Accessibility features

Also identify:
- Key information areas
- Interactive elements
- Forms or input fields
- Images and media
- Loading indicators

Return as comprehensive visual analysis."""
        
        try:
            response = providers.ask_llm(analysis_prompt, max_output_tokens=600)
            
            screenshot_analysis = {
                "url": url,
                "timestamp": datetime.now().isoformat(),
                "visual_analysis": response,
                "success": True
            }
            
            self.automation_data["screenshots"].append(screenshot_analysis)
            self._save_automation_data()
            
            self._log_browser("screenshot_analyzed", {"url": url})
            
            return screenshot_analysis
            
        except Exception as e:
            self._log_browser("screenshot_error", {
                "url": url,
                "error": str(e)
            })
            return {"error": str(e)}
    
    def automate_trading_research(self) -> Dict[str, Any]:
        """Automate crypto trading research across multiple sources."""
        trading_sources = [
            {"name": "TradingView", "url": "https://www.tradingview.com/markets/crypto/", "focus": "technical analysis"},
            {"name": "CoinDesk", "url": "https://www.coindesk.com/", "focus": "news and analysis"},
            {"name": "CryptoQuant", "url": "https://www.cryptoquant.com/", "focus": "on-chain data"},
            {"name": "Glassnode", "url": "https://www.glassnode.com/", "focus": "market intelligence"}
        ]
        
        trading_research = []
        
        for source in trading_sources:
            try:
                # Extract data
                data = self.extract_data_from_page(source["url"])
                
                if "error" not in data:
                    # Analyze for trading insights
                    analysis_prompt = f"""Analyze this crypto trading data from {source['name']}:

Focus: {source['focus']}
Data: {data.get('data', '')[:800]}

Extract:
1. Key market insights
2. Trading signals or patterns
3. Price predictions or forecasts
4. Important metrics
5. Risk factors
6. Trading opportunities

Return as actionable trading intelligence."""
                    
                    analysis = providers.ask_llm(analysis_prompt, max_output_tokens=500)
                    
                    research_item = {
                        "source": source["name"],
                        "url": source["url"],
                        "focus": source["focus"],
                        "analysis": analysis,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    trading_research.append(research_item)
                    
            except Exception as e:
                self._log_browser("trading_research_error", {
                    "source": source["name"],
                    "error": str(e)
                })
        
        # Create trading summary
        if trading_research:
            summary_prompt = f"""Create a comprehensive trading summary from these sources:

{json.dumps([{'source': r['source'], 'analysis': r['analysis']} for r in trading_research], indent=2)}

Provide:
1. Overall market sentiment
2. Key trading opportunities
3. Risk assessment
4. Recommended actions
5. Important price levels
6. Market trends to watch"""
            
            trading_summary = providers.ask_llm(summary_prompt, max_output_tokens=600)
            
            research_result = {
                "timestamp": datetime.now().isoformat(),
                "sources_analyzed": len(trading_research),
                "research_data": trading_research,
                "trading_summary": trading_summary
            }
            
            self.automation_data["scraped_data"].append(research_result)
            self._save_automation_data()
            
            return research_result
        
        return {"error": "No trading data collected"}
    
    def get_automation_status(self):
        """Get browser automation status."""
        return {
            "status": "active",
            "last_updated": datetime.now().isoformat(),
            "automation_count": len(self.automation_data.get("automations", [])),
            "data_points": len(self.automation_data.get("scraped_data", [])),
            "forms_filled": len(self.automation_data.get("forms_filled", [])),
            "screenshots_taken": len(self.automation_data.get("screenshots", [])),
            "browser_windows": len(self.window_interactor.list_browser_windows())
        }
        
    def interact_with_browser(self, action: str, **kwargs) -> Dict[str, Any]:
        """Interact with browser windows and elements.
        
        Args:
            action: The action to perform (list_windows, activate_window, click, type, scroll, etc.)
            **kwargs: Additional parameters for the action
            
        Returns:
            Dict with the result of the interaction
        """
        try:
            if action == "list_windows":
                windows = self.window_interactor.list_browser_windows()
                return {"success": True, "windows": [w.__dict__ for w in windows]}
                
            elif action == "activate_window":
                title = kwargs.get("title")
                if not title:
                    return {"success": False, "error": "Window title is required"}
                success = self.window_interactor.activate_window(title)
                return {"success": success}
                
            elif action == "click":
                x = kwargs.get("x")
                y = kwargs.get("y")
                button = kwargs.get("button", "left")
                clicks = kwargs.get("clicks", 1)
                
                if x is not None and y is not None:
                    success = self.window_interactor.click_element(x, y, button, clicks)
                    return {"success": success}
                else:
                    return {"success": False, "error": "x and y coordinates are required"}
                    
            elif action == "type":
                text = kwargs.get("text")
                if not text:
                    return {"success": False, "error": "Text is required"}
                success = self.window_interactor.type_text(text)
                return {"success": success}
                
            elif action == "press":
                key = kwargs.get("key")
                if not key:
                    return {"success": False, "error": "Key is required"}
                success = self.window_interactor.press_key(key)
                return {"success": success}
                
            elif action == "scroll":
                clicks = kwargs.get("clicks", 1)
                success = self.window_interactor.scroll(clicks)
                return {"success": success}
                
            elif action == "move_mouse":
                x = kwargs.get("x")
                y = kwargs.get("y")
                duration = kwargs.get("duration", 0.5)
                
                if x is not None and y is not None:
                    success = self.window_interactor.move_mouse(x, y, duration)
                    return {"success": success}
                else:
                    return {"success": False, "error": "x and y coordinates are required"}
                    
            elif action == "get_screen_size":
                width, height = self.window_interactor.get_screen_size()
                return {"success": True, "width": width, "height": height}
                
            elif action == "get_mouse_position":
                x, y = self.window_interactor.get_mouse_position()
                return {"success": True, "x": x, "y": y}
                
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            logger.error(f"Error in interact_with_browser: {e}")
            return {"success": False, "error": str(e)}
    
    def find_and_click_element(self, element_info: Dict[str, Any]) -> Dict[str, Any]:
        """Find and click an element based on its properties.
        
        Args:
            element_info: Dictionary containing element properties like text, class, id, etc.
            
        Returns:
            Dict with the result of the operation
        """
        try:
            # First try to find by image if image path is provided
            if "image_path" in element_info and element_info["image_path"]:
                success = self.window_interactor.find_and_click(element_info["image_path"])
                if success:
                    return {"success": True, "method": "image_matching"}
            
            # If no image or image matching failed, try other methods
            if "coordinates" in element_info and len(element_info["coordinates"]) == 2:
                x, y = element_info["coordinates"]
                success = self.window_interactor.click_element(x, y)
                return {"success": success, "method": "coordinates"}
                
            # TODO: Add more element location strategies (OCR, etc.)
            
            return {"success": False, "error": "No valid element location method found"}
            
        except Exception as e:
            logger.error(f"Error in find_and_click_element: {e}")
            return {"success": False, "error": str(e)}
    
    def extract_visible_text(self, region: Optional[Tuple[int, int, int, int]] = None) -> Dict[str, Any]:
        """Extract visible text from the screen or a specific region.
        
        Args:
            region: Optional (left, top, width, height) tuple defining the region to extract from
            
        Returns:
            Dict containing the extracted text and metadata
        """
        try:
            import pytesseract
            from PIL import ImageGrab
            
            # Capture the screen or region
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()
            
            # Use OCR to extract text
            text = pytesseract.image_to_string(screenshot)
            
            return {
                "success": True,
                "text": text.strip(),
                "region": region,
                "timestamp": datetime.now().isoformat()
            }
            
        except ImportError:
            return {"success": False, "error": "Required OCR libraries not installed"}
        except Exception as e:
            logger.error(f"Error in extract_visible_text: {e}")
            return {"success": False, "error": str(e)}

# Global browser automation instance
_browser_automation: Optional[BrowserAutomation] = None


def get_browser_automation() -> BrowserAutomation:
    """Get the global browser automation instance."""
    global _browser_automation
    if not _browser_automation:
        _browser_automation = BrowserAutomation()
    return _browser_automation
