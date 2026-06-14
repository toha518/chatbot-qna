"""
pipeline/multi_part.py — Multi-part query split & merge.

Extracted from server.py.
3-layer: Comparison Guard → Heuristic Split → E5 Semantic Merge + CLF Guard.
"""

import re
import numpy as np

# ── COMPILED REGEX (module level) ──
_COMPARISON_GUARD = re.compile(
    r'(?:perbedaan|bedanya?|apa\s+bedanya?|perbandingan|bandingkan|peran|tugas|fungsi)'
    r'\s+.+?(?:dan|dengan)\s+',
    re.IGNORECASE
)

_SPLIT_PATTERN = re.compile(
    r'\s+(?:dan|serta|sedangkan|namun|tetapi|tapi)\s+'
    r'|(?<=\?)\s+(?=[A-Za-z])'
    r'|\.\s+'
    r'|,\s*'
)

SEMANTIC_MERGE_THRESHOLD = 0.78


def is_comparison_query(raw_query: str) -> bool:
    """Check if query is a comparison pattern (skip split)."""
    return bool(_COMPARISON_GUARD.search(raw_query))


def heuristic_split(raw_query: str) -> list[str]:
    """
    Split raw query on conjunction / delimiter boundaries.

    Returns cleaned parts (normalized spacing, stripped).
    """
    parts = _SPLIT_PATTERN.split(raw_query.strip())
    cleaned = []
    for p in parts:
        p = re.sub(r'\s+', ' ', p.replace(',', ' ').replace(';', ' ')).strip().rstrip('?.').strip()
        if p:
            cleaned.append(p)
    return cleaned


async def semantic_merge(
    parts: list[str],
    encode_fn,
) -> list[str]:
    """
    Merge semantically similar adjacent parts using E5 cosine similarity.

    Args:
        parts: List of query parts after heuristic split
        encode_fn: Async function (str → np.ndarray)

    Returns:
        Merged list of parts (adjacent parts with cosim >= threshold merged)
    """
    if len(parts) <= 1:
        return parts

    merged = [parts[0]]
    for i in range(1, len(parts)):
        prev_vec = await encode_fn(merged[-1])
        curr_vec = await encode_fn(parts[i])
        if prev_vec.ndim == 1:
            prev_vec = prev_vec.reshape(1, -1)
        if curr_vec.ndim == 1:
            curr_vec = curr_vec.reshape(1, -1)

        from sklearn.metrics.pairwise import cosine_similarity
        sim = float(cosine_similarity(prev_vec, curr_vec).flatten()[0])

        if sim >= SEMANTIC_MERGE_THRESHOLD:
            merged[-1] = merged[-1] + " " + parts[i]
            print(f"[MERGE] Part {i-1}+{i}: sim={sim:.3f} -> '{merged[-1][:60]}'")
        else:
            merged.append(parts[i])
            print(f"[SPLIT] Part {i-1} vs {i}: sim={sim:.3f} -> separate intents")

    return merged


def clf_filter_parts(
    parts: list[str],
    classify_fn,
) -> list[str] | None:
    """
    Skip multi-part if 0-1 parts are substantive (greeting/capability/fb).

    Args:
        parts: List of query parts after semantic merge
        classify_fn: Function (str → (domain, confidence))

    Returns:
        Original parts list if ≥2 substantive, None if should skip multi-part
        (meaning process as single query)
    """
    if len(parts) <= 1:
        return parts

    non_substantive = 0
    for p in parts:
        p_clf, _ = classify_fn(p)
        if p_clf in ("greeting", "capability", "positive_feedback", "negative_feedback"):
            non_substantive += 1

    if non_substantive >= len(parts) - 1:
        print(f"[SPLIT] {non_substantive}/{len(parts)} part non-substantif "
              f"— skip multi-part, pake query asli")
        return None

    return parts
