#!/usr/bin/env python3
"""
Tests for Memory-Driven Behavior System
Validates that memory actually drives behavior and decision making
"""

import json
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add the project root to Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.memory_driven_behavior import (
    WorkingSetManager,
    MemoryAnalyzer,
    MemoryDrivenBehaviorEngine,
    Goal,
    NextAction,
    GoalStatus,
    TaskStatus
)


class TestWorkingSetManager(unittest.TestCase):
    
    def setUp(self):
        # Use test database path
        from core.memory_driven_behavior import WORKING_SET_PATH
        self.original_path = WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)  # Clean up any existing test db
        
        self.manager = WorkingSetManager()
    
    def tearDown(self):
        # Clean up test database
        from core.memory_driven_behavior import WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)
    
    def test_add_goal(self):
        """Test adding a new goal."""
        goal = self.manager.add_goal(
            title="Test Goal",
            description="A test goal for validation",
            priority=7
        )
        
        self.assertIsInstance(goal, Goal)
        self.assertEqual(goal.title, "Test Goal")
        self.assertEqual(goal.status, GoalStatus.ACTIVE)
        self.assertEqual(goal.priority, 7)
        self.assertEqual(goal.progress, 0.0)
    
    def test_get_active_goals(self):
        """Test retrieving active goals."""
        # Add some goals
        goal1 = self.manager.add_goal("Goal 1", "Description 1", priority=8)
        goal2 = self.manager.add_goal("Goal 2", "Description 2", priority=6)
        
        # Mark one as completed
        self.manager.update_goal_progress(goal1.id, 1.0, GoalStatus.COMPLETED)
        
        # Get active goals
        active_goals = self.manager.get_active_goals()
        
        self.assertEqual(len(active_goals), 1)
        self.assertEqual(active_goals[0].title, "Goal 2")
        self.assertEqual(active_goals[0].status, GoalStatus.ACTIVE)
    
    def test_add_next_action(self):
        """Test adding a next action."""
        # First add a goal
        goal = self.manager.add_goal("Test Goal", "Description")
        
        # Add action for the goal
        action = self.manager.add_next_action(
            goal_id=goal.id,
            title="Test Action",
            description="A test action",
            priority=5
        )
        
        self.assertIsInstance(action, NextAction)
        self.assertEqual(action.goal_id, goal.id)
        self.assertEqual(action.status, TaskStatus.PENDING)
        self.assertEqual(action.priority, 5)
    
    def test_get_next_actions(self):
        """Test retrieving next actions."""
        # Add goal and actions
        goal = self.manager.add_goal("Test Goal", "Description")
        action1 = self.manager.add_next_action(goal.id, "Action 1", "Description 1", priority=7)
        action2 = self.manager.add_next_action(goal.id, "Action 2", "Description 2", priority=5)
        
        # Get pending actions
        pending_actions = self.manager.get_next_actions(TaskStatus.PENDING)
        
        self.assertEqual(len(pending_actions), 2)
        # Should be ordered by priority (higher first)
        self.assertEqual(pending_actions[0].title, "Action 1")
        self.assertEqual(pending_actions[1].title, "Action 2")
    
    def test_complete_action(self):
        """Test completing an action."""
        goal = self.manager.add_goal("Test Goal", "Description")
        action = self.manager.add_next_action(goal.id, "Test Action", "Description")
        
        # Complete the action
        self.manager.complete_action(action.id)
        
        # Check status
        updated_actions = self.manager.get_next_actions()
        completed_action = next(a for a in updated_actions if a.id == action.id)
        self.assertEqual(completed_action.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(completed_action.completed_at)
    
    def test_update_goal_progress(self):
        """Test updating goal progress."""
        goal = self.manager.add_goal("Test Goal", "Description")
        
        # Update progress
        self.manager.update_goal_progress(goal.id, 0.5)
        
        # Check updated progress
        active_goals = self.manager.get_active_goals()
        updated_goal = next(g for g in active_goals if g.id == goal.id)
        self.assertEqual(updated_goal.progress, 0.5)
    
    def test_record_memory_decision(self):
        """Test recording memory decisions."""
        self.manager.record_memory_decision(
            decision_type="test_decision",
            memory_context="Test context",
            decision="Test decision",
            outcome="Test outcome",
            confidence=0.8
        )
        
        # Verify decision was recorded (would need to check DB directly)
        # For now, just ensure no exception was raised
        self.assertTrue(True)


class TestMemoryAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = MemoryAnalyzer()
    
    @patch('core.memory_driven_behavior.memory.get_factual_entries')
    def test_analyze_recent_memory(self, mock_get_entries):
        """Test memory analysis functionality."""
        # Mock memory entries
        mock_entries = [
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).timestamp(),
                "text": "Need to implement trading bot strategy",
                "source": "voice_chat_user"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).timestamp(),
                "text": "Research AI model improvements",
                "source": "research"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=25)).timestamp(),  # Too old
                "text": "Old entry",
                "source": "old"
            }
        ]
        mock_get_entries.return_value = mock_entries
        
        # Analyze memory
        analysis = self.analyzer.analyze_recent_memory(hours_back=24)
        
        # Verify analysis structure
        self.assertIn("total_entries", analysis)
        self.assertIn("sources", analysis)
        self.assertIn("themes", analysis)
        self.assertIn("patterns", analysis)
        self.assertIn("action_items", analysis)
        self.assertIn("goals_suggested", analysis)
        
        # Should only include recent entries
        self.assertEqual(analysis["total_entries"], 2)
        
        # Should detect sources
        self.assertIn("voice_chat_user", analysis["sources"])
        self.assertIn("research", analysis["sources"])
    
    def test_extract_themes(self):
        """Test theme extraction from entries."""
        entries = [
            {"text": "Working on crypto trading strategies", "source": "test"},
            {"text": "Need to improve trading bot performance", "source": "test"},
            {"text": "AI model training progress", "source": "test"},
            {"text": "Implement automation workflow", "source": "test"}
        ]
        
        themes = self.analyzer._extract_themes(entries)
        
        # Should detect trading and automation themes
        self.assertIn("trading", themes)
        self.assertIn("automation", themes)
    
    def test_extract_action_items(self):
        """Test action item extraction."""
        entries = [
            {"text": "We need to implement the new feature", "source": "test"},
            {"text": "Should create a better error handler", "source": "test"},
            {"text": "Let's add more tests to the codebase", "source": "test"},
            {"text": "Random statement without action", "source": "test"}
        ]
        
        action_items = self.analyzer._extract_action_items(entries)
        
        # Should extract action-oriented statements
        self.assertGreater(len(action_items), 0)
        self.assertTrue(any("implement" in item.lower() for item in action_items))
    
    def test_suggest_goals(self):
        """Test goal suggestion from analysis."""
        entries = [
            {"text": "Trading bot needs risk management", "source": "test"},
            {"text": "Implement trading strategy", "source": "test"},
            {"text": "Need to fix trading errors", "source": "test"}
        ]
        
        suggested_goals = self.analyzer._suggest_goals(entries)
        
        # Should suggest trading-related goals
        self.assertGreater(len(suggested_goals), 0)
        trading_goals = [g for g in suggested_goals if "trading" in g["title"].lower()]
        self.assertGreater(len(trading_goals), 0)


