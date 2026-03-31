import json
import time

from django.conf import settings
from django.db import connection, reset_queries

from profiler.utils import build_profile


class QueryProfilerMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not settings.DEBUG:
            return self.get_response(request)

        reset_queries()
        t0 = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)

        queries = connection.queries
        cache_hit = getattr(request, "queryscope_cache_hit", False)
        profile = build_profile(queries, elapsed_ms, cache_hit=cache_hit)

        skip_body_profile = request.path.rstrip("/").endswith("/profile/compare")
        content_type = response.get("Content-Type", "")
        if (
            not skip_body_profile
            and content_type.startswith("application/json")
            and not getattr(response, "streaming", False)
        ):
            try:
                raw = response.content
                data = json.loads(raw.decode(response.charset or "utf-8"))
                if isinstance(data, dict):
                    data["_profile"] = profile
                    encoded = json.dumps(data).encode(response.charset or "utf-8")
                    response.content = encoded
                    response["Content-Length"] = str(len(encoded))
            except (json.JSONDecodeError, UnicodeDecodeError, TypeError, AttributeError):
                pass

        response["X-Query-Count"] = str(profile["query_count"])
        response["X-Query-Time-Ms"] = str(profile["total_ms"])
        response["X-Duplicate-Qs"] = str(profile["duplicate_queries"])
        return response
