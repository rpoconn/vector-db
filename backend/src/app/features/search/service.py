"""Semantic product search: embed the query, find nearest products, hydrate them."""

from typing import Annotated

from fastapi import Depends, Request

from app.features.products.service import ProductService, get_product_service
from app.features.search.indexer import SearchIndex
from app.features.search.schemas import SearchHit, SearchParams, SearchResponse


class SearchService:
    def __init__(self, index: SearchIndex, products: ProductService) -> None:
        self._index = index
        self._products = products

    async def search(self, params: SearchParams) -> SearchResponse:
        where = {"category": params.category} if params.category is not None else None
        matches = await self._index.query(params.q, params.limit, where)
        scores = {match.id: match.score for match in matches}
        products = await self._products.get_by_ids([match.id for match in matches])
        return SearchResponse(
            query=params.q,
            hits=[SearchHit(product=product, score=scores[product.id]) for product in products],
        )


def get_search_index(request: Request) -> SearchIndex:
    index: SearchIndex = request.app.state.search_index
    return index


def get_search_service(
    index: Annotated[SearchIndex, Depends(get_search_index)],
    products: Annotated[ProductService, Depends(get_product_service)],
) -> SearchService:
    return SearchService(index, products)
