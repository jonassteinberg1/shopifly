# ADR-001: Use Streamlit for Dashboard

## Status
Accepted

## Date
2026-01-10

## Context
Need a visualization dashboard to display classified insights. Options considered:
- **Streamlit** - Python-native, fast to build, good for data apps
- **React/Next.js** - More customizable, better UX, but requires JS expertise
- **Plotly Dash** - Similar to Streamlit, steeper learning curve
- **Grafana** - Good for metrics, overkill for this use case

## Decision
Use Streamlit because:
1. Python-native (matches existing codebase)
2. Fastest development time (hours not days)
3. Built-in charts and data tables
4. Good enough for internal/personal use tool
5. Easy deployment (single command)

## Consequences
**Positive:**
- Rapid development
- No context switching between Python and JS
- Easy to iterate

**Negative:**
- Limited customization vs React
- Not ideal for complex UIs
- Single-user performance only

**Mitigation:**
If we need more customization later, we can migrate to React with the same data layer.
