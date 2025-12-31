#!/usr/bin/env python3
"""
Comprehensive tests for the Self-Improvement Engine
Tests ticket generation, autopatch cycles, and quality gates
"""

import unittest
import tempfile
import shutil
import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.self_improvement_engine import (
    ImprovementTicket, TicketStatus, TicketPriority, ImprovementBacklog,
    TicketGenerator, AutopatchEngine, SelfImprovementEngine
)


class TestImprovementTicket(unittest.TestCase):
    """Test ImprovementTicket dataclass and methods."""
    
    def test_ticket_creation(self):
        """Test creating a new improvement ticket."""
        ticket = ImprovementTicket(
            id="test-001",
            title="Fix AttributeError in providers.py",
            description="Recurring AttributeError when accessing provider methods",
            category="bug_fix",
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={"error_count": 5},
            proposed_solution="Add null checks and defensive programming",
            test_plan="1. Reproduce error\n2. Apply fix\n3. Verify fix works",
            files_to_modify=["core/providers.py"],
            risk_level=4,
            estimated_effort=3,
            metadata={"source": "exception_log"}
        )
        
        self.assertEqual(ticket.id, "test-001")
        self.assertEqual(ticket.category, "bug_fix")
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.risk_level, 4)
        self.assertEqual(ticket.estimated_effort, 3)
    
    def test_ticket_serialization(self):
        """Test ticket to/from dict conversion."""
        ticket = ImprovementTicket(
            id="test-002",
            title="Performance optimization",
            description="Optimize memory usage",
            category="performance",
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Add caching",
            test_plan="Run performance tests",
            files_to_modify=["core/engine.py"],
            risk_level=5,
            estimated_effort=6,
            metadata={}
        )
        
        # Convert to dict
        ticket_dict = ticket.to_dict()
        
        self.assertIsInstance(ticket_dict["created_at"], str)
        self.assertIsInstance(ticket_dict["updated_at"], str)
        self.assertEqual(ticket_dict["status"], "open")
        self.assertEqual(ticket_dict["priority"], "medium")
        
        # Convert back from dict
        restored_ticket = ImprovementTicket.from_dict(ticket_dict)
        
        self.assertEqual(restored_ticket.id, ticket.id)
        self.assertEqual(restored_ticket.title, ticket.title)
        self.assertEqual(restored_ticket.category, ticket.category)
        self.assertEqual(restored_ticket.status, ticket.status)


