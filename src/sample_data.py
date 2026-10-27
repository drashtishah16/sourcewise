"""
Sample fictional source documents and default brand profiles for demonstration and testing.
All data in this file is explicitly fictional and provided for testing and evaluation purposes.
"""
from typing import Dict, Any

SAMPLE_ARTICLE_TITLE = "Fictional Case Study: How NexusPay Cut PostgreSQL Query Latency by 42% Using Multi-Tier Caching"
SAMPLE_ARTICLE_TYPE = "Case Study"
SAMPLE_ARTICLE_URL = "https://example.com/case-studies/nexuspay-caching-architecture"

SAMPLE_ARTICLE_TEXT = """NexusPay, a high-growth fintech platform processing over 12 million daily micro-transactions, faced critical database throughput bottlenecks during the Q3 2025 shopping surge. Peak-hour 99th-percentile query latency exceeded 820ms on their primary PostgreSQL clusters, triggering connection pool exhaustion and checkout timeouts.

To address this scaling ceiling without costly horizontal database sharding, NexusPay's engineering team deployed a two-tier caching architecture in October 2025. The solution combined an in-memory Redis cluster for hot customer session state with an edge read-through cache for localized ledger balance verification.

Within thirty days of full production rollout, NexusPay measured a 42% reduction in overall database query latency, dropping p99 response times from 820ms to 475ms. Furthermore, primary PostgreSQL CPU utilization dropped from 86% peak to an average of 44%, freeing capacity for complex fraud-scoring pipelines.

"Implementing the multi-tier caching strategy protected our transactional integrity while cutting infrastructure overhead by $18,500 per month," stated Elena Rostova, VP of Infrastructure Engineering at NexusPay. "Our developers can now ship new payment flows without constant fear of database saturation."

The engineering team emphasizes that cache invalidation requires disciplined event-driven messaging via Apache Kafka rather than time-to-live expiration alone. While the edge caching reduced read traffic, state synchronization introduces eventual consistency windows of up to 150 milliseconds that financial teams must account for in ledger reconciliations."""

SAMPLE_BRAND_PROFILE: Dict[str, Any] = {
    "name": "CloudPulse Architecture",
    "target_audience": "Senior Backend Engineers, Engineering Leaders, and Cloud Architects",
    "tone_of_voice": "Authoritative, technical, data-driven, yet accessible",
    "preferred_terminology": [
        "cloud-native",
        "latency reduction",
        "cache optimization",
        "transactional integrity",
        "p99 latency",
        "eventual consistency"
    ],
    "forbidden_terminology": [
        "magic bullet",
        "revolutionary breakthrough",
        "cheap",
        "100% bug-free",
        "guarantee"
    ],
    "primary_cta": "Read the comprehensive architecture teardown and benchmark your stack at cloudpulse.io/eval",
    "required_disclaimer": "Metrics reflect NexusPay's specific workload and query topology; individual infrastructure gains vary.",
    "hashtag_preferences": "#PostgreSQL #CloudArchitecture #Fintech #SystemDesign #DatabaseScaling",
    "content_length_prefs": {
        "linkedin_min": 100,
        "linkedin_max": 300,
        "instagram_min": 50,
        "instagram_max": 200,
        "video_seconds": 60
    }
}

