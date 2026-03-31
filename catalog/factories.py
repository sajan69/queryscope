import random
from datetime import date
from decimal import Decimal

import factory
from django.utils.text import slugify
from faker import Faker

from catalog.models import Author, Book, Publisher, Review, Tag

fake = Faker()


class PublisherFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Publisher

    name = factory.LazyAttribute(lambda _: fake.company())
    country = factory.LazyAttribute(lambda _: fake.country())
    founded_year = factory.LazyAttribute(lambda _: random.randint(1800, 2020))
    website = factory.LazyAttribute(lambda _: fake.url())


class AuthorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Author

    name = factory.LazyAttribute(lambda _: fake.name())
    bio = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=400))
    birth_year = factory.LazyAttribute(lambda _: random.randint(1900, 2005))
    nationality = factory.LazyAttribute(lambda _: fake.country())


class TagFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tag
        django_get_or_create = ("slug",)

    name = factory.Sequence(lambda n: f"Tag {n}")
    slug = factory.LazyAttribute(lambda o: slugify(o.name))


class BookFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Book
        skip_postgeneration_save = True

    title = factory.LazyAttribute(lambda _: fake.catch_phrase())
    author = factory.SubFactory(AuthorFactory)
    publisher = factory.SubFactory(PublisherFactory)
    isbn = factory.Sequence(lambda n: f"978{n:010d}"[:13])
    price = factory.LazyAttribute(lambda _: Decimal(str(round(random.uniform(5, 80), 2))))
    pages = factory.LazyAttribute(lambda _: random.randint(50, 900))
    published_at = factory.LazyAttribute(
        lambda _: fake.date_between_dates(date_start=date(1950, 1, 1), date_end=date.today())
    )

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for tag in extracted:
                self.tags.add(tag)
        else:
            n = random.randint(0, 4)
            for _ in range(n):
                self.tags.add(TagFactory())


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    book = factory.SubFactory(BookFactory)
    reviewer = factory.LazyAttribute(lambda _: fake.name())
    rating = factory.LazyAttribute(lambda _: random.randint(1, 5))
    body = factory.LazyAttribute(lambda _: fake.paragraph(nb_sentences=4))
