from pydantic import BaseModel

class DomainEmail(BaseModel):
    domain: str
    email: str