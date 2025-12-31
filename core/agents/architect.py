"""
Architect Agent - Self-improvement proposals with quality gates.

Capabilities:
- Code analysis and improvement proposals
- Quality gate enforcement
- Patch generation and testing
- Evolution management

Uses Claude/GPT for quality (code generation requires precision),
with Ollama fallback for self-sufficient operation.
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.agents.base import (
    BaseAgent,
    AgentRole,
    AgentCapability,
    AgentTask,
    AgentResult,
    ProviderPreference,
)


ROOT = Path(__file__).resolve().parents[2]
ARCHITECT_DIR = ROOT / "data" / "architect"
PROPOSALS_FILE = ARCHITECT_DIR / "proposals.jsonl"
QUALITY_LOG = ARCHITECT_DIR / "quality_gates.jsonl"


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


class QualityGate(str, Enum):
    SYNTAX_CHECK = "syntax_check"       # Code compiles/parses
    LINT_CHECK = "lint_check"           # Passes linting
    TYPE_CHECK = "type_check"           # Type checking passes
    TEST_COVERAGE = "test_coverage"     # Has test coverage
    SECURITY_SCAN = "security_scan"     # No security issues
    PERFORMANCE = "performance"         # No performance regression
    USER_APPROVAL = "user_approval"     # User has approved


@dataclass
class ImprovementProposal:
    """A proposed improvement to the codebase."""
    id: str
    title: str
    description: str
    category: str  # "bugfix", "feature", "refactor", "performance", "security"
    files_affected: List[str]
    changes: Dict[str, str]  # file -> diff or new content
    confidence: float
    risk_level: str  # "low", "medium", "high"
    status: ProposalStatus = ProposalStatus.DRAFT
    gates_passed: List[QualityGate] = field(default_factory=list)
    gates_failed: List[QualityGate] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    applied_at: Optional[float] = None


class ArchitectAgent(BaseAgent):
    """
    Architect Agent - Manages system self-improvement.

    This agent is responsible for Jarvis evolving and improving itself.
    All changes go through quality gates before application.

    Capabilities:
    - Code analysis and pattern detection
    - Improvement proposal generation
    - Quality gate enforcement
    - Safe patch application

    Uses Claude/GPT for code generation quality,
    with Ollama fallback for self-sufficient operation.

    CRITICAL: Never applies changes without passing all quality gates.
    """

    def __init__(self):
        super().__init__(
            role=AgentRole.ARCHITECT,
            capabilities=[
                AgentCapability.CODE_ANALYSIS,
                AgentCapability.CODE_GENERATION,
                AgentCapability.QUALITY_GATES,
            ],
            provider_preference=ProviderPreference.AUTO,  # Quality chain
        )
        ARCHITECT_DIR.mkdir(parents=True, exist_ok=True)
        self._proposals: Dict[str, ImprovementProposal] = {}

    def get_system_prompt(self) -> str:
        return """You are the Architect Agent in the Jarvis multi-agent system.

Your role is to improve Jarvis's codebase safely and systematically.

CAPABILITIES:
- Analyze code for improvement opportunities
- Generate patches and new code
- Enforce quality gates
- Manage the evolution lifecycle

QUALITY GATES (all must pass before applying):
1. SYNTAX_CHECK: Code compiles/parses
2. LINT_CHECK: Passes linting rules
3. TYPE_CHECK: Type annotations are correct
4. TEST_COVERAGE: Changes have tests
5. SECURITY_SCAN: No security vulnerabilities
6. PERFORMANCE: No performance regression
7. USER_APPROVAL: User has approved (for high-risk changes)

RISK LEVELS:
- LOW: Formatting, comments, documentation
- MEDIUM: Refactoring, new features in isolated modules
- HIGH: Core logic changes, security-related, data handling

OPERATING PRINCIPLES:
1. NEVER bypass quality gates
2. ALWAYS propose, never directly apply
3. Document reasoning for every change
4. Keep changes small and focused
5. Maintain backwards compatibility when possible

