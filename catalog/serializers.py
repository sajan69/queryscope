from rest_framework import serializers

from catalog.models import Author, Book, Review, Tag


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name", "nationality"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class ReviewSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "reviewer", "rating", "created_at"]


class BookSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    publisher = serializers.StringRelatedField()
    tags = TagSerializer(many=True, read_only=True)
    reviews = ReviewSummarySerializer(many=True, read_only=True)

    avg_rating = serializers.FloatField(read_only=True, required=False)
    review_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "isbn",
            "price",
            "pages",
            "published_at",
            "author",
            "publisher",
            "tags",
            "reviews",
            "avg_rating",
            "review_count",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get("annotated"):
            data.pop("avg_rating", None)
            data.pop("review_count", None)
        return data
