import logging

logger = logging.getLogger(__name__)


def check_eligibility(annual_revenue: float, requested_amount: float) -> dict:
    """Check the educational 30%-of-revenue heuristic, not real underwriting."""
    logger.info("Tool called: check_eligibility")
    eligible = requested_amount <= annual_revenue * 0.30
    return {
        "eligible": eligible,
        "message": (
            "The SME passes the basic demo eligibility check."
            if eligible else
            "The requested amount is too high compared with annual revenue under the demo heuristic."
        ),
    }


def recommend_financing(financing_purpose: str) -> str | None:
    """Suggest a demo category by purpose; return None for unknown purposes."""
    logger.info("Tool called: recommend_financing")
    purpose = financing_purpose.lower()
    for keywords, category in [
        (("equipment", "machine"), "Equipment financing or leasing"),
        (("invoice", "cash flow"), "Invoice financing or factoring"),
        (("working capital",), "Working capital loan or credit line"),
        (("expansion", "growth"), "Business growth loan"),
    ]:
        if any(word in purpose for word in keywords):
            return category
    return None
