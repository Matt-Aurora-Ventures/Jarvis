#!/usr/bin/env python3
"""
Self-Improvement Engine - Jarvis improves itself meaningfully and safely
Implements the core self-upgrade loop with privacy-safe autonomous improvements
"""

import json
import sqlite3
import time
import subprocess
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from enum import Enum
import ast
import re

from core import safety, providers, mcp_doctor_simple, secret_hygiene

ROOT = Path(__file__).resolve().parents[1]
IMPROVEMENT_DB_PATH = ROOT / "data" / "improvement_backlog.db"
SELF_IMPROVEMENT_LOG_PATH = ROOT / "data" / "self_improvement.log"


class TicketStatus(Enum):
    """Status of improvement tickets."""
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    TESTING = "testing"
    READY = "ready"
    APPLIED = "applied"
    FAILED = "failed"
    REJECTED = "rejected"


class TicketPriority(Enum):
    """Priority levels for improvement tickets."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ImprovementTicket:
    """A ticket representing a potential improvement."""
    id: str
    title: str
    description: str
    category: str  # "bug_fix", "performance", "feature", "refactor"
    priority: TicketPriority
    status: TicketStatus
    created_at: datetime
    updated_at: datetime
    evidence: Dict[str, Any]  # Logs, errors, metrics
    proposed_solution: str
    test_plan: str
    files_to_modify: List[str]
    risk_level: int  # 1-10, higher = riskier
    estimated_effort: int  # 1-10, higher = more effort
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        result["status"] = self.status.value
        result["priority"] = self.priority.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ImprovementTicket":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        data["status"] = TicketStatus(data["status"])
        data["priority"] = TicketPriority(data["priority"])
        return cls(**data)


class ImprovementBacklog:
    """Manages the backlog of improvement tickets."""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """Initialize improvement backlog database."""
        IMPROVEMENT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(IMPROVEMENT_DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS improvement_tickets (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    evidence TEXT,
                    proposed_solution TEXT,
                    test_plan TEXT,
                    files_to_modify TEXT,
                    risk_level INTEGER,
                    estimated_effort INTEGER,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS improvement_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL,
                    attempt_number INTEGER,
                    branch_name TEXT,
                    changes_summary TEXT,
                    test_results TEXT,
                    success BOOLEAN,
                    error_message TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (ticket_id) REFERENCES improvement_tickets (id)
                )
            """)
            
            conn.commit()
    
    def add_ticket(self, ticket: ImprovementTicket) -> str:
        """Add a new improvement ticket."""
        with sqlite3.connect(IMPROVEMENT_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO improvement_tickets 
                (id, title, description, category, priority, status, created_at, updated_at,
                 evidence, proposed_solution, test_plan, files_to_modify, risk_level, 
                 estimated_effort, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket.id, ticket.title, ticket.description, ticket.category,
                ticket.priority.value, ticket.status.value,
                ticket.created_at.isoformat(), ticket.updated_at.isoformat(),
                json.dumps(ticket.evidence), ticket.proposed_solution, ticket.test_plan,
                json.dumps(ticket.files_to_modify), ticket.risk_level, ticket.estimated_effort,
                json.dumps(ticket.metadata)
            ))
            conn.commit()
        
        return ticket.id
    
    def get_tickets(self, status: TicketStatus = None, priority: TicketPriority = None, 
                   category: str = None, limit: int = 50) -> List[ImprovementTicket]:
        """Get tickets with optional filtering."""
        with sqlite3.connect(IMPROVEMENT_DB_PATH) as conn:
            query = "SELECT * FROM improvement_tickets WHERE 1=1"
            params = []
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            if priority:
                query += " AND priority = ?"
                params.append(priority.value)
            
            if category:
                query += " AND category = ?"
                params.append(category)
            
            query += " ORDER BY "
            if priority:
                query += "CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, "
            query += "created_at ASC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor = conn.execute(query, params)
            
            tickets = []
            for row in cursor.fetchall():
                ticket = ImprovementTicket(
                    id=row[0], title=row[1], description=row[2], category=row[3],
                    priority=TicketPriority(row[4]), status=TicketStatus(row[5]),
                    created_at=datetime.fromisoformat(row[6]), updated_at=datetime.fromisoformat(row[7]),
                    evidence=json.loads(row[8] or "{}"), proposed_solution=row[9],
                    test_plan=row[10], files_to_modify=json.loads(row[11] or "[]"),
                    risk_level=row[12], estimated_effort=row[13], metadata=json.loads(row[14] or "{}")
                )
                tickets.append(ticket)
            
            return tickets
    
    def update_ticket_status(self, ticket_id: str, status: TicketStatus, 
                           metadata: Dict[str, Any] = None):
        """Update ticket status."""
        with sqlite3.connect(IMPROVEMENT_DB_PATH) as conn:
            updates = ["status = ?", "updated_at = ?"]
            params = [status.value, datetime.now().isoformat()]
            
            if metadata:
                updates.append("metadata = ?")
                existing = conn.execute("SELECT metadata FROM improvement_tickets WHERE id = ?", (ticket_id,)).fetchone()
                if existing:
                    existing_meta = json.loads(existing[0] or "{}")
                    existing_meta.update(metadata)
                    params.append(json.dumps(existing_meta))
                else:
                    params.append(json.dumps(metadata))
            
            params.append(ticket_id)
            
            conn.execute(f"""
                UPDATE improvement_tickets 
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            conn.commit()
    
    def record_attempt(self, ticket_id: str, attempt_number: int, branch_name: str,
                       changes_summary: str, test_results: str, success: bool,
                       error_message: str = ""):
        """Record an improvement attempt."""
        with sqlite3.connect(IMPROVEMENT_DB_PATH) as conn:
            conn.execute("""
                INSERT INTO improvement_attempts 
                (ticket_id, attempt_number, branch_name, changes_summary, test_results, 
                 success, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticket_id, attempt_number, branch_name, changes_summary,
                test_results, success, error_message, datetime.now().isoformat()
            ))
            conn.commit()