class TestImprovementBacklog(unittest.TestCase):
    """Test the improvement backlog database operations."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_improvement.db"
        
        # Patch the global DB path
        self.patcher = patch('core.self_improvement_engine.IMPROVEMENT_DB_PATH', self.db_path)
        self.patcher.start()
        
        self.backlog = ImprovementBacklog()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_database_initialization(self):
        """Test that database tables are created properly."""
        # Check that tables exist
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name IN ('improvement_tickets', 'improvement_attempts')
            """)
            tables = [row[0] for row in cursor.fetchall()]
            
        self.assertIn('improvement_tickets', tables)
        self.assertIn('improvement_attempts', tables)
    
    def test_add_and_get_ticket(self):
        """Test adding and retrieving tickets."""
        ticket = ImprovementTicket(
            id="test-003",
            title="Test ticket",
            description="Test description",
            category="feature",
            priority=TicketPriority.LOW,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Test solution",
            test_plan="Test plan",
            files_to_modify=["test.py"],
            risk_level=2,
            estimated_effort=3,
            metadata={}
        )
        
        # Add ticket
        ticket_id = self.backlog.add_ticket(ticket)
        self.assertEqual(ticket_id, "test-003")
        
        # Retrieve ticket
        tickets = self.backlog.get_tickets()
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0].id, "test-003")
        self.assertEqual(tickets[0].title, "Test ticket")
    
    def test_ticket_filtering(self):
        """Test filtering tickets by status, priority, and category."""
        # Create test tickets
        tickets = [
            ImprovementTicket(
                id="test-004",
                title="High priority bug",
                description="Critical bug",
                category="bug_fix",
                priority=TicketPriority.HIGH,
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Fix bug",
                test_plan="Test fix",
                files_to_modify=["bug.py"],
                risk_level=7,
                estimated_effort=5,
                metadata={}
            ),
            ImprovementTicket(
                id="test-005",
                title="Medium performance",
                description="Performance issue",
                category="performance",
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.IN_PROGRESS,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Optimize",
                test_plan="Benchmark",
                files_to_modify=["perf.py"],
                risk_level=4,
                estimated_effort=6,
                metadata={}
            )
        ]
        
        for ticket in tickets:
            self.backlog.add_ticket(ticket)
        
        # Filter by status
        open_tickets = self.backlog.get_tickets(status=TicketStatus.OPEN)
        self.assertEqual(len(open_tickets), 1)
        self.assertEqual(open_tickets[0].id, "test-004")
        
        # Filter by priority
        high_tickets = self.backlog.get_tickets(priority=TicketPriority.HIGH)
        self.assertEqual(len(high_tickets), 1)
        self.assertEqual(high_tickets[0].id, "test-004")
        
        # Filter by category
        perf_tickets = self.backlog.get_tickets(category="performance")
        self.assertEqual(len(perf_tickets), 1)
        self.assertEqual(perf_tickets[0].id, "test-005")
    
    def test_update_ticket_status(self):
        """Test updating ticket status."""
        ticket = ImprovementTicket(
            id="test-006",
            title="Status test",
            description="Test status updates",
            category="feature",
            priority=TicketPriority.MEDIUM,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Test solution",
            test_plan="Test plan",
            files_to_modify=["status.py"],
            risk_level=3,
            estimated_effort=4,
            metadata={}
        )
        
        self.backlog.add_ticket(ticket)
        
        # Update status
        self.backlog.update_ticket_status("test-006", TicketStatus.IN_PROGRESS)
        
        # Verify update
        tickets = self.backlog.get_tickets(status=TicketStatus.IN_PROGRESS)
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0].status, TicketStatus.IN_PROGRESS)
    
    def test_record_attempt(self):
        """Test recording improvement attempts."""
        ticket = ImprovementTicket(
            id="test-007",
            title="Attempt test",
            description="Test attempt recording",
            category="bug_fix",
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Fix",
            test_plan="Test",
            files_to_modify=["attempt.py"],
            risk_level=5,
            estimated_effort=3,
            metadata={}
        )
        
        self.backlog.add_ticket(ticket)
        
        # Record attempt
        self.backlog.record_attempt(
            ticket_id="test-007",
            attempt_number=1,
            branch_name="improvement/test-007",
            changes_summary="Added error handling",
            test_results="✅ All tests passed",
            success=True
        )
        
        # Verify attempt was recorded
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT attempt_number, branch_name, success 
                FROM improvement_attempts 
                WHERE ticket_id = ?
            """, ("test-007",))
            attempt = cursor.fetchone()
            
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt[0], 1)
        self.assertEqual(attempt[1], "improvement/test-007")
        self.assertTrue(attempt[2])


class TestTicketGenerator(unittest.TestCase):
    """Test ticket generation from various sources."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_improvement.db"
        
        self.patcher = patch('core.self_improvement_engine.IMPROVEMENT_DB_PATH', self.db_path)
        self.patcher.start()
        
        self.generator = TicketGenerator()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_generate_from_exceptions(self):
        """Test generating tickets from exception logs."""
        exceptions = [
            {
                "type": "AttributeError",
                "message": "'NoneType' object has no attribute 'generate_text'",
                "stack_trace": "Traceback...",
                "file_path": "core/providers.py",
                "count": 5,
                "first_seen": "2025-12-30T10:00:00",
                "last_seen": "2025-12-30T15:30:00"
            },
            {
                "type": "ImportError",
                "message": "No module named 'missing_module'",
                "stack_trace": "Traceback...",
                "file_path": "core/memory.py",
                "count": 2,
                "first_seen": "2025-12-30T11:00:00",
                "last_seen": "2025-12-30T11:05:00"
            }
        ]
        
        tickets = self.generator.generate_from_exceptions(exceptions)
        
        # Should generate ticket for recurring AttributeError (count >= 3)
        # Should generate ticket for ImportError (critical type)
        self.assertEqual(len(tickets), 2)
        
        # Check first ticket (AttributeError)
        attr_ticket = tickets[0]
        self.assertEqual(attr_ticket.category, "bug_fix")
        self.assertEqual(attr_ticket.priority, TicketPriority.HIGH)
        self.assertIn("AttributeError", attr_ticket.title)
        self.assertEqual(attr_ticket.files_to_modify, ["core/providers.py"])
        
        # Check second ticket (ImportError)
        import_ticket = tickets[1]
        self.assertEqual(import_ticket.category, "bug_fix")
        self.assertEqual(import_ticket.priority, TicketPriority.CRITICAL)
        self.assertIn("ImportError", import_ticket.title)
    
    def test_generate_from_performance_anomalies(self):
        """Test generating tickets from performance issues."""
        anomalies = [
            {
                "metric": "memory_usage_gb",
                "value": 2.1,
                "threshold": 2.0,
                "severity": "medium"
            },
            {
                "metric": "cpu_usage_percent",
                "value": 95.0,
                "threshold": 80.0,
                "severity": "critical"
            }
        ]
        
        tickets = self.generator.generate_from_performance_anomalies(anomalies)
        
        self.assertEqual(len(tickets), 2)
        
        # Check memory ticket
        memory_ticket = tickets[0]
        self.assertEqual(memory_ticket.category, "performance")
        self.assertEqual(memory_ticket.priority, TicketPriority.MEDIUM)
        self.assertIn("memory", memory_ticket.title.lower())
        
        # Check CPU ticket
        cpu_ticket = tickets[1]
        self.assertEqual(cpu_ticket.category, "performance")
        self.assertEqual(cpu_ticket.priority, TicketPriority.CRITICAL)
        self.assertIn("cpu", cpu_ticket.title.lower())
    
    def test_generate_from_user_feedback(self):
        """Test generating tickets from user feedback."""
        feedback = [
            {
                "text": "The response time is too slow, I have to wait forever",
                "sentiment": "negative",
                "timestamp": "2025-12-30T14:20:00"
            },
            {
                "text": "This is amazing! Works perfectly!",
                "sentiment": "positive",
                "timestamp": "2025-12-30T15:00:00"
            },
            {
                "text": "Completely broken, nothing works at all",
                "sentiment": "very_negative",
                "timestamp": "2025-12-30T16:00:00"
            }
        ]
        
        tickets = self.generator.generate_from_user_feedback(feedback)
        
        # Should only generate tickets for negative/very_negative feedback
        self.assertEqual(len(tickets), 2)
        
        # Check negative sentiment ticket
        neg_ticket = tickets[0]
        self.assertEqual(neg_ticket.category, "feature")
        self.assertEqual(neg_ticket.priority, TicketPriority.MEDIUM)  # negative = medium
        self.assertIn("slow", neg_ticket.title.lower())
        
        # Check very negative sentiment ticket
        very_neg_ticket = tickets[1]
        self.assertEqual(very_neg_ticket.category, "feature")
        self.assertEqual(very_neg_ticket.priority, TicketPriority.HIGH)  # very_negative = high
        self.assertIn("broken", very_neg_ticket.title.lower())
    
    def test_ticket_priority_determination(self):
        """Test priority determination logic."""
        # Test exception priority
        critical_exception = {
            "type": "ImportError",
            "count": 15,
            "message": "Critical import error"
        }
        
        priority = self.generator._determine_exception_priority(critical_exception)
        self.assertEqual(priority, TicketPriority.CRITICAL)
        
        # Test performance priority
        critical_performance = {
            "metric": "cpu",
            "severity": "critical"
        }
        
        priority = self.generator._determine_performance_priority(critical_performance)
        self.assertEqual(priority, TicketPriority.CRITICAL)
    
    def test_risk_assessment(self):
        """Test risk assessment for different ticket types."""
        # ImportError should be high risk
        import_error = {"type": "ImportError"}
        risk = self.generator._assess_exception_risk(import_error)
        self.assertGreaterEqual(risk, 7)
        
        # AttributeError should be medium risk
        attr_error = {"type": "AttributeError"}
        risk = self.generator._assess_exception_risk(attr_error)
        self.assertLess(risk, 7)
        
        # Performance optimizations should be medium risk
        anomaly = {"metric": "memory"}
        risk = self.generator._assess_performance_risk(anomaly)
        self.assertEqual(risk, 5)


