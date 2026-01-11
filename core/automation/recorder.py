"""
Action Recorder - Record, playback, and analyze action sequences.

Features:
- Record user actions and system events
- Playback recorded sequences
- Action sequence analysis
- Macro creation from recordings
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid
import json
from pathlib import Path

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of recordable actions."""
    COMMAND = "command"
    TRADE = "trade"
    TRANSFER = "transfer"
    SETTING_CHANGE = "setting_change"
    QUERY = "query"
    NAVIGATION = "navigation"
    CUSTOM = "custom"


class RecordingStatus(Enum):
    """Status of a recording session."""
    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    PLAYING = "playing"


@dataclass
class RecordedAction:
    """A single recorded action."""
    action_type: ActionType
    name: str
    params: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration_ms: float = 0
    result: Any = None
    success: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


@dataclass
class ActionRecording:
    """A complete recording session."""
    name: str
    description: str = ""
    actions: List[RecordedAction] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    total_duration_ms: float = 0
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    def add_action(self, action: RecordedAction) -> None:
        """Add an action to the recording."""
        self.actions.append(action)
        self.updated_at = datetime.utcnow()
        self._recalculate_duration()

    def _recalculate_duration(self) -> None:
        """Recalculate total duration from actions."""
        if not self.actions:
            self.total_duration_ms = 0
            return

        start = self.actions[0].timestamp
        end = self.actions[-1].timestamp
        self.total_duration_ms = (end - start).total_seconds() * 1000


@dataclass
class PlaybackResult:
    """Result of playing back a recording."""
    recording_id: str
    recording_name: str
    actions_played: int
    actions_total: int
    success: bool
    errors: List[Dict[str, str]]
    duration_ms: float
    started_at: datetime
    completed_at: datetime


