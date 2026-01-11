"""Data layer for dashboard queries."""

from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def get_db_path() -> Path:
    """Get the path to the SQLite database."""
    return Path(__file__).parent.parent / "data" / "shopify.db"


def _get_connection() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def get_insights_summary() -> dict[str, Any]:
    """Get summary statistics for insights.

    Returns:
        Dictionary with total counts and averages.
    """
    conn = _get_connection()
    try:
        total_raw = conn.execute("SELECT COUNT(*) FROM raw_sources").fetchone()[0]
        total_insights = conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0]

        avg_frustration_row = conn.execute(
            "SELECT AVG(frustration_level) FROM insights"
        ).fetchone()
        avg_frustration = avg_frustration_row[0] if avg_frustration_row[0] else 0

        wtp_count = conn.execute(
            "SELECT COUNT(*) FROM insights WHERE willingness_to_pay = 1"
        ).fetchone()[0]

        return {
            "total_raw": total_raw,
            "total_insights": total_insights,
            "avg_frustration": round(avg_frustration, 2),
            "wtp_count": wtp_count,
            "wtp_rate": round(wtp_count / total_insights * 100, 1) if total_insights > 0 else 0,
        }
    finally:
        conn.close()


def get_category_breakdown() -> list[dict[str, Any]]:
    """Get count of insights by category.

    Returns:
        List of dicts with category and count.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT category, COUNT(*) as count, AVG(frustration_level) as avg_frustration
            FROM insights
            GROUP BY category
            ORDER BY count DESC
            """
        )
        return [
            {
                "category": row["category"],
                "count": row["count"],
                "avg_frustration": round(row["avg_frustration"], 2),
            }
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def get_trends_data() -> list[dict[str, Any]]:
    """Get insights aggregated by date.

    Returns:
        List of dicts with date and count.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT DATE(r.created_at) as date, COUNT(*) as count
            FROM insights i
            JOIN raw_sources r ON r.source_id = i.source_id
            GROUP BY DATE(r.created_at)
            ORDER BY date DESC
            LIMIT 30
            """
        )
        return [
            {"date": row["date"], "count": row["count"]}
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


def get_keyword_frequencies() -> dict[str, int]:
    """Get frequency of keywords across all insights.

    Returns:
        Dictionary of keyword to count.
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("SELECT keywords FROM insights WHERE keywords IS NOT NULL")
        all_keywords: Counter[str] = Counter()

        for row in cursor.fetchall():
            if row["keywords"]:
                keywords = [kw.strip().lower() for kw in row["keywords"].split(",")]
                all_keywords.update(keywords)

        # Return top 50 keywords
        return dict(all_keywords.most_common(50))
    finally:
        conn.close()


def get_top_opportunities() -> list[dict[str, Any]]:
    """Get top opportunities based on category frequency and frustration.

    Returns:
        List of opportunity dicts ranked by score.
    """
    conn = _get_connection()
    try:
        # Calculate opportunity score based on:
        # - Category frequency (more mentions = higher score)
        # - Average frustration level
        # - WTP rate
        cursor = conn.execute(
            """
            SELECT
                category,
                COUNT(*) as frequency,
                AVG(frustration_level) as avg_frustration,
                SUM(CASE WHEN willingness_to_pay = 1 THEN 1 ELSE 0 END) as wtp_count,
                ROUND(SUM(CASE WHEN willingness_to_pay = 1 THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as wtp_rate
            FROM insights
            GROUP BY category
            ORDER BY COUNT(*) * AVG(frustration_level) DESC
            LIMIT 10
            """
        )

        results = []
        for row in cursor.fetchall():
            # Simple scoring: frequency * avg_frustration * (1 + wtp_rate/100)
            frequency = row["frequency"]
            avg_frust = row["avg_frustration"]
            wtp_rate = row["wtp_rate"] or 0
            score = frequency * avg_frust * (1 + wtp_rate / 100)

            results.append({
                "category": row["category"],
                "frequency": frequency,
                "avg_frustration": round(avg_frust, 2),
                "wtp_count": row["wtp_count"],
                "wtp_rate": wtp_rate,
                "score": round(score, 1),
            })

        return sorted(results, key=lambda x: x["score"], reverse=True)
    finally:
        conn.close()


def get_competitor_mentions() -> list[dict[str, int]]:
    """Get mentions of competitor apps/solutions in insights.

    Returns:
        List of dicts with competitor name and count.
    """
    # Common Shopify competitors and related apps
    competitors = [
        "woocommerce", "bigcommerce", "magento", "squarespace", "wix",
        "gorgias", "klaviyo", "mailchimp", "yotpo", "judge.me",
        "shipstation", "shippo", "easyship", "aftership",
        "oberlo", "dsers", "spocket", "printful",
        "quickbooks", "xero", "stripe", "paypal",
    ]

    conn = _get_connection()
    try:
        mentions: Counter[str] = Counter()

        # Search in content snippets and workarounds
        cursor = conn.execute(
            "SELECT content_snippet, current_workaround FROM insights"
        )

        for row in cursor.fetchall():
            text = f"{row['content_snippet']} {row['current_workaround'] or ''}".lower()
            for competitor in competitors:
                if competitor in text:
                    mentions[competitor] += 1

        return [
            {"competitor": name, "count": count}
            for name, count in mentions.most_common(15)
            if count > 0
        ]
    finally:
        conn.close()
