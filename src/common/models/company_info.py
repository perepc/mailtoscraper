from pydantic import BaseModel

class CompanyInfo(BaseModel):
    name: str
    url: str
    description: str
    products_services: str
    target_audience: str
    value_proposition: str