class ActionRecorder:
    """
    Records and plays back action sequences.

    Usage:
        recorder = ActionRecorder()

        # Start recording
        recorder.start_recording("my-macro")

        # Record actions
        recorder.record_action(ActionType.COMMAND, "buy_token", {"token": "SOL", "amount": 10})

        # Stop recording
        recording = recorder.stop_recording()

        # Playback
        result = await recorder.playback(recording.id, action_handlers)
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._recordings: Dict[str, ActionRecording] = {}
        self._current_recording: Optional[ActionRecording] = None
        self._status = RecordingStatus.IDLE
        self._storage_path = storage_path
        self._action_handlers: Dict[ActionType, Callable] = {}
        self._playback_speed = 1.0

    @property
    def status(self) -> RecordingStatus:
        """Get current recording status."""
        return self._status

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._status == RecordingStatus.RECORDING

    def register_handler(self, action_type: ActionType, handler: Callable) -> None:
        """Register a handler for an action type."""
        self._action_handlers[action_type] = handler

    def start_recording(
        self,
        name: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> str:
        """Start a new recording session."""
        if self._status == RecordingStatus.RECORDING:
            raise RuntimeError("Already recording")

        self._current_recording = ActionRecording(
            name=name,
            description=description,
            tags=tags or [],
        )
        self._status = RecordingStatus.RECORDING
        logger.info(f"Started recording: {name}")
        return self._current_recording.id

    def pause_recording(self) -> None:
        """Pause the current recording."""
        if self._status != RecordingStatus.RECORDING:
            return
        self._status = RecordingStatus.PAUSED
        logger.info("Recording paused")

    def resume_recording(self) -> None:
        """Resume a paused recording."""
        if self._status != RecordingStatus.PAUSED:
            return
        self._status = RecordingStatus.RECORDING
        logger.info("Recording resumed")

    def stop_recording(self) -> Optional[ActionRecording]:
        """Stop recording and save."""
        if self._current_recording is None:
            return None

        recording = self._current_recording
        self._recordings[recording.id] = recording
        self._current_recording = None
        self._status = RecordingStatus.IDLE

        logger.info(f"Stopped recording: {recording.name} ({len(recording.actions)} actions)")
        return recording

    def record_action(
        self,
        action_type: ActionType,
        name: str,
        params: Dict[str, Any],
        result: Any = None,
        success: bool = True,
        duration_ms: float = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Record a single action."""
        if self._status != RecordingStatus.RECORDING:
            return None

        action = RecordedAction(
            action_type=action_type,
            name=name,
            params=params,
            result=result,
            success=success,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._current_recording.add_action(action)
        logger.debug(f"Recorded action: {action_type.value}/{name}")
        return action.id

    def get_recording(self, recording_id: str) -> Optional[ActionRecording]:
        """Get a recording by ID."""
        return self._recordings.get(recording_id)

    def get_recordings(
        self,
        tags: Optional[List[str]] = None,
        name_contains: Optional[str] = None,
    ) -> List[ActionRecording]:
        """Get recordings with optional filtering."""
        recordings = list(self._recordings.values())

        if tags:
            recordings = [r for r in recordings if any(t in r.tags for t in tags)]
        if name_contains:
            recordings = [r for r in recordings if name_contains.lower() in r.name.lower()]

        return sorted(recordings, key=lambda r: r.created_at, reverse=True)

    def delete_recording(self, recording_id: str) -> bool:
        """Delete a recording."""
        if recording_id in self._recordings:
            del self._recordings[recording_id]
            logger.info(f"Deleted recording: {recording_id}")
            return True
        return False

    def duplicate_recording(
        self,
        recording_id: str,
        new_name: Optional[str] = None,
    ) -> Optional[ActionRecording]:
        """Create a copy of a recording."""
        original = self._recordings.get(recording_id)
        if not original:
            return None

        new_recording = ActionRecording(
            name=new_name or f"{original.name} (copy)",
            description=original.description,
            actions=list(original.actions),  # Shallow copy
            tags=list(original.tags),
            metadata=dict(original.metadata),
        )

        self._recordings[new_recording.id] = new_recording
        return new_recording

    async def playback(
        self,
        recording_id: str,
        handlers: Optional[Dict[ActionType, Callable]] = None,
        speed: float = 1.0,
        start_from: int = 0,
        stop_on_error: bool = True,
        dry_run: bool = False,
    ) -> PlaybackResult:
        """
        Play back a recorded sequence.

        Args:
            recording_id: ID of recording to play
            handlers: Optional override handlers
            speed: Playback speed multiplier
            start_from: Action index to start from
            stop_on_error: Whether to stop on first error
            dry_run: If True, don't execute actions
        """
        recording = self._recordings.get(recording_id)
        if not recording:
            raise ValueError(f"Recording not found: {recording_id}")

        handlers = handlers or self._action_handlers
        self._status = RecordingStatus.PLAYING
        self._playback_speed = speed

        started_at = datetime.utcnow()
        errors = []
        actions_played = 0

        try:
            actions = recording.actions[start_from:]
            prev_timestamp = actions[0].timestamp if actions else None

            for i, action in enumerate(actions):
                # Simulate timing between actions
                if prev_timestamp and i > 0:
                    delay = (action.timestamp - prev_timestamp).total_seconds()
                    delay = delay / speed  # Adjust for playback speed
                    if delay > 0:
                        await asyncio.sleep(min(delay, 5.0))  # Cap at 5 seconds

                prev_timestamp = action.timestamp

                if dry_run:
                    logger.info(f"[DRY RUN] Would execute: {action.action_type.value}/{action.name}")
                    actions_played += 1
                    continue

                # Find handler
                handler = handlers.get(action.action_type)
                if not handler:
                    error = f"No handler for action type: {action.action_type.value}"
                    errors.append({"action": action.name, "error": error})
                    if stop_on_error:
                        break
                    continue

                # Execute action
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(action.name, action.params)
                    else:
                        handler(action.name, action.params)
                    actions_played += 1

                except Exception as e:
                    errors.append({"action": action.name, "error": str(e)})
                    logger.error(f"Playback error on {action.name}: {e}")
                    if stop_on_error:
                        break

        finally:
            self._status = RecordingStatus.IDLE

        completed_at = datetime.utcnow()

        return PlaybackResult(
            recording_id=recording_id,
            recording_name=recording.name,
            actions_played=actions_played,
            actions_total=len(recording.actions),
            success=len(errors) == 0,
            errors=errors,
            duration_ms=(completed_at - started_at).total_seconds() * 1000,
            started_at=started_at,
            completed_at=completed_at,
        )

    def analyze_recording(self, recording_id: str) -> Dict[str, Any]:
        """Analyze a recording for patterns and statistics."""
        recording = self._recordings.get(recording_id)
        if not recording:
            return {}

        actions = recording.actions
        if not actions:
            return {"action_count": 0}

        # Action type distribution
        type_counts = {}
        for action in actions:
            type_counts[action.action_type.value] = type_counts.get(action.action_type.value, 0) + 1

        # Success rate
        success_count = sum(1 for a in actions if a.success)

        # Duration stats
        durations = [a.duration_ms for a in actions if a.duration_ms > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0

        # Time between actions
        intervals = []
        for i in range(1, len(actions)):
            interval = (actions[i].timestamp - actions[i-1].timestamp).total_seconds()
            intervals.append(interval)
        avg_interval = sum(intervals) / len(intervals) if intervals else 0

        # Find repeated sequences
        repeated_patterns = self._find_patterns(actions)

        return {
            "action_count": len(actions),
            "type_distribution": type_counts,
            "success_rate": success_count / len(actions) if actions else 0,
            "total_duration_ms": recording.total_duration_ms,
            "avg_action_duration_ms": avg_duration,
            "avg_interval_seconds": avg_interval,
            "repeated_patterns": repeated_patterns,
            "unique_actions": len(set(a.name for a in actions)),
        }

    def _find_patterns(
        self,
        actions: List[RecordedAction],
        min_length: int = 2,
        min_occurrences: int = 2,
    ) -> List[Dict[str, Any]]:
        """Find repeated action sequences."""
        patterns = []

        # Create sequence of action signatures
        signatures = [(a.action_type.value, a.name) for a in actions]

        # Look for repeated subsequences
        for length in range(min_length, min(6, len(signatures) // 2 + 1)):
            seen = {}
            for i in range(len(signatures) - length + 1):
                seq = tuple(signatures[i:i + length])
                if seq in seen:
                    seen[seq] += 1
                else:
                    seen[seq] = 1

            for seq, count in seen.items():
                if count >= min_occurrences:
                    patterns.append({
                        "sequence": [{"type": t, "name": n} for t, n in seq],
                        "occurrences": count,
                        "length": length,
                    })

        return patterns

    def create_macro(
        self,
        recording_id: str,
        macro_name: str,
        parameterize: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a reusable macro from a recording.

        Args:
            recording_id: Source recording
            macro_name: Name for the macro
            parameterize: List of param keys to make variable
        """
        recording = self._recordings.get(recording_id)
        if not recording:
            return None

        parameterize = parameterize or []

        # Build macro definition
        steps = []
        parameters = {}

        for i, action in enumerate(recording.actions):
            step = {
                "action_type": action.action_type.value,
                "name": action.name,
                "params": {},
            }

            for key, value in action.params.items():
                if key in parameterize:
                    param_name = f"{key}_{i}"
                    step["params"][key] = f"${{{param_name}}}"
                    parameters[param_name] = {
                        "type": type(value).__name__,
                        "default": value,
                        "description": f"{key} for step {i+1}",
                    }
                else:
                    step["params"][key] = value

            steps.append(step)

        return {
            "name": macro_name,
            "description": f"Macro from recording: {recording.name}",
            "parameters": parameters,
            "steps": steps,
            "source_recording": recording_id,
            "created_at": datetime.utcnow().isoformat(),
        }

    async def save(self) -> None:
        """Save all recordings to storage."""
        if not self._storage_path:
            return

        data = {
            "recordings": [
                {
                    "id": r.id,
                    "name": r.name,
                    "description": r.description,
                    "created_at": r.created_at.isoformat(),
                    "updated_at": r.updated_at.isoformat(),
                    "total_duration_ms": r.total_duration_ms,
                    "tags": r.tags,
                    "metadata": r.metadata,
                    "actions": [
                        {
                            "id": a.id,
                            "action_type": a.action_type.value,
                            "name": a.name,
                            "params": a.params,
                            "timestamp": a.timestamp.isoformat(),
                            "duration_ms": a.duration_ms,
                            "success": a.success,
                            "metadata": a.metadata,
                        }
                        for a in r.actions
                    ],
                }
                for r in self._recordings.values()
            ],
            "saved_at": datetime.utcnow().isoformat(),
        }

        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._storage_path.write_text(json.dumps(data, indent=2))
        logger.info(f"Saved {len(self._recordings)} recordings")

    async def load(self) -> int:
        """Load recordings from storage."""
        if not self._storage_path or not self._storage_path.exists():
            return 0

        try:
            data = json.loads(self._storage_path.read_text())

            for r_data in data.get("recordings", []):
                actions = [
                    RecordedAction(
                        id=a["id"],
                        action_type=ActionType(a["action_type"]),
                        name=a["name"],
                        params=a["params"],
                        timestamp=datetime.fromisoformat(a["timestamp"]),
                        duration_ms=a["duration_ms"],
                        success=a["success"],
                        metadata=a.get("metadata", {}),
                    )
                    for a in r_data.get("actions", [])
                ]

                recording = ActionRecording(
                    id=r_data["id"],
                    name=r_data["name"],
                    description=r_data.get("description", ""),
                    created_at=datetime.fromisoformat(r_data["created_at"]),
                    updated_at=datetime.fromisoformat(r_data["updated_at"]),
                    total_duration_ms=r_data.get("total_duration_ms", 0),
                    tags=r_data.get("tags", []),
                    metadata=r_data.get("metadata", {}),
                    actions=actions,
                )

                self._recordings[recording.id] = recording

            logger.info(f"Loaded {len(self._recordings)} recordings")
            return len(self._recordings)

        except Exception as e:
            logger.error(f"Failed to load recordings: {e}")
            return 0


# Singleton instance
_recorder: Optional[ActionRecorder] = None


def get_recorder() -> ActionRecorder:
    """Get the global recorder instance."""
    global _recorder
    if _recorder is None:
        _recorder = ActionRecorder()
    return _recorder
