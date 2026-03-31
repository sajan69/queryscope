import hashlib

from django.db import connection, transaction


def explain_sql(sql: str | None) -> str | None:
    if not sql:
        return None
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN ANALYZE {sql}")
                return "\n".join(row[0] for row in cursor.fetchall())
    except Exception:
        return None


def build_profile(queries, elapsed_ms: float, *, cache_hit: bool = False) -> dict:
    seen = {}
    slowest_q = None
    slowest_t = 0.0

    for q in queries:
        key = hashlib.md5(q["sql"].encode(), usedforsecurity=False).hexdigest()
        seen[key] = seen.get(key, 0) + 1
        t = float(q.get("time", 0)) * 1000
        if t > slowest_t:
            slowest_t = t
            slowest_q = q["sql"]

    dups = sum(v - 1 for v in seen.values() if v > 1)
    explain = explain_sql(slowest_q)

    return {
        "query_count": len(queries),
        "total_ms": elapsed_ms,
        "duplicate_queries": dups,
        "slowest_query_ms": round(slowest_t, 2),
        "slowest_sql": slowest_q,
        "explain": explain,
        "cache_hit": cache_hit,
        "queries": [
            {"sql": q["sql"], "time_ms": round(float(q.get("time", 0)) * 1000, 2)}
            for q in queries
        ],
    }
