import random
from decimal import Decimal

from django.db.models import F
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.factories import BookFactory
from catalog.models import Author, Book, Publisher


class BookBulkView(APIView):
    def post(self, request):
        mode = request.data.get("mode", "bulk")
        count = int(request.data.get("count", 50))

        authors = list(Author.objects.all())
        publishers = list(Publisher.objects.all())
        if not authors or not publishers:
            return Response(
                {"detail": "Seed the database first (authors and publishers required)."},
                status=400,
            )

        books = [
            BookFactory.build(
                author=random.choice(authors),
                publisher=random.choice(publishers),
            )
            for _ in range(count)
        ]

        if mode == "loop":
            for book in books:
                book.save()
        else:
            Book.objects.bulk_create(books, batch_size=500)

        return Response({"ok": True, "mode": mode, "count": count})

    def patch(self, request):
        mode = request.data.get("mode", "bulk")

        if mode == "loop":
            for book in Book.objects.iterator():
                book.price = book.price * Decimal("1.10")
                book.save(update_fields=["price"])
        else:
            Book.objects.update(price=F("price") * Decimal("1.10"))

        return Response({"ok": True, "mode": mode})
