from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from django.core.cache import cache as django_cache
from django.db import connection, reset_queries
from django.db.models import Avg, Count

from catalog.models import Book
from catalog.serializers import BookSerializer
from profiler.utils import build_profile


@dataclass(frozen=True)
class BookListParams:
    select_related: bool
    prefetch_related: bool
    annotate: bool
    cache: bool
    limit: int

    @classmethod
    def from_querydict(cls, q: Any) -> BookListParams:
        def truthy(key: str) -> bool:
            return str(q.get(key, "")).lower() == "true"

        limit = int(q.get("limit", 50))
        return cls(
            select_related=truthy("select_related"),
            prefetch_related=truthy("prefetch_related"),
            annotate=truthy("annotate"),
            cache=truthy("cache"),
            limit=limit,
        )


def _build_queryset(params: BookListParams):
    qs = Book.objects.all()[: params.limit]
    if params.select_related:
        qs = qs.select_related("author", "publisher")
    if params.prefetch_related:
        qs = qs.prefetch_related("tags", "reviews")
    if params.annotate:
        qs = qs.annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
        )
    return qs


def evaluate_book_list(params: BookListParams) -> tuple[list, list, bool]:
    """Returns (books instances, serialized data list, cache_hit)."""
    qs = _build_queryset(params)
    cache_hit = False
    if params.cache:
        cache_key = (
            f"books:{params.select_related}:{params.prefetch_related}:"
            f"{params.annotate}:{params.limit}"
        )
        books = django_cache.get(cache_key)
        if books is None:
            books = list(qs)
            django_cache.set(cache_key, books, 60)
        else:
            cache_hit = True
    else:
        books = list(qs)

    serializer = BookSerializer(books, many=True, context={"annotated": params.annotate})
    return books, serializer.data, cache_hit


def profile_book_list(params: BookListParams) -> dict:
    """Run list query in isolation; resets SQL log first."""
    reset_queries()
    t0 = time.perf_counter()
    _, _, cache_hit = evaluate_book_list(params)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    return build_profile(connection.queries, elapsed_ms, cache_hit=cache_hit)
