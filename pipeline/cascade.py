"""
pipeline/cascade.py — Cascade concat fallback untuk follow-up pendek.

Extracted from server.py (v2.10.0+).
Logic: concat prev query depth 1-3 → BM25 re-score → E5 similarity guard.
Short follow-up (<3 kata + history) skip BM25 gate & E5 guard.
"""

from sklearn.metrics.pairwise import cosine_similarity
import numpy as np


async def handle_cascade(
    query: str,
    prev_queries: list[str],
    query_vec: np.ndarray,
    encode_fn,
    bm25_score_fn,
    *,
    is_short_followup: bool = False,
    original_bm25: float = 0.0,
    max_depth: int = 3,
    bm25_threshold: float = 5.0,
    e5_threshold: float = 0.78,
) -> tuple[float, str | None, bool]:
    """
    Cascade concat prev query depth 1-3, re-score BM25.

    Args:
        query: User current query (original, not sanitized beyond spaces)
        prev_queries: Previous user queries (newest first — reversed history)
        query_vec: E5 embedding of current query (reuse from domain filter)
        encode_fn: Async function (str → np.ndarray), e.g. async_encode_query
        bm25_score_fn: Sync function (str → float), e.g. get_bm25_score
        is_short_followup: If True (<3 kata + history), skip BM25 gate & E5 guard
        original_bm25: Original BM25 score (used for short follow-up fallback)
        max_depth: Cascade depth (default 3)
        bm25_threshold: BM25 score to consider cascade success (default 5.0)
        e5_threshold: E5 cosine sim for topic drift detection (default 0.78)

    Returns:
        (bm25_top, cascade_query, cascade_used):
            - bm25_top: Updated BM25 score (cascade result, or 3.0 for
              short follow-up fail, or original_bm25 unchanged if no cascade)
            - cascade_query: Enhanced query if success, None otherwise
            - cascade_used: True if cascade succeeded
    """
    bm25_top = original_bm25
    cascade_query: str | None = None
    cascade_used = False
    best_cascade_bm25 = 0.0

    for depth in range(1, min(max_depth + 1, len(prev_queries) + 1)):
        context_parts = list(reversed(prev_queries[:depth])) + [query]
        enhanced_query = " — ".join(context_parts)
        bm25_cascade = bm25_score_fn(enhanced_query)
        best_cascade_bm25 = bm25_cascade
        print(f"[CASCADE] Depth={depth}: BM25 {bm25_cascade:.1f}")

        if bm25_cascade >= bm25_threshold:
            # E5 similarity guard — skip for short follow-up
            if is_short_followup:
                e5_sim = 1.0
            else:
                prev_vec = await encode_fn(prev_queries[0])
                if prev_vec.ndim == 1:
                    prev_vec = prev_vec.reshape(1, -1)
                curr_vec = query_vec
                if curr_vec.ndim == 1:
                    curr_vec = curr_vec.reshape(1, -1)
                e5_sim = float(cosine_similarity(prev_vec, curr_vec).flatten()[0])

            if is_short_followup or e5_sim >= e5_threshold:
                bm25_top = bm25_cascade
                cascade_query = enhanced_query
                cascade_used = True
                print(f"[CASCADE] Depth={depth} berhasil! BM25={bm25_cascade:.1f}"
                      f"{'' if is_short_followup else f', E5 sim={e5_sim:.2f}'}")
                break
            else:
                print(f"[CASCADE] Depth={depth} E5 sim terlalu rendah "
                      f"({e5_sim:.2f}) — topic drift, skip cascade")

    if not cascade_used and not is_short_followup:
        print(f"[CASCADE] Gagal di semua depth — BM25 max {best_cascade_bm25:.1f}")

    # Short follow-up: cascade gagal pun jangan OOC — set ke borderline
    if not cascade_used and is_short_followup and bm25_top < 3.0:
        print(f"[CASCADE] Short follow-up gagal — borderline fallback (3.0)")
        bm25_top = 3.0

    return bm25_top, cascade_query, cascade_used
