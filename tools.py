def check_eligibility(annual_revenue: float, requested_amount: float):
    # Demo rule only — not a real financial lending rule
    max_amount = annual_revenue * 0.30

    if requested_amount <= max_amount:
        return {
            "eligible": True,
            "message": "The SME passes the basic eligibility check."
        }

    return {
        "eligible": False,
        "message": "The requested amount is too high compared with annual revenue."
    }


def recommend_financing(financing_purpose: str):
    purpose = financing_purpose.lower()

    if "equipment" in purpose or "machine" in purpose:
        return "Equipment financing or leasing"

    elif "invoice" in purpose or "cash flow" in purpose:
        return "Invoice financing or factoring"

    elif "working capital" in purpose:
        return "Working capital loan or credit line"

    elif "expansion" in purpose or "growth" in purpose:
        return "Business growth loan"

    else:
        return "Financing option requires further analysis"