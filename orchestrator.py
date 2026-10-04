from models import FinancingRequest
from tools import check_eligibility, recommend_financing


def assessment_result(eligibility: dict, recommendation: str | None) -> dict:
    review = not eligibility["eligible"] or recommendation is None
    return {
        "eligibility": eligibility,
        "recommended_financing": None if review else recommendation,
        "requires_human_review": review,
        "status": "Escalated for human review" if review else "Initial assessment completed",
    }


def process_financing_request(request: FinancingRequest) -> dict:
    eligibility = check_eligibility(request.annual_revenue, request.requested_amount)
    recommendation = recommend_financing(request.financing_purpose) if eligibility["eligible"] else None
    return assessment_result(eligibility, recommendation)
