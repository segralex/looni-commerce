from __future__ import annotations

from uuid import UUID

from domain.search.repository import SearchFilters, SearchRepository

from .database import Database


class SQLiteSearchRepository(SearchRepository):
    def __init__(self, db: Database):
        self.db = db

    def search_listing_ids(
        self,
        filters: SearchFilters,
        *,
        limit: int,
        offset: int,
    ) -> tuple[UUID, ...]:
        conn = self.db.connect()
        cur = conn.cursor()

        where_clauses: list[str] = []
        params: list[object] = []

        if filters.keyword:
            where_clauses.append("listing_search_fts MATCH ?")
            params.append(filters.keyword)

        if filters.published_only:
            where_clauses.append("status = ?")
            params.append("PUBLISHED")

        if filters.category is not None:
            where_clauses.append("category = ?")
            params.append(filters.category)

        if filters.seller_id is not None:
            where_clauses.append("seller_id = ?")
            params.append(str(filters.seller_id))

        if filters.condition is not None:
            where_clauses.append("condition = ?")
            params.append(filters.condition.value)

        if filters.location is not None:
            where_clauses.append("LOWER(location) = LOWER(?)")
            params.append(filters.location)

        if filters.min_price is not None:
            where_clauses.append("CAST(price AS REAL) >= CAST(? AS REAL)")
            params.append(str(filters.min_price))

        if filters.max_price is not None:
            where_clauses.append("CAST(price AS REAL) <= CAST(? AS REAL)")
            params.append(str(filters.max_price))

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        if filters.keyword:
            order_sql = "ORDER BY bm25(listing_search_fts), datetime(created_at) DESC"
        else:
            order_sql = "ORDER BY datetime(created_at) DESC"

        sql = f"""
            SELECT listing_id
            FROM listing_search_fts
            {where_sql}
            {order_sql}
            LIMIT ? OFFSET ?
        """

        params.extend([limit, offset])
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        return tuple(UUID(row["listing_id"]) for row in rows)
