"""Database errors for the PostgreSQL data layer."""
from __future__ import annotations

from app.cloudbase.client import CloudBaseError


class DatabaseError(CloudBaseError):
    """Raised when PostgreSQL cannot complete a data-layer request.

    Subclasses CloudBaseError so existing API and admin handlers keep mapping
    data-layer failures to the same responses they used for the document API.
    """
