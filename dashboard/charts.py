"""Chart generation helpers for dashboard."""

from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud


def create_category_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Create a horizontal bar chart of categories.

    Args:
        data: List of dicts with 'category' and 'count' keys.

    Returns:
        Plotly figure.
    """
    if not data:
        return go.Figure()

    categories = [d["category"] for d in data]
    counts = [d["count"] for d in data]
    frustrations = [d.get("avg_frustration", 3) for d in data]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=categories,
            x=counts,
            orientation="h",
            marker=dict(
                color=frustrations,
                colorscale="RdYlGn_r",
                colorbar=dict(title="Avg Frustration"),
                cmin=1,
                cmax=5,
            ),
            text=counts,
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Insights by Category",
        xaxis_title="Count",
        yaxis_title="Category",
        yaxis=dict(categoryorder="total ascending"),
        height=max(400, len(categories) * 30),
    )

    return fig


def create_trends_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Create a line chart of insights over time.

    Args:
        data: List of dicts with 'date' and 'count' keys.

    Returns:
        Plotly figure.
    """
    if not data:
        return go.Figure()

    # Sort by date
    sorted_data = sorted(data, key=lambda x: x["date"])
    dates = [d["date"] for d in sorted_data]
    counts = [d["count"] for d in sorted_data]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=counts,
            mode="lines+markers",
            name="Insights",
            line=dict(color="#1f77b4", width=2),
            marker=dict(size=8),
        )
    )

    fig.update_layout(
        title="Insights Over Time",
        xaxis_title="Date",
        yaxis_title="Count",
        hovermode="x unified",
    )

    return fig


def create_wordcloud(keywords: dict[str, int]) -> WordCloud | None:
    """Create a word cloud from keyword frequencies.

    Args:
        keywords: Dictionary of keyword to frequency.

    Returns:
        WordCloud object or None if no keywords.
    """
    if not keywords:
        return None

    wc = WordCloud(
        width=800,
        height=400,
        background_color="white",
        colormap="viridis",
        max_words=50,
    )

    wc.generate_from_frequencies(keywords)
    return wc


def create_opportunities_table(data: list[dict[str, Any]]) -> go.Figure:
    """Create a table visualization of opportunities.

    Args:
        data: List of opportunity dicts.

    Returns:
        Plotly figure with table.
    """
    if not data:
        return go.Figure()

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Rank", "Category", "Frequency", "Avg Frustration", "WTP Rate", "Score"],
                    fill_color="#1f77b4",
                    font=dict(color="white", size=12),
                    align="left",
                ),
                cells=dict(
                    values=[
                        list(range(1, len(data) + 1)),
                        [d["category"].replace("_", " ").title() for d in data],
                        [d["frequency"] for d in data],
                        [f"{d['avg_frustration']:.1f}" for d in data],
                        [f"{d['wtp_rate']:.0f}%" for d in data],
                        [f"{d['score']:.0f}" for d in data],
                    ],
                    fill_color=[
                        ["#f5f5f5" if i % 2 == 0 else "white" for i in range(len(data))]
                    ],
                    align="left",
                ),
            )
        ]
    )

    fig.update_layout(
        title="Top Opportunities by Score",
        height=max(300, len(data) * 35 + 100),
    )

    return fig


def create_competitor_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Create a bar chart of competitor mentions.

    Args:
        data: List of dicts with 'competitor' and 'count' keys.

    Returns:
        Plotly figure.
    """
    if not data:
        return go.Figure()

    competitors = [d["competitor"].title() for d in data]
    counts = [d["count"] for d in data]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=competitors,
            y=counts,
            marker_color="#ff7f0e",
            text=counts,
            textposition="outside",
        )
    )

    fig.update_layout(
        title="Competitor/App Mentions",
        xaxis_title="Competitor/App",
        yaxis_title="Mentions",
        xaxis_tickangle=-45,
    )

    return fig
