"""
Prompt Distiller for Jarvis.
Synthesizes research into optimized prompts and learning materials.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import prompts, providers, research_engine, evolution, guardian

ROOT = Path(__file__).resolve().parents[1]
DISTILLED_PROMPTS_PATH = ROOT / "data" / "distilled_prompts.json"
LEARNING_SUMMARY_PATH = ROOT / "data" / "learning_summary.json"


class PromptDistiller:
    """Distills research knowledge into actionable prompts and improvements."""
    
    def __init__(self):
        self._load_distilled()
        self._load_learning_summary()
        
    def _load_distilled(self):
        """Load previously distilled prompts."""
        if DISTILLED_PROMPTS_PATH.exists():
            with open(DISTILLED_PROMPTS_PATH, "r") as f:
                self.distilled_prompts = json.load(f)
        else:
            self.distilled_prompts = {
                "prompts": {},
                "last_updated": None,
                "version": "1.0"
            }
    
    def _save_distilled(self):
        """Save distilled prompts."""
        self.distilled_prompts["last_updated"] = datetime.now().isoformat()
        with open(DISTILLED_PROMPTS_PATH, "w") as f:
            json.dump(self.distilled_prompts, f, indent=2)
    
    def _load_learning_summary(self):
        """Load learning summary."""
        if LEARNING_SUMMARY_PATH.exists():
            with open(LEARNING_SUMMARY_PATH, "r") as f:
                self.learning_summary = json.load(f)
        else:
            self.learning_summary = {
                "key_insights": [],
                "skill_improvements": [],
                "new_techniques": [],
                "research_areas": [],
                "last_updated": None
            }
    
    def _save_learning_summary(self):
        """Save learning summary."""
        self.learning_summary["last_updated"] = datetime.now().isoformat()
        with open(LEARNING_SUMMARY_PATH, "w") as f:
            json.dump(self.learning_summary, f, indent=2)
    
    def synthesize_research(self, topic: str, research_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Synthesize multiple research sources into actionable knowledge."""
        # Combine all insights
        all_insights = []
        all_applications = []
        all_examples = []
        all_improvements = []
        
        for item in research_data:
            insights = item.get("insights", {})
            all_insights.extend(insights.get("insights", []))
            all_applications.extend(insights.get("applications", []))
            all_examples.extend(insights.get("examples", []))
            all_improvements.extend(insights.get("improvements", []))
        
        # Use LLM to synthesize
        prompt = f"""Synthesize this research about {topic} into actionable knowledge:

KEY INSIGHTS:
{json.dumps(all_insights[:10], indent=2)}

APPLICATIONS:
{json.dumps(all_applications[:10], indent=2)}

EXAMPLES:
{json.dumps(all_examples[:5], indent=2)}

IMPROVEMENTS:
{json.dumps(all_improvements[:10], indent=2)}

Create:
1. A comprehensive understanding of the topic
2. 3-5 actionable techniques for an AI assistant
3. Specific prompt templates for implementing these techniques
4. Code patterns or architectures if applicable
5. Next research directions

Output as JSON with keys: understanding, techniques, prompt_templates, code_patterns, next_research"""
        
        try:
            response = providers.ask_llm(prompt, max_output_tokens=2000)
            if response:
                try:
                    return json.loads(response)
                except Exception as e:
                    return {
                        "understanding": response,
                        "techniques": [],
                        "prompt_templates": [],
                        "code_patterns": [],
                        "next_research": []
                    }
        except Exception as e:
            print(f"Synthesis error: {e}")
        
        return {"understanding": "", "techniques": [], "prompt_templates": [], "code_patterns": [], "next_research": []}
    
    def create_prompts_from_techniques(self, topic: str, techniques: List[str]) -> List[Dict[str, Any]]:
        """Create optimized prompts from techniques."""
        created_prompts = []
        
        for technique in techniques:
            prompt = f"""Create an optimized prompt template for this AI technique: {technique}

The prompt should:
1. Be clear and specific
2. Include variable placeholders like {variable}
3. Have examples of usage
4. Include best practices

Output as JSON with: name, category, template, description, example_usage"""
            
            try:
                response = providers.ask_llm(prompt, max_output_tokens=800)
                if response:
                    try:
                        prompt_data = json.loads(response)
                        prompt_data["source_topic"] = topic
                        prompt_data["created_at"] = datetime.now().isoformat()
                        created_prompts.append(prompt_data)
                    except Exception as e:
                        # Create basic prompt
                        created_prompts.append({
                            "name": technique,
                            "category": "research_derived",
                            "template": f"Apply {technique}: {{input}}",
                            "description": technique,
                            "example_usage": f"Input: example\nOutput: apply {technique}",
                            "source_topic": topic,
                            "created_at": datetime.now().isoformat()
                        })
            except Exception as e:
                print(f"Prompt creation error: {e}")
        
        return created_prompts
    
    def distill_topic(self, topic: str) -> Dict[str, Any]:
        """Distill all research on a topic into prompts and knowledge."""
        # Get research data
        engine = research_engine.get_research_engine()
        research_data = engine.get_research_summary(topic, limit=20)
        
        if not research_data:
            return {"success": False, "error": "No research found"}
        
        # Synthesize research
        synthesis = self.synthesize_research(topic, research_data)
        
        # Create prompts from techniques
        new_prompts = self.create_prompts_from_techniques(topic, synthesis.get("techniques", []))
        
        # Save distilled prompts
        self.distilled_prompts["prompts"][topic] = {
            "synthesis": synthesis,
            "prompts": new_prompts,
            "research_count": len(research_data),
            "created_at": datetime.now().isoformat()
        }
        self._save_distilled()
        
        # Update learning summary
        self._update_learning_summary(topic, synthesis)
        
        # Apply new prompts to the system
        self._apply_new_prompts(new_prompts)
        
        return {
            "success": True,
            "topic": topic,
            "prompts_created": len(new_prompts),
            "synthesis": synthesis
        }
    
    def _update_learning_summary(self, topic: str, synthesis: Dict[str, Any]):
        """Update the overall learning summary."""
        # Add key insights
        for insight in synthesis.get("understanding", "").split("."):
            insight = insight.strip()
            if insight and len(insight) > 20:
                if insight not in self.learning_summary["key_insights"]:
                    self.learning_summary["key_insights"].append(insight)
                    self.learning_summary["key_insights"] = self.learning_summary["key_insights"][-50:]  # Keep last 50
        
        # Add new techniques
        for technique in synthesis.get("techniques", []):
            if technique not in self.learning_summary["new_techniques"]:
                self.learning_summary["new_techniques"].append(technique)
        
        # Add research areas
        if topic not in self.learning_summary["research_areas"]:
            self.learning_summary["research_areas"].append(topic)
        
        self._save_learning_summary()
    
    def _apply_new_prompts(self, new_prompts: List[Dict[str, Any]]):
        """Apply new prompts to the prompts system."""
        for prompt_data in new_prompts:
            try:
                # Create custom prompt
                prompts.create_custom_prompt(
                    name=prompt_data["name"],
                    category=prompt_data["category"],
                    template=prompt_data["template"],
                    description=prompt_data["description"]
                )
            except Exception as e:
                print(f"Error applying prompt: {e}")
    
    def generate_improvements_from_research(self, topic: str = None) -> List[evolution.ImprovementProposal]:
        """Generate improvement proposals from distilled research."""
        improvements = []
        
        if topic:
            distilled = self.distilled_prompts["prompts"].get(topic, {})
            synthesis = distilled.get("synthesis", {})
            
            # Create improvements from synthesis
            for technique in synthesis.get("techniques", []):
                proposal = evolution.ImprovementProposal(
                    category="skill",
                    title=f"Implement {technique}",
                    description=f"Add capability for {technique} based on research",
                    source="research_distillation",
                    priority=0.8
                )
                improvements.append(proposal)
        else:
            # Generate from all recent research
            for topic_name, data in self.distilled_prompts["prompts"].items():
                synthesis = data.get("synthesis", {})
                for pattern in synthesis.get("code_patterns", [])[:2]:
                    proposal = evolution.ImprovementProposal(
                        category="module",
                        title=f"Code pattern: {topic_name}",
                        description=pattern,
                        source="research_distillation",
                        priority=0.7
                    )
                    improvements.append(proposal)
        
        return improvements
    
    def get_learning_report(self) -> Dict[str, Any]:
        """Get comprehensive learning report."""
        engine = research_engine.get_research_engine()
        
        # Get stats
        total_research = len(engine.get_research_summary(limit=1000))
        total_concepts = len(engine.get_knowledge_graph())
        total_prompts = sum(len(data.get("prompts", [])) for data in self.distilled_prompts["prompts"].values())
        
        return {
            "research_summary": {
                "total_pages_processed": total_research,
                "total_concepts_learned": total_concepts,
                "total_prompts_created": total_prompts,
                "topics_researched": list(self.distilled_prompts["prompts"].keys())
            },
            "key_insights": self.learning_summary["key_insights"][:10],
            "new_techniques": self.learning_summary["new_techniques"][:10],
            "last_updated": self.learning_summary["last_updated"]
        }


# Global distiller instance
_distiller: Optional[PromptDistiller] = None


def get_prompt_distiller() -> PromptDistiller:
    """Get the global prompt distiller instance."""
    global _distiller
    if not _distiller:
        _distiller = PromptDistiller()
    return _distiller
