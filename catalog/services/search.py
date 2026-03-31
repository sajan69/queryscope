from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import Q

from catalog.models import Book
from catalog.serializers import BookSerializer


def evaluate_book_search(q: str, mode: str) -> tuple[list, list]:
    mode = (mode or "naive").lower()
    if not q.strip():
        return [], []

    q = q.strip()
    if mode == "naive":
        qs = Book.objects.filter(Q(title__icontains=q) | Q(author__name__icontains=q)).select_related(
            "author", "publisher"
        )
    elif mode == "btree":
        qs = Book.objects.filter(title__startswith=q).select_related("author", "publisher")
    elif mode == "fulltext":
        qs = (
            Book.objects.filter(search_vector=SearchQuery(q))
            .select_related("author", "publisher")
            .annotate(rank=SearchRank("search_vector", SearchQuery(q)))
            .order_by("-rank")
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")

    books = list(qs[:100])
    serializer = BookSerializer(books, many=True, context={"annotated": False})
    return books, serializer.data
