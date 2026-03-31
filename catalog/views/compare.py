from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.services.books import BookListParams, profile_book_list


def _params_from_config(cfg: dict, limit: int) -> BookListParams:
    return BookListParams(
        select_related=bool(cfg.get("select_related")),
        prefetch_related=bool(cfg.get("prefetch_related")),
        annotate=bool(cfg.get("annotate")),
        cache=bool(cfg.get("cache")),
        limit=limit,
    )


class ProfileCompareView(APIView):
    def post(self, request):
        limit = int(request.data.get("limit", 50))
        cfg_a = request.data.get("config_a") or {}
        cfg_b = request.data.get("config_b") or {}

        pa = _params_from_config(cfg_a, limit)
        pb = _params_from_config(cfg_b, limit)

        profile_a = profile_book_list(pa)
        profile_b = profile_book_list(pb)

        t_a = profile_a["total_ms"] or 0
        t_b = profile_b["total_ms"] or 0
        time_reduction_ms = t_a - t_b
        time_reduction_pct = (time_reduction_ms / t_a * 100) if t_a else 0.0

        return Response(
            {
                "config_a": profile_a,
                "config_b": profile_b,
                "diff": {
                    "query_count_reduction": profile_a["query_count"] - profile_b["query_count"],
                    "time_reduction_ms": round(time_reduction_ms, 2),
                    "time_reduction_pct": round(time_reduction_pct, 1),
                },
            }
        )