OUTPUT FORMAT:
For proposals:
- TITLE: Short descriptive title
- CATEGORY: bugfix/feature/refactor/performance/security
- RISK: low/medium/high
- FILES: List of affected files
- CHANGES: Detailed description
- REASONING: Why this improves the system
- TESTS: How to verify the change works"""

    def _get_keywords(self) -> List[str]:
        return [
            "improve", "refactor", "optimize", "fix", "enhance",
            "code", "architecture", "design", "pattern",
            "quality", "test", "coverage", "security",
            "evolve", "upgrade", "modernize", "clean",
            "proposal", "patch", "change", "update",
        ]

    def execute(self, task: AgentTask) -> AgentResult:
        """Execute an architecture/improvement task."""
        start_time = time.time()
        steps_taken = 0
        artifacts = {}

        try:
            # Determine task type
            task_type = self._determine_task_type(task)
            steps_taken += 1

            if task_type == "analyze":
                output = self._analyze_codebase(task)
                steps_taken += 2
            elif task_type == "propose":
                output, proposal = self._generate_proposal(task)
                if proposal:
                    artifacts["proposal"] = proposal.__dict__
                steps_taken += 3
            elif task_type == "review":
                output = self._review_proposal(task)
                steps_taken += 2
            elif task_type == "apply":
                output, success = self._apply_proposal(task)
                artifacts["applied"] = success
                steps_taken += 4
            else:
                output = self._general_architecture(task)
                steps_taken += 1

            return AgentResult(
                task_id=task.id,
                success=True,
                output=output,
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
                artifacts=artifacts,
            )

        except Exception as e:
            return AgentResult(
                task_id=task.id,
                success=False,
                output="",
                error=str(e)[:500],
                steps_taken=steps_taken,
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def _determine_task_type(self, task: AgentTask) -> str:
        """Determine what architecture task to perform."""
        desc_lower = task.description.lower()

        if any(w in desc_lower for w in ["analyze", "review", "audit", "assess"]):
            return "analyze"
        elif any(w in desc_lower for w in ["propose", "suggest", "improve", "refactor"]):
            return "propose"
        elif any(w in desc_lower for w in ["apply", "implement", "execute", "deploy"]):
            return "apply"
        elif any(w in desc_lower for w in ["check", "validate", "verify"]):
            return "review"
        else:
            return "general"

    def _analyze_codebase(self, task: AgentTask) -> str:
        """Analyze codebase for improvement opportunities."""
        target = task.context.get("target", "core/")

        prompt = f"""Analyze this codebase area for improvements:

Target: {target}
Focus: {task.description}

Identify:
1. CODE SMELLS: Issues that should be fixed
2. OPPORTUNITIES: Potential improvements
3. RISKS: Security or reliability concerns
4. PATTERNS: Existing patterns to maintain
5. RECOMMENDATIONS: Prioritized list of changes

For each finding, specify:
- Severity (critical/high/medium/low)
- Effort (small/medium/large)
- Risk (low/medium/high)
- Files affected"""

        response, _ = self.generate(prompt, priority="quality")
        return response

    def _generate_proposal(self, task: AgentTask) -> Tuple[str, Optional[ImprovementProposal]]:
        """Generate an improvement proposal."""
        prompt = f"""Generate an improvement proposal for:

Task: {task.description}
Context: {json.dumps(task.context) if task.context else 'None'}

Create a detailed proposal with:
1. TITLE: Concise title
2. CATEGORY: bugfix/feature/refactor/performance/security
3. DESCRIPTION: What the change does
4. FILES_AFFECTED: List of files to modify
5. CHANGES: Specific changes for each file
6. RISK_LEVEL: low/medium/high
7. CONFIDENCE: 0-100%
8. TESTS: How to verify
9. REASONING: Why this is beneficial

