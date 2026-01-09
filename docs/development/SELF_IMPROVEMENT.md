# SELF_IMPROVEMENT.md - Self-Upgrade Loop Design and Implementation

## Overview

The Self-Improvement Engine enables Jarvis to autonomously identify issues, create solutions, and improve itself over time while maintaining privacy and safety. This addresses the core requirement for a "reliable, testable, self-improving assistant that uses MCP correctly and upgrades itself over time."

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                SELF-IMPROVEMENT ENGINE                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ IMPROVEMENT     │    │   TICKET        │    │   AUTOPATCH     │
│ BACKLOG         │    │ GENERATOR      │    │   ENGINE        │
│                 │    │                 │    │                 │
│ • SQLite DB     │───▶│ • Exception     │───▶│ • Branch mgmt   │
│ • Ticket states │    │ • Performance   │    │ • Test creation │
│ • Priority      │    │ • User feedback  │    │ • Patch apply   │
│ • History       │    │ • Auto-categorize│    │ • PR generation │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌─────────────────────────────────────────────────┐
         │              QUALITY GATES                       │
         └─────────────────────────────────────────────────┘
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP DOCTOR    │    │   SECRET SCAN   │    │  LOOP METRICS   │
│                 │    │                 │    │                 │
│ • Server health │    │ • No secrets    │    │ • No degradation│
│ • Functionality │    │ • Privacy safe  │    │ • Performance   │
│ • Integration   │    │ • Git hygiene   │    │ • Stability     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Core Components

### 1. Improvement Backlog

**Database Schema:**
```sql
-- Tickets table
CREATE TABLE improvement_tickets (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,  -- bug_fix, performance, feature, refactor
    priority TEXT,  -- low, medium, high, critical
    status TEXT,   -- open, in_progress, testing, ready, applied, failed
    evidence TEXT, -- JSON with logs, errors, metrics
    proposed_solution TEXT,
    test_plan TEXT,
    files_to_modify TEXT,
    risk_level INTEGER,  -- 1-10
    estimated_effort INTEGER, -- 1-10
    metadata TEXT
);

-- Attempts table for tracking autopatch cycles
CREATE TABLE improvement_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id TEXT,
    attempt_number INTEGER,
    branch_name TEXT,
    changes_summary TEXT,
    test_results TEXT,
    success BOOLEAN,
    error_message TEXT,
    timestamp TEXT
);
```

**Ticket Lifecycle:**
1. **OPEN** → Initial ticket creation
2. **IN_PROGRESS** → Autopatch cycle started
3. **TESTING** → Patch applied, tests running
4. **READY** → Tests passed, ready for review
5. **APPLIED** → Changes merged
6. **FAILED** → Tests failed or error occurred
7. **REJECTED** → Manual review rejected

### 2. Ticket Generator

**Sources of Improvement Tickets:**

#### Exception-Based Tickets
```python
# Example exception ticket
{
    "id": "exception_1705123456_7890",
    "title": "Fix AttributeError in core/providers.py",
    "description": "Recurring AttributeError: 'NoneType' object has no attribute 'generate_text'",
    "category": "bug_fix",
    "priority": "high",
    "evidence": {
        "exception": {
            "type": "AttributeError",
            "message": "...",
            "count": 5,
            "first_seen": "2025-12-30T10:00:00",
            "last_seen": "2025-12-30T15:30:00"
        }
    },
    "proposed_solution": "Add null checks and defensive programming for provider access",
    "test_plan": "1. Reproduce the error\n2. Apply fix\n3. Verify error no longer occurs",
    "files_to_modify": ["core/providers.py"],
    "risk_level": 4,
    "estimated_effort": 3
}
```

#### Performance-Based Tickets
```python
# Example performance ticket
{
    "id": "perf_1705123456_1234",
    "title": "Optimize memory usage in research_engine.py",
    "description": "Memory usage exceeds threshold: 2.1GB (threshold: 2.0GB)",
    "category": "performance",
    "priority": "medium",
    "evidence": {
        "anomaly": {
            "metric": "memory_usage_gb",
            "value": 2.1,
            "threshold": 2.0,
            "severity": "medium"
        }
    },
    "proposed_solution": "Optimize memory usage and implement better garbage collection",
    "files_to_modify": ["core/research_engine.py"],
    "risk_level": 5,
    "estimated_effort": 6
}
```

#### User Feedback Tickets
```python
# Example feedback ticket
{
    "id": "feedback_1705123456_5678",
    "title": "Address user feedback: Response time is too slow",
    "description": "User feedback: 'The assistant takes too long to respond to simple queries'",
    "category": "feature",
    "priority": "high",
    "evidence": {
        "feedback": {
            "text": "Response time is too slow",
            "sentiment": "negative",
            "timestamp": "2025-12-30T14:20:00"
        }
    },
    "proposed_solution": "Improve performance and responsiveness",
    "files_to_modify": ["core/providers.py", "core/conversation.py"],
    "risk_level": 3,
    "estimated_effort": 4
}
```

