"""The ONE tunable file: penalties, severity multipliers, category caps and bands."""

PENALTIES = {
    "domain_mismatch": 25, "financial_request": 20, "impersonation": 20,
    "registration_fee": 20, "credential_request": 20, "kyc_threat": 15,
    "suspicious_url": 15, "inconsistency": 15, "fake_authority": 15,
    "misleading_claim": 15, "ela_anomaly": 15, "urgency": 10, "threat": 10,
    "action_pressure": 10, "editing_software_exif": 10, "ip_url": 10,
    "url_shortener": 8, "http_not_https": 5, "unusual_language": 5,
    "exif_time_mismatch": 5, "debunked_by_source": 40,
    "ai_generation_indicator": 20, "manipulation_indicator": 20, "visual_inconsistency": 10,
}
SEVERITY_MULT = {"high": 1.0, "medium": 0.6, "low": 0.3}
CATEGORY_OF = {
    "editing_software_exif": "image_forensics", "exif_time_mismatch": "image_forensics", "ela_anomaly": "image_forensics",
    "domain_mismatch": "url_domain", "suspicious_url": "url_domain", "url_shortener": "url_domain",
    "ip_url": "url_domain", "http_not_https": "url_domain", "debunked_by_source": "claim_evidence",
    "ai_generation_indicator": "visual_analysis", "manipulation_indicator": "visual_analysis",
    "visual_inconsistency": "visual_analysis",
}  # everything else -> "message_content"
CATEGORY_CAPS = {"image_forensics": 25, "visual_analysis": 45, "url_domain": 30, "message_content": 45, "claim_evidence": 40}
BANDS = [(75, "LOW"), (45, "MEDIUM"), (0, "HIGH")]

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


def category_of(key: str) -> str:
    return CATEGORY_OF.get(key, "message_content")


def penalty_for(key: str, severity: str) -> int:
    """Points for one signal before the per-category cap (rounded half up)."""
    return int(PENALTIES.get(key, 0) * SEVERITY_MULT.get(severity, 0.3) + 0.5)


def band(score: int) -> str:
    for floor, name in BANDS:
        if score >= floor:
            return name
    return "HIGH"
