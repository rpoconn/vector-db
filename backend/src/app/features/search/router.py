from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.features.search.schemas import SearchParams, SearchResponse
from app.features.search.service import SearchService, get_search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search_products(
    service: Annotated[SearchService, Depends(get_search_service)],
    params: Annotated[SearchParams, Query()],
) -> SearchResponse:
    """Products ranked by semantic similarity to `q`, optionally within one category."""
    return await service.search(params)
