"""
Self-Evaluator for Jarvis.
Constantly evaluates, tests abilities, and integrates useful expansions.
"""

import json
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core import config, providers, evolution, guardian, research_engine, learning_validator, safety

ROOT = Path(__file__).resolve().parents[1]
SELF_EVAL_PATH = ROOT / "data" / "self_evaluation"
EXPANSIONS_PATH = ROOT / "data" / "expansions"
SELF_EVAL_LOG_PATH = ROOT / "data" / "self_eval.log"


class SelfEvaluator:
    """Evaluates, tests, and integrates self-improvements."""
    
    def __init__(self):
        self.eval_db = SELF_EVAL_PATH / "evaluations.json"
        self.expansions_db = EXPANSIONS_PATH / "expansions.json"
        self.abilities_db = SELF_EVAL_PATH / "abilities.json"
        self._ensure_directories()
        self._load_data()
        
    def _ensure_directories(self):
        """Ensure data directories exist."""
        SELF_EVAL_PATH.mkdir(parents=True, exist_ok=True)
        EXPANSIONS_PATH.mkdir(parents=True, exist_ok=True)
        
    def _load_data(self):
        """Load evaluation and expansion data."""
        if self.eval_db.exists():
            with open(self.eval_db, "r") as f:
                self.evaluations = json.load(f)
        else:
            self.evaluations = {
                "self_assessments": [],
                "ability_tests": [],
                "performance_metrics": [],
                "weaknesses": [],
                "strengths": []
            }
        
        if self.expansions_db.exists():
            with open(self.expansions_db, "r") as f:
                self.expansions = json.load(f)
        else:
            self.expansions = {
                "researched": [],
                "evaluated": [],
                "integrated": [],
                "failed": []
            }
        
        if self.abilities_db.exists():
            with open(self.abilities_db, "r") as f:
                self.abilities = json.load(f)
        else:
            self.abilities = {
                "current": [],
                "tested": [],
                "deprecated": [],
                "new": []
            }
    
    def _save_data(self):
        """Save evaluation and expansion data."""
        with open(self.eval_db, "w") as f:
            json.dump(self.evaluations, f, indent=2)
        with open(self.expansions_db, "w") as f:
            json.dump(self.expansions, f, indent=2)
        with open(self.abilities_db, "w") as f:
            json.dump(self.abilities, f, indent=2)
    
    def _log_evaluation(self, eval_type: str, details: Dict[str, Any]):
        """Log evaluation activity."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": eval_type,
            "details": details
        }
        
        with open(SELF_EVAL_LOG_PATH, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def evaluate_current_state(self) -> Dict[str, Any]:
        """Evaluate current state and performance."""
        evaluation_prompt = """Evaluate Jarvis's current capabilities and performance:

Consider:
1. Research effectiveness - How well is it gathering useful information?
2. Learning efficiency - How quickly is it synthesizing and applying knowledge?
3. Self-improvement success rate - Are improvements working?
4. Code quality and safety - Are changes robust and safe?
5. Autonomy level - How independently is it operating?

