from django.db import models
from django.db.models import Avg, Count
from django.contrib.postgres.search import SearchQuery


class BookQuerySet(models.QuerySet):
    def optimized(self):
        return (
            self.select_related("author", "publisher")
            .prefetch_related("tags", "reviews")
            .annotate(
                avg_rating=Avg("reviews__rating"),
                review_count=Count("reviews", distinct=True),
            )
        )

    def with_search(self, query: str):
        return self.optimized().filter(search_vector=SearchQuery(query))


class BookManager(models.Manager):
    def get_queryset(self):
        return BookQuerySet(self.model, using=self._db)

    def optimized(self):
        return self.get_queryset().optimized()

    def with_search(self, query: str):
        return self.get_queryset().with_search(query)
