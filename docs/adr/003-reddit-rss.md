# ADR-003: Use Reddit RSS (Not JSON API)

## Status
Accepted

## Date
2026-01-10

## Context
Reddit denied our API access request. Need alternative approach.

## Decision
Use Reddit RSS feeds because:
1. Public, no API key required
2. Already implemented in `scrapers/reddit_selenium.py`
3. Supports hot, new, top, rising endpoints
4. Can fetch comments via RSS

## Consequences
**Positive:**
- Works without API approval
- No rate limits
- Simple implementation

**Negative:**
- Less data than full API (e.g., no user metadata)
- RSS may have delays vs real-time API

**Mitigation:**
RSS provides sufficient data for our use case. Can revisit if Reddit approves API later.
