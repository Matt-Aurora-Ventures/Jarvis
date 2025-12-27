"""
Ability Acquisition System for Jarvis.
Continuously researches and integrates open-source capabilities.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, providers, research_engine, evolution, guardian

ROOT = Path(__file__).resolve().parents[1]
ABILITIES_PATH = ROOT / "data" / "abilities"
MODELS_PATH = ROOT / "data" / "models"
ACQUISITION_LOG_PATH = ROOT / "data" / "ability_acquisitions.log"


# Open-source model sources
OPEN_SOURCE_SOURCES = {
    "huggingface": {
        "base_url": "https://huggingface.co",
        "search_url": "https://huggingface.co/models",
        "api_url": "https://huggingface.co/api/models",
        "focus": ["text-generation", "conversational", "instruction-following"]
    },
    "github": {
        "base_url": "https://github.com",
        "search_url": "https://github.com/search",
        "focus": ["llm", "language-model", "autonomous-agent", "ai-assistant"]
    },
    "ollama": {
        "base_url": "https://ollama.com",
        "search_url": "https://ollama.com/library",
        "focus": ["chat", "code", "instruct"]
    }
}


class AbilityAcquisition:
    """Manages acquisition of new open-source abilities."""
    
    def __init__(self):
        self.abilities_db = ABILITIES_PATH / "abilities.json"
        self.models_db = MODELS_PATH / "models.json"
        self._ensure_directories()
        self._load_abilities()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        ABILITIES_PATH.mkdir(parents=True, exist_ok=True)
        MODELS_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_abilities(self):
        """Load existing abilities database."""
        if self.abilities_db.exists():
            with open(self.abilities_db, "r") as f:
                self.abilities = json.load(f)
        else:
            self.abilities = {
                "acquired": [],
                "pending": [],
                "failed": [],
                "categories": {
                    "reasoning": [],
                    "coding": [],
                    "conversation": [],
                    "analysis": [],
                    "automation": []
                }
            }
        
        if self.models_db.exists():
            with open(self.models_db, "r") as f:
                self.models = json.load(f)
        else:
            self.models = {
                "available": [],
                "installed": [],
                "tested": []
            }
    
    def _save_abilities(self):
        """Save abilities database."""
        with open(self.abilities_db, "w") as f:
            json.dump(self.abilities, f, indent=2)
        with open(self.models_db, "w") as f:
            json.dump(self.models, f, indent=2)
    
    def _log_acquisition(self, action: str, details: Dict[str, Any]):
        """Log acquisition activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details
        }
        
        with open(ACQUISITION_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def discover_open_source_models(self) -> List[Dict[str, Any]]:
        """Discover new open-source models."""
        discoveries = []
        
        # Research goal-relevant free models and tools
        queries = [
            "free crypto trading AI models",
            "open source autonomous agents",
            "free automation tools for AI",
            "self-improving AI systems open source",
            "free market analysis models",
            "autonomous trading bots open source",
            "free AI research automation",
            "open source self-learning AI",
            "free crypto analysis tools",
            "autonomous decision making AI",
            "lightweight local LLM 1-3B open source",
            "quantized GGUF models for local inference"
        ]
        
        engine = research_engine.get_research_engine()
        
        for query in queries:
            results = engine.search_web(query, max_results=5)
            
            for result in results:
                if any(keyword in result["title"].lower() for keyword in ["model", "llm", "open source", "free"]):
                    discoveries.append({
                        "source": "web_search",
                        "title": result["title"],
                        "url": result["url"],
                        "snippet": result["snippet"],
                        "query": query
                    })
        
        # Check for Ollama models
        try:
            import requests
            response = requests.get("https://ollama.com/api/tags", timeout=10)
            if response.status_code == 200:
                ollama_models = response.json().get("models", [])
                for model in ollama_models[:10]:
                    discoveries.append({
                        "source": "ollama",
                        "title": model["name"],
                        "size": model.get("size", ""),
                        "modified": model.get("modified", ""),
                        "digest": model.get("digest", "")[:16] + "..."
                    })
        except Exception as e:
            self._log_acquisition("ollama_discovery_error", {"error": str(e)})
        
        self._log_acquisition("models_discovered", {"count": len(discoveries)})
        return discoveries
    
    def evaluate_ability(self, discovery: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate if a discovered model/ability is worth acquiring."""
        evaluation_prompt = f"""Evaluate this open-source AI model/ability for Jarvis integration:

Title: {discovery.get('title', 'Unknown')}
Source: {discovery.get('source', 'Unknown')}
Details: {discovery.get('snippet', discovery.get('size', 'No details'))}
URL: {discovery.get('url', 'No URL')}

Jarvis Goals: Crypto trading, autonomy, self-improvement, automation, information gathering

Consider:
1. Is it 100% free and open source? (no API keys, no paid tiers)
2. Does it enhance crypto trading capabilities?
3. Does it increase autonomy or self-improvement?
4. Does it provide automation or information gathering?
5. Can it run locally without expensive hardware?
6. Is it actively maintained and documented?
7. Does it solve a current Jarvis limitation?

Rate from 1-10 (10=perfect fit) and provide brief reasoning focusing on crypto trading and autonomy goals."""
        
        try:
            response = providers.generate_text(evaluation_prompt, max_output_tokens=300)
            if response:
                # Extract rating
                rating = 5
                for word in response.split():
                    if word.isdigit() and 1 <= int(word) <= 10:
                        rating = int(word)
                        break
                
                return {
                    "rating": rating,
                    "reasoning": response,
                    "recommended": rating >= 7
                }
        except Exception as e:
            self._log_acquisition("evaluation_error", {"error": str(e)})
            pass
        
        return {"rating": 5, "reasoning": "Unable to evaluate", "recommended": False}
    
    def acquire_ability(self, discovery: Dict[str, Any]) -> bool:
        """Attempt to acquire and integrate a new ability."""
        ability_id = f"{discovery.get('source', 'unknown')}_{hash(discovery.get('title', ''))}"
        
        # Check if already acquired
        if ability_id in [a["id"] for a in self.abilities["acquired"]]:
            return False
        
        try:
            if discovery.get("source") == "ollama":
                return self._acquire_ollama_model(discovery, ability_id)
            elif "github.com" in discovery.get("url", ""):
                return self._acquire_github_project(discovery, ability_id)
            elif "huggingface.co" in discovery.get("url", ""):
                return self._acquire_huggingface_model(discovery, ability_id)
            else:
                # Generic ability from research
                return self._acquire_researched_ability(discovery, ability_id)
                
        except Exception as e:
            self._log_acquisition("acquisition_failed", {
                "ability_id": ability_id,
                "error": str(e)
            })
            return False
    
    def _acquire_ollama_model(self, discovery: Dict[str, Any], ability_id: str) -> bool:
        """Acquire an Ollama model."""
        model_name = discovery.get("title", "")
        if not model_name:
            return False
        
        # Check if Ollama is available
        try:
            result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return False
        except Exception as e:
            return False
        
        # Pull the model
        try:
            self._log_acquisition("ollama_pull_start", {"model": model_name})
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes timeout
            )
            
            if result.returncode == 0:
                # Add to abilities
                ability = {
                    "id": ability_id,
                    "type": "ollama_model",
                    "name": model_name,
                    "source": "ollama",
                    "acquired_at": datetime.now().isoformat(),
                    "capabilities": ["text_generation", "conversation"],
                    "size": discovery.get("size", "")
                }
                
                self.abilities["acquired"].append(ability)
                self.models["installed"].append(model_name)
                self._save_abilities()
                
                self._log_acquisition("ollama_acquired", {"model": model_name})
                return True
            else:
                self._log_acquisition("ollama_pull_failed", {
                    "model": model_name,
                    "error": result.stderr
                })
                return False
                
        except Exception as e:
            self._log_acquisition("ollama_pull_error", {
                "model": model_name,
                "error": str(e)
            })
            return False
    
    def _acquire_github_project(self, discovery: Dict[str, Any], ability_id: str) -> bool:
        """Acquire a GitHub project as an ability."""
        # For now, just log it as a potential ability
        ability = {
            "id": ability_id,
            "type": "github_project",
            "name": discovery.get("title", ""),
            "source": "github",
            "url": discovery.get("url", ""),
            "acquired_at": datetime.now().isoformat(),
            "capabilities": ["research_reference"],
            "status": "referenced"
        }
        
        self.abilities["acquired"].append(ability)
        self._save_abilities()
        
        self._log_acquisition("github_referenced", {
            "title": discovery.get("title"),
            "url": discovery.get("url")
        })
        return True
    
    def _acquire_huggingface_model(self, discovery: Dict[str, Any], ability_id: str) -> bool:
        """Acquire a Hugging Face model reference."""
        ability = {
            "id": ability_id,
            "type": "huggingface_model",
            "name": discovery.get("title", ""),
            "source": "huggingface",
            "url": discovery.get("url", ""),
            "acquired_at": datetime.now().isoformat(),
            "capabilities": ["text_generation", "research"],
            "status": "referenced"
        }
        
        self.abilities["acquired"].append(ability)
        self._save_abilities()
        
        self._log_acquisition("huggingface_referenced", {
            "title": discovery.get("title"),
            "url": discovery.get("url")
        })
        return True
    
    def _acquire_researched_ability(self, discovery: Dict[str, Any], ability_id: str) -> bool:
        """Acquire an ability from research findings."""
        # Extract capabilities from research
        content = discovery.get("snippet", "")
        capabilities = []
        
        if any(word in content.lower() for word in ["reason", "logic", "thinking"]):
            capabilities.append("reasoning")
        if any(word in content.lower() for word in ["code", "program", "script"]):
            capabilities.append("coding")
        if any(word in content.lower() for word in ["chat", "talk", "conversation"]):
            capabilities.append("conversation")
        if any(word in content.lower() for word in ["analyze", "analysis", "understand"]):
            capabilities.append("analysis")
        if any(word in content.lower() for word in ["auto", "agent", "autonomous"]):
            capabilities.append("automation")
        
        ability = {
            "id": ability_id,
            "type": "researched_ability",
            "name": discovery.get("title", ""),
            "source": "research",
            "acquired_at": datetime.now().isoformat(),
            "capabilities": capabilities or ["general"],
            "details": discovery.get("snippet", "")
        }
        
        self.abilities["acquired"].append(ability)
        self._save_abilities()
        
        self._log_acquisition("researched_ability", {
            "title": discovery.get("title"),
            "capabilities": capabilities
        })
        return True
    
    def integrate_ability(self, ability: Dict[str, Any]) -> bool:
        """Integrate an acquired ability into Jarvis."""
        try:
            if ability["type"] == "ollama_model":
                # Add Ollama model to providers
                return self._integrate_ollama_model(ability)
            elif ability["type"] == "researched_ability":
                # Create new prompt or capability
                return self._integrate_researched_ability(ability)
            else:
                # Log as reference material
                return self._integrate_reference(ability)
                
        except Exception as e:
            self._log_acquisition("integration_failed", {
                "ability_id": ability.get("id"),
                "error": str(e)
            })
            return False
    
    def _integrate_ollama_model(self, ability: Dict[str, Any]) -> bool:
        """Integrate Ollama model into providers."""
        # This would update the providers.py to include the new model
        # For now, just log it
        self._log_acquisition("ollama_integrated", {
            "model": ability["name"]
        })
        return True
    
    def _integrate_researched_ability(self, ability: Dict[str, Any]) -> bool:
        """Integrate researched ability as new prompts/capabilities."""
        # Create improvement proposal
        from core.evolution import ImprovementProposal
        from core import safety

        ability_name = ability.get("name", "Unknown Ability")
        proposal = ImprovementProposal(
            category="skill",
            title=f"{ability_name} ability",
            description=f"Auto-integrated ability from {ability.get('source', 'research')}",
            code_snippet=(
                f"def run(context: dict, **kwargs) -> str:\n"
                f"    \"\"\"Placeholder for {ability_name} integration.\"\"\"\n"
                f"    return \"Ability '{ability_name}' is available for use.\"\n"
            ),
            source="ability_acquisition",
            files_to_modify=[],
            rationale="Enhance Jarvis with new open-source capability",
            confidence=0.8
        )
        
        # Apply if safe
        if guardian.validate_code_for_safety(proposal.code_snippet or "")[0]:
            result = evolution.apply_improvement(
                proposal,
                safety.SafetyContext(apply=True, dry_run=False),
            )
            self._log_acquisition("ability_integrated", {
                "ability_id": ability["id"],
                "type": "code_integration"
            })
            return result.get("status") == "applied"
        
        return False
    
    def _integrate_reference(self, ability: Dict[str, Any]) -> bool:
        """Integrate as reference material."""
        self._log_acquisition("reference_integrated", {
            "ability_id": ability["id"],
            "url": ability.get("url", "")
        })
        return True
    
    def run_acquisition_cycle(self) -> Dict[str, Any]:
        """Run a full autonomous acquisition cycle focused on free, goal-relevant abilities."""
        self._log_acquisition("cycle_started", {})
        
        # Discover new abilities
        discoveries = self.discover_open_source_models()
        
        # Evaluate each discovery with higher standards for free/goal-relevance
        evaluated = []
        for discovery in discoveries[:15]:  # Increase to 15 per cycle
            evaluation = self.evaluate_ability(discovery)
            if evaluation.get("recommended", False) and evaluation.get("rating", 0) >= 6:  # Lower threshold
                discovery["evaluation"] = evaluation
                evaluated.append(discovery)
        
        # Sort by rating and acquire top abilities
        evaluated.sort(key=lambda x: x["evaluation"].get("rating", 0), reverse=True)
        
        acquired = 0
        integrated = 0
        
        for discovery in evaluated[:7]:  # Increase to 7 per cycle for more autonomy
            if self.acquire_ability(discovery):
                acquired += 1
                
                # Try to integrate immediately with autonomous integration
                ability_id = f"{discovery.get('source', 'unknown')}_{hash(discovery.get('title', ''))}"
                for ability in self.abilities["acquired"]:
                    if ability["id"] == ability_id:
                        if self.integrate_ability(ability):
                            integrated += 1
                            
                            # Trigger restart if major capability added
                            if discovery["evaluation"].get("rating", 0) >= 9:
                                self._log_acquisition("major_capability_added", {
                                    "ability": ability["name"],
                                    "rating": discovery["evaluation"].get("rating")
                                })
                                # Signal restart needed
                                return {
                                    "discovered": len(discoveries),
                                    "evaluated": len(evaluated),
                                    "acquired": acquired,
                                    "integrated": integrated,
                                    "total_abilities": len(self.abilities["acquired"]),
                                    "restart_needed": True,
                                    "reason": f"Major capability integrated: {ability['name']}"
                                }
                        break
        
        result = {
            "discovered": len(discoveries),
            "evaluated": len(evaluated),
            "acquired": acquired,
            "integrated": integrated,
            "total_abilities": len(self.abilities["acquired"]),
            "restart_needed": False
        }
        
        self._log_acquisition("cycle_completed", result)
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get acquisition system status."""
        categories = {}
        for cat, cap_list in self.abilities["categories"].items():
            categories[cat] = len([
                ability for ability in self.abilities["acquired"]
                if any(cap in ability.get("capabilities", []) for cap in cap_list)
            ])
        return {
            "total_abilities": len(self.abilities["acquired"]),
            "total_models": len(self.models["installed"]),
            "categories": categories,
            "recent_acquisitions": self.abilities["acquired"][-5:],
            "available_models": self.models["installed"]
        }


# Global acquisition instance
_acquisition: Optional[AbilityAcquisition] = None


def get_ability_acquisition() -> AbilityAcquisition:
    """Get the global ability acquisition instance."""
    global _acquisition
    if not _acquisition:
        _acquisition = AbilityAcquisition()
    return _acquisition
