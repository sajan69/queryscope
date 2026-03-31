from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Book
from catalog.serializers import BookSerializer
from catalog.services.books import BookListParams, evaluate_book_list


class BookListView(APIView):
    def get(self, request):
        params = BookListParams.from_querydict(request.query_params)
        _, data, cache_hit = evaluate_book_list(params)
        request.queryscope_cache_hit = cache_hit
        return Response({"data": data})


class BookDetailView(APIView):
    def get(self, request, pk: int):
        sr = request.query_params.get("select_related") == "true"
        pr = request.query_params.get("prefetch_related") == "true"
        an = request.query_params.get("annotate") == "true"

        qs = Book.objects.filter(pk=pk)
        if sr:
            qs = qs.select_related("author", "publisher")
        if pr:
            qs = qs.prefetch_related("tags", "reviews")
        if an:
            from django.db.models import Avg, Count

            qs = qs.annotate(
                avg_rating=Avg("reviews__rating"),
                review_count=Count("reviews", distinct=True),
            )

        book = qs.first()
        if book is None:
            return Response({"detail": "Not found."}, status=404)

        serializer = BookSerializer(book, context={"annotated": an})
        return Response({"data": serializer.data})
