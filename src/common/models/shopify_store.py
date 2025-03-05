from pydantic import BaseModel, EmailStr
from typing import Optional

class ShopifyStore(BaseModel):
    custom_domain: str
    shopify_url: str
    email: Optional[EmailStr] = None 
    region: str
    lang: str