### 3. Autopatch Engine

**Autopatch Cycle:**

1. **Ticket Selection**
   ```python
   def select_next_ticket(self) -> ImprovementTicket:
       # Score: (10-priority) + (risk/2) + (effort/2)
       # Prefer low-risk, low-effort, high-priority tickets
       # Skip tickets with risk_level > 7
   ```

2. **Test Creation**
   ```python
   def create_test_for_ticket(self, ticket: ImprovementTicket) -> str:
       # Auto-generate test that reproduces the issue
       # Test should fail before fix, pass after fix
   ```

3. **Branch Management**
   ```python
   def apply_patch_on_branch(self, ticket: ImprovementTicket, patch: Dict):
       # Create feature branch: improvement/{ticket_id}
       # Apply changes
       # Add and commit
   ```

4. **Test Execution**
   ```python
   def run_tests(self, branch_name: str) -> Dict:
       # Run pytest on the specific test
       # Capture results and coverage
   ```

5. **PR Generation**
   ```python
   def create_pull_request_summary(self, ticket, patch, test_results):
       # Generate comprehensive PR description
       # Include risk assessment and quality checks
   ```

## Quality Gates

### 1. MCP Doctor Validation
```python
def _run_mcp_doctor(self) -> bool:
    result = mcp_doctor_simple.run_all_tests()
    return all(r.passed for r in result.values())
```

**Checks:**
- Shell MCP server functionality
- Git MCP server functionality  
- System-monitor MCP server functionality
- Obsidian-memory MCP server functionality

### 2. Secret Scanning
```python
def _run_secret_scan(self) -> bool:
    # Scan for API keys, tokens, passwords
    # Check .gitignore compliance
    # Verify no secrets in changes
```

**Checks:**
- No API keys in code
- No credentials in config files
- Proper .gitignore coverage
- No private data in commits

### 3. Loop Metrics Validation
```python
def _check_loop_metrics(self) -> bool:
    # Check for circular logic
    # Verify no infinite loops
    # Monitor resource usage
    # Ensure no performance degradation
```

**Checks:**
- No new circular logic patterns
- Resource usage within limits
- Response time not degraded
- Error rates not increased

## Privacy and Safety

### Data Privacy Protection
- **No Private Data**: Never include user content, conversations, or personal data
- **Local Only**: All processing happens locally, no external data transmission
- **Sanitized Evidence**: Strip sensitive information from tickets and evidence
- **Configurable Scanning**: User can disable specific scanning sources

### Safety Mechanisms
- **Risk Assessment**: Every ticket has risk level (1-10)
- **Effort Estimation**: Every ticket has effort estimation (1-10)
- **Manual Review**: High-risk tickets require manual approval
- **Rollback Capability**: All changes made on feature branches
- **Test Requirements**: Every improvement must have tests

### Secret Hygiene
```python
SECRET_PATTERNS = [
    r'(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*["\']?[a-zA-Z0-9+/]{20,}["\']?',
    r'(?i)(aws|google|openai|groq|gemini)_?[_-]?(key|secret|token)',
    r'-----BEGIN [A-Z]+ KEY BLOCK-----',
    r'ghp_[a-zA-Z0-9]{36}',  # GitHub personal access token
    r'sk-[a-zA-Z0-9]{48}',     # OpenAI API key
    r'AIza[0-9A-Za-z_-]{35}',   # Google API key
]
```

## Usage Examples

### Manual Improvement Creation
```python
from core.self_improvement_engine import get_self_improvement_engine

engine = get_self_improvement_engine()

# Create manual ticket
ticket = ImprovementTicket(
    id="manual_001",
    title="Add error handling to search pipeline",
    description="Search pipeline fails gracefully on network errors",
    category="bug_fix",
    priority=TicketPriority.HIGH,
    status=TicketStatus.OPEN,
    created_at=datetime.now(),
    updated_at=datetime.now(),
    evidence={"manual": True},
    proposed_solution="Add try-catch blocks and retry logic",
    test_plan="1. Test network error scenarios\n2. Verify graceful failure",
    files_to_modify=["core/enhanced_search_pipeline.py"],
    risk_level=3,
    estimated_effort=4
)

engine.backlog.add_ticket(ticket)
```

### Autonomous Improvement Cycle
```python
# Scan for new improvements
scan_result = engine.scan_for_improvements()
print(f"Found {scan_result['tickets_found']} new tickets")

# Run autopatch cycle
autopatch_result = engine.run_autopatch_cycle()
if autopatch_result["status"] == "completed":
    print(f"Improvement {autopatch_result['ticket_id']} ready for review")
    print(f"Branch: {autopatch_result['branch_name']}")
    print(f"Tests: {'✅ Passed' if autopatch_result['test_success'] else '❌ Failed'}")
```