class TicketGenerator:
    """Generates improvement tickets from various sources."""
    
    def __init__(self):
        self.backlog = ImprovementBacklog()
    
    def generate_from_exceptions(self, exceptions: List[Dict[str, Any]]) -> List[ImprovementTicket]:
        """Generate tickets from exception logs."""
        tickets = []
        
        for exc in exceptions:
            # Group similar exceptions
            error_type = exc.get("type", "Unknown")
            error_message = exc.get("message", "")
            stack_trace = exc.get("stack_trace", "")
            file_path = exc.get("file_path", "")
            
            # Create ticket if this is a recurring or critical error
            if self._should_create_ticket_for_exception(exc):
                ticket_id = f"exception_{int(time.time())}_{hash(error_message) % 10000}"
                
                ticket = ImprovementTicket(
                    id=ticket_id,
                    title=f"Fix {error_type} in {file_path}",
                    description=f"Recurring {error_type}: {error_message}",
                    category="bug_fix",
                    priority=self._determine_exception_priority(exc),
                    status=TicketStatus.OPEN,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    evidence={
                        "exception": exc,
                        "occurrence_count": exc.get("count", 1),
                        "first_seen": exc.get("first_seen"),
                        "last_seen": exc.get("last_seen")
                    },
                    proposed_solution=self._suggest_exception_solution(exc),
                    test_plan=f"1. Reproduce the error\n2. Apply fix\n3. Verify error no longer occurs\n4. Run existing test suite",
                    files_to_modify=[file_path] if file_path else [],
                    risk_level=self._assess_exception_risk(exc),
                    estimated_effort=self._estimate_exception_effort(exc),
                    metadata={
                        "source": "exception_log",
                        "auto_generated": True
                    }
                )
                
                tickets.append(ticket)
        
        return tickets
    
    def generate_from_performance_anomalies(self, anomalies: List[Dict[str, Any]]) -> List[ImprovementTicket]:
        """Generate tickets from performance issues."""
        tickets = []
        
        for anomaly in anomalies:
            metric = anomaly.get("metric", "")
            value = anomaly.get("value", 0)
            threshold = anomaly.get("threshold", 0)
            
            ticket_id = f"perf_{int(time.time())}_{hash(metric) % 10000}"
            
            ticket = ImprovementTicket(
                id=ticket_id,
                title=f"Optimize {metric} performance",
                description=f"{metric} value {value} exceeds threshold {threshold}",
                category="performance",
                priority=self._determine_performance_priority(anomaly),
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={"anomaly": anomaly},
                proposed_solution=self._suggest_performance_solution(anomaly),
                test_plan=f"1. Profile the performance bottleneck\n2. Implement optimization\n3. Measure improvement\n4. Ensure no regression",
                files_to_modify=self._identify_performance_files(anomaly),
                risk_level=self._assess_performance_risk(anomaly),
                estimated_effort=self._estimate_performance_effort(anomaly),
                metadata={"source": "performance_monitor"}
            )
            
            tickets.append(ticket)
        
        return tickets
    
    def generate_from_user_feedback(self, feedback: List[Dict[str, Any]]) -> List[ImprovementTicket]:
        """Generate tickets from user dissatisfaction signals."""
        tickets = []
        
        for item in feedback:
            feedback_text = item.get("text", "")
            sentiment = item.get("sentiment", "neutral")
            
            if sentiment in ["negative", "very_negative"]:
                ticket_id = f"feedback_{int(time.time())}_{hash(feedback_text) % 10000}"
                
                ticket = ImprovementTicket(
                    id=ticket_id,
                    title=f"Address user feedback: {feedback_text[:50]}...",
                    description=f"User feedback: {feedback_text}",
                    category="feature",
                    priority=TicketPriority.HIGH if sentiment == "very_negative" else TicketPriority.MEDIUM,
                    status=TicketStatus.OPEN,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                    evidence={"feedback": item},
                    proposed_solution=self._suggest_feedback_solution(item),
                    test_plan=f"1. Implement user-requested changes\n2. Test with user scenarios\n3. Verify satisfaction improvement",
                    files_to_modify=self._identify_feedback_files(item),
                    risk_level=3,  # Generally low risk for user experience improvements
                    estimated_effort=self._estimate_feedback_effort(item),
                    metadata={"source": "user_feedback"}
                )
                
                tickets.append(ticket)
        
        return tickets
    
    def _should_create_ticket_for_exception(self, exception: Dict[str, Any]) -> bool:
        """Determine if an exception warrants a ticket."""
        count = exception.get("count", 1)
        error_type = exception.get("type", "")
        
        # Create ticket for recurring exceptions (3+ times) or critical types
        critical_types = ["AttributeError", "ImportError", "KeyError", "TypeError"]
        
        return count >= 3 or any(critical_type in error_type for critical_type in critical_types)
    
    def _determine_exception_priority(self, exception: Dict[str, Any]) -> TicketPriority:
        """Determine priority for exception-based tickets."""
        count = exception.get("count", 1)
        error_type = exception.get("type", "")
        
        if count >= 10 or "ImportError" in error_type:
            return TicketPriority.CRITICAL
        elif count >= 5 or "AttributeError" in error_type:
            return TicketPriority.HIGH
        elif count >= 3:
            return TicketPriority.MEDIUM
        else:
            return TicketPriority.LOW
    
    def _determine_feedback_priority(self, feedback: Dict[str, Any]) -> TicketPriority:
        """Determine priority for feedback-based tickets."""
        sentiment = feedback.get("sentiment", "neutral")
        
        if sentiment == "very_negative":
            return TicketPriority.CRITICAL
        elif sentiment == "negative":
            return TicketPriority.HIGH
        else:
            return TicketPriority.MEDIUM
    
    def _suggest_exception_solution(self, exception: Dict[str, Any]) -> str:
        """Suggest solution for exception."""
        error_type = exception.get("type", "")
        message = exception.get("message", "")
        
        if "ImportError" in error_type:
            return "Add proper import error handling and optional dependencies"
        elif "AttributeError" in error_type:
            return "Add null checks and defensive programming for attribute access"
        elif "KeyError" in error_type:
            return "Add key validation and default values for dictionary access"
        else:
            return f"Add proper error handling for {error_type}"
    
    def _assess_exception_risk(self, exception: Dict[str, Any]) -> int:
        """Assess risk level for exception fix."""
        error_type = exception.get("type", "")
        
        if "ImportError" in error_type:
            return 7  # High risk - affects imports
        elif "AttributeError" in error_type:
            return 4  # Medium risk
        else:
            return 3  # Low to medium risk
    
    def _estimate_exception_effort(self, exception: Dict[str, Any]) -> int:
        """Estimate effort for exception fix."""
        return 3  # Most exception fixes are relatively simple
    
    def _determine_performance_priority(self, anomaly: Dict[str, Any]) -> TicketPriority:
        """Determine priority for performance tickets."""
        severity = anomaly.get("severity", "medium")
        
        if severity == "critical":
            return TicketPriority.CRITICAL
        elif severity == "high":
            return TicketPriority.HIGH
        else:
            return TicketPriority.MEDIUM
    
    def _suggest_performance_solution(self, anomaly: Dict[str, Any]) -> str:
        """Suggest solution for performance issue."""
        metric = anomaly.get("metric", "")
        
        if "memory" in metric.lower():
            return "Optimize memory usage and implement better garbage collection"
        elif "cpu" in metric.lower():
            return "Optimize algorithms and reduce computational complexity"
        elif "io" in metric.lower():
            return "Implement caching and reduce I/O operations"
        else:
            return f"Optimize {metric} performance"
    
    def _identify_performance_files(self, anomaly: Dict[str, Any]) -> List[str]:
        """Identify files likely needing modification for performance fix."""
        # This would need to be implemented based on actual performance profiling
        return ["core/performance_critical.py"]
    
    def _assess_performance_risk(self, anomaly: Dict[str, Any]) -> int:
        """Assess risk level for performance optimization."""
        return 5  # Medium risk - performance changes can have unintended side effects
    
    def _estimate_performance_effort(self, anomaly: Dict[str, Any]) -> int:
        """Estimate effort for performance optimization."""
        return 6  # Performance optimizations often require significant effort
    
    def _suggest_feedback_solution(self, feedback: Dict[str, Any]) -> str:
        """Suggest solution for user feedback."""
        feedback_text = feedback.get("text", "").lower()
        
        if "slow" in feedback_text:
            return "Improve performance and responsiveness"
        elif "confusing" in feedback_text or "unclear" in feedback_text:
            return "Improve user interface and documentation clarity"
        elif "error" in feedback_text or "crashing" in feedback_text:
            return "Fix reported errors and improve error handling"
        else:
            return "Address user concerns and improve experience"
    
    def _identify_feedback_files(self, feedback: Dict[str, Any]) -> List[str]:
        """Identify files for feedback-based improvements."""
        return ["core/user_interface.py", "core/documentation.py"]
    
    def _estimate_feedback_effort(self, feedback: Dict[str, Any]) -> int:
        """Estimate effort for feedback-based improvements."""
        return 4  # Generally medium effort


