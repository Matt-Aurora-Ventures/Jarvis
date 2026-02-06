"""
Campaign Orchestrator for ClawdBots multi-agent marketing campaigns.

Enables coordinated marketing campaigns across the ClawdBot team:
- Jarvis (CTO): Technical content, documentation, development
- Matt (COO): Operations, coordination, announcements
- Friday (CMO): Marketing, social media, engagement

File-based storage at /root/clawdbots/campaigns.json
"""

import json
import os
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
import threading

logger = logging.getLogger(__name__)

# Default campaigns file location
DEFAULT_CAMPAIGNS_FILE = "/root/clawdbots/campaigns.json"

# Valid task statuses
VALID_STATUSES = {"pending", "in_progress", "completed", "failed"}

# Bot roles
BOT_ROLES = {
    "jarvis": "CTO",
    "matt": "COO",
    "friday": "CMO"
}


class CampaignOrchestrator:
    """
    Orchestrates multi-agent marketing campaigns for ClawdBots.

    Provides:
    - Campaign creation with timeline and goals
    - Task assignment to specific bots
    - Progress tracking and status updates
    - Metrics tracking (reach, engagement, conversions)
    - Campaign reporting
    """

    def __init__(self, campaigns_file: str = DEFAULT_CAMPAIGNS_FILE):
        """
        Initialize the campaign orchestrator.

        Args:
            campaigns_file: Path to JSON file for storing campaigns
        """
        self.campaigns_file = campaigns_file
        self._lock = threading.Lock()
        self._data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        """Load campaigns data from file, handling errors gracefully."""
        if not os.path.exists(self.campaigns_file):
            return {"campaigns": [], "version": "1.0"}

        try:
            with open(self.campaigns_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "campaigns" not in data:
                    data["campaigns"] = []
                return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading campaigns file, starting fresh: {e}")
            return {"campaigns": [], "version": "1.0"}

    def _save_data(self) -> None:
        """Save campaigns data to file, creating directories if needed."""
        with self._lock:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.campaigns_file), exist_ok=True)

            # Write atomically via temp file
            temp_file = f"{self.campaigns_file}.tmp"
            try:
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, indent=2, default=str)

                # Atomic rename
                os.replace(temp_file, self.campaigns_file)
            except Exception as e:
                logger.error(f"Error saving campaigns: {e}")
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                raise

    def _get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Get a campaign by ID."""
        for campaign in self._data["campaigns"]:
            if campaign["id"] == campaign_id:
                return campaign
        return None

    def _get_task(self, campaign: Dict[str, Any], task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID within a campaign."""
        for task in campaign.get("tasks", []):
            if task["id"] == task_id:
                return task
        return None

    # ============================================
    # Campaign Management
    # ============================================

    def create_campaign(
        self,
        name: str,
        description: str,
        start_date: str,
        end_date: str
    ) -> str:
        """
        Create a new marketing campaign.

        Args:
            name: Campaign name
            description: Campaign description/goals
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            Campaign ID
        """
        campaign_id = f"campaign-{uuid.uuid4().hex[:8]}"

        campaign = {
            "id": campaign_id,
            "name": name,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "tasks": [],
            "metrics": {
                "reach": 0,
                "engagement": 0,
                "conversions": 0
            }
        }

        self._data["campaigns"].append(campaign)
        self._save_data()

        logger.info(f"Created campaign '{name}' with ID {campaign_id}")
        return campaign_id

    def list_campaigns(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        List all campaigns.

        Args:
            active_only: If True, only return campaigns within their date range

        Returns:
            List of campaign summaries
        """
        campaigns = self._data["campaigns"]

        if active_only:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            campaigns = [
                c for c in campaigns
                if c["start_date"] <= today <= c["end_date"]
            ]

        return [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "start_date": c["start_date"],
                "end_date": c["end_date"],
                "task_count": len(c.get("tasks", []))
            }
            for c in campaigns
        ]

    # ============================================
    # Task Management
    # ============================================

    def assign_task(
        self,
        campaign_id: str,
        bot: str,
        task_type: str,
        content: str,
        deadline: str
    ) -> str:
        """
        Assign a task to a specific bot.

        Args:
            campaign_id: Campaign to add task to
            bot: Bot name (jarvis, matt, friday)
            task_type: Type of task (content_creation, announcement, social_media, etc.)
            content: Task content/description
            deadline: Task deadline (YYYY-MM-DD)

        Returns:
            Task ID

        Raises:
            ValueError: If campaign not found
        """
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")

        task_id = f"task-{uuid.uuid4().hex[:8]}"

        task = {
            "id": task_id,
            "bot": bot.lower(),
            "bot_role": BOT_ROLES.get(bot.lower(), "Unknown"),
            "task_type": task_type,
            "content": content,
            "deadline": deadline,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        campaign["tasks"].append(task)
        campaign["updated_at"] = datetime.utcnow().isoformat()
        self._save_data()

        logger.info(f"Assigned task {task_id} to {bot} in campaign {campaign_id}")
        return task_id

    def update_task_status(
        self,
        campaign_id: str,
        task_id: str,
        status: str
    ) -> bool:
        """
        Update a task's status.

        Args:
            campaign_id: Campaign containing the task
            task_id: Task to update
            status: New status (pending, in_progress, completed, failed)

        Returns:
            True if updated successfully

        Raises:
            ValueError: If campaign/task not found or invalid status
        """
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {status}. Valid: {VALID_STATUSES}")

        campaign = self._get_campaign(campaign_id)
        if not campaign:
            raise ValueError(f"Campaign not found: {campaign_id}")

        task = self._get_task(campaign, task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        task["status"] = status
        task["updated_at"] = datetime.utcnow().isoformat()
        campaign["updated_at"] = datetime.utcnow().isoformat()
        self._save_data()

        logger.info(f"Updated task {task_id} status to {status}")
        return True

    # ============================================
    # Campaign Status & Progress
    # ============================================

    def get_campaign_status(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed status of a campaign.

        Args:
            campaign_id: Campaign ID

        Returns:
            Campaign status dict or None if not found
        """
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None

        # Calculate progress
        tasks = campaign.get("tasks", [])
        completed_count = sum(1 for t in tasks if t["status"] == "completed")
        total_count = len(tasks)
        progress = (completed_count / total_count * 100) if total_count > 0 else 0.0

        return {
            "id": campaign["id"],
            "name": campaign["name"],
            "description": campaign["description"],
            "start_date": campaign["start_date"],
            "end_date": campaign["end_date"],
            "created_at": campaign.get("created_at"),
            "updated_at": campaign.get("updated_at"),
            "tasks": campaign.get("tasks", []),
            "metrics": campaign.get("metrics", {"reach": 0, "engagement": 0, "conversions": 0}),
            "progress": progress,
            "task_summary": {
                "total": total_count,
                "completed": completed_count,
                "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
                "pending": sum(1 for t in tasks if t["status"] == "pending"),
                "failed": sum(1 for t in tasks if t["status"] == "failed")
            }
        }

    # ============================================
    # Metrics
    # ============================================

    def update_metrics(
        self,
        campaign_id: str,
        reach: int = 0,
        engagement: int = 0,
        conversions: int = 0,
        incremental: bool = False
    ) -> bool:
        """
        Update campaign metrics.

        Args:
            campaign_id: Campaign ID
            reach: Number of people reached
            engagement: Number of engagements (likes, comments, shares)
            conversions: Number of conversions
            incremental: If True, add to existing values; if False, replace

        Returns:
            True if updated successfully
        """
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return False

        metrics = campaign.get("metrics", {"reach": 0, "engagement": 0, "conversions": 0})

        if incremental:
            metrics["reach"] += reach
            metrics["engagement"] += engagement
            metrics["conversions"] += conversions
        else:
            metrics["reach"] = reach
            metrics["engagement"] = engagement
            metrics["conversions"] = conversions

        campaign["metrics"] = metrics
        campaign["updated_at"] = datetime.utcnow().isoformat()
        self._save_data()

        logger.info(f"Updated metrics for campaign {campaign_id}: {metrics}")
        return True

    # ============================================
    # Reporting
    # ============================================

    def generate_campaign_report(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        Generate a comprehensive campaign report.

        Args:
            campaign_id: Campaign ID

        Returns:
            Report dict or None if campaign not found
        """
        campaign = self._get_campaign(campaign_id)
        if not campaign:
            return None

        tasks = campaign.get("tasks", [])
        metrics = campaign.get("metrics", {"reach": 0, "engagement": 0, "conversions": 0})

        # Tasks by bot
        tasks_by_bot = {}
        for task in tasks:
            bot = task["bot"]
            tasks_by_bot[bot] = tasks_by_bot.get(bot, 0) + 1

        # Tasks by status
        tasks_by_status = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "failed": 0
        }
        for task in tasks:
            status = task["status"]
            tasks_by_status[status] = tasks_by_status.get(status, 0) + 1

        # Calculate completion rate
        total_tasks = len(tasks)
        completed_tasks = tasks_by_status["completed"]
        completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign["name"],
            "description": campaign["description"],
            "date_range": {
                "start": campaign["start_date"],
                "end": campaign["end_date"]
            },
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "completion_rate": completion_rate
            },
            "tasks_by_bot": tasks_by_bot,
            "tasks_by_status": tasks_by_status,
            "metrics": metrics,
            "tasks_detail": [
                {
                    "id": t["id"],
                    "bot": t["bot"],
                    "type": t["task_type"],
                    "status": t["status"],
                    "deadline": t["deadline"]
                }
                for t in tasks
            ]
        }

    # ============================================
    # Bot-Specific Helpers
    # ============================================

    def get_tasks_for_bot(self, bot: str, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all tasks assigned to a specific bot.

        Args:
            bot: Bot name (jarvis, matt, friday)
            campaign_id: Optional campaign filter

        Returns:
            List of tasks for the bot
        """
        bot = bot.lower()
        tasks = []

        campaigns = self._data["campaigns"]
        if campaign_id:
            campaign = self._get_campaign(campaign_id)
            campaigns = [campaign] if campaign else []

        for campaign in campaigns:
            for task in campaign.get("tasks", []):
                if task["bot"] == bot:
                    tasks.append({
                        **task,
                        "campaign_id": campaign["id"],
                        "campaign_name": campaign["name"]
                    })

        return tasks

    def get_pending_tasks(self, bot: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all pending tasks, optionally filtered by bot.

        Args:
            bot: Optional bot filter

        Returns:
            List of pending tasks
        """
        tasks = []

        for campaign in self._data["campaigns"]:
            for task in campaign.get("tasks", []):
                if task["status"] == "pending":
                    if bot is None or task["bot"] == bot.lower():
                        tasks.append({
                            **task,
                            "campaign_id": campaign["id"],
                            "campaign_name": campaign["name"]
                        })

        # Sort by deadline
        tasks.sort(key=lambda t: t.get("deadline", "9999-99-99"))
        return tasks
