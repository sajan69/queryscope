from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

from catalog.managers import BookManager


class Publisher(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    country = models.CharField(max_length=100)
    founded_year = models.IntegerField()
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["country", "founded_year"], name="pub_country_year_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class Author(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    bio = models.TextField(blank=True)
    birth_year = models.IntegerField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    slug = models.SlugField(unique=True)

    def __str__(self) -> str:
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=300)
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="books")
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name="books")
    tags = models.ManyToManyField(Tag, related_name="books", blank=True)
    isbn = models.CharField(max_length=20, unique=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    pages = models.IntegerField()
    published_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    search_vector = SearchVectorField(null=True)

    objects = BookManager()

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["title"], name="book_title_btree_idx"),
            models.Index(fields=["author", "published_at"], name="book_author_date_idx"),
            models.Index(fields=["price"], name="book_price_idx"),
            GinIndex(fields=["search_vector"], name="book_search_gin_idx"),
        ]

    def __str__(self) -> str:
        return self.title


class Review(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.CharField(max_length=150)
    rating = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["book", "rating"], name="review_book_rating_idx"),
        ]
