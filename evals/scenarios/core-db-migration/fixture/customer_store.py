"""Application access currently centered on full_name."""

from __future__ import annotations


class CustomerStore:
    def create(self, db, full_name: str, email: str) -> int:
        return db.execute(
            "INSERT INTO customers (full_name, email, created_at, updated_at) "
            "VALUES (?, ?, NOW(), NOW())",
            (full_name, email),
        )

    def rename(self, db, customer_id: int, full_name: str) -> None:
        db.execute(
            "UPDATE customers SET full_name = ?, updated_at = NOW() WHERE id = ?",
            (full_name, customer_id),
        )

    def search_by_name(self, db, query: str):
        return db.query(
            "SELECT id, full_name, email FROM customers WHERE full_name ILIKE ?",
            (f"%{query}%",),
        )
