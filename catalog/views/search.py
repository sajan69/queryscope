from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.services.search import evaluate_book_search


class BookSearchView(APIView):
    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        mode = (request.query_params.get("mode") or "naive").lower()
        index_param = request.query_params.get("index", "true").lower() == "true"

        if not q:
            return Response(
                {
                    "data": [],
                    "meta": {
                        "mode": mode,
                        "index_param": index_param,
                        "note": "pg_hint_plan not installed; planner hints are informational only.",
                    },
                }
            )

        try:
            _, data = evaluate_book_search(q, mode)
        except ValueError as e:
            return Response({"detail": str(e)}, status=400)

        return Response(
            {
                "data": data,
                "meta": {
                    "mode": mode,
                    "index_param": index_param,
                    "note": "pg_hint_plan not installed; index_param reserved for future hints.",
                },
            }
        )
