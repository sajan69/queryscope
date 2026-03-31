from django.urls import path

from catalog.views.analytics import BookAnalyticsView
from catalog.views.books import BookDetailView, BookListView
from catalog.views.bulk import BookBulkView
from catalog.views.compare import ProfileCompareView
from catalog.views.search import BookSearchView

urlpatterns = [
    path("books/search/", BookSearchView.as_view()),
    path("books/analytics/", BookAnalyticsView.as_view()),
    path("books/bulk/", BookBulkView.as_view()),
    path("books/<int:pk>/", BookDetailView.as_view()),
    path("books/", BookListView.as_view()),
    path("profile/compare/", ProfileCompareView.as_view()),
]
