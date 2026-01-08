# =============================================================================
# SHOPIFLY - Reddit Scraper (Sanitized Code Snippet)
# =============================================================================
# This shows exactly what data we collect and how we handle it.
# Full source: https://github.com/jonassteinberg1/shopifly
# =============================================================================

# Target subreddits - focused on Shopify/e-commerce communities
SUBREDDITS = [
    "shopify",
    "ecommerce",
    "dropship",
    "smallbusiness",
    "Entrepreneur",
]

# Keywords indicating pain points (we only keep posts matching these)
PAIN_POINT_KEYWORDS = [
    "frustrated", "annoying", "hate", "wish", "missing",
    "need", "want", "problem", "issue", "bug", "broken",
    "expensive", "alternative", "help", "stuck", "can't",
    "doesn't work", "looking for", "recommend", "suggestion",
]

# Search queries used
SEARCH_QUERIES = ["shopify", "shopify app", "shopify problem", "shopify help"]


def scrape_subreddit(subreddit, limit=100):
    """
    Scrape a single subreddit for Shopify pain points.

    - Uses Reddit search API (read-only)
    - Filters to last 30 days
    - Only keeps posts mentioning "shopify" + pain keywords
    - Rate limited (1 second between requests)
    """
    for query in SEARCH_QUERIES:
        # Search for posts (READ-ONLY operation)
        posts = subreddit.search(
            query,
            sort="new",
            time_filter="month",  # Last 30 days only
            limit=limit // 4      # Split limit across queries
        )

        for post in posts:
            if is_relevant(post):
                yield extract_data(post)

            time.sleep(1.0)  # Rate limiting - 1 second delay


def is_relevant(post):
    """Only keep posts that mention Shopify AND express frustration."""
    text = f"{post.title} {post.selftext}".lower()

    # Must mention Shopify
    if "shopify" not in text:
        return False

    # Must contain pain indicator
    return any(keyword in text for keyword in PAIN_POINT_KEYWORDS)


def extract_data(post):
    """
    Extract ONLY public, non-sensitive data.

    We collect:
    - Post content (title, body) - PUBLIC
    - Post metadata (score, comments) - PUBLIC
    - Post URL - PUBLIC

    We DO NOT collect:
    - User profiles or history
    - Private messages
    - Email addresses or PII
    - Anything requiring authentication beyond read access
    """
    return {
        # Unique identifier for deduplication
        "source_id": f"reddit_post_{post.id}",

        # Public post content
        "title": post.title,
        "content": post.selftext or "[No body text]",
        "url": f"https://reddit.com{post.permalink}",

        # Public metadata (helps prioritize high-engagement issues)
        "subreddit": str(post.subreddit),
        "score": post.score,
        "num_comments": post.num_comments,
        "created_at": datetime.fromtimestamp(post.created_utc),

        # Author stored minimally (username only, no profile data)
        "author": str(post.author) if post.author else "[deleted]",
    }


# =============================================================================
# WHAT HAPPENS NEXT (Off-Platform)
# =============================================================================
#
# 1. Data is stored in LOCAL SQLite database (never shared/sold)
# 2. Anthropic Claude AI categorizes the pain points
# 3. We aggregate: "47 posts mention inventory sync issues"
# 4. We build Shopify apps addressing top pain points
# 5. Merchants benefit from apps solving their actual problems
#
# =============================================================================
