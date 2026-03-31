from django.urls import path

from dashboard.views import (
    DashboardView,
    analytics_partial,
    books_partial,
    compare_partial,
    search_partial,
)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="index"),
    path("partials/books/", books_partial, name="partials_books"),
    path("partials/search/", search_partial, name="partials_search"),
    path("partials/analytics/", analytics_partial, name="partials_analytics"),
    path("partials/compare/", compare_partial, name="partials_compare"),
]
