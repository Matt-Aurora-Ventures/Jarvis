"""
Tests for core/scheduler/cron.py

CronParser and CronSchedule tests covering:
- parse(expression) -> CronSchedule
- get_next_run(schedule) -> datetime
- Support for: minute, hour, day, month, weekday
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta


class TestCronParser:
    """Tests for CronParser class."""

    def test_parse_all_wildcards(self):
        """Parsing '* * * * *' should match every minute."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("* * * * *")

        assert schedule.minutes == list(range(0, 60))
        assert schedule.hours == list(range(0, 24))
        assert schedule.days == list(range(1, 32))
        assert schedule.months == list(range(1, 13))
        assert schedule.weekdays == list(range(0, 7))

    def test_parse_specific_values(self):
        """Parsing specific values should work."""
        from core.scheduler.cron import CronParser

        # Every day at 9:30 AM
        schedule = CronParser.parse("30 9 * * *")

        assert schedule.minutes == [30]
        assert schedule.hours == [9]

    def test_parse_range(self):
        """Parsing ranges (1-5) should work."""
        from core.scheduler.cron import CronParser

        # Monday through Friday at midnight
        schedule = CronParser.parse("0 0 * * 1-5")

        assert schedule.minutes == [0]
        assert schedule.hours == [0]
        assert schedule.weekdays == [1, 2, 3, 4, 5]

    def test_parse_list(self):
        """Parsing lists (1,3,5) should work."""
        from core.scheduler.cron import CronParser

        # At 8, 12, and 18 hours
        schedule = CronParser.parse("0 8,12,18 * * *")

        assert schedule.hours == [8, 12, 18]

    def test_parse_step(self):
        """Parsing steps (*/5) should work."""
        from core.scheduler.cron import CronParser

        # Every 5 minutes
        schedule = CronParser.parse("*/5 * * * *")

        expected_minutes = list(range(0, 60, 5))
        assert schedule.minutes == expected_minutes

    def test_parse_step_with_range(self):
        """Parsing steps with ranges (1-30/5) should work."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("1-30/5 * * * *")

        expected = [1, 6, 11, 16, 21, 26]
        assert schedule.minutes == expected

    def test_parse_combined_expressions(self):
        """Parsing combined expressions should work."""
        from core.scheduler.cron import CronParser

        # Every 15 minutes, hours 9-17, Monday-Friday
        schedule = CronParser.parse("*/15 9-17 * * 1-5")

        assert schedule.minutes == [0, 15, 30, 45]
        assert schedule.hours == list(range(9, 18))
        assert schedule.weekdays == [1, 2, 3, 4, 5]

    def test_parse_invalid_too_few_fields(self):
        """Parsing should fail with too few fields."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError, match="Invalid cron expression"):
            CronParser.parse("* * * *")

    def test_parse_invalid_too_many_fields(self):
        """Parsing should fail with too many fields."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError, match="Invalid cron expression"):
            CronParser.parse("* * * * * *")

    def test_parse_invalid_value_out_of_range(self):
        """Parsing should fail with out-of-range values."""
        from core.scheduler.cron import CronParser

        # 60 is invalid for minutes (0-59)
        with pytest.raises(ValueError):
            CronParser.parse("60 * * * *")

    def test_parse_invalid_negative_value(self):
        """Parsing should fail with negative values."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.parse("-1 * * * *")

    def test_parse_invalid_day_zero(self):
        """Parsing should fail with day 0 (days are 1-31)."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.parse("* * 0 * *")

    def test_parse_invalid_month_zero(self):
        """Parsing should fail with month 0 (months are 1-12)."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.parse("* * * 0 *")

    def test_parse_weekday_sunday_as_zero(self):
        """Sunday should be 0 in cron weekday field."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 0 * * 0")
        assert 0 in schedule.weekdays  # Sunday

    def test_parse_weekday_sunday_as_seven(self):
        """Sunday can also be 7 in some cron implementations."""
        from core.scheduler.cron import CronParser

        # Our implementation should normalize 7 to 0
        schedule = CronParser.parse("0 0 * * 7")
        assert 0 in schedule.weekdays  # Sunday normalized


class TestCronSchedule:
    """Tests for CronSchedule dataclass."""

    def test_cron_schedule_creation(self):
        """CronSchedule should store parsed fields."""
        from core.scheduler.cron import CronSchedule

        schedule = CronSchedule(
            minutes=[0, 30],
            hours=[9],
            days=list(range(1, 32)),
            months=list(range(1, 13)),
            weekdays=list(range(0, 7)),
            expression="0,30 9 * * *"
        )

        assert schedule.minutes == [0, 30]
        assert schedule.expression == "0,30 9 * * *"

    def test_cron_schedule_matches_time(self):
        """CronSchedule should check if a datetime matches."""
        from core.scheduler.cron import CronSchedule

        schedule = CronSchedule(
            minutes=[30],
            hours=[9],
            days=list(range(1, 32)),
            months=list(range(1, 13)),
            weekdays=list(range(0, 7)),
            expression="30 9 * * *"
        )

        # January 1, 2026, 9:30 AM (Wednesday, weekday=2)
        matching_time = datetime(2026, 1, 1, 9, 30)
        assert schedule.matches(matching_time) is True

        # Different minute
        non_matching = datetime(2026, 1, 1, 9, 31)
        assert schedule.matches(non_matching) is False


class TestCronParserGetNextRun:
    """Tests for CronParser.get_next_run()."""

    def test_get_next_run_basic(self):
        """get_next_run should return next matching datetime."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("30 9 * * *")
        from_time = datetime(2026, 1, 1, 8, 0)

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run == datetime(2026, 1, 1, 9, 30)

    def test_get_next_run_same_day_later(self):
        """get_next_run should find same day if time allows."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 18 * * *")
        from_time = datetime(2026, 1, 1, 10, 0)

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run.day == 1  # Same day
        assert next_run.hour == 18

    def test_get_next_run_next_day(self):
        """get_next_run should go to next day if time passed."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 9 * * *")
        from_time = datetime(2026, 1, 1, 10, 0)  # After 9 AM

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run.day == 2  # Next day
        assert next_run.hour == 9

    def test_get_next_run_respects_weekday(self):
        """get_next_run should respect weekday constraint."""
        from core.scheduler.cron import CronParser

        # Every Monday at 9 AM (weekday 1)
        schedule = CronParser.parse("0 9 * * 1")
        # January 1, 2026 is a Wednesday
        from_time = datetime(2026, 1, 1, 0, 0)

        next_run = CronParser.get_next_run(schedule, from_time)

        # Should be Monday, January 5, 2026
        assert next_run.weekday() == 0  # Python: Monday=0
        assert next_run.day == 5

    def test_get_next_run_respects_month(self):
        """get_next_run should respect month constraint."""
        from core.scheduler.cron import CronParser

        # Only in March
        schedule = CronParser.parse("0 0 1 3 *")
        from_time = datetime(2026, 1, 1, 0, 0)

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run.month == 3
        assert next_run.day == 1

    def test_get_next_run_every_5_minutes(self):
        """get_next_run should handle minute steps."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("*/5 * * * *")
        from_time = datetime(2026, 1, 1, 10, 3)

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run.minute == 5
        assert next_run.hour == 10

    def test_get_next_run_from_current(self):
        """get_next_run should use current time if not provided."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("* * * * *")

        before = datetime.utcnow()
        next_run = CronParser.get_next_run(schedule)
        after = datetime.utcnow() + timedelta(minutes=2)

        # Should be within next 2 minutes
        assert before <= next_run <= after

    def test_get_next_run_skips_current_minute(self):
        """get_next_run should skip the current minute."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("* * * * *")
        from_time = datetime(2026, 1, 1, 10, 30, 45)  # 45 seconds into minute

        next_run = CronParser.get_next_run(schedule, from_time)

        # Should be next minute
        assert next_run.minute == 31

    def test_get_next_run_year_rollover(self):
        """get_next_run should handle year rollover."""
        from core.scheduler.cron import CronParser

        # January 1st only
        schedule = CronParser.parse("0 0 1 1 *")
        from_time = datetime(2026, 12, 31, 23, 0)

        next_run = CronParser.get_next_run(schedule, from_time)

        assert next_run.year == 2027
        assert next_run.month == 1
        assert next_run.day == 1

    def test_get_next_run_no_valid_time_in_range(self):
        """get_next_run should raise if no valid time found."""
        from core.scheduler.cron import CronParser, CronSchedule

        # Invalid schedule that can never match (February 30)
        # We need to create this manually as parse() would reject it
        schedule = CronSchedule(
            minutes=[0],
            hours=[0],
            days=[30],
            months=[2],  # February
            weekdays=list(range(0, 7)),
            expression="0 0 30 2 *"
        )

        from_time = datetime(2026, 1, 1, 0, 0)

        with pytest.raises(ValueError, match="Could not find next run"):
            CronParser.get_next_run(schedule, from_time)


class TestCronValidation:
    """Tests for cron expression validation."""

    def test_validate_valid_expression(self):
        """Valid expression should pass validation."""
        from core.scheduler.cron import CronParser

        # Should not raise
        CronParser.validate("0 9 * * 1-5")

    def test_validate_invalid_expression(self):
        """Invalid expression should fail validation."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.validate("invalid cron")

    def test_validate_empty_expression(self):
        """Empty expression should fail validation."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.validate("")

    def test_validate_whitespace_only(self):
        """Whitespace-only expression should fail validation."""
        from core.scheduler.cron import CronParser

        with pytest.raises(ValueError):
            CronParser.validate("   ")


class TestCronCommonSchedules:
    """Tests for common cron schedule patterns."""

    def test_hourly(self):
        """Hourly cron should trigger every hour."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 * * * *")

        assert schedule.minutes == [0]
        assert len(schedule.hours) == 24

    def test_daily_at_midnight(self):
        """Daily midnight cron should work."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 0 * * *")

        assert schedule.minutes == [0]
        assert schedule.hours == [0]

    def test_weekly_sunday_midnight(self):
        """Weekly Sunday midnight cron should work."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 0 * * 0")

        assert schedule.weekdays == [0]  # Sunday

    def test_monthly_first_day(self):
        """Monthly first day cron should work."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 0 1 * *")

        assert schedule.days == [1]

    def test_yearly_january_first(self):
        """Yearly January 1st cron should work."""
        from core.scheduler.cron import CronParser

        schedule = CronParser.parse("0 0 1 1 *")

        assert schedule.days == [1]
        assert schedule.months == [1]
