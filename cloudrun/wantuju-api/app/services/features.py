"""Feature configuration service."""
from __future__ import annotations

from typing import Any

from app.cloudbase.nosql import CloudBaseNoSQL


FEATURE_CONFIGS_COLLECTION = "feature_configs"


def to_public_feature(config: dict[str, Any]) -> dict[str, Any]:
    public = config.get("public") if isinstance(config.get("public"), dict) else {}
    ui = config.get("ui") if isinstance(config.get("ui"), dict) else {}
    return {
        "type": config.get("type"),
        "enabled": config.get("enabled"),
        "order": config.get("order"),
        **public,
        "ui": ui,
    }


class FeatureService:
    def __init__(self, db: CloudBaseNoSQL | None = None):
        self.db = db or CloudBaseNoSQL()

    def list_enabled_features(self) -> list[dict[str, Any]]:
        docs = self.db.list_documents(FEATURE_CONFIGS_COLLECTION, limit=200)
        features = [
            to_public_feature(doc)
            for doc in docs
            if doc.get("enabled") is True
        ]
        return sorted(features, key=lambda item: item.get("order") or 0)

    def get_enabled_feature(self, feature_type: str) -> dict[str, Any] | None:
        for feature in self.list_enabled_features():
            if feature.get("type") == feature_type:
                return feature
        return None

    def get_enabled_config(self, feature_type: str) -> dict[str, Any] | None:
        doc = self.db.find_one(
            FEATURE_CONFIGS_COLLECTION,
            {"type": feature_type, "enabled": True},
        )
        return doc if doc else None
