"""
Cron expression parser and scheduler.

Provides:
- CronSchedule: Parsed cron schedule data
- CronParser: Parse cron expressions and calculate next run times
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CronSchedule:
    """
    Parsed cron schedule.

    Attributes:
        minutes: List of valid minutes (0-59)
        hours: List of valid hours (0-23)
        days: List of valid days of month (1-31)
        months: List of valid months (1-12)
        weekdays: List of valid weekdays (0-6, 0=Sunday)
        expression: Original cron expression
    """
    minutes: List[int]
    hours: List[int]
    days: List[int]
    months: List[int]
    weekdays: List[int]
    expression: str

    def matches(self, dt: datetime) -> bool:
        """
        Check if a datetime matches this schedule.

        Args:
            dt: Datetime to check

        Returns:
            True if the datetime matches the schedule
        """
        # Convert Python weekday (0=Monday) to cron weekday (0=Sunday)
        cron_weekday = (dt.weekday() + 1) % 7

        return (
            dt.minute in self.minutes and
            dt.hour in self.hours and
            dt.day in self.days and
            dt.month in self.months and
            cron_weekday in self.weekdays
        )


class CronParser:
    """
    Parser for cron expressions.

    Cron format: minute hour day_of_month month day_of_week

    Supports:
    - * : any value
    - 5 : specific value
    - 1-5 : range
    - 1,3,5 : list
    - */5 : step
    - 1-30/5 : range with step
    """

    # Field ranges
    FIELD_RANGES = {
        "minute": (0, 59),
        "hour": (0, 23),
        "day": (1, 31),
        "month": (1, 12),
        "weekday": (0, 6),
    }

    FIELD_NAMES = ["minute", "hour", "day", "month", "weekday"]

    @classmethod
    def parse(cls, expression: str) -> CronSchedule:
        """
        Parse a cron expression into a CronSchedule.

        Args:
            expression: Cron expression (5 fields: minute hour day month weekday)

        Returns:
            CronSchedule with parsed values

        Raises:
            ValueError: If expression is invalid
        """
        if not expression or not expression.strip():
            raise ValueError("Invalid cron expression: empty")

        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: expected 5 fields, got {len(parts)}")

        parsed = {}
        for i, (part, field_name) in enumerate(zip(parts, cls.FIELD_NAMES)):
            min_val, max_val = cls.FIELD_RANGES[field_name]
            parsed[field_name] = cls._parse_field(part, min_val, max_val, field_name)

        return CronSchedule(
            minutes=parsed["minute"],
            hours=parsed["hour"],
            days=parsed["day"],
            months=parsed["month"],
            weekdays=parsed["weekday"],
            expression=expression,
        )

    @classmethod
    def _parse_field(cls, part: str, min_val: int, max_val: int, field_name: str) -> List[int]:
        """
        Parse a single cron field.

        Args:
            part: Field value (e.g., "*", "5", "1-5", "*/15")
            min_val: Minimum allowed value
            max_val: Maximum allowed value
            field_name: Name of field for error messages

        Returns:
            List of valid values for this field
        """
        if part == "*":
            return list(range(min_val, max_val + 1))

        values = set()

        for segment in part.split(","):
            try:
                if "/" in segment:
                    # Step value: */5 or 1-30/5
                    base, step_str = segment.split("/", 1)
                    step = int(step_str)
                    if step <= 0:
                        raise ValueError(f"Invalid step value: {step}")

                    if base == "*":
                        start = min_val
                        end = max_val
                    elif "-" in base:
                        start_str, end_str = base.split("-", 1)
                        start = int(start_str)
                        end = int(end_str)
                    else:
                        start = int(base)
                        end = max_val

                    values.update(range(start, end + 1, step))

                elif "-" in segment:
                    # Range: 1-5
                    start_str, end_str = segment.split("-", 1)
                    start = int(start_str)
                    end = int(end_str)
                    if start > end:
                        raise ValueError(f"Invalid range: {start}-{end}")
                    values.update(range(start, end + 1))

                else:
                    # Single value
                    val = int(segment)
                    values.add(val)

            except ValueError as e:
                if "invalid literal" in str(e).lower():
                    raise ValueError(f"Invalid cron expression: invalid value '{segment}' in {field_name}")
                raise

        # Normalize weekday 7 to 0 (both represent Sunday)
        if field_name == "weekday" and 7 in values:
            values.remove(7)
            values.add(0)

        # Validate all values are in range
        for val in values:
            if val < min_val or val > max_val:
                raise ValueError(
                    f"Invalid cron expression: {field_name} value {val} "
                    f"out of range ({min_val}-{max_val})"
                )

        if not values:
            raise ValueError(f"Invalid cron expression: no valid values for {field_name}")

        return sorted(values)

    @classmethod
    def validate(cls, expression: str) -> None:
        """
        Validate a cron expression.

        Args:
            expression: Cron expression to validate

        Raises:
            ValueError: If expression is invalid
        """
        cls.parse(expression)

    @classmethod
    def get_next_run(
        cls,
        schedule: CronSchedule,
        from_time: Optional[datetime] = None,
        max_iterations: int = 366 * 24 * 60,
    ) -> datetime:
        """
        Calculate the next run time for a cron schedule.

        Args:
            schedule: Parsed CronSchedule
            from_time: Starting time (defaults to now)
            max_iterations: Maximum minutes to search

        Returns:
            Next datetime that matches the schedule

        Raises:
            ValueError: If no valid time found within search range
        """
        if from_time is None:
            from_time = datetime.utcnow()

        # Start from next minute
        candidate = from_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

        for _ in range(max_iterations):
            if schedule.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        raise ValueError(
            f"Could not find next run time for schedule '{schedule.expression}' "
            f"within {max_iterations} minutes from {from_time}"
        )


# Common cron presets
CRON_PRESETS = {
    "every_minute": "* * * * *",
    "hourly": "0 * * * *",
    "daily": "0 0 * * *",
    "daily_9am": "0 9 * * *",
    "weekly": "0 0 * * 0",  # Sunday midnight
    "monthly": "0 0 1 * *",  # First of month
    "yearly": "0 0 1 1 *",  # January 1st
    "weekdays_9am": "0 9 * * 1-5",
    "every_5_minutes": "*/5 * * * *",
    "every_15_minutes": "*/15 * * * *",
    "every_30_minutes": "*/30 * * * *",
}
