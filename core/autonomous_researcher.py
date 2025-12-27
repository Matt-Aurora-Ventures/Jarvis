"""
Autonomous Researcher for Jarvis.
Continuously researches newest free models and documents findings.
"""

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers, research_engine, storage_utils

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_PATH = ROOT / "data" / "autonomous_research"
MARKDOWN_PATH = ROOT / "data" / "research_docs"
RESEARCH_LOG_PATH = ROOT / "data" / "autonomous_research.log"


class AutonomousResearcher:
    """Manages continuous autonomous research and documentation."""
    
    def __init__(self):
        self.storage = storage_utils.get_storage(RESEARCH_PATH)
        self.md_storage = storage_utils.get_md_storage(MARKDOWN_PATH)
        self.research_db = RESEARCH_PATH / "research_data.json"
        
        # Research targets for newest lightweight models
        self.research_targets = [
            "llama 3.2 1b 3b gguf",
            "qwen 2.5 1.5b instruct",
            "phi 3.5 mini instruct",
            "gemma 2 2b",
            "mistral 7b quantized",
            "deepseek coder 1.3b",
            "tinyllama 1.1b",
            "minicpm latest small model",
            "local llm benchmarks 2024",
            "lightweight speech to text open source",
            "lightweight tts piper voices",
            "self hosted natural tts alternatives",
            "youtube transcript mcp server",
            "solana dex api documentation",
            "base chain dex api",
            "hyperliquid api data pull",
            "prompt engineering for creative agencies",
            "automation prompts for web design",
            "macos network security monitoring",
            "packet monitoring tools for mac",
            "resource optimization for always-on agents",
        ]
        self._load_research()

    def _load_research(self) -> None:
        """Load research state from disk."""
        if self.research_db.exists():
            try:
                with open(self.research_db, "r", encoding="utf-8") as handle:
                    self.research_data = json.load(handle)
                return
            except Exception:
                pass
        self.research_data = {
            "models_discovered": [],
            "research_sessions": [],
            "latest_findings": {},
            "markdown_docs": [],
            "research_summary": ""
        }

    def _save_research(self) -> None:
        """Persist research state to disk."""
        self.research_db.parent.mkdir(parents=True, exist_ok=True)
        with open(self.research_db, "w", encoding="utf-8") as handle:
            json.dump(self.research_data, handle, indent=2)
        
    def _log_research(self, action: str, details: Dict[str, Any]):
        """Log research activity."""
        self.storage.log_event("research_log", action, details)
    
    def research_newest_models(self) -> Dict[str, Any]:
        """Research the newest free models available."""
        session_id = f"research_{int(time.time())}"
        research_session = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "models_found": [],
            "sources_checked": [],
            "markdown_generated": []
        }
        
        self._log_research("research_session_started", {"session_id": session_id})
        
        # Research each target
        for target in self.research_targets:
            try:
                # Web search for the target
                engine = research_engine.get_research_engine()
                results = engine.search_web(target, max_results=3)
                
                for result in results:
                    model_info = self._extract_model_info(result, target)
                    if model_info:
                        research_session["models_found"].append(model_info)
                        self.research_data["models_discovered"].append(model_info)
                
                research_session["sources_checked"].append({
                    "target": target,
                    "results": len(results),
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                self._log_research("research_target_error", {
                    "target": target,
                    "error": str(e)
                })
        
        # Generate markdown documentation
        markdown_file = self._generate_research_markdown(research_session)
        research_session["markdown_generated"].append(markdown_file)
        
        # Update research data
        self.research_data["research_sessions"].append(research_session)
        self.research_data["latest_findings"] = {
            "last_research": datetime.now().isoformat(),
            "total_models": len(self.research_data["models_discovered"]),
            "latest_session": session_id
        }
        
        self._save_research()
        
        result = {
            "session_id": session_id,
            "models_found": len(research_session["models_found"]),
            "sources_checked": len(research_session["sources_checked"]),
            "markdown_file": markdown_file,
            "total_models_in_db": len(self.research_data["models_discovered"])
        }
        
        self._log_research("research_session_completed", result)
        return result
    
    def _extract_model_info(self, search_result: Dict[str, Any], target: str) -> Optional[Dict[str, Any]]:
        """Extract model information from search result."""
        try:
            # Use browser automation when available, otherwise fall back to search snippets.
            browser = None
            try:
                from core import browser_automation
                browser = browser_automation.get_browser_automation()
            except Exception as exc:
                self._log_research("browser_automation_unavailable", {
                    "url": search_result.get("url", ""),
                    "error": str(exc)
                })

            if browser:
                page_data = browser.extract_data_from_page(search_result["url"])
            else:
                page_data = {"data": search_result.get("snippet", ""), "error": "browser_unavailable"}
            
            if "error" not in page_data:
                # Analyze the extracted data
                analysis_prompt = f"""Analyze this webpage for free AI model information:

URL: {search_result['url']}
Title: {search_result['title']}
Extracted Data: {page_data.get('data', '')}

Extract:
1. Model name and version
2. Model size (parameters)
3. Whether it's free/open source
4. Hardware requirements
5. Performance benchmarks
6. How to access/download
7. Key features and capabilities
8. Release date/recency

Focus on newest free models that Jarvis could use."""
                
                analysis = providers.generate_text(analysis_prompt, max_output_tokens=400)
                
                return {
                    "model_name": search_result["title"],
                    "url": search_result["url"],
                    "snippet": search_result["snippet"],
                    "research_target": target,
                    "extracted_data": page_data.get("data", ""),
                    "analysis": analysis,
                    "discovered_at": datetime.now().isoformat()
                }
            # Lightweight fallback when browser automation is unavailable.
            return {
                "model_name": search_result.get("title", "Unknown Model"),
                "url": search_result.get("url", ""),
                "snippet": search_result.get("snippet", ""),
                "research_target": target,
                "extracted_data": "",
                "analysis": search_result.get("snippet", ""),
                "discovered_at": datetime.now().isoformat()
            }
                
        except Exception as e:
            self._log_research("model_extraction_error", {
                "url": search_result.get("url", ""),
                "error": str(e)
            })
        
        return None
    
    def _generate_research_markdown(self, research_session: Dict[str, Any]) -> str:
        """Generate markdown documentation for research findings."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filename = f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = MARKDOWN_PATH / filename
        
        # Generate content
        content = f"""# Autonomous Research Report

**Generated:** {timestamp}  
**Session ID:** {research_session["session_id"]}  
**Models Found:** {len(research_session["models_found"])}  

## Executive Summary

This autonomous research session discovered {len(research_session["models_found"])} potential free AI models across {len(research_session["sources_checked"])} research targets. The research focused on the newest free models available for autonomous integration.

## Key Findings

"""
        
        # Add model details
        for i, model in enumerate(research_session["models_found"][:10], 1):  # Limit to top 10
            content += f"""### {i}. {model['model_name']}

**Research Target:** {model['research_target']}  
**URL:** {model['url']}  
**Discovered:** {model['discovered_at']}

**Summary:** {model['snippet']}

**Analysis:** {model['analysis'][:500]}...

---

"""
        
        # Add research targets summary
        content += """## Research Targets Covered

"""
        for source in research_session["sources_checked"]:
            content += f"- **{source['target']}**: {source['results']} results\n"
        
        # Add recommendations
        content += f"""
## Recommendations for Jarvis

Based on this research, Jarvis should consider:

1. **Top Priority Models**: Models with highest autonomy potential
2. **Integration Feasibility**: Models that can run locally
3. **Capability Gaps**: Models that fill current Jarvis limitations
4. **Recent Releases**: Newest models with latest capabilities

## Next Steps

1. Evaluate top models for integration
2. Test model accessibility and performance
3. Plan integration roadmap
4. Monitor for new releases

---
*This report was generated autonomously by Jarvis Research System*
"""
        
        # Save markdown
        with open(filepath, "w") as f:
            f.write(content)
        
        # Track in database
        self.research_data["markdown_docs"].append({
            "filename": filename,
            "filepath": str(filepath),
            "session_id": research_session["session_id"],
            "generated_at": datetime.now().isoformat()
        })
        
        return str(filepath)
    
    def get_research_summary(self) -> Dict[str, Any]:
        """Get current research status and summary."""
        if not self.research_data["models_discovered"]:
            return {
                "status": "no_research_yet",
                "models_count": 0,
                "sessions_count": 0,
                "markdown_docs": 0
            }
        
        # Generate summary of latest findings
        latest_models = self.research_data["models_discovered"][-5:]
        
        summary_prompt = f"""Summarize these latest AI model discoveries for Jarvis:

{json.dumps([{'name': m['model_name'], 'target': m['research_target'], 'analysis': m['analysis'][:200]} for m in latest_models], indent=2)}

Provide:
1. Key trends in free models
2. Most promising models for Jarvis
3. Integration priorities
4. Capability gaps filled
5. Next research recommendations"""
        
        try:
            summary = providers.generate_text(summary_prompt, max_output_tokens=500)
            self.research_data["research_summary"] = summary
        except Exception as e:
            summary = "Unable to generate summary"
        
        return {
            "status": "active",
            "models_count": len(self.research_data["models_discovered"]),
            "sessions_count": len(self.research_data["research_sessions"]),
            "markdown_docs": len(self.research_data["markdown_docs"]),
            "latest_research": self.research_data["latest_findings"].get("last_research"),
            "summary": summary,
            "latest_models": latest_models
        }
    
    def continuous_research_cycle(self) -> Dict[str, Any]:
        """Run a continuous research cycle."""
        self._log_research("continuous_cycle_started", {})
        
        # Run main research
        research_result = self.research_newest_models()
        
        # Update research targets based on findings
        self._update_research_targets()
        
        # Generate insights
        summary = self.get_research_summary()
        
        result = {
            "research_completed": research_result,
            "summary": summary,
            "next_cycle_scheduled": time.time() + 3600  # 1 hour from now
        }
        
        self._log_research("continuous_cycle_completed", result)
        return result
    
    def _update_research_targets(self):
        """Update research targets based on latest findings."""
        if len(self.research_data["models_discovered"]) > 0:
            # Analyze trends to update targets
            recent_models = self.research_data["models_discovered"][-10:]
            
            trends_prompt = f"""Based on these recent model discoveries, suggest 5 new research targets for Jarvis:

{json.dumps([{'name': m['model_name'], 'target': m['research_target']} for m in recent_models], indent=2)}

Focus on:
1. Emerging model families
2. Performance improvements
3. New capabilities
4. Better accessibility
5. Latest releases

Return as a simple list of 5 search queries."""
            
            try:
                new_targets = providers.generate_text(trends_prompt, max_output_tokens=200)
                
                # Extract targets from response
                lines = new_targets.split('\n')
                for line in lines:
                    if line.strip() and len(line.strip()) > 10:
                        target = line.strip().strip('-').strip().strip('"').strip()
                        if target not in self.research_targets:
                            self.research_targets.append(target)
                            # Keep only recent 15 targets
                            self.research_targets = self.research_targets[-15:]
                            break
                            
            except Exception as e:
                pass


# Global researcher instance
_researcher: Optional[AutonomousResearcher] = None


def get_autonomous_researcher() -> AutonomousResearcher:
    """Get the global autonomous researcher instance."""
    global _researcher
    if not _researcher:
        _researcher = AutonomousResearcher()
    return _researcher
