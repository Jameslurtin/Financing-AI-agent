from pydantic import BaseModel, ConfigDict, Field


class FinancingRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)

    company_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=200)
    annual_revenue: float = Field(gt=0)
    employees: int = Field(gt=0, strict=True)
    requested_amount: float = Field(gt=0)
    financing_purpose: str = Field(min_length=1, max_length=1000)
