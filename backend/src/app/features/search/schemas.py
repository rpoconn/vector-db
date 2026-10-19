from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.features.products.schemas import ProductSummary

SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class SearchParams(BaseModel):
    q: SearchText = Field(description="Free-text query, matched by meaning rather than keywords")
    category: str | None = Field(default=None, min_length=1)
    limit: int = Field(default=24, ge=1, le=100)


class SearchHit(BaseModel):
    product: ProductSummary
    score: float = Field(description="Cosine similarity between query and product, 1.0 = identical")


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]
