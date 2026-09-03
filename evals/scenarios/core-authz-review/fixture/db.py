"""Document lookup currently keyed only by document id."""

from __future__ import annotations


class DocumentDB:
    def fetch_document(self, document_id: str):
        return self.conn.fetchone(
            "SELECT id, org_id, title, body FROM documents WHERE id = ?",
            (document_id,),
        )
