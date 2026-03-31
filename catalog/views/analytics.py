from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.services.analytics import run_analytics


class BookAnalyticsView(APIView):
    def get(self, request):
        mode = (request.query_params.get("mode") or "orm").lower()
        payload = run_analytics(mode)
        return Response(payload)