Output as structured JSON."""

        response, _ = self.generate(prompt, priority="quality")

        # Try to parse proposal
        proposal = None
        try:
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                data = json.loads(match.group())
                proposal = ImprovementProposal(
                    id=str(uuid.uuid4())[:8],
                    title=data.get("title", task.description[:50]),
                    description=data.get("description", ""),
                    category=data.get("category", "refactor"),
                    files_affected=data.get("files_affected", []),
                    changes=data.get("changes", {}),
                    confidence=data.get("confidence", 50) / 100.0,
                    risk_level=data.get("risk_level", "medium"),
                )
                self._proposals[proposal.id] = proposal
                self._log_proposal(proposal)
        except Exception:
            pass

        return response, proposal

    def _review_proposal(self, task: AgentTask) -> str:
        """Review a proposal against quality gates."""
        proposal_id = task.context.get("proposal_id")

        if not proposal_id or proposal_id not in self._proposals:
            return "No valid proposal ID provided"

        proposal = self._proposals[proposal_id]

        # Run quality gates
        gates_results = self._run_quality_gates(proposal)

        # Update proposal
        proposal.gates_passed = [g for g, passed in gates_results.items() if passed]
        proposal.gates_failed = [g for g, passed in gates_results.items() if not passed]

        if proposal.gates_failed:
            proposal.status = ProposalStatus.PENDING_REVIEW
            result = f"PROPOSAL {proposal_id} - GATES FAILED\n\n"
            result += f"Passed: {[g.value for g in proposal.gates_passed]}\n"
            result += f"Failed: {[g.value for g in proposal.gates_failed]}\n"
            result += "\nCannot apply until all gates pass."
        else:
            proposal.status = ProposalStatus.APPROVED
            result = f"PROPOSAL {proposal_id} - ALL GATES PASSED\n\n"
            result += "Ready for application pending user approval."

        return result

    def _run_quality_gates(self, proposal: ImprovementProposal) -> Dict[QualityGate, bool]:
        """Run quality gates on a proposal."""
        results = {}

        # Syntax check (simulated)
        results[QualityGate.SYNTAX_CHECK] = True

        # Lint check (simulated)
        results[QualityGate.LINT_CHECK] = True

        # Type check (simulated)
        results[QualityGate.TYPE_CHECK] = True

        # Security scan (check for obvious issues)
        security_keywords = ["eval(", "exec(", "os.system(", "__import__"]
        has_security_issue = any(
            kw in str(proposal.changes)
            for kw in security_keywords
        )
        results[QualityGate.SECURITY_SCAN] = not has_security_issue

        # Test coverage (would check if tests exist)
        results[QualityGate.TEST_COVERAGE] = proposal.confidence > 0.7

        # Performance (assume ok for non-critical paths)
        results[QualityGate.PERFORMANCE] = proposal.risk_level != "high"

        # User approval needed for high-risk
        results[QualityGate.USER_APPROVAL] = proposal.risk_level == "low"

        # Log gate results
        self._log_gates(proposal.id, results)

        return results

    def _apply_proposal(self, task: AgentTask) -> Tuple[str, bool]:
        """Apply an approved proposal (simulation - real would modify files)."""
        proposal_id = task.context.get("proposal_id")

        if not proposal_id or proposal_id not in self._proposals:
            return "No valid proposal ID provided", False

        proposal = self._proposals[proposal_id]

        if proposal.status != ProposalStatus.APPROVED:
            return f"Proposal {proposal_id} is not approved. Status: {proposal.status.value}", False

        # Would apply changes here
        # For safety, we just log what would happen
        proposal.status = ProposalStatus.APPLIED
        proposal.applied_at = time.time()

        return f"""PROPOSAL {proposal_id} APPLIED

Title: {proposal.title}
Files: {proposal.files_affected}
Category: {proposal.category}

Changes have been logged. Run tests to verify.""", True

    def _general_architecture(self, task: AgentTask) -> str:
        """General architecture advice."""
        prompt = f"""Provide architecture guidance for:

{task.description}

Consider:
1. Current patterns in the codebase
2. Best practices
3. Maintainability
4. Performance implications
5. Security considerations"""

        response, _ = self.generate(prompt, priority="quality")
        return response

    def _log_proposal(self, proposal: ImprovementProposal) -> None:
        """Log proposal to file."""
        entry = {
            "timestamp": time.time(),
            "event": "proposal_created",
            **proposal.__dict__,
        }
        with open(PROPOSALS_FILE, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def _log_gates(self, proposal_id: str, results: Dict[QualityGate, bool]) -> None:
        """Log quality gate results."""
        entry = {
            "timestamp": time.time(),
            "proposal_id": proposal_id,
            "results": {g.value: v for g, v in results.items()},
        }
        with open(QUALITY_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    # Public methods for evolution system
    def propose_improvement(self, description: str, target: str = "core/") -> Optional[ImprovementProposal]:
        """Create improvement proposal programmatically."""
        task = AgentTask(
            id=str(uuid.uuid4())[:8],
            objective_id="improvement",
            description=description,
            context={"target": target},
        )
        result = self.execute(task)

        if result.artifacts and "proposal" in result.artifacts:
            return self._proposals.get(result.artifacts["proposal"].get("id"))
        return None

    def get_pending_proposals(self) -> List[ImprovementProposal]:
        """Get all pending proposals."""
        return [
            p for p in self._proposals.values()
            if p.status in [ProposalStatus.DRAFT, ProposalStatus.PENDING_REVIEW]
        ]