### Status Monitoring
```python
# Get improvement status
status = engine.get_improvement_status()
print(f"Total tickets: {status['total_tickets']}")
print(f"Ready for review: {status['ready_for_review']}")
print(f"In progress: {status['in_progress']}")

# Get specific tickets
high_priority_tickets = engine.backlog.get_tickets(
    priority=TicketPriority.HIGH,
    status=TicketStatus.OPEN
)
```

## Integration Points

### 1. Error Logging Integration
```python
# In error handling code
try:
    # Some operation
    pass
except Exception as e:
    # Log to improvement engine
    engine.ticket_generator.generate_from_exceptions([{
        "type": type(e).__name__,
        "message": str(e),
        "stack_trace": traceback.format_exc(),
        "file_path": "core/module.py",
        "count": 1,
        "timestamp": datetime.now().isoformat()
    }])
```

### 2. Performance Monitoring Integration
```python
# In performance monitoring
if memory_usage > threshold:
    engine.ticket_generator.generate_from_performance_anomalies([{
        "metric": "memory_usage_gb",
        "value": memory_usage,
        "threshold": threshold,
        "severity": "medium"
    }])
```

### 3. User Feedback Integration
```python
# In conversation handling
if user_sentiment == "negative":
    engine.ticket_generator.generate_from_user_feedback([{
        "text": user_message,
        "sentiment": user_sentiment,
        "timestamp": datetime.now().isoformat()
    }])
```

## Configuration

### Environment Variables
```bash
# Enable/disable self-improvement
SELF_IMPROVEMENT_ENABLED=true

# Scan intervals (seconds)
IMPROVEMENT_SCAN_INTERVAL=3600

# Risk threshold (skip tickets above this risk level)
IMPROVEMENT_MAX_RISK_LEVEL=7

# Auto-apply threshold (auto-apply tickets below this risk level)
IMPROVEMENT_AUTO_APPLY_MAX_RISK=5
```

### Configuration File
```json
{
  "self_improvement": {
    "enabled": true,
    "scan_interval_hours": 1,
    "max_risk_level": 7,
    "auto_apply_max_risk": 5,
    "require_manual_review": true,
    "sources": {
      "exceptions": true,
      "performance": true,
      "user_feedback": true,
      "code_analysis": false
    },
    "quality_gates": {
      "mcp_doctor": true,
      "secret_scan": true,
      "loop_metrics": true,
      "test_coverage": 0.8
    }
  }
}
```

## Monitoring and Metrics

### Key Metrics
- **Ticket Creation Rate**: New tickets per hour/day
- **Resolution Rate**: Tickets completed per hour/day  
- **Success Rate**: Percentage of autopatch attempts that succeed
- **Risk Distribution**: Breakdown of tickets by risk level
- **Category Distribution**: Breakdown by improvement type

### Dashboard Metrics
```python
def get_dashboard_metrics():
    status = engine.get_improvement_status()
    
    return {
        "health_score": calculate_health_score(status),
        "improvement_velocity": calculate_velocity(status),
        "risk_exposure": calculate_risk_exposure(status),
        "quality_trend": calculate_quality_trend(status)
    }
```

## Troubleshooting

### Common Issues

**Autopatch Fails:**
- Check MCP doctor status: `./bin/lifeos doctor --mcp`
- Verify git repository status: `git status`
- Check test environment: `python -m pytest tests/`

**No Tickets Created:**
- Verify error logging is enabled
- Check performance monitoring configuration
- Ensure user feedback collection is active

**High Risk Tickets:**
- Review risk assessment criteria
- Consider manual review for complex changes
- Implement additional safety checks

### Debug Mode
```python
import logging
logging.getLogger('core.self_improvement_engine').setLevel(logging.DEBUG)
```

## Future Enhancements

### Advanced Features
1. **LLM-Powered Patch Generation**: Use LLM to generate actual code fixes
2. **Semantic Code Analysis**: Deep understanding of codebase structure
3. **Predictive Improvements**: Anticipate issues before they occur
4. **Cross-Repository Learning**: Learn from multiple similar codebases
5. **Automated Documentation**: Update docs alongside code changes

### Integration Opportunities
- **CI/CD Pipeline**: Automatic testing and deployment
- **Code Review Automation**: Automated PR reviews
- **Performance Profiling**: Continuous performance optimization
- **Security Scanning**: Automated vulnerability detection

---

**Implementation Date:** 2025-12-30  
**Status:** Production Ready  
**Privacy Level:** High (no user data)  
**Safety Level:** High (risk-gated, manual review)  
**Autonomy Level:** Medium (human-in-the-loop for high-risk changes)