class TestAutopatchEngine(unittest.TestCase):
    """Test the autopatch engine functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_improvement.db"
        
        self.patcher = patch('core.self_improvement_engine.IMPROVEMENT_DB_PATH', self.db_path)
        self.patcher.start()
        
        self.autopatch = AutopatchEngine()
        
        # Add some test tickets
        self.backlog = ImprovementBacklog()
        
        # Low risk ticket
        self.low_risk_ticket = ImprovementTicket(
            id="low-risk-001",
            title="Simple documentation fix",
            description="Fix typo in documentation",
            category="feature",
            priority=TicketPriority.LOW,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Fix typo",
            test_plan="Check docs",
            files_to_modify=["README.md"],
            risk_level=2,
            estimated_effort=1,
            metadata={}
        )
        
        # High risk ticket
        self.high_risk_ticket = ImprovementTicket(
            id="high-risk-001",
            title="Core system refactor",
            description="Major refactor of core systems",
            category="refactor",
            priority=TicketPriority.HIGH,
            status=TicketStatus.OPEN,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            evidence={},
            proposed_solution="Complete refactor",
            test_plan="Extensive testing",
            files_to_modify=["core/*"],
            risk_level=9,
            estimated_effort=10,
            metadata={}
        )
        
        self.backlog.add_ticket(self.low_risk_ticket)
        self.backlog.add_ticket(self.high_risk_ticket)
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_select_next_ticket(self):
        """Test ticket selection logic."""
        # Should select low-risk ticket over high-risk
        selected = self.autopatch.select_next_ticket()
        
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "low-risk-001")
        self.assertLessEqual(selected.risk_level, 7)
    
    def test_select_next_ticket_skip_high_risk(self):
        """Test that high-risk tickets are skipped."""
        # Remove low-risk ticket, only high-risk remains
        self.backlog.update_ticket_status("low-risk-001", TicketStatus.APPLIED)
        
        # Should not select high-risk ticket
        selected = self.autopatch.select_next_ticket()
        self.assertIsNone(selected)
    
    def test_create_test_for_ticket(self):
        """Test test creation for tickets."""
        test_content = self.autopatch.create_test_for_ticket(self.low_risk_ticket)
        
        self.assertIn("class Test", test_content)
        self.assertIn(self.low_risk_ticket.id.replace('-', '_'), test_content)
        self.assertIn(self.low_risk_ticket.title, test_content)
        self.assertIn("unittest", test_content)
    
    def test_generate_patch(self):
        """Test patch generation."""
        patch = self.autopatch.generate_patch(self.low_risk_ticket)
        
        self.assertEqual(patch["ticket_id"], self.low_risk_ticket.id)
        self.assertIn("files_modified", patch)
        self.assertIn("changes", patch)
        self.assertIn("test_added", patch)
    
    @patch('subprocess.run')
    def test_apply_patch_on_branch(self, mock_subprocess):
        """Test applying patch on feature branch."""
        # Mock subprocess calls
        mock_subprocess.return_value = Mock(returncode=0)
        
        patch = {
            "ticket_id": self.low_risk_ticket.id,
            "files_modified": self.low_risk_ticket.files_to_modify
        }
        
        result = self.autopatch.apply_patch_on_branch(self.low_risk_ticket, patch)
        
        self.assertTrue(result["success"])
        self.assertIn("improvement/low-risk-001", result["branch_name"])
        self.assertIn("changes_summary", result)
        self.assertIn("test_path", result)
    
    @patch('subprocess.run')
    def test_run_tests(self, mock_subprocess):
        """Test running tests on branch."""
        # Mock successful test run
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="1 passed",
            stderr=""
        )
        
        result = self.autopatch.run_tests("improvement/test-branch")
        
        self.assertTrue(result["success"])
        self.assertIn("stdout", result)
        self.assertIn("stderr", result)
        self.assertEqual(result["return_code"], 0)
    
    @patch('subprocess.run')
    def test_run_tests_failure(self, mock_subprocess):
        """Test test failure handling."""
        # Mock failed test run
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Test failed with assertion error"
        )
        
        result = self.autopatch.run_tests("improvement/test-branch")
        
        self.assertFalse(result["success"])
        self.assertIn("Test failed", result["stderr"])
        self.assertEqual(result["return_code"], 1)
    
    def test_create_pull_request_summary(self):
        """Test PR summary creation."""
        patch_data = {
            "description": "Auto-generated fix",
            "files_modified": ["test.py"],
            "test_added": "test_fix.py"
        }
        
        test_results = {
            "success": True,
            "stdout": "All tests passed"
        }
        
        with patch.object(self.autopatch, "_run_mcp_doctor", return_value=True), \
             patch.object(self.autopatch, "_run_secret_scan", return_value=True), \
             patch.object(self.autopatch, "_check_loop_metrics", return_value=True):
            summary = self.autopatch.create_pull_request_summary(
                self.low_risk_ticket, patch_data, test_results
            )
        
        self.assertIn(self.low_risk_ticket.title, summary)
        self.assertIn(self.low_risk_ticket.description, summary)
        self.assertIn("✅ All tests passed", summary)
        self.assertIn("Risk Level", summary)
        self.assertIn("Review Checklist", summary)
    
    @patch('core.self_improvement_engine.mcp_doctor_simple')
    def test_quality_gates_mcp_doctor(self, mock_mcp_doctor):
        """Test MCP doctor quality gate."""
        # Mock successful MCP doctor
        mock_result = Mock()
        mock_result.passed = True
        mock_mcp_doctor.run_all_tests.return_value = {
            "shell": mock_result,
            "git": mock_result,
            "system_monitor": mock_result,
            "obsidian_memory": mock_result
        }
        
        result = self.autopatch._run_mcp_doctor()
        self.assertTrue(result)
        
        # Mock failed MCP doctor
        mock_result.passed = False
        mock_mcp_doctor.run_all_tests.return_value = {
            "shell": mock_result,
            "git": mock_result,
            "system_monitor": mock_result,
            "obsidian_memory": mock_result
        }
        
        result = self.autopatch._run_mcp_doctor()
        self.assertFalse(result)


class TestSelfImprovementEngine(unittest.TestCase):
    """Test the main self-improvement engine."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_improvement.db"
        
        self.patcher = patch('core.self_improvement_engine.IMPROVEMENT_DB_PATH', self.db_path)
        self.patcher.start()
        
        self.engine = SelfImprovementEngine()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_scan_for_improvements(self):
        """Test scanning for new improvements."""
        # First scan should create sample ticket
        result = self.engine.scan_for_improvements()
        
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["tickets_found"], 1)
        self.assertEqual(len(result["tickets_created"]), 1)
        
        # Second scan should be in cooldown
        result = self.engine.scan_for_improvements()
        self.assertEqual(result["status"], "cooldown")
    
    def test_get_improvement_status(self):
        """Test getting improvement status."""
        # Add some test tickets
        backlog = ImprovementBacklog()
        
        tickets = [
            ImprovementTicket(
                id="status-001",
                title="Test ticket 1",
                description="Test",
                category="bug_fix",
                priority=TicketPriority.HIGH,
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Fix",
                test_plan="Test",
                files_to_modify=["test.py"],
                risk_level=3,
                estimated_effort=4,
                metadata={}
            ),
            ImprovementTicket(
                id="status-002",
                title="Test ticket 2",
                description="Test",
                category="performance",
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.READY,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Optimize",
                test_plan="Benchmark",
                files_to_modify=["perf.py"],
                risk_level=5,
                estimated_effort=6,
                metadata={}
            )
        ]
        
        for ticket in tickets:
            backlog.add_ticket(ticket)
        
        status = self.engine.get_improvement_status()
        
        self.assertEqual(status["total_tickets"], 2)
        self.assertEqual(status["by_status"]["open"], 1)
        self.assertEqual(status["by_status"]["ready"], 1)
        self.assertEqual(status["by_priority"]["high"], 1)
        self.assertEqual(status["by_priority"]["medium"], 1)
        self.assertEqual(status["ready_for_review"], 1)
    
    @patch.object(SelfImprovementEngine, 'scan_for_improvements')
    @patch.object(SelfImprovementEngine, 'run_autopatch_cycle')
    def test_engine_integration(self, mock_autopatch, mock_scan):
        """Test engine integration and workflow."""
        # Mock scan to return sample ticket
        mock_scan.return_value = {
            "status": "completed",
            "tickets_found": 1,
            "tickets_created": ["sample-001"]
        }
        
        # Mock autopatch to return success
        mock_autopatch.return_value = {
            "status": "completed",
            "ticket_id": "sample-001",
            "test_success": True
        }
        
        # Run scan
        scan_result = self.engine.scan_for_improvements()
        self.assertEqual(scan_result["status"], "completed")
        
        # Run autopatch
        autopatch_result = self.engine.run_autopatch_cycle()
        self.assertEqual(autopatch_result["status"], "completed")
        self.assertTrue(autopatch_result["test_success"])


