from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.signals import post_save
from django.dispatch import receiver

from catalog.models import Book


@receiver(post_save, sender=Book)
def update_book_search_vector(sender, instance, **kwargs):
    author_name = instance.author.name if instance.author_id else ""
    Book.objects.filter(pk=instance.pk).update(
        search_vector=SearchVector(Value(instance.title), weight="A")
        + SearchVector(Value(author_name), weight="B")
    )
