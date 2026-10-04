from tools import check_eligibility, recommend_financing


def process_financing_request(request):

    eligibility = check_eligibility(
        annual_revenue=request.annual_revenue,
        requested_amount=request.requested_amount
    )

    # Decision point
    if not eligibility["eligible"]:
        return {
            "eligibility": eligibility,
            "recommended_financing": None,
            "requires_human_review": True,
            "status": "Escalated for human review"
        }

    recommendation = recommend_financing(
        request.financing_purpose
    )

    return {
        "eligibility": eligibility,
        "recommended_financing": recommendation,
        "requires_human_review": False,
        "status": "Initial assessment completed"
    }