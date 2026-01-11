# ADR-002: Use SQLite for Storage (Not Airtable)

## Status
Accepted

## Date
2026-01-10

## Context
Project originally supported both SQLite (local) and Airtable (production).
Need to decide on primary storage for autonomous development.

## Decision
Use SQLite exclusively for this phase because:
1. No API rate limits
2. Faster for development/testing
3. All data stays on EC2 instance
4. No external dependencies
5. Simpler debugging

Airtable support remains in code for future use.

## Consequences
**Positive:**
- No API costs
- Faster iteration
- Simpler debugging

**Negative:**
- No cloud backup (must manage ourselves)
- No Airtable UI for manual data review

**Mitigation:**
Regular SQLite backups. Can migrate to Postgres later if needed.
