"""
Context Organizer for Jarvis.
Organizes and manages information flow across all autonomous systems.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import config, providers

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = ROOT / "data" / "context_organization"
KNOWLEDGE_BASE_PATH = ROOT / "data" / "knowledge_base"
CONTEXT_LOG_PATH = ROOT / "data" / "context_organization.log"


class ContextOrganizer:
    """Organizes and manages context across all autonomous systems."""
    
    def __init__(self):
        self.context_db = CONTEXT_PATH / "context_database.json"
        self.knowledge_db = KNOWLEDGE_BASE_PATH / "knowledge_base.json"
        self._ensure_directories()
        self._load_context()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        CONTEXT_PATH.mkdir(parents=True, exist_ok=True)
        KNOWLEDGE_BASE_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_context(self):
        """Load context database."""
        if self.context_db.exists():
            with open(self.context_db, "r") as f:
                self.context_data = json.load(f)
        else:
            self.context_data = {
                "research_context": [],
                "ability_context": [],
                "trading_context": [],
                "automation_context": [],
                "knowledge_graph": {},
                "context_connections": [],
                "last_updated": None
            }
        
        if self.knowledge_db.exists():
            with open(self.knowledge_db, "r") as f:
                self.knowledge_base = json.load(f)
        else:
            self.knowledge_base = {
                "concepts": {},
                "relationships": [],
                "insights": [],
                "actionable_items": []
            }
    
    def _save_context(self):
        """Save context data."""
        with open(self.context_db, "w") as f:
            json.dump(self.context_data, f, indent=2)
        with open(self.knowledge_db, "w") as f:
            json.dump(self.knowledge_base, f, indent=2)
    
    def _log_context(self, action: str, details: Dict[str, Any]):
        """Log context organization activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(CONTEXT_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def organize_research_context(self, research_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize research findings into structured context."""
        context_item = {
            "id": f"research_{int(time.time())}",
            "type": "research",
            "timestamp": datetime.now().isoformat(),
            "data": research_data,
            "extracted_insights": [],
            "connections": [],
            "actionable_items": []
        }
        
        # Extract insights from research
        if research_data.get("models_found", 0) > 0:
            insights_prompt = f"""Extract key insights from this AI model research:

{json.dumps(research_data, indent=2)[:1000]}

Provide:
1. Key trends in free AI models
2. Important capabilities discovered
3. Integration opportunities
4. Competitive advantages
5. Actionable recommendations

Return as structured insights."""
            
            try:
                insights = providers.generate_text(insights_prompt, max_output_tokens=400)
                context_item["extracted_insights"] = insights.split('\n')
            except Exception as e:
                pass
        
        # Add to context database
        self.context_data["research_context"].append(context_item)
        self.context_data["last_updated"] = datetime.now().isoformat()
        
        # Update knowledge base
        self._update_knowledge_base(context_item)
        
        self._save_context()
        self._log_context("research_organized", {"id": context_item["id"]})
        
        return context_item
    
    def organize_ability_context(self, ability_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize ability acquisition context."""
        context_item = {
            "id": f"ability_{int(time.time())}",
            "type": "ability",
            "timestamp": datetime.now().isoformat(),
            "data": ability_data,
            "capabilities_added": [],
            "integration_status": "pending",
            "dependencies": []
        }
        
        # Extract capabilities
        if ability_data.get("acquired", 0) > 0:
            # Analyze what capabilities were added
            capabilities_prompt = f"""Analyze these newly acquired abilities and extract key capabilities:

{json.dumps(ability_data, indent=2)[:800]}

List the main capabilities Jarvis now has access to."""
            
            try:
                capabilities = providers.generate_text(capabilities_prompt, max_output_tokens=300)
                context_item["capabilities_added"] = capabilities.split('\n')
            except Exception as e:
                pass
        
        self.context_data["ability_context"].append(context_item)
        self.context_data["last_updated"] = datetime.now().isoformat()
        
        self._update_knowledge_base(context_item)
        self._save_context()
        self._log_context("ability_organized", {"id": context_item["id"]})
        
        return context_item
    
    def organize_trading_context(self, trading_data: Dict[str, Any]) -> Dict[str, Any]:
        """Organize trading research context."""
        context_item = {
            "id": f"trading_{int(time.time())}",
            "type": "trading",
            "timestamp": datetime.now().isoformat(),
            "data": trading_data,
            "market_insights": [],
            "strategies_evaluated": [],
            "risk_factors": []
        }
        
        # Extract market insights
        if trading_data.get("strategies_researched", 0) > 0:
            insights_prompt = f"""Extract market insights from this trading research:

{json.dumps(trading_data, indent=2)[:800]}

Provide:
1. Market conditions analysis
2. Strategy effectiveness insights
3. Risk factors identified
4. Trading opportunities
5. Market sentiment summary"""
            
            try:
                insights = providers.generate_text(insights_prompt, max_output_tokens=400)
                context_item["market_insights"] = insights.split('\n')
            except Exception as e:
                pass
        
        self.context_data["trading_context"].append(context_item)
        self.context_data["last_updated"] = datetime.now().isoformat()
        
        self._update_knowledge_base(context_item)
        self._save_context()
        self._log_context("trading_organized", {"id": context_item["id"]})
        
        return context_item
    
    def _update_knowledge_base(self, context_item: Dict[str, Any]):
        """Update the knowledge base with new context."""
        # Extract concepts
        concepts = self._extract_concepts(context_item)
        for concept in concepts:
            if concept not in self.knowledge_base["concepts"]:
                self.knowledge_base["concepts"][concept] = {
                    "first_seen": context_item["timestamp"],
                    "context_items": [],
                    "connections": []
                }
            self.knowledge_base["concepts"][concept]["context_items"].append(context_item["id"])
        
        # Add relationships
        relationships = self._extract_relationships(context_item)
        for rel in relationships:
            if rel not in self.knowledge_base["relationships"]:
                self.knowledge_base["relationships"].append(rel)
        
        # Add actionable items
        if context_item.get("actionable_items"):
            self.knowledge_base["actionable_items"].extend(context_item["actionable_items"])
        
        # Add insights
        self.knowledge_base["insights"].extend(context_item.get("extracted_insights", []))
    
    def _extract_concepts(self, context_item: Dict[str, Any]) -> List[str]:
        """Extract key concepts from context item."""
        concepts = []
        data_str = str(context_item.get("data", ""))
        
        # Common AI/crypto concepts to look for
        concept_patterns = [
            "llama", "qwen", "mistral", "phi", "gemma", "deepseek",
            "crypto", "bitcoin", "ethereum", "trading", "defi",
            "automation", "autonomy", "research", "integration",
            "model", "api", "open source", "free", "local"
        ]
        
        for pattern in concept_patterns:
            if pattern.lower() in data_str.lower():
                concepts.append(pattern)
        
        return list(set(concepts))
    
    def _extract_relationships(self, context_item: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract relationships from context item."""
        relationships = []
        
        # Simple relationship extraction
        if context_item["type"] == "research" and "trading" in str(context_item.get("data", "")).lower():
            relationships.append({
                "from": "research",
                "to": "trading",
                "type": "informs",
                "context": context_item["id"]
            })
        
        if context_item["type"] == "ability" and "automation" in str(context_item.get("data", "")).lower():
            relationships.append({
                "from": "ability",
                "to": "automation",
                "type": "enables",
                "context": context_item["id"]
            })
        
        return relationships
    
    def get_context_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of all context."""
        return {
            "total_context_items": sum([
                len(self.context_data["research_context"]),
                len(self.context_data["ability_context"]),
                len(self.context_data["trading_context"]),
                len(self.context_data["automation_context"])
            ]),
            "research_context_count": len(self.context_data["research_context"]),
            "ability_context_count": len(self.context_data["ability_context"]),
            "trading_context_count": len(self.context_data["trading_context"]),
            "automation_context_count": len(self.context_data["automation_context"]),
            "knowledge_concepts": len(self.knowledge_base["concepts"]),
            "knowledge_relationships": len(self.knowledge_base["relationships"]),
            "actionable_items": len(self.knowledge_base["actionable_items"]),
            "last_updated": self.context_data.get("last_updated")
        }
    
    def generate_context_report(self) -> str:
        """Generate a comprehensive context report."""
        summary = self.get_context_summary()
        
        report = f"""# Jarvis Context Organization Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Last Updated:** {summary.get('last_updated', 'Never')}

## Context Overview

- **Total Context Items:** {summary['total_context_items']}
- **Research Context:** {summary['research_context_count']} items
- **Ability Context:** {summary['ability_context_count']} items  
- **Trading Context:** {summary['trading_context_count']} items
- **Automation Context:** {summary['automation_context_count']} items

## Knowledge Base

- **Concepts Tracked:** {summary['knowledge_concepts']}
- **Relationships:** {summary['knowledge_relationships']}
- **Actionable Items:** {summary['actionable_items']}

## Recent Activity

"""
        
        # Add recent context items
        recent_contexts = []
        recent_contexts.extend(self.context_data["research_context"][-3:])
        recent_contexts.extend(self.context_data["ability_context"][-3:])
        recent_contexts.extend(self.context_data["trading_context"][-3:])
        
        recent_contexts.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        for ctx in recent_contexts[:5]:
            report += f"""### {ctx['type'].title()} Context - {ctx['timestamp']}

**ID:** {ctx['id']}
"""
            if ctx.get("extracted_insights"):
                report += f"**Insights:** {len(ctx['extracted_insights'])} items\n"
            if ctx.get("capabilities_added"):
                report += f"**Capabilities:** {len(ctx['capabilities_added'])} added\n"
            if ctx.get("market_insights"):
                report += f"**Market Insights:** {len(ctx['market_insights'])} items\n"
            
            report += "\n---\n"
        
        # Add top concepts
        if self.knowledge_base["concepts"]:
            report += "\n## Top Concepts\n\n"
            for concept, data in list(self.knowledge_base["concepts"].items())[:10]:
                report += f"- **{concept}**: {len(data['context_items'])} references\n"
        
        report += "\n---\n*This report was generated by Jarvis Context Organizer*"
        
        return report


# Global context organizer instance
_context_organizer: Optional[ContextOrganizer] = None


def get_context_organizer() -> ContextOrganizer:
    """Get the global context organizer instance."""
    global _context_organizer
    if not _context_organizer:
        _context_organizer = ContextOrganizer()
    return _context_organizer
