from catalog.views.analytics import BookAnalyticsView
from catalog.views.books import BookDetailView, BookListView
from catalog.views.bulk import BookBulkView
from catalog.views.compare import ProfileCompareView
from catalog.views.search import BookSearchView

__all__ = [
    "BookAnalyticsView",
    "BookBulkView",
    "BookDetailView",
    "BookListView",
    "BookSearchView",
    "ProfileCompareView",
]
