import json
import time

from django.db import connection, reset_queries
from django.shortcuts import render
from django.views.generic import TemplateView

from catalog.services.analytics import run_analytics
from catalog.services.books import BookListParams, evaluate_book_list, profile_book_list
from catalog.services.search import evaluate_book_search
from profiler.utils import build_profile


class DashboardView(TemplateView):
    template_name = "dashboard/index.html"


def books_partial(request):
    reset_queries()
    t0 = time.perf_counter()
    params = BookListParams.from_querydict(request.GET)
    _, data, cache_hit = evaluate_book_list(params)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    profile = build_profile(connection.queries, elapsed_ms, cache_hit=cache_hit)
    return render(
        request,
        "dashboard/partials/metrics_block.html",
        {
            "profile": profile,
            "data_json": json.dumps(data),
            "section_title": "Books list",
        },
    )


def search_partial(request):
    reset_queries()
    t0 = time.perf_counter()
    q = (request.GET.get("q") or "").strip()
    mode = request.GET.get("mode") or "naive"
    if not q:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        profile = build_profile(connection.queries, elapsed_ms, cache_hit=False)
        return render(
            request,
            "dashboard/partials/metrics_block.html",
            {
                "profile": profile,
                "data_json": "[]",
                "section_title": "Search (empty query)",
            },
        )
    try:
        _, data = evaluate_book_search(q, mode)
    except ValueError as e:
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        profile = build_profile(connection.queries, elapsed_ms, cache_hit=False)
        return render(
            request,
            "dashboard/partials/metrics_block.html",
            {
                "profile": profile,
                "data_json": "[]",
                "section_title": f"Search error: {e}",
            },
            status=400,
        )
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    profile = build_profile(connection.queries, elapsed_ms, cache_hit=False)
    return render(
        request,
        "dashboard/partials/metrics_block.html",
        {
            "profile": profile,
            "data_json": json.dumps(data),
            "section_title": f"Search ({mode})",
        },
    )


def _bool_from_post(post, key: str) -> bool:
    return post.get(key) == "on"


def analytics_partial(request):
    reset_queries()
    t0 = time.perf_counter()
    mode = (request.GET.get("mode") or "orm").lower()
    payload = run_analytics(mode)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    profile = build_profile(connection.queries, elapsed_ms, cache_hit=False)
    return render(
        request,
        "dashboard/partials/analytics_block.html",
        {
            "profile": profile,
            "data_json": json.dumps(payload, default=str),
            "section_title": f"Analytics ({mode})",
            "mode": payload["mode"],
            "summary": payload.get("summary"),
        },
    )


def compare_partial(request):
    if request.method != "POST":
        return render(request, "dashboard/partials/compare.html", {"error": "POST required"}, status=405)

    limit = int(request.POST.get("limit") or 50)

    pa = BookListParams(
        select_related=_bool_from_post(request.POST, "config_a_select_related"),
        prefetch_related=_bool_from_post(request.POST, "config_a_prefetch_related"),
        annotate=_bool_from_post(request.POST, "config_a_annotate"),
        cache=_bool_from_post(request.POST, "config_a_cache"),
        limit=limit,
    )
    pb = BookListParams(
        select_related=_bool_from_post(request.POST, "config_b_select_related"),
        prefetch_related=_bool_from_post(request.POST, "config_b_prefetch_related"),
        annotate=_bool_from_post(request.POST, "config_b_annotate"),
        cache=_bool_from_post(request.POST, "config_b_cache"),
        limit=limit,
    )

    profile_a = profile_book_list(pa)
    profile_b = profile_book_list(pb)

    t_a = profile_a["total_ms"] or 0
    t_b = profile_b["total_ms"] or 0
    time_reduction_ms = t_a - t_b
    time_reduction_pct = (time_reduction_ms / t_a * 100) if t_a else 0.0

    diff = {
        "query_count_reduction": profile_a["query_count"] - profile_b["query_count"],
        "time_reduction_ms": round(time_reduction_ms, 2),
        "time_reduction_pct": round(time_reduction_pct, 1),
    }

    return render(
        request,
        "dashboard/partials/compare.html",
        {
            "config_a": profile_a,
            "config_b": profile_b,
            "diff": diff,
        },
    )
