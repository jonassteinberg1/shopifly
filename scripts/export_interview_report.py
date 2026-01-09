#!/usr/bin/env python3
"""Export interview research reports in various formats."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.classifier import ProblemCategory
from analysis.interview_reranker import InterviewReranker, format_opportunity_report
from research.interview_storage import InterviewStorage
from storage import get_storage


def generate_weekly_summary(
    interview_storage: InterviewStorage,
    main_storage,
) -> str:
    """Generate a weekly summary report.

    Args:
        interview_storage: Interview data storage.
        main_storage: Main insights storage.

    Returns:
        Formatted report string.
    """
    stats = interview_storage.get_interview_stats()
    category_stats = interview_storage.get_category_summary()
    participants = interview_storage.get_all_participants()
    insights = interview_storage.get_all_insights()

    # Get recent participants (last 7 days)
    now = datetime.utcnow()
    recent_participants = [
        p for p in participants
        if (now - p.interview_date).days <= 7
    ]

    lines = [
        "=" * 80,
        "WEEKLY INTERVIEW RESEARCH SUMMARY",
        f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 80,
        "",
        "## Overview",
        "",
        f"- Total Participants: {stats['total_participants']}",
        f"- Total Insights: {stats['total_insights']}",
        f"- Interviews This Week: {len(recent_participants)}",
        f"- Beta Testers: {stats['beta_testers']}",
        f"- WTP Rate: {stats['wtp_rate']:.1f}%",
        "",
    ]

    if stats['avg_wtp_amount']:
        lines.append(f"- Avg WTP: ${stats['avg_wtp_amount']:.0f}/month")
        lines.append("")

    # Top pain points
    lines.extend([
        "## Top Pain Points by Interview Count",
        "",
    ])

    for cat, data in sorted(
        category_stats.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )[:5]:
        wtp_str = f", Avg WTP: ${data['avg_wtp']:.0f}" if data['avg_wtp'] else ""
        lines.append(
            f"- {cat}: {data['count']} mentions, "
            f"Frustration: {data['avg_frustration']:.1f}/5{wtp_str}"
        )

    lines.append("")

    # High frustration insights
    high_frustration = interview_storage.get_high_frustration_insights(min_level=4)
    if high_frustration:
        lines.extend([
            "## High Frustration Insights (4-5/5)",
            "",
        ])
        for insight in high_frustration[:5]:
            lines.append(f"- [{insight.pain_category.value}] {insight.pain_summary}")
            if insight.verbatim_quotes:
                lines.append(f'  Quote: "{insight.verbatim_quotes[0][:100]}..."')
        lines.append("")

    # WTP insights
    wtp_insights = interview_storage.get_insights_with_wtp()
    if wtp_insights:
        lines.extend([
            "## Willingness to Pay Signals",
            "",
        ])
        for insight in wtp_insights[:5]:
            wtp_range = f"${insight.wtp_amount_low or '?'}-${insight.wtp_amount_high or '?'}/mo"
            lines.append(f"- [{insight.pain_category.value}] {wtp_range}")
            if insight.wtp_quote:
                lines.append(f'  Quote: "{insight.wtp_quote[:100]}..."')
        lines.append("")

    # Recent participants
    if recent_participants:
        lines.extend([
            "## Recent Interviews (Last 7 Days)",
            "",
        ])
        for p in recent_participants:
            lines.append(
                f"- {p.participant_id}: {p.store_vertical}, {p.monthly_gmv_range}, "
                f"{p.app_count} apps"
            )
        lines.append("")

    return "\n".join(lines)


def generate_correlation_report(
    interview_storage: InterviewStorage,
    main_storage,
) -> str:
    """Generate a correlation report between scraped and interview data.

    Args:
        interview_storage: Interview data storage.
        main_storage: Main insights storage.

    Returns:
        Formatted report string.
    """
    scraped_insights = main_storage.get_all_insights()
    interview_insights = interview_storage.get_all_insights()

    # Get unique categories from scraped data
    scraped_categories = {i.get("category", "other") for i in scraped_insights}

    correlation = interview_storage.generate_correlation_report(scraped_categories)

    lines = [
        "=" * 80,
        "INTERVIEW-SCRAPED DATA CORRELATION REPORT",
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 80,
        "",
        "## Data Sources",
        "",
        f"- Scraped Insights: {len(scraped_insights)}",
        f"- Interview Insights: {len(interview_insights)}",
        f"- Scraped Categories: {len(scraped_categories)}",
        "",
        "## Correlation Analysis",
        "",
        f"### Validated Pain Points (Both Sources): {len(correlation.validated)}",
        "",
    ]

    for cat in sorted(correlation.validated):
        lines.append(f"- {cat}")

    lines.extend([
        "",
        f"### Interview-Only Pain Points: {len(correlation.interview_only)}",
        "(Discovered through interviews, not in scraped data)",
        "",
    ])

    for cat in sorted(correlation.interview_only):
        lines.append(f"- {cat}")

    lines.extend([
        "",
        f"### Scraped-Only Pain Points: {len(correlation.scraped_only)}",
        "(In scraped data, not yet validated through interviews)",
        "",
    ])

    for cat in sorted(correlation.scraped_only):
        lines.append(f"- {cat}")

    lines.extend([
        "",
        f"### WTP-Validated Categories: {len(correlation.wtp_validated)}",
        "(Categories with confirmed willingness to pay)",
        "",
    ])

    for cat in sorted(correlation.wtp_validated):
        lines.append(f"- {cat}")

    lines.append("")

    return "\n".join(lines)


def generate_opportunity_report(
    interview_storage: InterviewStorage,
    main_storage,
    top_n: int = 10,
) -> str:
    """Generate a ranked opportunity report.

    Args:
        interview_storage: Interview data storage.
        main_storage: Main insights storage.
        top_n: Number of top opportunities to include.

    Returns:
        Formatted report string.
    """
    scraped_insights = main_storage.get_all_insights()
    interview_insights = interview_storage.get_all_insights()

    reranker = InterviewReranker(scraped_insights, interview_insights)
    opportunities = reranker.get_top_opportunities(top_n)

    return format_opportunity_report(opportunities)


def export_json(
    interview_storage: InterviewStorage,
    main_storage,
) -> str:
    """Export all interview data as JSON.

    Args:
        interview_storage: Interview data storage.
        main_storage: Main insights storage.

    Returns:
        JSON string.
    """
    participants = interview_storage.get_all_participants()
    insights = interview_storage.get_all_insights()
    stats = interview_storage.get_interview_stats()
    category_stats = interview_storage.get_category_summary()

    # Get correlation
    scraped_insights = main_storage.get_all_insights()
    scraped_categories = {i.get("category", "other") for i in scraped_insights}
    correlation = interview_storage.generate_correlation_report(scraped_categories)

    data = {
        "generated_at": datetime.utcnow().isoformat(),
        "stats": stats,
        "category_summary": category_stats,
        "correlation": {
            "validated": correlation.validated,
            "interview_only": correlation.interview_only,
            "scraped_only": correlation.scraped_only,
            "wtp_validated": correlation.wtp_validated,
        },
        "participants": [
            {
                "participant_id": p.participant_id,
                "interview_date": p.interview_date.isoformat(),
                "store_vertical": p.store_vertical,
                "monthly_gmv_range": p.monthly_gmv_range,
                "store_age_months": p.store_age_months,
                "team_size": p.team_size,
                "app_count": p.app_count,
                "monthly_app_budget": p.monthly_app_budget,
                "beta_tester": p.beta_tester,
            }
            for p in participants
        ],
        "insights": [
            {
                "interview_id": i.interview_id,
                "participant_id": i.participant_id,
                "pain_category": i.pain_category.value,
                "pain_summary": i.pain_summary,
                "verbatim_quotes": i.verbatim_quotes,
                "frustration_level": i.frustration_level,
                "frequency": i.frequency.value,
                "business_impact": i.business_impact.value,
                "current_workaround": i.current_workaround,
                "apps_tried": i.apps_tried,
                "ideal_solution": i.ideal_solution,
                "wtp_amount_low": i.wtp_amount_low,
                "wtp_amount_high": i.wtp_amount_high,
                "wtp_quote": i.wtp_quote,
            }
            for i in insights
        ],
    }

    return json.dumps(data, indent=2)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Export interview research reports"
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["weekly", "correlation", "opportunities", "json"],
        default="weekly",
        help="Report format to generate",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--db-path",
        help="SQLite database path",
    )
    parser.add_argument(
        "--top",
        "-t",
        type=int,
        default=10,
        help="Number of top opportunities (for opportunities report)",
    )

    args = parser.parse_args()

    # Initialize storage
    interview_storage = InterviewStorage(db_path=args.db_path)
    main_storage = get_storage(backend="sqlite", db_path=args.db_path)

    # Generate report
    if args.format == "weekly":
        report = generate_weekly_summary(interview_storage, main_storage)
    elif args.format == "correlation":
        report = generate_correlation_report(interview_storage, main_storage)
    elif args.format == "opportunities":
        report = generate_opportunity_report(interview_storage, main_storage, args.top)
    elif args.format == "json":
        report = export_json(interview_storage, main_storage)
    else:
        print(f"Unknown format: {args.format}", file=sys.stderr)
        sys.exit(1)

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report)
        print(f"Report written to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