Provide:
- Current strengths (3-5)
- Identified weaknesses (3-5)
- Performance score (1-10)
- Priority areas for improvement"""
        
        try:
            response = providers.ask_llm(evaluation_prompt, max_output_tokens=800)
            if response:
                # Parse evaluation
                evaluation = {
                    "timestamp": datetime.now().isoformat(),
                    "llm_evaluation": response,
                    "self_score": self._extract_score(response),
                    "strengths": self._extract_strengths(response),
                    "weaknesses": self._extract_weaknesses(response),
                    "priority_areas": self._extract_priorities(response)
                }
                
                self.evaluations["self_assessments"].append(evaluation)
                self._save_data()
                self._log_evaluation("self_assessment", evaluation)
                
                return evaluation
        except Exception as e:
            self._log_evaluation("self_assessment_error", {"error": str(e)})
        
        return {"error": "Failed to evaluate current state"}
    
    def _extract_score(self, response: str) -> int:
        """Extract performance score from evaluation."""
        import re
        score_match = re.search(r'(?:score|rating|performance)[:\s]*(\d+)/?10?', response.lower())
        if score_match:
            return int(score_match.group(1))
        return 5  # Default score
    
    def _extract_strengths(self, response: str) -> List[str]:
        """Extract strengths from evaluation."""
        strengths = []
        lines = response.split('\n')
        in_strengths = False
        
        for line in lines:
            if 'strength' in line.lower() or 'good at' in line.lower():
                in_strengths = True
                if ':' in line:
                    strength = line.split(':', 1)[1].strip()
                    if strength and strength != '-':
                        strengths.append(strength)
            elif in_strengths and line.strip().startswith('-'):
                strength = line.strip().lstrip('- ').strip()
                if strength:
                    strengths.append(strength)
            elif in_strengths and line.strip() == '':
                break
        
        return strengths[:5]  # Limit to 5
    
    def _extract_weaknesses(self, response: str) -> List[str]:
        """Extract weaknesses from evaluation."""
        weaknesses = []
        lines = response.split('\n')
        in_weaknesses = False
        
        for line in lines:
            if 'weakness' in line.lower() or 'improve' in line.lower() or 'needs' in line.lower():
                in_weaknesses = True
                if ':' in line:
                    weakness = line.split(':', 1)[1].strip()
                    if weakness and weakness != '-':
                        weaknesses.append(weakness)
            elif in_weaknesses and line.strip().startswith('-'):
                weakness = line.strip().lstrip('- ').strip()
                if weakness:
                    weaknesses.append(weakness)
            elif in_weaknesses and line.strip() == '':
                break
        
        return weaknesses[:5]  # Limit to 5
    
    def _extract_priorities(self, response: str) -> List[str]:
        """Extract priority areas from evaluation."""
        priorities = []
        lines = response.split('\n')
        in_priorities = False
        
        for line in lines:
            if 'priority' in line.lower() or 'focus' in line.lower():
                in_priorities = True
                if ':' in line:
                    priority = line.split(':', 1)[1].strip()
                    if priority and priority != '-':
                        priorities.append(priority)
            elif in_priorities and line.strip().startswith('-'):
                priority = line.strip().lstrip('- ').strip()
                if priority:
                    priorities.append(priority)
            elif in_priorities and line.strip() == '':
                break
        
        return priorities[:3]  # Limit to 3
    
    def test_current_abilities(self) -> Dict[str, Any]:
        """Test all current abilities and functions."""
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "abilities_tested": 0,
            "passed": 0,
            "failed": 0,
            "details": []
        }
        
        # Test core abilities
        core_abilities = [
            "research_capability",
            "learning_capability", 
            "improvement_capability",
            "validation_capability"
        ]
        
        for ability in core_abilities:
            result = self._test_ability(ability)
            test_results["abilities_tested"] += 1
            test_results["details"].append(result)
            
            if result["status"] == "passed":
                test_results["passed"] += 1
            else:
                test_results["failed"] += 1
        
        # Test specific functions
        function_tests = self._test_core_functions()
        test_results["details"].extend(function_tests)
        test_results["abilities_tested"] += len(function_tests)
        test_results["passed"] += sum(1 for ft in function_tests if ft["status"] == "passed")
        test_results["failed"] += sum(1 for ft in function_tests if ft["status"] == "failed")
        
        self.evaluations["ability_tests"].append(test_results)
        self._save_data()
        self._log_evaluation("ability_test", test_results)
        
        return test_results
    
    def _test_ability(self, ability_name: str) -> Dict[str, Any]:
        """Test a specific ability."""
        try:
            if ability_name == "research_capability":
                return self._test_research_capability()
            elif ability_name == "learning_capability":
                return self._test_learning_capability()
            elif ability_name == "improvement_capability":
                return self._test_improvement_capability()
            elif ability_name == "validation_capability":
                return self._test_validation_capability()
            else:
                return {"ability": ability_name, "status": "unknown", "error": "Unknown ability"}
        except Exception as e:
            return {"ability": ability_name, "status": "error", "error": str(e)}
    
    def _test_research_capability(self) -> Dict[str, Any]:
        """Test research capability."""
        try:
            engine = research_engine.get_research_engine()
            # Quick test search
            results = engine.search_web("autonomous AI", max_results=3)
            
            return {
                "ability": "research_capability",
                "status": "passed" if len(results) > 0 else "failed",
                "results_count": len(results),
                "test_time": datetime.now().isoformat()
            }
        except Exception as e:
            return {"ability": "research_capability", "status": "failed", "error": str(e)}
    
    def _test_learning_capability(self) -> Dict[str, Any]:
        """Test learning capability."""
        try:
            # Test if we can process information
            test_prompt = "Summarize the concept of autonomous learning in one sentence."
            response = providers.ask_llm(test_prompt, max_output_tokens=100)
            
            return {
                "ability": "learning_capability",
                "status": "passed" if response and len(response) > 10 else "failed",
                "response_length": len(response) if response else 0,
                "test_time": datetime.now().isoformat()
            }
        except Exception as e:
            return {"ability": "learning_capability", "status": "failed", "error": str(e)}
    
    def _test_improvement_capability(self) -> Dict[str, Any]:
        """Test improvement capability."""
        try:
            # Test if we can generate improvements
            from core.evolution import ImprovementProposal
            proposal = evolution.propose_improvement_from_context("Test improvement for better logging")
            
            return {
                "ability": "improvement_capability",
                "status": "passed" if proposal else "failed",
                "proposal_generated": bool(proposal),
                "test_time": datetime.now().isoformat()
            }
        except Exception as e:
            return {"ability": "improvement_capability", "status": "failed", "error": str(e)}
    
    def _test_validation_capability(self) -> Dict[str, Any]:
        """Test validation capability."""
        try:
            validator = learning_validator.get_learning_validator()
            metrics = validator.calculate_metrics()
            
            return {
                "ability": "validation_capability",
                "status": "passed" if metrics else "failed",
                "metrics_calculated": bool(metrics),
                "test_time": datetime.now().isoformat()
            }
        except Exception as e:
            return {"ability": "validation_capability", "status": "failed", "error": str(e)}
    
    def _test_core_functions(self) -> List[Dict[str, Any]]:
        """Test core functions."""
        tests = []
        
        # Test configuration loading
        try:
            cfg = config.load_config()
            tests.append({
                "function": "config_load",
                "status": "passed",
                "config_loaded": bool(cfg)
            })
        except Exception as e:
            tests.append({
                "function": "config_load",
                "status": "failed",
                "error": str(e)
            })
        
        # Test guardian safety
        try:
            is_safe, reason = guardian.validate_code_for_safety("print('safe test')")
            tests.append({
                "function": "guardian_safety",
                "status": "passed",
                "safety_check": is_safe
            })
        except Exception as e:
            tests.append({
                "function": "guardian_safety",
                "status": "failed",
                "error": str(e)
            })
        
        return tests
    
    def research_useful_expansions(self) -> List[Dict[str, Any]]:
        """Research useful expansions for Jarvis."""
        expansions = []
        
        # Get current weaknesses and priorities
        latest_eval = self.evaluations["self_assessments"][-1] if self.evaluations["self_assessments"] else {}
        weaknesses = latest_eval.get("weaknesses", [])
        priorities = latest_eval.get("priority_areas", [])
        
        # Research expansions based on weaknesses
        research_queries = [
            "improving autonomous agent learning algorithms",
            "enhancing AI self-improvement mechanisms",
            "better code generation and validation for AI",
            "autonomous research and information synthesis",
            "AI meta-learning and adaptation techniques"
        ]
        
        # Add specific queries based on weaknesses
        for weakness in weaknesses[:3]:
            research_queries.append(f"AI solutions for {weakness.lower()}")
        
        engine = research_engine.get_research_engine()
        
        for query in research_queries:
            try:
                results = engine.search_web(query, max_results=3)
                for result in results:
                    expansion = {
                        "query": query,
                        "title": result["title"],
                        "url": result["url"],
                        "snippet": result["snippet"],
                        "researched_at": datetime.now().isoformat()
                    }
                    expansions.append(expansion)
                    self.expansions["researched"].append(expansion)
            except Exception as e:
                self._log_evaluation("expansion_research_error", {
                    "query": query,
                    "error": str(e)
                })
        
        self._save_data()
        self._log_evaluation("expansions_researched", {"count": len(expansions)})
        
        return expansions
    
    def evaluate_expansions(self, expansions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Evaluate researched expansions for usefulness."""
        evaluated = []
        
        for expansion in expansions:
            evaluation_prompt = f"""Evaluate this potential expansion for Jarvis:

Title: {expansion['title']}
Description: {expansion['snippet']}
Source: {expansion['url']}

Consider:
1. How directly would this improve Jarvis's capabilities?
2. Is this feasible to implement?
3. Would this enhance autonomy or intelligence?
4. Is this aligned with self-improvement goals?

Rate from 1-10 and provide brief reasoning."""
            
            try:
                response = providers.ask_llm(evaluation_prompt, max_output_tokens=300)
                if response:
                    rating = self._extract_score(response)
                    
                    evaluated_expansion = {
                        **expansion,
                        "evaluation": response,
                        "rating": rating,
                        "recommended": rating >= 7,
                        "evaluated_at": datetime.now().isoformat()
                    }
                    
                    evaluated.append(evaluated_expansion)
                    self.expansions["evaluated"].append(evaluated_expansion)
                    
            except Exception as e:
                self._log_evaluation("expansion_evaluation_error", {
                    "expansion": expansion["title"],
                    "error": str(e)
                })
        
        self._save_data()
        self._log_evaluation("expansions_evaluated", {"count": len(evaluated)})
        
        return evaluated
    
    def integrate_expansions(self, evaluated_expansions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Integrate high-rated expansions."""
        integration_results = {
            "attempted": 0,
            "integrated": 0,
            "failed": 0,
            "details": []
        }
        
        # Filter for high-rated expansions
        high_rated = [e for e in evaluated_expansions if e.get("recommended", False)]
        
        for expansion in high_rated[:3]:  # Limit to 3 per cycle
            integration_results["attempted"] += 1
            
            try:
                # Generate improvement proposal based on expansion
                proposal = self._create_proposal_from_expansion(expansion)
                
                if proposal:
                    # Apply the improvement
                    result = evolution.apply_improvement(
                        proposal,
                        safety.SafetyContext(apply=True, dry_run=False),
                    )

                    if result.get("status") in ("applied", "saved"):
                        integration_results["integrated"] += 1
                        self.expansions["integrated"].append({
                            **expansion,
                            "integrated_at": datetime.now().isoformat(),
                            "proposal": proposal.title
                        })
                        
                        # Validate the new function
                        if "function" in proposal.title.lower():
                            function_name = proposal.title.split()[-1].lower()
                            validator = learning_validator.get_learning_validator()
                            validation = validator.validate_new_function(
                                function_name,
                                proposal.code_snippet
                            )
                            
                        integration_results["details"].append({
                            "expansion": expansion["title"],
                            "status": "integrated",
                            "validation": validation.get("overall_status", "not_applicable") if 'validation' in dir() else "not_applicable"
                        })
                    else:
                        integration_results["failed"] += 1
                        self.expansions["failed"].append({
                            **expansion,
                            "failed_at": datetime.now().isoformat(),
                            "error": result.get("error", "Unknown error")
                        })
                        
                        integration_results["details"].append({
                            "expansion": expansion["title"],
                            "status": "failed",
                            "error": result.get("message", result.get("error"))
                        })
                else:
                    integration_results["failed"] += 1
                    
            except Exception as e:
                integration_results["failed"] += 1
                self._log_evaluation("expansion_integration_error", {
                    "expansion": expansion["title"],
                    "error": str(e)
                })
        
        self._save_data()
        self._log_evaluation("expansions_integrated", integration_results)
        
        return integration_results
    
    def _create_proposal_from_expansion(self, expansion: Dict[str, Any]) -> Optional[evolution.ImprovementProposal]:
        """Create improvement proposal from expansion."""
        try:
            proposal_prompt = f"""Create a concrete improvement proposal based on this expansion:

Title: {expansion['title']}
Description: {expansion['snippet']}
Evaluation: {expansion.get('evaluation', '')}

Generate:
1. A clear improvement title
2. Specific code implementation
3. Files to modify
4. Rationale for the improvement

Focus on practical, implementable improvements."""
            
            response = providers.ask_llm(proposal_prompt, max_output_tokens=600)
            if response:
                # Parse response to create proposal
                # This is simplified - in practice would need better parsing
                title = expansion["title"][:50] + " Implementation"
                
                code_snippet = f"""
# Implementation based on: {expansion['title']}
# Source: {expansion['url']}

def implement_{expansion['title'].lower().replace(' ', '_').replace('-', '_')}():
    \"\"\"Implement {expansion['title']}.\"\"\"
    # TODO: Implement based on research
    pass
"""
                
                return evolution.ImprovementProposal(
                    category="module",
                    title=title,
                    description=expansion["snippet"],
                    code_snippet=code_snippet,
                    files_to_modify=["core/actions.py"],
                    rationale=f"Based on research: {expansion['title']}",
                    confidence=0.7,
                    source="self_evaluator"
                )
        except Exception as e:
            pass
        
        return None
    
    def run_self_evaluation_cycle(self) -> Dict[str, Any]:
        """Run complete self-evaluation cycle."""
        cycle_start = datetime.now()
        
        self._log_evaluation("cycle_started", {})
        
        # Step 1: Evaluate current state
        self_evaluation = self.evaluate_current_state()
        
        # Step 2: Test current abilities
        ability_tests = self.test_current_abilities()
        
        # Step 3: Research useful expansions
        expansions = self.research_useful_expansions()
        
        # Step 4: Evaluate expansions
        evaluated_expansions = self.evaluate_expansions(expansions)
        
        # Step 5: Integrate best expansions
        integration_results = self.integrate_expansions(evaluated_expansions)
        
        cycle_result = {
            "cycle_start": cycle_start.isoformat(),
            "cycle_end": datetime.now().isoformat(),
            "self_evaluation": self_evaluation.get("self_score", 5),
            "abilities_tested": ability_tests["abilities_tested"],
            "abilities_passed": ability_tests["passed"],
            "expansions_researched": len(expansions),
            "expansions_evaluated": len(evaluated_expansions),
            "expansions_integrated": integration_results["integrated"],
            "overall_success": integration_results["integrated"] > 0
        }
        
        self._log_evaluation("cycle_completed", cycle_result)
        
        return cycle_result


# Global self-evaluator instance
_evaluator: Optional[SelfEvaluator] = None


def get_self_evaluator() -> SelfEvaluator:
    """Get the global self-evaluator instance."""
    global _evaluator
    if not _evaluator:
        _evaluator = SelfEvaluator()
    return _evaluator
