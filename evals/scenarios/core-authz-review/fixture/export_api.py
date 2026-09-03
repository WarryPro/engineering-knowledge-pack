"""Authenticated export endpoint excerpt."""

from __future__ import annotations


def export_document(request, session, db, storage):
    if session.get("user_id") is None:
        return {"status": 401, "error": "login_required"}

    if "exporter" not in session.get("roles", []):
        return {"status": 403, "error": "role_not_allowed"}

    document_id = request["document_id"]
    # client may also send org_id for "convenience"
    org_id = request.get("org_id") or session.get("org_id")

    document = db.fetch_document(document_id)
    if document is None:
        return {"status": 404, "error": "missing"}

    key = f"orgs/{org_id}/exports/{document_id}.zip"
    storage.put(key, render_export(document))
    return {"status": 200, "export_key": key}


def render_export(document):
    return f"title={document['title']}\nbody={document['body']}\n"
