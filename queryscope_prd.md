# QueryScope — Technical PRD

**Django ORM Profiling Dashboard**


|                   |                                       |
| ----------------- | ------------------------------------- |
| **Version**       | 1.0                                   |
| **Status**        | Draft                                 |
| **Date**          | March 2026                            |
| **Document type** | Technical PRD                         |
| **Project code**  | QS-2026                               |
| **Stack**         | Django 5.x, DRF, PostgreSQL 15+, HTMX |
| **Author**        | Engineering Lead                      |
| **Est. duration** | 4–5 weeks (solo developer)            |


> **Purpose:** This PRD defines the complete technical specification for QueryScope — an interactive Django ORM profiling dashboard. It showcases advanced ORM patterns, query optimization, database indexing, and real-time profiling using a simple bookstore catalog domain. Every section includes implementation-ready details so a developer can begin coding immediately.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Data models](#2-data-models)
3. [API endpoints](#3-api-endpoints)
4. [QueryProfilerMiddleware](#4-queryprofiler-middleware)
5. [Dashboard UI](#5-dashboard-ui)
6. [ORM patterns — implementation reference](#6-orm-patterns--implementation-reference)
7. [Serializers](#7-serializers)
8. [Project structure](#8-project-structure)
9. [Local setup](#9-local-setup)
10. [Testing strategy](#10-testing-strategy)
11. [Implementation milestones](#11-implementation-milestones)
12. [Appendix](#12-appendix)

---

## 1. Project overview

### 1.1 Vision

QueryScope is a single Django application that serves two purposes simultaneously: it is a functional REST API for a bookstore catalog, and it is a live laboratory where users can observe, compare, and understand the performance impact of Django ORM optimization techniques in real time.

The core interaction is simple — a user toggles ORM features on or off in a browser UI, hits a button, and immediately sees query count, execution time, SQL log, and PostgreSQL `EXPLAIN ANALYZE` output. No separate tooling, no copying URLs — everything is in one page.

### 1.2 Goals

- Demonstrate N+1 query problems and their resolution using `select_related` and `prefetch_related`
- Show the measurable impact of database indexes (B-tree, GIN, composite) using `EXPLAIN ANALYZE`
- Teach `annotate`, `aggregate`, `F()` expressions, and bulk operations through side-by-side comparison
- Provide a reusable `QueryProfilerMiddleware` that attaches profiling data to every API response
- Build an interactive Django templates dashboard that makes ORM behavior visible without developer tools

### 1.3 Non-goals

- This is not a production-ready application — it is a profiling and demonstration tool
- Authentication, user management, and multi-tenancy are out of scope
- Frontend frameworks (React, Vue) are explicitly excluded — Django templates + HTMX only
- Celery, background tasks, and async views are out of scope for v1

### 1.4 Tech stack


| Layer             | Technology              | Version   | Purpose                                    |
| ----------------- | ----------------------- | --------- | ------------------------------------------ |
| Backend framework | Django                  | 5.1+      | Views, ORM, middleware, templates          |
| API layer         | Django REST Framework   | 3.15+     | Serializers, ViewSets, routing             |
| Database          | PostgreSQL              | 15+       | `EXPLAIN ANALYZE`, GIN indexes, pg_stat    |
| Frontend          | Django templates + HTMX | htmx 1.9+ | Dynamic UI without a full JS framework     |
| Profiling         | django-debug-toolbar    | 4.x       | SQL panel, cache panel, timer              |
| Profiling (deep)  | django-silk             | 5.x       | Per-request SQL breakdown, history         |
| Caching           | Django cache (Redis)    | Redis 7+  | QuerySet cache demonstration               |
| Dev tooling       | factory_boy, Faker      | latest    | Realistic seed data generation             |
| Testing           | pytest-django           | latest    | Unit + integration tests for each endpoint |


---

## 2. Data models

### 2.1 Overview

The domain is a bookstore catalog. The schema is intentionally minimal — four core models — but structured to expose every interesting ORM pattern: foreign keys for `select_related`, reverse relations for `prefetch_related`, M2M for batch fetching, and numeric fields for annotation and aggregation.

### 2.2 Model definitions

#### Publisher

```python
class Publisher(models.Model):
    name         = models.CharField(max_length=200, db_index=True)
    country      = models.CharField(max_length=100)
    founded_year = models.IntegerField()
    website      = models.URLField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['country', 'founded_year'], name='pub_country_year_idx'),
        ]
```

#### Author

```python
class Author(models.Model):
    name        = models.CharField(max_length=200, db_index=True)
    bio         = models.TextField(blank=True)
    birth_year  = models.IntegerField(null=True, blank=True)
    nationality = models.CharField(max_length=100, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
```

#### Tag

```python
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    slug = models.SlugField(unique=True)
```

#### Book (central model)

```python
class Book(models.Model):
    title         = models.CharField(max_length=300)
    author        = models.ForeignKey(Author, on_delete=models.CASCADE, related_name='books')
    publisher     = models.ForeignKey(Publisher, on_delete=models.CASCADE, related_name='books')
    tags          = models.ManyToManyField(Tag, related_name='books', blank=True)
    isbn          = models.CharField(max_length=20, unique=True)
    price         = models.DecimalField(max_digits=8, decimal_places=2)
    pages         = models.IntegerField()
    published_at  = models.DateField()
    created_at    = models.DateTimeField(auto_now_add=True)

    # Full-text search vector (populated by signal)
    search_vector = SearchVectorField(null=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['author', 'published_at'], name='book_author_date_idx'),
            models.Index(fields=['price'], name='book_price_idx'),
            GinIndex(fields=['search_vector'], name='book_search_gin_idx'),
        ]
```

#### Review

```python
class Review(models.Model):
    book       = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='reviews')
    reviewer   = models.CharField(max_length=150)
    rating     = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['book', 'rating'], name='review_book_rating_idx'),
        ]
```

### 2.3 Custom manager

```python
class BookManager(models.Manager):
    def optimized(self):
        """Returns fully-joined queryset — author, publisher, tags, review stats."""
        return (
            self.get_queryset()
            .select_related('author', 'publisher')
            .prefetch_related('tags', 'reviews')
            .annotate(
                avg_rating=Avg('reviews__rating'),
                review_count=Count('reviews', distinct=True),
            )
        )

    def with_search(self, query):
        """Full-text search using GIN index."""
        return self.optimized().filter(search_vector=SearchQuery(query))
```

### 2.4 Seed data

```python
# management/commands/seed_db.py
class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        publishers = PublisherFactory.create_batch(10)
        authors    = AuthorFactory.create_batch(20)
        books      = [
            BookFactory(
                author=random.choice(authors),
                publisher=random.choice(publishers)
            )
            for _ in range(200)
        ]
        for book in books:
            ReviewFactory.create_batch(random.randint(1, 15), book=book)
```

---

## 3. API endpoints

### 3.1 URL structure

```python
# urls.py
urlpatterns = [
    path('api/books/',             BookListView.as_view()),
    path('api/books/<int:pk>/',    BookDetailView.as_view()),
    path('api/books/search/',      BookSearchView.as_view()),
    path('api/books/analytics/',   BookAnalyticsView.as_view()),
    path('api/books/bulk/',        BookBulkView.as_view()),
    path('api/profile/compare/',   ProfileCompareView.as_view()),
    path('dashboard/',             DashboardView.as_view()),
]
```

### 3.2 Endpoint: `/api/books/`

This is the primary teaching endpoint. It accepts query parameters that map directly to ORM toggles, executes the queryset with the selected optimizations, and returns both the book data and a profiling summary.

#### Query parameters


| Parameter          | Type | Default | Effect                                                                             |
| ------------------ | ---- | ------- | ---------------------------------------------------------------------------------- |
| `select_related`   | bool | false   | Adds `.select_related('author', 'publisher')` — eliminates FK N+1                  |
| `prefetch_related` | bool | false   | Adds `.prefetch_related('tags', 'reviews')` — eliminates reverse FK N+1            |
| `annotate`         | bool | false   | Adds `.annotate(avg_rating=Avg(), review_count=Count())` — moves aggregation to DB |
| `index`            | bool | true    | Simulates index presence by toggling query hint via pg_hint_plan                   |
| `cache`            | bool | false   | Wraps queryset in `cache.get_or_set()` with 60s TTL                                |
| `limit`            | int  | 50      | Number of books returned (10 / 50 / 200 for dataset size demo)                     |


#### View implementation

```python
class BookListView(APIView):
    def get(self, request):
        sr    = request.query_params.get('select_related') == 'true'
        pr    = request.query_params.get('prefetch_related') == 'true'
        an    = request.query_params.get('annotate') == 'true'
        cache = request.query_params.get('cache') == 'true'
        limit = int(request.query_params.get('limit', 50))

        qs = Book.objects.all()[:limit]

        if sr:  qs = qs.select_related('author', 'publisher')
        if pr:  qs = qs.prefetch_related('tags', 'reviews')
        if an:  qs = qs.annotate(
                    avg_rating=Avg('reviews__rating'),
                    review_count=Count('reviews', distinct=True)
                )

        if cache:
            cache_key = f'books:{sr}:{pr}:{an}:{limit}'
            books = django_cache.get(cache_key)
            if books is None:
                books = list(qs)  # Force evaluation
                django_cache.set(cache_key, books, 60)
        else:
            books = list(qs)

        serializer = BookSerializer(books, many=True, context={'annotated': an})
        return Response(serializer.data)
```

#### Response structure

```json
{
  "data": [ "...book objects..." ],
  "_profile": {
    "query_count": 51,
    "total_ms": 342,
    "duplicate_queries": 50,
    "slowest_query_ms": 12,
    "slowest_sql": "SELECT * FROM books_author WHERE id = 7",
    "cache_hit": false,
    "explain": "Seq Scan on books_author (cost=0.00..1.50 rows=1)"
  }
}
```

---

### 3.3 Endpoint: `/api/books/search/`

Demonstrates the difference between naive `ILIKE` search, B-tree index search, and PostgreSQL full-text search using a GIN index on a `SearchVectorField`.

#### Query parameters


| Parameter | Type                           | Effect                                                    |
| --------- | ------------------------------ | --------------------------------------------------------- |
| `q`       | string                         | Search term — applied to title and author name            |
| `mode`    | `naive` | `btree` | `fulltext` | Controls which search strategy is used                    |
| `index`   | bool                           | Enables or disables index use (via pg_hint_plan for demo) |


#### Mode 1: naive (Seq Scan baseline)

```python
# No index — forces sequential scan on title
qs = Book.objects.filter(title__icontains=query)
# EXPLAIN output: Seq Scan on books_book (cost=0..8420 rows=3)
```

#### Mode 2: btree (B-tree index on title)

```python
# Migration: models.Index(fields=['title'], name='book_title_btree_idx')
# Note: B-tree only helps with prefix matches (title__startswith)
# ILIKE with a leading wildcard still causes Seq Scan
qs = Book.objects.filter(title__startswith=query)
# EXPLAIN: Index Scan using book_title_btree_idx (cost=0..12 rows=3)
```

#### Mode 3: fulltext (GIN index + tsvector)

```python
# SearchVectorField populated via post_save signal:
# @receiver(post_save, sender=Book)
# def update_search_vector(sender, instance, **kwargs):
#     Book.objects.filter(pk=instance.pk).update(
#         search_vector=SearchVector('title', weight='A') +
#                       SearchVector('author__name', weight='B')
#     )

qs = (
    Book.objects
    .filter(search_vector=SearchQuery(query))
    .annotate(rank=SearchRank('search_vector', SearchQuery(query)))
    .order_by('-rank')
)
# EXPLAIN: Bitmap Heap Scan on books_book (cost=12..48 rows=8)
#          -> Bitmap Index Scan on book_search_gin_idx
```

---

### 3.4 Endpoint: `/api/books/analytics/`

Teaches the difference between Python-side aggregation (loading all objects into memory) vs pushing computation to the database via `annotate` and `aggregate`.

#### Mode: python (anti-pattern for comparison)

```python
# BAD — loads all reviews into Python memory
books = Book.objects.prefetch_related('reviews').all()
result = []
for book in books:
    ratings = [r.rating for r in book.reviews.all()]
    result.append({
        'title': book.title,
        'avg_rating': sum(ratings) / len(ratings) if ratings else 0,
        'review_count': len(ratings),
    })
```

#### Mode: orm (correct pattern)

```python
# GOOD — single query, computation in PostgreSQL
books = Book.objects.annotate(
    avg_rating   = Avg('reviews__rating'),
    review_count = Count('reviews', distinct=True),
    max_rating   = Max('reviews__rating'),
    min_rating   = Min('reviews__rating'),
    price_rank   = Window(
        expression=Rank(),
        order_by=F('price').asc()
    )
).select_related('author', 'publisher')

# Additional aggregate over the full table:
summary = Book.objects.aggregate(
    total_books    = Count('id'),
    avg_price      = Avg('price'),
    total_reviews  = Count('reviews'),
    avg_rating_all = Avg('reviews__rating'),
)
```

---

### 3.5 Endpoint: `/api/books/bulk/`

Demonstrates the write-side ORM — the dramatic performance difference between a loop of individual `.save()` calls vs `bulk_create` and `bulk_update`.

```python
class BookBulkView(APIView):
    def post(self, request):
        mode  = request.data.get('mode', 'bulk')  # 'loop' | 'bulk'
        count = int(request.data.get('count', 50))
        books = [BookFactory.build() for _ in range(count)]

        if mode == 'loop':
            # BAD: count INSERT statements
            for book in books:
                book.save()
        else:
            # GOOD: 1 INSERT with VALUES (...), (...), ...
            Book.objects.bulk_create(books, batch_size=500)

    def patch(self, request):
        mode = request.data.get('mode', 'bulk')
        # Apply a 10% price increase
        if mode == 'loop':
            for book in Book.objects.all():
                book.price = book.price * Decimal('1.10')
                book.save(update_fields=['price'])
        else:
            # 1 UPDATE statement using F() — no race condition
            Book.objects.update(price=F('price') * Decimal('1.10'))
```

---

### 3.6 Endpoint: `/api/profile/compare/`

Accepts two sets of ORM parameters, executes both, and returns a side-by-side diff. This powers the dashboard's compare view.

```json
// POST /api/profile/compare/
{
  "config_a": { "select_related": false, "prefetch_related": false, "annotate": false },
  "config_b": { "select_related": true,  "prefetch_related": true,  "annotate": true  },
  "limit": 50
}

// Response:
{
  "config_a": { "...profile..." },
  "config_b": { "...profile..." },
  "diff": {
    "query_count_reduction": 98,
    "time_reduction_ms": 290,
    "time_reduction_pct": 85.3
  }
}
```

---

## 4. QueryProfiler Middleware

### 4.1 Purpose

The middleware wraps every request, captures the SQL log from `connection.queries`, analyzes it for N+1 patterns and duplicates, runs `EXPLAIN ANALYZE` on the slowest query, and attaches the full profile to the response as a JSON header and as a `_profile` key in the response body.

### 4.2 Full implementation

```python
import time, json, hashlib
from django.db import connection, reset_queries
from django.conf import settings


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
        profile = self._analyze(queries, elapsed_ms)

        # Attach to JSON response body if applicable
        if response.get('Content-Type', '').startswith('application/json'):
            data = json.loads(response.content)
            if isinstance(data, dict):
                data['_profile'] = profile
                response.content = json.dumps(data).encode()
                response['Content-Length'] = len(response.content)

        # Always attach as headers (readable by dashboard JS)
        response['X-Query-Count']   = profile['query_count']
        response['X-Query-Time-Ms'] = profile['total_ms']
        response['X-Duplicate-Qs']  = profile['duplicate_queries']
        return response

    def _analyze(self, queries, elapsed_ms):
        seen     = {}
        slowest_q = None
        slowest_t = 0

        for q in queries:
            key = hashlib.md5(q['sql'].encode()).hexdigest()
            seen[key] = seen.get(key, 0) + 1
            t = float(q.get('time', 0)) * 1000
            if t > slowest_t:
                slowest_t = t
                slowest_q = q['sql']

        dups    = sum(v - 1 for v in seen.values() if v > 1)
        explain = self._explain(slowest_q) if slowest_q else None

        return {
            'query_count':       len(queries),
            'total_ms':          elapsed_ms,
            'duplicate_queries': dups,
            'slowest_query_ms':  round(slowest_t, 2),
            'slowest_sql':       slowest_q,
            'explain':           explain,
            'queries': [
                {'sql': q['sql'], 'time_ms': round(float(q.get('time', 0)) * 1000, 2)}
                for q in queries
            ],
        }

    def _explain(self, sql):
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'EXPLAIN ANALYZE {sql}')
                return '\n'.join(row[0] for row in cursor.fetchall())
        except Exception:
            return None
```

### 4.3 Settings integration

```python
# settings.py
MIDDLEWARE = [
    ...
    'queryscope.middleware.QueryProfilerMiddleware',  # After SecurityMiddleware
]

# Required for connection.queries to be populated
DEBUG = True

# Optional: log all queries to console during development
LOGGING = {
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        }
    }
}
```

---

## 5. Dashboard UI

### 5.1 Layout

The dashboard is a single Django template view at `/dashboard/`. All interactivity is driven by HTMX for partial page updates — no JavaScript framework needed. The layout has three zones:

- **Left panel** — ORM toggle controls
- **Center panel** — live metrics (query count, time, duplicates, bar chart)
- **Right panel** — SQL log and EXPLAIN ANALYZE output

### 5.2 Toggle panel

Each toggle maps directly to an API query parameter. When toggled, HTMX fires a GET to `/api/books/` with the current configuration and swaps the metrics zone without a page reload.


| Toggle                 | API param                     | What it teaches                           | Default |
| ---------------------- | ----------------------------- | ----------------------------------------- | ------- |
| `select_related`       | `select_related=true`         | Eliminates FK lookups with JOIN           | OFF     |
| `prefetch_related`     | `prefetch_related=true`       | Batches reverse FK + M2M fetches          | OFF     |
| Annotate (avg + count) | `annotate=true`               | Pushes AVG/COUNT into SQL GROUP BY        | OFF     |
| db_index / GIN         | `index=true`                  | Shows Seq Scan vs Index Scan in EXPLAIN   | ON      |
| QuerySet cache         | `cache=true`                  | Cache hit/miss via Django cache framework | OFF     |
| Dataset size           | `limit=10|50|200`             | Scales N+1 penalty to show magnitude      | 50      |
| Scenario tab           | `mode=books|search|analytics` | Switches endpoint context                 | books   |


### 5.3 Metrics zone

Updated on every toggle via HTMX swap. Displays:

- Total SQL query count (red if > 5, green if ≤ 3)
- Response time in ms with trend arrow vs previous request
- Duplicate query count (N+1 indicator)
- Cache hit / miss badge
- Animated bar chart: breakdown by category (main, author N+1, review N+1, aggregate)

### 5.4 SQL log panel

Color-coded query list from the profiler:

- 🔴 **Red border** — duplicate query (N+1 signature)
- 🟡 **Yellow border** — slow query (> 10ms)
- 🟢 **Green border** — optimized (joined, batched, or cached)

Each row shows: truncated query text, execution time, and a badge (`DUP` / `SLOW` / `JOIN` / `BATCH` / `CACHE HIT`).

### 5.5 EXPLAIN ANALYZE panel

Raw PostgreSQL `EXPLAIN ANALYZE` output for the slowest query in the last request. Syntax-highlighted:

- **Red** — `Seq Scan` (unindexed, expensive)
- **Green** — `Index Scan` or `Bitmap Index Scan`
- **Gray** — planning and timing summary lines

### 5.6 Compare mode

Splits the metrics zone into Config A and Config B columns. Both are configurable independently. Hitting **Compare** fires `POST /api/profile/compare/` and shows diff metrics: query count reduction, time reduction in ms, time reduction as a percentage.

### 5.7 HTMX integration

```html
{# dashboard.html #}
<input type="checkbox" id="t-sr"
       hx-get="/api/books/"
       hx-include="#orm-config-form"
       hx-target="#metrics-zone"
       hx-trigger="change"
       hx-swap="innerHTML">

<form id="orm-config-form">
  <input type="hidden" name="select_related"  id="v-sr"    value="false">
  <input type="hidden" name="prefetch_related" id="v-pr"   value="false">
  <input type="hidden" name="annotate"         id="v-an"   value="false">
  <input type="hidden" name="limit"            id="v-limit" value="50">
</form>
```

---

## 6. ORM patterns — implementation reference

### 6.1 `select_related` (SQL JOIN)

`select_related` resolves `ForeignKey` and `OneToOneField` traversals in a single SQL JOIN instead of issuing one query per object. Use it when you know you will access a related object for every row in the queryset.

#### Without `select_related` — N+1

```python
# 1 query to fetch books, then 1 per book for author = 51 total
books = Book.objects.all()[:50]
for book in books:
    print(book.author.name)  # triggers SELECT each time
```

#### With `select_related`

```python
# 1 JOIN query: SELECT book.*, author.* FROM books JOIN authors ON ...
books = Book.objects.select_related('author', 'publisher').all()[:50]
for book in books:
    print(book.author.name)  # already loaded, no SQL
```

#### Depth traversal

```python
# Traverse multiple levels in one query:
Book.objects.select_related('author__nationality_obj', 'publisher__country_obj')

# Restrict to specific fields to avoid over-fetching:
Book.objects.select_related('author').only(
    'title', 'author__name', 'author__nationality'
)
```

---

### 6.2 `prefetch_related` (batch fetch)

`prefetch_related` handles reverse FK relations and `ManyToManyFields`. It issues a separate query per relation but fetches all related objects in one batch, then joins them in Python. Never use it for simple `ForeignKey` fields — use `select_related` there.

```python
# 3 queries total: books + all reviews IN (...) + all tags IN (...)
books = Book.objects.prefetch_related('reviews', 'tags').all()[:50]

# Custom Prefetch with filtering:
from django.db.models import Prefetch

good_reviews = Review.objects.filter(rating__gte=4)
books = Book.objects.prefetch_related(
    Prefetch('reviews', queryset=good_reviews, to_attr='good_reviews'),
    Prefetch('tags'),
)
# Access as: book.good_reviews (list, not queryset)
```

---

### 6.3 `annotate` and `aggregate`

```python
from django.db.models import Avg, Count, Max, Min, Sum, F, Q

# Per-object annotation — adds a computed column to each row:
books = Book.objects.annotate(
    avg_rating   = Avg('reviews__rating'),
    review_count = Count('reviews', distinct=True),
    is_expensive = Q(price__gte=30),
)

# Table-level aggregate — single scalar result:
Book.objects.aggregate(
    total     = Count('id'),
    avg_price = Avg('price'),
)

# Conditional annotation using Case/When:
from django.db.models import Case, When, Value

Book.objects.annotate(
    rating_tier=Case(
        When(avg_rating__gte=4, then=Value('high')),
        When(avg_rating__gte=2, then=Value('medium')),
        default=Value('low'),
    )
)
```

---

### 6.4 `F()` expressions

`F()` lets you reference model field values in queries without loading them into Python. This avoids race conditions in concurrent updates and keeps computation in the database.

```python
# Apply 10% price increase — 1 UPDATE, no Python load:
Book.objects.update(price=F('price') * 1.10)

# Compare two fields on the same model:
Book.objects.filter(pages__gt=F('published_at__year'))

# Increment a counter atomically — safe under concurrent requests:
Book.objects.filter(pk=pk).update(view_count=F('view_count') + 1)
```

---

### 6.5 Database indexes


| Index type       | Use case                        | Django syntax                                 | EXPLAIN shows                    |
| ---------------- | ------------------------------- | --------------------------------------------- | -------------------------------- |
| B-tree (default) | Equality, range, ORDER BY       | `models.Index(fields=['title'])`              | `Index Scan` / `Index Only Scan` |
| Composite B-tree | Multi-column WHERE clause       | `models.Index(fields=['author','date'])`      | `Index Scan using compound_idx`  |
| GIN              | Full-text search, JSONB, arrays | `GinIndex(fields=['search_vector'])`          | `Bitmap Index Scan`              |
| Partial index    | Filtered subset                 | `models.Index(..., condition=Q(active=True))` | `Index Scan with filter`         |
| `db_index=True`  | Quick single-column index       | `CharField(db_index=True)`                    | `Index Scan`                     |


---

### 6.6 `bulk_create` and `bulk_update`

```python
# bulk_create: 1 INSERT with multiple VALUES rows
Book.objects.bulk_create(book_objects, batch_size=500)
# SQL: INSERT INTO books_book (...) VALUES (...), (...), (...)

# bulk_update: 1 UPDATE per changed field (not per object)
for book in books:
    book.price = book.price * Decimal('1.05')
Book.objects.bulk_update(books, ['price'], batch_size=500)

# update_or_create: INSERT ON CONFLICT DO UPDATE
Book.objects.update_or_create(
    isbn=isbn,
    defaults={'price': new_price, 'title': new_title}
)
```

---

## 7. Serializers

```python
class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Author
        fields = ['id', 'name', 'nationality']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Tag
        fields = ['id', 'name', 'slug']


class ReviewSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model  = Review
        fields = ['id', 'reviewer', 'rating', 'created_at']


class BookSerializer(serializers.ModelSerializer):
    author    = AuthorSerializer(read_only=True)
    publisher = serializers.StringRelatedField()
    tags      = TagSerializer(many=True, read_only=True)
    reviews   = ReviewSummarySerializer(many=True, read_only=True)

    # Annotated fields — present only when ?annotate=true
    avg_rating   = serializers.FloatField(read_only=True, required=False)
    review_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model  = Book
        fields = [
            'id', 'title', 'isbn', 'price', 'pages', 'published_at',
            'author', 'publisher', 'tags', 'reviews',
            'avg_rating', 'review_count',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not self.context.get('annotated'):
            data.pop('avg_rating', None)
            data.pop('review_count', None)
        return data
```

---

## 8. Project structure

```
queryscope/
├── manage.py
├── requirements.txt
├── queryscope/                  # Django project settings
│   ├── settings/
│   │   ├── base.py
│   │   └── dev.py
│   ├── urls.py
│   └── wsgi.py
├── catalog/                     # Main app
│   ├── models.py
│   ├── serializers.py
│   ├── views/
│   │   ├── books.py             # BookListView, BookDetailView
│   │   ├── search.py            # BookSearchView
│   │   ├── analytics.py         # BookAnalyticsView
│   │   ├── bulk.py              # BookBulkView
│   │   └── compare.py           # ProfileCompareView
│   ├── managers.py              # BookManager
│   ├── signals.py               # search_vector update
│   ├── factories.py             # factory_boy definitions
│   ├── admin.py
│   └── migrations/
├── profiler/                    # Profiling infrastructure
│   ├── middleware.py            # QueryProfilerMiddleware
│   └── utils.py                 # explain(), detect_n1()
├── dashboard/                   # Template views
│   ├── views.py                 # DashboardView
│   └── templates/
│       └── dashboard/
│           ├── base.html
│           ├── index.html
│           └── partials/
│               ├── metrics.html
│               ├── sql_log.html
│               └── explain.html
├── management/
│   └── commands/
│       └── seed_db.py
└── tests/
    ├── test_books.py
    ├── test_middleware.py
    └── test_profiler.py
```

---

## 9. Local setup (uv native workflow)

## 9.1 Prerequisites

- Python 3.12+
- PostgreSQL 15+
- Redis 7+ (optional)
- uv package manager

Install uv:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

verify:

```
uv --version
```

---

## 9.2 Project initialization

### 1. Clone repository

```
git clone https://github.com/yourname/queryscope.git
cd queryscope
```

---

### 2. Create virtual environment

```
uv venv
```

activate:

mac/linux

```
source .venv/bin/activate
```

windows

```
.venv\Scripts\activate
```

---

### 3. Initialize project metadata

```
uv init
```

This creates:

```
pyproject.toml
```

---

### 4. Add dependencies

```
uv add django djangorestframework psycopg2-binary \
django-debug-toolbar django-silk \
factory-boy faker django-redis python-decouple \
pytest-django pytest-factoryboy
```

dev dependencies:

```
uv add --dev pytest pytest-django pytest-factoryboy
```

---

### 5. Lock dependencies

```
uv lock
```

This generates:

```
uv.lock
```

Install from lock:

```
uv sync
```

---

## 9.3 pyproject.toml

```
[project]
name = "queryscope"
version = "0.1.0"
description = "Django ORM profiling dashboard"
readme = "README.md"
requires-python = ">=3.12"

dependencies = [
    "django>=5.1",
    "djangorestframework>=3.15",
    "psycopg2-binary>=2.9",
    "django-debug-toolbar>=4.0",
    "django-silk>=5.0",
    "factory-boy>=3.3",
    "faker>=24.0",
    "django-redis>=5.4",
    "python-decouple>=3.8",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-django>=4.8",
    "pytest-factoryboy>=2.6"
]

[tool.uv]
package = false
```

---

## 9.4 Environment variables

```
.env
```

```
DATABASE_URL=postgresql://localhost/queryscope
REDIS_URL=redis://localhost:6379/0
DEBUG=True
SECRET_KEY=dev-secret-key-replace-in-production
```

---

## 9.5 Database setup

```
createdb queryscope
```

run migrations:

```
python manage.py migrate
```

seed data:

```
python manage.py seed_db --books 200 --reviews-per-book 10
```

---

## 9.6 Run development server

```
python manage.py runserver
```

```
Dashboard → http://localhost:8000/dashboard/
API       → http://localhost:8000/api/books/
Debug     → http://localhost:8000/__debug__/
```

---

## 9.7 Daily workflow

install new package:

```
uv add package_name
```

install dev package:

```
uv add --dev package_name
```

update dependencies:

```
uv lock --upgrade
```

sync environment:

```
uv sync
```

---

## 10. Testing strategy

### 10.1 Query count assertions

Every endpoint has a test that asserts the exact number of SQL queries for a given configuration. This catches regressions when the ORM configuration changes.

```python
from django.test import TestCase
from django.db import connection, reset_queries


class BookListQueryCountTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        BookFactory.create_batch(50)

    def test_naive_produces_n_plus_one(self):
        reset_queries()
        with self.settings(DEBUG=True):
            response = self.client.get('/api/books/?limit=50')
        # 1 main + 50 author + 50 review = 101
        self.assertGreater(len(connection.queries), 50)

    def test_optimized_uses_three_queries(self):
        reset_queries()
        with self.settings(DEBUG=True):
            response = self.client.get(
                '/api/books/?limit=50&select_related=true&prefetch_related=true'
            )
        # 1 main JOIN + 1 reviews batch + 1 tags batch = 3
        self.assertLessEqual(len(connection.queries), 3)
```

### 10.2 Profiler middleware tests

```python
class MiddlewareProfileTest(TestCase):
    def test_profile_attached_to_response(self):
        response = self.client.get('/api/books/')
        data = response.json()
        self.assertIn('_profile', data)
        self.assertIn('query_count', data['_profile'])
        self.assertIn('total_ms', data['_profile'])

    def test_n1_detected_in_profile(self):
        BookFactory.create_batch(10)
        response = self.client.get('/api/books/?limit=10')
        profile = response.json()['_profile']
        self.assertGreater(profile['duplicate_queries'], 0)
```

### 10.3 Search index tests

```python
class SearchIndexTest(TestCase):
    def setUp(self):
        self.book = BookFactory(title='The Great Gatsby')
        Book.objects.filter(pk=self.book.pk).update(
            search_vector=SearchVector('title')
        )

    def test_fulltext_finds_book(self):
        response = self.client.get('/api/books/search/?q=Gatsby&mode=fulltext')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['data']), 1)

    def test_naive_search_uses_seq_scan(self):
        response = self.client.get('/api/books/search/?q=Gatsby&mode=naive')
        profile = response.json()['_profile']
        self.assertIn('Seq Scan', profile.get('explain', ''))
```

---

## 11. Implementation milestones


| Sprint | Week | Deliverable                   | Definition of done                                               |
| ------ | ---- | ----------------------------- | ---------------------------------------------------------------- |
| 1      | 1    | Models, migrations, seed data | 200 books seeded, admin accessible, all relations correct        |
| 1      | 1    | `QueryProfilerMiddleware`     | `X-Query-Count` header on every API response, `_profile` in body |
| 2      | 2    | Books list endpoint           | All 4 ORM toggles work, query count changes correctly per toggle |
| 2      | 2    | Search endpoint               | 3 modes work, EXPLAIN shows correct scan type for each mode      |
| 3      | 3    | Analytics endpoint            | `annotate` vs `python` mode, Window functions working            |
| 3      | 3    | Bulk endpoint                 | `loop` vs `bulk_create` timing diff visible in profile           |
| 4      | 4    | Dashboard template + HTMX     | Toggles update metrics without page reload                       |
| 4      | 4    | SQL log + EXPLAIN panel       | Color-coded log, EXPLAIN output rendered per request             |
| 5      | 5    | Compare mode                  | Side-by-side A/B profile with diff metrics                       |
| 5      | 5    | Tests + documentation         | All query count assertions passing, README complete              |


---

## 12. Appendix

### 12.1 PostgreSQL `pg_stat_statements`

For deeper production-style profiling, enable `pg_stat_statements` to track cumulative query statistics across all executions.

```sql
-- Enable the extension:
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Query the top slowest queries:
SELECT query, calls, mean_exec_time, total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

```python
# In a Django view (bonus analytics tab):
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT query, calls, round(mean_exec_time::numeric, 2) AS mean_ms
        FROM pg_stat_statements
        ORDER BY mean_exec_time DESC
        LIMIT 10
    ''')
    return cursor.fetchall()
```

### 12.2 Key Django ORM references

- `django.db.models.query` — QuerySet API source of truth
- `django.db.connection.queries` — raw SQL log (`DEBUG=True` required)
- `django.db.models.expressions` — `F()`, `Q()`, `Value()`, `Case()`, `When()`
- `django.contrib.postgres.search` — `SearchVector`, `SearchQuery`, `SearchRank`, `SearchVectorField`
- `django.contrib.postgres.indexes` — `GinIndex`, `GistIndex`, `BrinIndex`

### 12.3 Performance benchmarks (expected)


| Configuration                         | Queries (50 books) | Approx. time |
| ------------------------------------- | ------------------ | ------------ |
| No optimization                       | 101                | 300–400ms    |
| `select_related` only                 | 51                 | 180–220ms    |
| `select_related` + `prefetch_related` | 3                  | 40–60ms      |
| + `annotate`                          | 3                  | 35–55ms      |
| + QuerySet cache (hit)                | 0                  | < 5ms        |
| Full-text search, no index            | 1 Seq Scan         | 80–150ms     |
| Full-text search, GIN index           | 1 Bitmap Scan      | 5–15ms       |


> **Note:** All timing benchmarks are estimates based on a local PostgreSQL instance with default configuration and no connection pooling. The relative differences between configurations are what matter for the demonstration — absolute values will vary by hardware.

---

*QueryScope PRD v1.0 — March 2026*