from pydantic import BaseModel

class FinancingRequest(BaseModel):
    company_name: str
    industry: str
    annual_revenue: float
    employees: int
    requested_amount: float
    financing_purpose: str