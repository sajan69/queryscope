from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, F, Max, Min, Window
from django.db.models.functions import Rank

from catalog.models import Book


def run_analytics(mode: str) -> dict[str, Any]:
    """Run analytics in `python` or `orm` mode; returns serializable dict (no Response)."""
    mode = (mode or "orm").lower()

    if mode == "python":
        books = Book.objects.prefetch_related("reviews").select_related("author", "publisher")
        result = []
        for book in books:
            ratings = [r.rating for r in book.reviews.all()]
            result.append(
                {
                    "title": book.title,
                    "avg_rating": sum(ratings) / len(ratings) if ratings else 0.0,
                    "review_count": len(ratings),
                    "max_rating": max(ratings) if ratings else None,
                    "min_rating": min(ratings) if ratings else None,
                }
            )
        return {"mode": "python", "books": result, "summary": None}

    books_qs = (
        Book.objects.annotate(
            avg_rating=Avg("reviews__rating"),
            review_count=Count("reviews", distinct=True),
            max_rating=Max("reviews__rating"),
            min_rating=Min("reviews__rating"),
            price_rank=Window(expression=Rank(), order_by=F("price").asc()),
        )
        .select_related("author", "publisher")
        .order_by("id")
    )

    summary = Book.objects.aggregate(
        total_books=Count("id"),
        avg_price=Avg("price"),
        total_reviews=Count("reviews"),
        avg_rating_all=Avg("reviews__rating"),
    )

    books_data = [
        {
            "title": b.title,
            "avg_rating": float(b.avg_rating) if b.avg_rating is not None else None,
            "review_count": b.review_count,
            "max_rating": b.max_rating,
            "min_rating": b.min_rating,
            "price_rank": b.price_rank,
            "author": b.author.name,
            "publisher": str(b.publisher),
        }
        for b in books_qs
    ]

    summary_out = {k: float(v) if isinstance(v, Decimal) else v for k, v in summary.items()}

    return {"mode": "orm", "books": books_data, "summary": summary_out}
