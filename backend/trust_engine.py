from .models import ClaimCheck, Evidence


def calculate_trust(checks: list[ClaimCheck], evidence: list[Evidence], issues: list[str]) -> tuple[int, str, str]:
    """Transparent heuristic for a classroom/research prototype, not a probabilistic guarantee."""
    if not evidence:
        return 30, "Low", "Evidence retrieval unavailable — answer is unverified"
    supported = sum(item.status == "Supported" for item in checks)
    contradicted = sum(item.status == "Contradicted" for item in checks)
    uncertain = sum(item.status == "Uncertain" for item in checks)
    high_quality = sum(item.quality == "High" for item in evidence)
    total = max(len(checks), 1)
    score = 45 + round(30 * supported / total) - round(22 * contradicted / total) - round(12 * uncertain / total)
    score += min(12, high_quality * 4) - min(10, len(issues) * 3)
    score = max(0, min(100, score))
    level = "High" if score >= 80 else "Medium" if score >= 55 else "Low"
    status = "Verified" if supported and not contradicted and not uncertain else "Partially verified" if supported else "Needs verification"
    return score, level, status
