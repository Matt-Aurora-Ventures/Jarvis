#!/usr/bin/env python3
"""
Financial Report Generator Script.

Generates daily/monthly/yearly financial reports for the Jarvis revenue model.

Usage:
    python scripts/financial_report.py --daily
    python scripts/financial_report.py --monthly 2026-01
    python scripts/financial_report.py --html
    python scripts/financial_report.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.revenue.financial_report import FinancialReporter
from core.revenue.fee_calculator import FeeCalculator
from core.revenue.charity_handler import CharityHandler
from core.revenue.subscription_tiers import SubscriptionManager


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}\n")


def format_usd(amount: float) -> str:
    """Format amount as USD."""
    return f"${amount:,.2f}"


def run_daily_report(reporter: FinancialReporter, date: str = None) -> None:
    """Generate and display daily report."""
    print_section("DAILY REVENUE REPORT")

    report = reporter.generate_daily_report(date)

    print(f"Date: {report['date']}")
    print(f"Generated: {datetime.fromtimestamp(report['generated_at'], tz=timezone.utc).isoformat()}")
    print()
    print("Revenue Summary:")
    print(f"  Total Fees Collected:    {format_usd(report['total_fees'])}")
    print(f"  User Earnings (75%):     {format_usd(report['user_earnings'])}")
    print(f"  Charity Payout (5%):     {format_usd(report['charity_payout'])}")
    print(f"  Company Revenue (20%):   {format_usd(report['company_revenue'])}")
    print()
    print("Activity:")
    print(f"  Fee Transactions:        {report['fee_count']}")
    print(f"  Unique Users:            {report['unique_users']}")
    print(f"  Unique Tokens:           {report['unique_symbols']}")


def run_monthly_report(reporter: FinancialReporter, month: str) -> None:
    """Generate and display monthly report."""
    print_section(f"MONTHLY REVENUE REPORT - {month}")

    report = reporter.generate_monthly_report(month)

    print(f"Month: {report['month']}")
    print(f"Generated: {datetime.fromtimestamp(report['generated_at'], tz=timezone.utc).isoformat()}")
    print()

    print("Revenue Breakdown:")
    print(f"  Total Fees:              {format_usd(report['total_fees'])}")
    rb = report['revenue_breakdown']
    print(f"  User Earnings (75%):     {format_usd(rb['user_earnings'])}")
    print(f"  Charity Payout (5%):     {format_usd(rb['charity_payout'])}")
    print(f"  Company Revenue (20%):   {format_usd(rb['company_revenue'])}")
    print()

    print("User Metrics:")
    um = report['user_metrics']
    print(f"  Total Users:             {um['total_users']}")
    print(f"  Avg Fee Per User:        {format_usd(um['avg_fee_per_user'])}")
    print(f"  Top User Fees:           {format_usd(um['top_user_fees'])}")
    print()

    print("Profitability:")
    pf = report['profitability']
    print(f"  Gross Revenue:           {format_usd(pf['gross_revenue'])}")
    print(f"  Days with Fees:          {pf['days_with_fees']}")


def run_top_earners(reporter: FinancialReporter, limit: int = 10) -> None:
    """Display top earners."""
    print_section("TOP EARNERS (Last 30 Days)")

    top = reporter.get_top_earners(limit=limit)

    if not top:
        print("No data available.")
        return

    print(f"{'Rank':<6} {'User ID':<20} {'Total Fees':>15}")
    print("-" * 45)
    for i, earner in enumerate(top, 1):
        print(f"{i:<6} {earner['user_id']:<20} {format_usd(earner['total_fees']):>15}")


def run_top_tokens(reporter: FinancialReporter, limit: int = 10) -> None:
    """Display top tokens."""
    print_section("TOP TOKENS BY FEE GENERATION (Last 30 Days)")

    top = reporter.get_top_tokens(limit=limit)

    if not top:
        print("No data available.")
        return

    print(f"{'Rank':<6} {'Symbol':<20} {'Total Fees':>15}")
    print("-" * 45)
    for i, token in enumerate(top, 1):
        print(f"{i:<6} {token['symbol']:<20} {format_usd(token['total_fees']):>15}")


def run_charity_report(data_dir: Path = None) -> None:
    """Display charity distribution report."""
    print_section("CHARITY DISTRIBUTION REPORT")

    handler = CharityHandler(data_dir=data_dir, load_defaults=True)

    print("Supported Charities:")
    print("-" * 60)
    for charity in handler.list_charities():
        print(f"  {charity['name']}")
        print(f"    Category: {charity['category']}")
        print(f"    Description: {charity['description']}")
        print(f"    Wallet: {charity['wallet_address'][:20]}...")
        print()

    total = handler.get_total_distributed()
    print(f"Total Distributed: {format_usd(total)}")

    ledger = handler.get_ledger()
    if ledger:
        print("\nRecent Distributions:")
        for entry in ledger[-5:]:
            print(f"  {entry['month']}: {format_usd(entry['amount'])} to {entry['charity']}")


def run_subscription_report(data_dir: Path = None) -> None:
    """Display subscription report."""
    print_section("SUBSCRIPTION REVENUE REPORT")

    manager = SubscriptionManager(data_dir=data_dir)
    summary = manager.get_revenue_summary()

    print(f"Total Paid Subscribers: {summary['total_subscribers']}")
    print(f"Monthly Recurring Revenue: {format_usd(summary['monthly_revenue'])}")
    print()

    if summary['by_tier']:
        print("By Tier:")
        for tier, info in summary['by_tier'].items():
            print(f"  {tier.upper()}:")
            print(f"    Count: {info['count']}")
            print(f"    Price: {format_usd(info['price'])}/mo")
            print(f"    Revenue: {format_usd(info['revenue'])}/mo")


def run_html_export(reporter: FinancialReporter) -> None:
    """Export HTML dashboard."""
    print_section("EXPORTING HTML DASHBOARD")

    path = reporter.export_html_dashboard()
    print(f"Dashboard exported to: {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate financial reports for Jarvis revenue model."
    )

    parser.add_argument(
        "--daily",
        action="store_true",
        help="Generate daily report"
    )
    parser.add_argument(
        "--monthly",
        metavar="YYYY-MM",
        help="Generate monthly report for specified month"
    )
    parser.add_argument(
        "--top-earners",
        action="store_true",
        help="Show top earners"
    )
    parser.add_argument(
        "--top-tokens",
        action="store_true",
        help="Show top tokens"
    )
    parser.add_argument(
        "--charity",
        action="store_true",
        help="Show charity report"
    )
    parser.add_argument(
        "--subscriptions",
        action="store_true",
        help="Show subscription report"
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Export HTML dashboard"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generate all reports"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit for top N queries"
    )

    args = parser.parse_args()

    # Default to daily if no args
    if not any([
        args.daily, args.monthly, args.top_earners, args.top_tokens,
        args.charity, args.subscriptions, args.html, args.all
    ]):
        args.daily = True

    reporter = FinancialReporter()

    if args.all:
        args.daily = True
        args.monthly = datetime.now(timezone.utc).strftime("%Y-%m")
        args.top_earners = True
        args.top_tokens = True
        args.charity = True
        args.subscriptions = True

    if args.daily:
        run_daily_report(reporter)

    if args.monthly:
        run_monthly_report(reporter, args.monthly)

    if args.top_earners:
        run_top_earners(reporter, args.limit)

    if args.top_tokens:
        run_top_tokens(reporter, args.limit)

    if args.charity:
        run_charity_report()

    if args.subscriptions:
        run_subscription_report()

    if args.html:
        run_html_export(reporter)

    print()


if __name__ == "__main__":
    main()
