# Shopifly - Reddit API Application Summary

## Project Overview

**Shopifly** is a market research tool that helps identify pain points experienced by Shopify merchants. By analyzing public discussions on Reddit, we discover gaps in the Shopify app ecosystem where new tools could help small business owners.

**GitHub Repository:** https://github.com/jonassteinberg1/shopifly

---

## What We Do

| Step | Description | Reddit Impact |
|------|-------------|---------------|
| 1. Search | Query 5 subreddits for Shopify-related posts | ~100 API calls/week |
| 2. Filter | Keep only posts mentioning pain points | Read-only, no writes |
| 3. Store | Save to local SQLite database | Data stays private |
| 4. Analyze | Use AI to categorize problems | Off-platform processing |
| 5. Build | Create apps solving top problems | Benefits merchant community |

---

## Data Collection (Minimal & Respectful)

### What We Collect
- Post title and body text (public content only)
- Subreddit name
- Post score and comment count
- Post permalink (for reference)

### What We Do NOT Collect
- Private messages
- User profile information
- Comment histories
- Any non-public content

---

## Technical Specifications

| Specification | Value |
|--------------|-------|
| API Library | PRAW (Python Reddit API Wrapper) |
| Access Type | Read-only (no posting/commenting/voting) |
| Rate Limiting | 1+ second delay between requests |
| Frequency | 1-2 manual runs per week |
| Max Posts/Run | ~500 across all subreddits |
| Storage | Local SQLite (private, never shared) |

---

## Target Subreddits

1. r/shopify - Primary source for merchant feedback
2. r/ecommerce - General e-commerce discussions
3. r/dropship - Dropshipping community (often Shopify-based)
4. r/smallbusiness - Small business owner perspectives
5. r/Entrepreneur - Entrepreneurial insights

---

## Search Methodology

We search for posts containing **both**:

1. **Shopify mention:** "shopify", "shopify app", "shopify problem"
2. **Pain indicators:** "frustrated", "need help", "looking for", "issue", "problem", "wish", "alternative"

This filters out general discussion and focuses only on posts where merchants express genuine struggles.

---

## Example Output

After collection and analysis, our output looks like:

```
Category: Inventory Management
Frequency: 47 mentions
Sample Quote: "Syncing inventory between Shopify and Amazon is a nightmare"
Frustration Level: High (4.2/5)
Willingness to Pay: Yes (73% mention budget)

Category: Analytics
Frequency: 38 mentions
Sample Quote: "Built-in analytics are useless for conversion tracking"
Frustration Level: Medium-High (3.8/5)
Willingness to Pay: Yes (68% mention paying for solutions)
```

---

## Benefits to Reddit Community

1. **Merchants get heard** - Their complaints drive real product development
2. **Better apps exist** - We build solutions for actual problems, not imagined ones
3. **No spam** - We're silent observers, not marketers
4. **Future surveys** - We'll ask r/shopify to vote on priorities (following all rules)

---

## Contact

We're happy to answer any questions or adjust our usage to comply with Reddit's requirements.

**Repository:** https://github.com/jonassteinberg1/shopifly