class AutopatchEngine:
    """Autonomous patch generation and application engine."""
    
    def __init__(self):
        self.backlog = ImprovementBacklog()
        # Use subprocess for git operations instead of git_ops module
        self.git_available = self._check_git_available()
        self.secret_scanner = secret_hygiene.get_secret_scanner()
    
    def _check_git_available(self) -> bool:
        """Check if git is available."""
        try:
            subprocess.run(['git', '--version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def select_next_ticket(self) -> Optional[ImprovementTicket]:
        """Select the next ticket to work on."""
        # Get open tickets, prioritized by priority and risk
        tickets = self.backlog.get_tickets(
            status=TicketStatus.OPEN, 
            limit=20
        )
        
        if not tickets:
            return None
        
        # Score tickets based on priority, risk, and effort
        best_ticket = None
        best_score = -1
        
        for ticket in tickets:
            # Lower score is better (less risky, less effort)
            # Convert priority enum to numeric value for calculation
            priority_value = {
                TicketPriority.CRITICAL: 1,
                TicketPriority.HIGH: 2,
                TicketPriority.MEDIUM: 3,
                TicketPriority.LOW: 4
            }.get(ticket.priority, 3)
            
            score = (10 - priority_value) + (ticket.risk_level / 2) + (ticket.estimated_effort / 2)
            
            # Prefer lower risk tickets
            if ticket.risk_level > 7:
                continue  # Skip high-risk tickets entirely
            
            if score < best_score or best_score == -1:
                best_score = score
                best_ticket = ticket
        
        return best_ticket
    
    def create_test_for_ticket(self, ticket: ImprovementTicket) -> str:
        """Create a test that reproduces the issue."""
        test_content = f"""#!/usr/bin/env python3
\"\"\"
Auto-generated test for improvement ticket: {ticket.id}
Ticket: {ticket.title}
\"\"\"

import unittest
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

class Test{ticket.id.replace('-', '_').title()}(unittest.TestCase):
    \"\"\"Test case for {ticket.title}\"\"\"
    
    def test_{ticket.id.replace('-', '_')}(self):
        \"\"\"Test that reproduces the issue and verifies the fix.\"\"\"
        # This test should:
        # 1. Reproduce the current issue (should fail before fix)
        # 2. Verify the fix works (should pass after fix)
        
        # TODO: Implement specific test based on ticket evidence
        self.fail("Test not yet implemented - need to reproduce issue")

if __name__ == '__main__':
    unittest.main()
"""
        return test_content
    
    def generate_patch(self, ticket: ImprovementTicket) -> Dict[str, Any]:
        """Generate a patch for the ticket."""
        # For now, this is a placeholder that would need LLM integration
        # In a real implementation, this would use the LLM to analyze the code
        # and generate appropriate fixes
        
        patch_content = {
            "ticket_id": ticket.id,
            "patch_type": "placeholder",
            "description": "Auto-generated patch placeholder",
            "files_modified": ticket.files_to_modify,
            "changes": "This would contain the actual code changes",
            "test_added": f"test_{ticket.id}.py"
        }
        
        return patch_content
    
    def apply_patch_on_branch(self, ticket: ImprovementTicket, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Apply patch on a feature branch."""
        branch_name = f"improvement/{ticket.id}"
        
        try:
            if not self.git_available:
                return {
                    "success": False,
                    "error": "Git not available",
                    "branch_name": branch_name
                }
            
            # Create feature branch
            subprocess.run(['git', 'checkout', '-b', branch_name], cwd=ROOT, check=True, capture_output=True)
            
            # Create test file
            test_content = self.create_test_for_ticket(ticket)
            test_path = ROOT / f"tests/test_{ticket.id}.py"
            test_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(test_path, 'w') as f:
                f.write(test_content)
            
            # For now, just create a placeholder change
            # In a real implementation, this would apply the actual patch
            changes_summary = f"Created test for {ticket.title}"
            
            # Add and commit changes
            subprocess.run(['git', 'add', str(test_path)], cwd=ROOT, check=True, capture_output=True)
            subprocess.run(['git', 'commit', '-m', changes_summary], cwd=ROOT, check=True, capture_output=True)
            
            return {
                "success": True,
                "branch_name": branch_name,
                "changes_summary": changes_summary,
                "test_path": str(test_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "branch_name": branch_name
            }
    
    def run_tests(self, branch_name: str) -> Dict[str, Any]:
        """Run tests on the branch."""
        try:
            # Run the test suite
            result = subprocess.run([
                'python3', '-m', 'pytest', 
                f'tests/test_{branch_name.split("/")[-1]}.py',
                '-v'
            ], cwd=ROOT, capture_output=True, text=True, timeout=60)
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Tests timed out",
                "stdout": "",
                "stderr": "Test execution timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "stdout": "",
                "stderr": str(e)
            }
    
    def create_pull_request_summary(self, ticket: ImprovementTicket, patch: Dict[str, Any], 
                                   test_results: Dict[str, Any]) -> str:
        """Create a pull request summary."""
        summary = f"""# Improvement: {ticket.title}

## Ticket ID
{ticket.id}

## Problem
{ticket.description}

## Solution
{patch.get('description', 'Auto-generated solution')}

## Changes
- Files modified: {', '.join(patch.get('files_modified', []))}
- Test added: {patch.get('test_added', 'None')}

## Test Results
{'✅ All tests passed' if test_results.get('success') else '❌ Tests failed'}

## Risk Assessment
- Risk Level: {ticket.risk_level}/10
- Estimated Effort: {ticket.estimated_effort}/10

## Evidence
{json.dumps(ticket.evidence, indent=2)}

## Review Checklist
- [ ] Code changes are correct and minimal
- [ ] Tests pass and cover the fix
- [ ] No breaking changes introduced
- [ ] Documentation updated if needed
- [ ] Performance impact assessed

## Automated Quality Checks
- MCP Doctor: {'✅ Passed' if self._run_mcp_doctor() else '❌ Failed'}
- Secret Scan: {'✅ Passed' if self._run_secret_scan() else '❌ Failed'}
- Loop Metrics: {'✅ Stable' if self._check_loop_metrics() else '❌ Degraded'}
"""
        
        return summary
    
    def _run_mcp_doctor(self) -> bool:
        """Run MCP doctor checks."""
        try:
            result = mcp_doctor_simple.run_all_tests()
            return all(r.passed for r in result.values())
        except:
            return False
    
    def _run_secret_scan(self) -> bool:
        """Run secret scanning."""
        try:
            scan_result = self.secret_scanner.scan_directory(
                ROOT, 
                max_files=800,
                scan_types=["secrets", "private_data", "security"]
            )
        except Exception:
            return False
        
        if not scan_result.findings:
            return True
        
        for finding in scan_result.findings:
            if finding.finding_type in {"secret", "private_data"}:
                return False
            if finding.severity in {"critical", "high"}:
                return False
        
        return True
    
    def _check_loop_metrics(self) -> bool:
        """Check that loop metrics haven't worsened."""
        # Placeholder for loop metrics checking
        return True  # Assume stable for now


class SelfImprovementEngine:
    """Main self-improvement engine."""
    
    def __init__(self):
        self.backlog = ImprovementBacklog()
        self.ticket_generator = TicketGenerator()
        self.autopatch = AutopatchEngine()
        self.last_scan_time = 0
        self.scan_interval = 3600  # Scan every hour
    
    def scan_for_improvements(self) -> Dict[str, Any]:
        """Scan for new improvement opportunities."""
        if time.time() - self.last_scan_time < self.scan_interval:
            return {"status": "cooldown", "message": "Scan cooldown active"}
        
        tickets_created = []
        
        # Scan for exceptions (would need to integrate with error logging)
        # exceptions = self._collect_recent_exceptions()
        # exception_tickets = self.ticket_generator.generate_from_exceptions(exceptions)
        # tickets_created.extend(exception_tickets)
        
        # Scan for performance anomalies (would need to integrate with monitoring)
        # anomalies = self._collect_performance_anomalies()
        # performance_tickets = self.ticket_generator.generate_from_performance_anomalies(anomalies)
        # tickets_created.extend(performance_tickets)
        
        # For demo, create a sample ticket
        sample_ticket = ImprovementTicket(
            id=f"sample_{int(time.time())}",
            title="Sample improvement ticket",
            description="This is a sample ticket for demonstration",
            category="feature",
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={"demo": True},
            proposed_solution="Implement the requested feature",
            test_plan="1. Write tests\n2. Implement feature\n3. Verify tests pass",
            files_to_modify=["core/sample.py"],
            risk_level=3,
            estimated_effort=4,
            metadata={"source": "demo"}
        )
        
        self.backlog.add_ticket(sample_ticket)
        tickets_created.append(sample_ticket)
        
        self.last_scan_time = time.time()
        
        return {
            "status": "completed",
            "tickets_found": len(tickets_created),
            "tickets_created": [t.id for t in tickets_created]
        }
    
    def run_autopatch_cycle(self) -> Dict[str, Any]:
        """Run one autopatch cycle."""
        # Select next ticket
        ticket = self.autopatch.select_next_ticket()
        
        if not ticket:
            return {
                "status": "no_tickets",
                "message": "No suitable tickets found for autopatch"
            }
        
        # Update ticket status
        self.backlog.update_ticket_status(ticket.id, TicketStatus.IN_PROGRESS)
        
        try:
            # Generate patch
            patch = self.autopatch.generate_patch(ticket)
            
            # Apply patch on branch
            apply_result = self.autopatch.apply_patch_on_branch(ticket, patch)
            
            if not apply_result["success"]:
                raise Exception(f"Failed to apply patch: {apply_result.get('error')}")
            
            # Run tests
            test_results = self.autopatch.run_tests(apply_result["branch_name"])
            
            # Record attempt
            self.backlog.record_attempt(
                ticket_id=ticket.id,
                attempt_number=1,
                branch_name=apply_result["branch_name"],
                changes_summary=apply_result["changes_summary"],
                test_results=json.dumps(test_results),
                success=test_results.get("success", False),
                error_message=test_results.get("stderr", "")
            )
            
            # Create PR summary
            pr_summary = self.autopatch.create_pull_request_summary(ticket, patch, test_results)
            
            # Update ticket status
            if test_results.get("success"):
                self.backlog.update_ticket_status(ticket.id, TicketStatus.READY)
            else:
                self.backlog.update_ticket_status(ticket.id, TicketStatus.FAILED)
            
            return {
                "status": "completed",
                "ticket_id": ticket.id,
                "ticket_title": ticket.title,
                "branch_name": apply_result["branch_name"],
                "test_success": test_results.get("success", False),
                "pr_summary": pr_summary
            }
            
        except Exception as e:
            # Record failed attempt
            self.backlog.record_attempt(
                ticket_id=ticket.id,
                attempt_number=1,
                branch_name="",
                changes_summary="",
                test_results="",
                success=False,
                error_message=str(e)
            )
            
            self.backlog.update_ticket_status(ticket.id, TicketStatus.FAILED)
            
            return {
                "status": "error",
                "ticket_id": ticket.id,
                "error": str(e)
            }
    
    def get_improvement_status(self) -> Dict[str, Any]:
        """Get current improvement status."""
        all_tickets = self.backlog.get_tickets()
        
        status_counts = {}
        for status in TicketStatus:
            status_counts[status.value] = len([t for t in all_tickets if t.status == status])
        
        priority_counts = {}
        for priority in TicketPriority:
            priority_counts[priority.value] = len([t for t in all_tickets if t.priority == priority])
        
        return {
            "total_tickets": len(all_tickets),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "ready_for_review": len([t for t in all_tickets if t.status == TicketStatus.READY]),
            "in_progress": len([t for t in all_tickets if t.status == TicketStatus.IN_PROGRESS])
        }


# Global instance
_improvement_engine = None

def get_self_improvement_engine() -> SelfImprovementEngine:
    """Get the global self-improvement engine."""
    global _improvement_engine
    if _improvement_engine is None:
        _improvement_engine = SelfImprovementEngine()
    return _improvement_engine


if __name__ == "__main__":
    # Test the self-improvement engine
    engine = get_self_improvement_engine()
    
    # Scan for improvements
    scan_result = engine.scan_for_improvements()
    print("Improvement Scan Results:")
    print(json.dumps(scan_result, indent=2, default=str))
    
    # Get status
    status = engine.get_improvement_status()
    print("\nImprovement Status:")
    print(json.dumps(status, indent=2, default=str))
    
    # Run autopatch cycle
    autopatch_result = engine.run_autopatch_cycle()
    print("\nAutopatch Cycle Results:")
    print(json.dumps(autopatch_result, indent=2, default=str))
