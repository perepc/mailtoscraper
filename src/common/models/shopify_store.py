from pydantic import BaseModel, EmailStr
from typing import Optional

class ShopifyStore(BaseModel):
    custom_domain: str
    shopify_domain: str
    email: Optional[EmailStr] = None 
    region: str
    lang: str