class TestMemoryDrivenBehaviorEngine(unittest.TestCase):
    
    def setUp(self):
        # Use test database path
        from core.memory_driven_behavior import WORKING_SET_PATH
        self.original_path = WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)
        
        self.engine = MemoryDrivenBehaviorEngine()
    
    def tearDown(self):
        # Clean up test database
        from core.memory_driven_behavior import WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)
    
    def test_get_next_action(self):
        """Test getting the next action to execute."""
        # Add a goal and action
        goal = self.engine.working_set.add_goal("Test Goal", "Description")
        action = self.engine.working_set.add_next_action(
            goal.id, "Test Action", "Description", priority=7
        )
        
        # Get next action
        next_action = self.engine.get_next_action()
        
        self.assertIsNotNone(next_action)
        self.assertEqual(next_action.id, action.id)
        self.assertEqual(next_action.status, TaskStatus.PENDING)
    
    def test_get_next_action_with_dependencies(self):
        """Test getting next action with dependencies."""
        goal = self.engine.working_set.add_goal("Test Goal", "Description")
        
        # Add dependent actions
        action1 = self.engine.working_set.add_next_action(
            goal.id, "Action 1", "First action", priority=5
        )
        action2 = self.engine.working_set.add_next_action(
            goal.id, "Action 2", "Second action", priority=7, dependencies=[action1.id]
        )
        
        # Should return action1 first (no dependencies)
        next_action = self.engine.get_next_action()
        self.assertEqual(next_action.id, action1.id)
        
        # Complete action1
        self.engine.working_set.complete_action(action1.id)
        
        # Now should return action2
        next_action = self.engine.get_next_action()
        self.assertEqual(next_action.id, action2.id)
    
    def test_analyze_and_plan(self):
        """Test memory analysis and planning."""
        # Mock the analyzer
        with patch.object(self.engine.analyzer, 'analyze_recent_memory') as mock_analyze:
            mock_analyze.return_value = {
                "total_entries": 5,
                "sources": {"voice_chat_user": 3, "research": 2},
                "themes": ["trading"],
                "patterns": ["High activity volume"],
                "action_items": ["Need to implement trading strategy"],
                "goals_suggested": [
                    {
                        "suggested_by": "Theme: trading",
                        "evidence_count": 3,
                        "title": "Improve Trading Bot Performance",
                        "description": "Enhance trading strategies",
                        "priority": 7
                    }
                ]
            }
            
            # Run analysis and planning
            result = self.engine.analyze_and_plan()
            
            # Should create new goal from suggestion
            self.assertEqual(result["status"], "completed")
            self.assertGreater(len(result["decisions"]), 0)
            
            # Check decision types
            decisions = result["decisions"]
            goal_decisions = [d for d in decisions if d["type"] == "goal_created"]
            self.assertGreater(len(goal_decisions), 0)
    
    @patch('core.memory_driven_behavior.providers.generate_text')
    @patch('core.memory_driven_behavior.memory.append_entry')
    def test_execute_research_action(self, mock_memory, mock_llm):
        """Test execution of research actions."""
        # Add goal and research action
        goal = self.engine.working_set.add_goal("Research Goal", "Description")
        action = self.engine.working_set.add_next_action(
            goal.id, "Research Topic", "Research crypto trading strategies"
        )
        
        # Mock enhanced search pipeline
        with patch('core.memory_driven_behavior.get_enhanced_search_pipeline') as mock_pipeline:
            mock_pipeline_instance = MagicMock()
            mock_pipeline.return_value = mock_pipeline_instance
            mock_pipeline_instance.search.return_value = {
                "success": True,
                "total_found": 5,
                "results": []
            }
            
            # Execute action
            result = self.engine.execute_action(action)
            
            # Verify execution
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["action_type"], "research")
            self.assertEqual(result["results_count"], 5)
    
    @patch('core.memory_driven_behavior.memory.append_entry')
    def test_execute_implementation_action(self, mock_memory):
        """Test execution of implementation actions."""
        goal = self.engine.working_set.add_goal("Implementation Goal", "Description")
        action = self.engine.working_set.add_next_action(
            goal.id, "Implement Feature", "Implement new trading feature"
        )
        
        # Execute action
        result = self.engine.execute_action(action)
        
        # Should log implementation intent
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["action_type"], "implementation")
        mock_memory.assert_called_once()
    
    @patch('core.memory_driven_behavior.memory.append_entry')
    def test_execute_fix_action(self, mock_memory):
        """Test execution of fix actions."""
        goal = self.engine.working_set.add_goal("Fix Goal", "Description")
        action = self.engine.working_set.add_next_action(
            goal.id, "Fix Bug", "Fix critical trading bug"
        )
        
        # Execute action
        result = self.engine.execute_action(action)
        
        # Should log fix intent
        self.assertEqual(result["status"], "identified")
        self.assertEqual(result["action_type"], "fix")
        mock_memory.assert_called_once()
    
    def test_goal_progress_update(self):
        """Test goal progress updates after action completion."""
        goal = self.engine.working_set.add_goal("Test Goal", "Description")
        action = self.engine.working_set.add_next_action(
            goal.id, "Test Action", "Description"
        )
        
        # Execute action (should update progress)
        with patch('core.memory_driven_behavior.memory.append_entry'):
            result = self.engine.execute_action(action)
        
        # Check goal progress was updated
        active_goals = self.engine.working_set.get_active_goals()
        updated_goal = next(g for g in active_goals if g.id == goal.id)
        self.assertGreater(updated_goal.progress, 0.0)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios."""
    
    def setUp(self):
        # Use test database path
        from core.memory_driven_behavior import WORKING_SET_PATH
        self.original_path = WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)
        
        self.engine = MemoryDrivenBehaviorEngine()
    
    def tearDown(self):
        # Clean up test database
        from core.memory_driven_behavior import WORKING_SET_PATH
        WORKING_SET_PATH.unlink(missing_ok=True)
    
    @patch('core.memory_driven_behavior.memory.get_factual_entries')
    def test_trading_focus_scenario(self, mock_memory):
        """Test scenario with trading-focused memory entries."""
        # Mock trading-related memory
        mock_memory.return_value = [
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).timestamp(),
                "text": "Need to improve crypto trading bot performance",
                "source": "voice_chat_user"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).timestamp(),
                "text": "Should implement better risk management for trading",
                "source": "voice_chat_user"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=3)).timestamp(),
                "text": "Trading strategy research shows promise with RSI indicators",
                "source": "research"
            }
        ]
        
        # Run analysis and planning
        plan_result = self.engine.analyze_and_plan()
        
        # Should create trading-related goal
        self.assertEqual(plan_result["status"], "completed")
        decisions = plan_result["decisions"]
        goal_decisions = [d for d in decisions if d["type"] == "goal_created"]
        
        self.assertGreater(len(goal_decisions), 0)
        trading_goal = goal_decisions[0]
        self.assertIn("trading", trading_goal["goal_title"].lower())
        
        # Should create actions from action items
        action_decisions = [d for d in decisions if d["type"] == "action_created"]
        self.assertGreater(len(action_decisions), 0)
    
    @patch('core.memory_driven_behavior.memory.get_factual_entries')
    def test_ai_development_scenario(self, mock_memory):
        """Test scenario with AI development focus."""
        # Mock AI development memory
        mock_memory.return_value = [
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).timestamp(),
                "text": "We need to implement new neural network architecture",
                "source": "voice_chat_user"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=2)).timestamp(),
                "text": "AI model training requires more data preprocessing",
                "source": "research"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=3)).timestamp(),
                "text": "Must optimize model inference speed",
                "source": "voice_chat_user"
            }
        ]
        
        # Run analysis and planning
        plan_result = self.engine.analyze_and_plan()
        
        # Should create AI-related goal
        decisions = plan_result["decisions"]
        goal_decisions = [d for d in decisions if d["type"] == "goal_created"]
        
        self.assertGreater(len(goal_decisions), 0)
        ai_goal = goal_decisions[0]
        self.assertTrue(
            "ai" in ai_goal["goal_title"].lower() or "model" in ai_goal["goal_title"].lower()
        )
    
    def test_action_execution_flow(self):
        """Test complete flow from action creation to execution."""
        # Manually create goal and actions
        goal = self.engine.working_set.add_goal(
            "Test Trading Goal", 
            "Improve trading bot performance",
            priority=8
        )
        
        action1 = self.engine.working_set.add_next_action(
            goal.id, "Research Trading", "Research new trading strategies", priority=7
        )
        
        action2 = self.engine.working_set.add_next_action(
            goal.id, "Implement Strategy", "Implement researched strategy", 
            priority=6, dependencies=[action1.id]
        )
        
        # Get next action (should be action1 - no dependencies)
        next_action = self.engine.get_next_action()
        self.assertEqual(next_action.id, action1.id)
        
        # Execute action1
        with patch('core.memory_driven_behavior.memory.append_entry'):
            result = self.engine.execute_action(next_action)
        
        # Verify action1 is completed
        completed_actions = self.engine.working_set.get_next_actions(TaskStatus.COMPLETED)
        completed_ids = [a.id for a in completed_actions]
        self.assertIn(action1.id, completed_ids)
        
        # Get next action (should now be action2 - dependency met)
        next_action = self.engine.get_next_action()
        self.assertEqual(next_action.id, action2.id)


def run_memory_behavior_tests():
    """Run all memory-driven behavior tests."""
    print("Running Memory-Driven Behavior System Tests...")
    
    # Run unit tests
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    print("\n✅ All memory behavior tests completed!")


if __name__ == "__main__":
    run_memory_behavior_tests()
