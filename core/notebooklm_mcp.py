"""
NotebookLM MCP Integration for Jarvis
Uses browser automation to interact with NotebookLM for research cycles.

Based on community approach since consumer NotebookLM has no official API.
Uses Playwright for reliable browser automation.
"""

from pathlib import Path
import json
import time
from typing import List, Dict, Optional
import asyncio

try:
    from playwright.async_api import async_playwright, Page
except ImportError:
    print("⚠️  Playwright not installed. Run: pip install playwright && playwright install")
    async_playwright = None

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_DATA = ROOT / "data" / "notebooklm"
NOTEBOOK_DATA.mkdir(parents=True, exist_ok=True)


class NotebookLMClient:
    """MCP-style client for NotebookLM integration."""
    
    def __init__(self):
        self.browser = None
        self.context = None
        self.page: Optional[Page] = None
        self.notebook_url = "https://notebooklm.google.com"
        
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
    
    async def connect(self):
        """Initialize browser and navigate to NotebookLM."""
        if not async_playwright:
            raise RuntimeError("Playwright not installed")
        
        self.playwright = await async_playwright().start()
        
        # Use persistent context to maintain login
        user_data_dir = ROOT / ".agent" / "browser_data" / "notebooklm"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,  # Visible for first-time login
            args=['--disable-blink-features=AutomationControlled']
        )
        
        self.page = await self.context.new_page()
        await self.page.goto(self.notebook_url)
        
        print("✓ Connected to NotebookLM")
        print("💡 If not logged in, please sign in manually in the browser window")
        
        # Wait for user to login if needed
        await self.page.wait_for_timeout(5000)
    
    async def disconnect(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def create_notebook(self, name: str, sources: List[str] = None) -> Dict:
        """
        Create a new NotebookLM notebook.
        
        Args:
            name: Notebook name
            sources: List of URLs or text content to add as sources
        
        Returns:
            Dict with notebook info
        """
        print(f"📝 Creating notebook: {name}")
        
        # Click "New notebook" button
        try:
            await self.page.click('button:has-text("New notebook")', timeout=5000)
        except Exception:
            print("⚠️  'New notebook' button not found - may need manual navigation")
            return {"error": "Could not create notebook"}
        
        await self.page.wait_for_timeout(2000)
        
        # Add sources if provided
        if sources:
            for source in sources:
                await self.add_source(source)
        
        notebook_info = {
            "name": name,
            "created_at": time.time(),
            "sources_count": len(sources) if sources else 0,
        }
        
        # Save to local tracking
        self._save_notebook(notebook_info)
        
        print(f"✅ Notebook created: {name}")
        return notebook_info
    
    async def add_source(self, content: str, source_type: str = "url"):
        """
        Add a source to the current notebook.
        
        Args:
            content: URL or text content
            source_type: "url" or "text"
        """
        print(f"📄 Adding source: {content[:50]}...")
        
        try:
            # Click "Add source" or similar button
            await self.page.click('button:has-text("Add source")', timeout=5000)
            await self.page.wait_for_timeout(1000)
            
            if source_type == "url":
                # Find URL input and paste
                await self.page.fill('input[type="url"]', content)
                await self.page.click('button:has-text("Add")')
            elif source_type == "text":
                # Find text area and paste
                await self.page.fill('textarea', content)
                await self.page.click('button:has-text("Save")')
            
            await self.page.wait_for_timeout(2000)
            print("✅ Source added")
            
        except Exception as e:
            print(f"⚠️  Error adding source: {e}")
    
    async def ask_question(self, question: str) -> str:
        """
        Ask a question to NotebookLM and get response.
        
        Args:
            question: Research question
        
        Returns:
            Generated response
        """
        print(f"❓ Asking: {question}")
        
        try:
            # Find chat input
            chat_input = await self.page.wait_for_selector('textarea[placeholder*="Ask"]', timeout=5000)
            await chat_input.fill(question)
            await chat_input.press('Enter')
            
            # Wait for response
            await self.page.wait_for_timeout(5000)
            
            # Extract response (selector may need adjustment based on actual DOM)
            responses = await self.page.query_selector_all('.response-message')
            if responses:
                last_response = await responses[-1].text_content()
                print(f"✅ Got response ({len(last_response)} chars)")
                return last_response.strip()
            
            return "No response received"
            
        except Exception as e:
            print(f"⚠️  Error asking question: {e}")
            return f"Error: {str(e)}"
    
    async def generate_study_guide(self) -> str:
        """Generate a study guide from notebook sources."""
        print("📚 Generating study guide...")
        
        try:
            await self.page.click('button:has-text("Study guide")', timeout=5000)
            await self.page.wait_for_timeout(5000)
            
            # Extract generated content
            content = await self.page.text_content('.study-guide-content')
            
            print(f"✅ Study guide generated ({len(content)} chars)")
            return content
            
        except Exception as e:
            print(f"⚠️  Error generating study guide: {e}")
            return f"Error: {str(e)}"
    
    def _save_notebook(self, info: Dict):
        """Save notebook info locally."""
        notebooks_file = NOTEBOOK_DATA / "notebooks.json"
        
        notebooks = []
        if notebooks_file.exists():
            with open(notebooks_file) as f:
                notebooks = json.load(f)
        
        notebooks.append(info)
        
        with open(notebooks_file, 'w') as f:
            json.dump(notebooks, f, indent=2)


# MCP Server Functions (compatible with Anthropic's MCP spec)

async def mcp_create_research_notebook(topic: str, sources: List[str]) -> Dict:
    """
    MCP Tool: Create a research notebook with sources.
    
    Args:
        topic: Research topic name
        sources: List of URLs or documents
    
    Returns:
        Notebook info
    """
    async with NotebookLMClient() as client:
        return await client.create_notebook(topic, sources)


async def mcp_research_question(question: str) -> str:
    """
    MCP Tool: Ask a research question to NotebookLM.
    
    Args:
        question: Research question
    
    Returns:
        Generated answer
    """
    async with NotebookLMClient() as client:
        return await client.ask_question(question)


async def mcp_generate_summary(topic: str) -> str:
    """
    MCP Tool: Generate a study guide/summary.
    
    Args:
        topic: Topic to summarize
    
    Returns:
        Generated summary
    """
    async with NotebookLMClient() as client:
        return await client.generate_study_guide()


# Example usage
async def example_research_cycle():
    """Example: Autonomous research cycle."""
    print("\n" + "="*60)
    print("🧠 JARVIS RESEARCH CYCLE - NotebookLM Integration")
    print("="*60 + "\n")
    
    async with NotebookLMClient() as client:
        # 1. Create research notebook
        notebook = await client.create_notebook(
            "Solana Trading Strategies",
            sources=[
                "https://docs.solana.com/",
                "https://www.investopedia.com/terms/t/trading-strategy.asp",
            ]
        )
        
        # 2. Ask research questions
        questions = [
            "What are the key advantages of Solana for DeFi trading?",
            "What are common high-frequency trading strategies?",
            "How do market makers operate on DEXs?",
        ]
        
        answers = {}
        for q in questions:
            answer = await client.ask_question(q)
            answers[q] = answer
            await asyncio.sleep(2)  # Rate limiting
        
        # 3. Generate summary
        summary = await client.generate_study_guide()
        
        # 4. Save research results
        research_file = NOTEBOOK_DATA / f"research_{int(time.time())}.json"
        with open(research_file, 'w') as f:
            json.dump({
                "notebook": notebook,
                "questions": questions,
                "answers": answers,
                "summary": summary,
                "timestamp": time.time(),
            }, f, indent=2)
        
        print(f"\n✅ Research complete! Saved to: {research_file}")
        return research_file


if __name__ == "__main__":
    asyncio.run(example_research_cycle())
