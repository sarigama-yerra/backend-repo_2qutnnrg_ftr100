"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional

# Core app schemas

class Cat(BaseModel):
    """
    Cats collection schema
    Collection name: "cat"
    """
    name: str = Field(..., description="Cat name")
    latitude: float = Field(..., description="Latitude for weather lookup")
    longitude: float = Field(..., description="Longitude for weather lookup")
    city: Optional[str] = Field(None, description="Optional city/label for this location")
    notes: Optional[str] = Field(None, description="Optional notes about the cat (coat length, age, etc.)")
    units: str = Field("metric", description="Units for recommendations: 'metric' or 'imperial'")


# Example schemas (kept for reference)
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
