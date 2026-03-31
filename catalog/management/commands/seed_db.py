import random

from django.core.management.base import BaseCommand

from catalog.factories import AuthorFactory, BookFactory, PublisherFactory, ReviewFactory


class Command(BaseCommand):
    help = "Seed the database with bookstore catalog data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--books",
            type=int,
            default=200,
            help="Number of books to create (default 200).",
        )
        parser.add_argument(
            "--reviews-per-book",
            type=int,
            default=10,
            help="Max reviews per book; actual count is random 1..max (default 10).",
        )

    def handle(self, *args, **options):
        n_books = options["books"]
        max_reviews = options["reviews_per_book"]

        publishers = PublisherFactory.create_batch(10)
        authors = AuthorFactory.create_batch(20)

        books = [
            BookFactory(
                author=random.choice(authors),
                publisher=random.choice(publishers),
            )
            for _ in range(n_books)
        ]

        for book in books:
            n = random.randint(1, max_reviews)
            ReviewFactory.create_batch(n, book=book)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(publishers)} publishers, {len(authors)} authors, "
                f"{len(books)} books with reviews."
            )
        )
