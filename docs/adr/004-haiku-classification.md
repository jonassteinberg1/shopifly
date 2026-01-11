# ADR-004: Use Claude Haiku for Classification

## Status
Accepted

## Date
2026-01-10

## Context
Need to classify scraped content with LLM. Model options:
- Claude 3 Haiku - Fast, cheap ($0.25/1M input)
- Claude 3 Sonnet - Better quality, more expensive
- Claude 3 Opus - Best quality, most expensive

## Decision
Use Claude 3 Haiku for initial classification because:
1. Cost: ~$2 per 1000 items (vs $15 for Sonnet)
2. Speed: Faster response times
3. Quality: Good enough for category assignment
4. Volume: Can afford to classify all scraped data

Enhanced classification (PRD A2) can add Sonnet for high-value items later.

## Consequences
**Positive:**
- Low cost enables full classification
- Fast iteration
- Can classify everything, not just samples

**Negative:**
- May miss nuanced classifications
- Lower accuracy than Sonnet

**Mitigation:**
PRD A2 defines two-stage approach: Haiku screening + Sonnet deep classification for high-value items.
