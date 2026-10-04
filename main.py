from fastapi import FastAPI

from models import FinancingRequest
from orchestrator import process_financing_request
from agent import generate_financing_explanation

app = FastAPI()


@app.get("/")
def home():
    return {"message": "Financing AI Agent is running"}


@app.post("/evaluate")
def evaluate_financing(request: FinancingRequest):

    # Orchestrator decides the workflow
    result = process_financing_request(request)

    # If the case requires human review, return safely
    if result["requires_human_review"]:
        return {
            "company": request.company_name,
            "eligibility": result["eligibility"],
            "recommended_financing": None,
            "requires_human_review": True,
            "status": result["status"],
            "ai_explanation": (
                "This request requires human review before "
                "a financing option can be recommended."
            )
        }

   
    ai_explanation = generate_financing_explanation(
        company_name=request.company_name,
        industry=request.industry,
        annual_revenue=request.annual_revenue,
        employees=request.employees,
        requested_amount=request.requested_amount,
        financing_purpose=request.financing_purpose,
        eligibility=result["eligibility"],
        recommendation=result["recommended_financing"]
    )

    return {
        "company": request.company_name,
        "eligibility": result["eligibility"],
        "recommended_financing": result["recommended_financing"],
        "requires_human_review": False,
        "status": result["status"],
        "ai_explanation": ai_explanation
    }