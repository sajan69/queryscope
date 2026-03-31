from django.contrib import admin

from catalog.models import Author, Book, Publisher, Review, Tag


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "founded_year")
    search_fields = ("name",)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("name", "nationality", "birth_year")
    search_fields = ("name",)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "publisher", "price", "published_at")
    list_filter = ("published_at", "publisher")
    search_fields = ("title", "isbn")
    inlines = [ReviewInline]
    filter_horizontal = ("tags",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("book", "reviewer", "rating", "created_at")