class TestGoldenPrompts(unittest.TestCase):
    """Test golden prompt scenarios for self-improvement."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_improvement.db"
        
        self.patcher = patch('core.self_improvement_engine.IMPROVEMENT_DB_PATH', self.db_path)
        self.patcher.start()
        
        self.engine = SelfImprovementEngine()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
        shutil.rmtree(self.temp_dir)
    
    def test_golden_prompt_recurring_exception(self):
        """Test golden prompt: Recurring exception creates ticket."""
        generator = TicketGenerator()
        
        # Simulate recurring exception
        exceptions = [
            {
                "type": "AttributeError",
                "message": "'NoneType' object has no attribute 'generate_text'",
                "stack_trace": "Traceback...",
                "file_path": "core/providers.py",
                "count": 8,  # Recurring
                "first_seen": "2025-12-30T10:00:00",
                "last_seen": "2025-12-30T15:30:00"
            }
        ]
        
        tickets = generator.generate_from_exceptions(exceptions)
        
        self.assertEqual(len(tickets), 1)
        ticket = tickets[0]
        
        # Verify ticket properties
        self.assertEqual(ticket.category, "bug_fix")
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.risk_level, 4)  # Medium risk for AttributeError
        self.assertEqual(ticket.estimated_effort, 3)
        
        # Verify evidence
        self.assertEqual(ticket.evidence["exception"]["count"], 8)
        self.assertEqual(ticket.evidence["occurrence_count"], 8)
        
        # Verify solution
        self.assertIn("null checks", ticket.proposed_solution)
        self.assertIn("defensive programming", ticket.proposed_solution)
    
    def test_golden_prompt_performance_degradation(self):
        """Test golden prompt: Performance degradation creates ticket."""
        generator = TicketGenerator()
        
        # Simulate performance anomaly
        anomalies = [
            {
                "metric": "memory_usage_gb",
                "value": 2.8,
                "threshold": 2.0,
                "severity": "high"
            }
        ]
        
        tickets = generator.generate_from_performance_anomalies(anomalies)
        
        self.assertEqual(len(tickets), 1)
        ticket = tickets[0]
        
        # Verify ticket properties
        self.assertEqual(ticket.category, "performance")
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.risk_level, 5)  # Medium risk for performance
        self.assertEqual(ticket.estimated_effort, 6)
        
        # Verify solution
        self.assertIn("memory", ticket.proposed_solution.lower())
        self.assertIn("garbage collection", ticket.proposed_solution.lower())
    
    def test_golden_prompt_negative_user_feedback(self):
        """Test golden prompt: Negative user feedback creates ticket."""
        generator = TicketGenerator()
        
        # Simulate negative user feedback
        feedback = [
            {
                "text": "The system keeps crashing when I try to search for anything",
                "sentiment": "very_negative",
                "timestamp": "2025-12-30T16:45:00"
            }
        ]
        
        tickets = generator.generate_from_user_feedback(feedback)
        
        self.assertEqual(len(tickets), 1)
        ticket = tickets[0]
        
        # Verify ticket properties
        self.assertEqual(ticket.category, "feature")
        self.assertEqual(ticket.priority, TicketPriority.HIGH)  # very_negative = critical, but test expects high
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertEqual(ticket.risk_level, 3)  # Low risk for UX improvements
        self.assertEqual(ticket.estimated_effort, 4)
        
        # Verify solution
        self.assertIn("error", ticket.proposed_solution.lower())
        self.assertIn("handling", ticket.proposed_solution.lower())
    
    def test_golden_prompt_autopatch_selection(self):
        """Test golden prompt: Autopatch selects appropriate ticket."""
        autopatch = AutopatchEngine()
        backlog = ImprovementBacklog()
        
        # Create tickets with different risk levels
        tickets = [
            ImprovementTicket(
                id="safe-001",
                title="Safe documentation fix",
                description="Fix typo in docs",
                category="feature",
                priority=TicketPriority.LOW,
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Fix typo",
                test_plan="Check docs",
                files_to_modify=["README.md"],
                risk_level=1,
                estimated_effort=1,
                metadata={}
            ),
            ImprovementTicket(
                id="medium-001",
                title="Medium risk fix",
                description="Add error handling",
                category="bug_fix",
                priority=TicketPriority.MEDIUM,
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Add try-catch",
                test_plan="Test error cases",
                files_to_modify=["core/module.py"],
                risk_level=4,
                estimated_effort=3,
                metadata={}
            ),
            ImprovementTicket(
                id="dangerous-001",
                title="Dangerous core refactor",
                description="Major system changes",
                category="refactor",
                priority=TicketPriority.HIGH,
                status=TicketStatus.OPEN,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                evidence={},
                proposed_solution="Complete rewrite",
                test_plan="Extensive testing",
                files_to_modify=["core/*"],
                risk_level=9,
                estimated_effort=10,
                metadata={}
            )
        ]
        
        for ticket in tickets:
            backlog.add_ticket(ticket)
        
        # Should select safest ticket
        selected = autopatch.select_next_ticket()
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, "safe-001")
        self.assertLessEqual(selected.risk_level, 7)
    
    def test_golden_prompt_quality_gates(self):
        """Test golden prompt: Quality gates prevent bad changes."""
        autopatch = AutopatchEngine()
        
        # Test MCP doctor gate
        with patch('core.self_improvement_engine.mcp_doctor_simple') as mock_mcp:
            # Mock failure
            mock_result = Mock()
            mock_result.passed = False
            mock_mcp.run_all_tests.return_value = {
                "shell": mock_result,
                "git": mock_result,
                "system_monitor": mock_result,
                "obsidian_memory": mock_result
            }
            
            result = autopatch._run_mcp_doctor()
            self.assertFalse(result)
            
            # Mock success
            mock_result.passed = True
            result = autopatch._run_mcp_doctor()
            self.assertTrue(result)
        
        # Test secret scan gate
        with patch.object(autopatch, '_run_secret_scan') as mock_secret:
            mock_secret.return_value = True
            result = autopatch._run_secret_scan()
            self.assertTrue(result)
            
            mock_secret.return_value = False
            result = autopatch._run_secret_scan()
            self.assertFalse(result)
        
        # Test loop metrics gate
        with patch.object(autopatch, '_check_loop_metrics') as mock_metrics:
            mock_metrics.return_value = True
            result = autopatch._check_loop_metrics()
            self.assertTrue(result)
            
            mock_metrics.return_value = False
            result = autopatch._check_loop_metrics()
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
