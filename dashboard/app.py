"""Shopify Insights Dashboard - Main Streamlit Application."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

from dashboard.data import (
    get_insights_summary,
    get_category_breakdown,
    get_trends_data,
    get_keyword_frequencies,
    get_top_opportunities,
    get_competitor_mentions,
)
from dashboard.charts import (
    create_category_chart,
    create_trends_chart,
    create_wordcloud,
    create_opportunities_table,
    create_competitor_chart,
)


# Page configuration
st.set_page_config(
    page_title="Shopify Insights Dashboard",
    page_icon="🛒",
    layout="wide",
)

st.title("🛒 Shopify Insights Dashboard")
st.markdown("*Discover app opportunities from merchant pain points*")

# ============================================================================
# SECTION 1: Overview
# ============================================================================
st.header("📊 Overview")

summary = get_insights_summary()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Raw Data Points",
        value=summary["total_raw"],
        help="Total scraped posts and reviews",
    )

with col2:
    st.metric(
        label="Classified Insights",
        value=summary["total_insights"],
        help="Posts classified by LLM",
    )

with col3:
    st.metric(
        label="Avg Frustration",
        value=f"{summary['avg_frustration']:.1f}/5",
        help="Average frustration level (1-5)",
    )

with col4:
    st.metric(
        label="WTP Signals",
        value=summary.get("wtp_count", 0),
        help="Posts with willingness to pay",
    )

st.divider()

# ============================================================================
# SECTION 2: Category Breakdown
# ============================================================================
st.header("📁 Category Breakdown")

category_data = get_category_breakdown()
if category_data:
    fig = create_category_chart(category_data)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No category data available yet.")

st.divider()

# ============================================================================
# SECTION 3: Trends Over Time
# ============================================================================
st.header("📈 Trends Over Time")

trends_data = get_trends_data()
if trends_data:
    fig = create_trends_chart(trends_data)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No trends data available yet.")

st.divider()

# ============================================================================
# SECTION 4: Word Cloud
# ============================================================================
st.header("☁️ Keyword Cloud")

keywords = get_keyword_frequencies()
if keywords:
    wordcloud_img = create_wordcloud(keywords)
    if wordcloud_img:
        st.image(wordcloud_img, use_container_width=True)
    else:
        st.info("Could not generate word cloud.")
else:
    st.info("No keyword data available yet.")

st.divider()

# ============================================================================
# SECTION 5: Top Opportunities
# ============================================================================
st.header("🎯 Top Opportunities")

opportunities = get_top_opportunities()
if opportunities:
    df = create_opportunities_table(opportunities)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No opportunities data available yet.")

st.divider()

# ============================================================================
# SECTION 6: Competitor Analysis
# ============================================================================
st.header("🏆 Competitor Mentions")

competitor_data = get_competitor_mentions()
if competitor_data:
    fig = create_competitor_chart(competitor_data)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No competitor data available yet.")
