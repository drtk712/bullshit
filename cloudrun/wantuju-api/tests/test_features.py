"""Feature configs load from PostgreSQL, including NULL validation."""
from __future__ import annotations

from app.admin.views import _form_patch
from app.db import FeatureConfigStore
from app.services.features import FeatureService
from app.services.tasks import TaskService


class _Storage:
    def get_download_urls(self, file_ids):
        raise AssertionError("validation should not download images when it is null")


def _insert(db, **overrides) -> str:
    document = {
        "type": "palm",
        "enabled": True,
        "order": 10,
        "param": [],
        "public": {
            "title": "看手相",
            "homeDesc": "趣味解读运势",
            "description": "上传清晰手掌照片",
        },
        "ui": {"requirements": ["手掌完整"]},
        "validation": None,
        "generation": {"prompt": "poster prompt"},
    }
    document.update(overrides)
    return db.insert_documents("feature_configs", [document])["ids"][0]


def test_enabled_features_use_sort_order_and_skip_null_validation(db):
    _insert(db, type="hair", order=20, public={"title": "设计发型", "homeDesc": "挑发型"})
    _insert(db)
    _insert(db, type="watermark", enabled=False, order=5, public={"title": "水印"})

    features = FeatureService(db).list_enabled_features()

    assert [item["type"] for item in features] == ["palm", "hair"]
    assert features[0]["order"] == 10
    assert features[0]["title"] == "看手相"
    assert features[0]["homeDesc"] == "趣味解读运势"
    config = FeatureService(db).get_enabled_config("palm")
    assert config is not None
    assert config["validation"] is None
    assert config["order"] == 10
    result = TaskService(db=db, storage=_Storage()).validate_image("cloud://test/a.jpg", config)
    assert result == {"passed": True, "reason": ""}


def test_nested_jsonb_fields_update_without_replacing_siblings(db):
    doc_id = _insert(db)
    store = FeatureConfigStore(db)

    store.update_feature(
        doc_id,
        {
            "public.title": "新手相",
            "ui.requirements": ["光线充足", "五指张开"],
            "generation.prompt": "new prompt",
        },
    )
    document = store.get_feature(doc_id)

    assert document["public"]["title"] == "新手相"
    assert document["public"]["homeDesc"] == "趣味解读运势"
    assert document["ui"]["requirements"] == ["光线充足", "五指张开"]
    assert document["generation"]["prompt"] == "new prompt"
    assert document["validation"] is None


def test_blank_admin_validation_is_stored_as_null(db):
    doc_id = _insert(
        db,
        validation={"serviceUrl": "http://example.test/v1", "model": "old", "prompt": "旧", "failMessage": "旧"},
    )
    patch = _form_patch(
        {
            "type": "palm",
            "order": "10",
            "public.title": "看手相",
            "public.category": "趣味",
            "public.description": "描述",
            "public.homeDesc": "一句",
            "public.uploadTitle": "上传",
            "public.cardSize": "normal",
            "public.previewImageHD": "",
            "ui.progressTitle": "进度",
            "ui.detailSubtitle": "副标题",
            "ui.requirements": "手掌完整",
            "ui.requirementItems": "",
            "ui.analysisItems": "",
            "ui.progressChecks": "",
            "ui.tags": "",
            "param": "",
            "validation.serviceUrl": "",
            "validation.model": "",
            "validation.prompt": "",
            "validation.failMessage": "",
            "validation.apiKey": "",
            "generation.prompt": "prompt",
        }
    )
    assert patch["validation"] is None

    FeatureConfigStore(db).update_feature(doc_id, patch)
    document = db.get_document("feature_configs", doc_id)
    assert document["validation"] is None
    assert document["public"]["title"] == "看手相"
    assert document["public"]["category"] == "趣味"


def test_rls_denies_client_role_and_backend_policy_allows_it(db):
    _insert(db)
    from app.db.pool import connection

    with connection() as conn:
        conn.execute("DROP POLICY IF EXISTS backend_all_feature_configs_client ON public.feature_configs")
        conn.execute(
            """
            DO $$
            BEGIN
              IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wantuju_client') THEN
                REVOKE ALL ON TABLE public.feature_configs FROM wantuju_client;
                DROP OWNED BY wantuju_client;
                DROP ROLE wantuju_client;
              END IF;
            END $$
            """
        )
        conn.execute("CREATE ROLE wantuju_client NOLOGIN NOBYPASSRLS")
        conn.execute("GRANT USAGE ON SCHEMA public TO wantuju_client")
        conn.execute("GRANT SELECT ON TABLE public.feature_configs TO wantuju_client")
        conn.execute("SET ROLE wantuju_client")
        try:
            hidden = conn.execute("SELECT count(*)::int AS n FROM public.feature_configs").fetchone()
        finally:
            conn.execute("RESET ROLE")
        assert hidden["n"] == 0

        conn.execute(
            """
            CREATE POLICY backend_all_feature_configs_client
            ON public.feature_configs
            FOR ALL TO wantuju_client
            USING (true) WITH CHECK (true)
            """
        )
        conn.execute("SET ROLE wantuju_client")
        try:
            visible = conn.execute("SELECT count(*)::int AS n FROM public.feature_configs").fetchone()
        finally:
            conn.execute("RESET ROLE")
        assert visible["n"] == 1

        policies = conn.execute(
            """
            SELECT polname
            FROM pg_policy
            WHERE polrelid = 'public.feature_configs'::regclass
              AND polname = 'backend_all_feature_configs'
            """
        ).fetchall()
        assert policies


def test_service_starts_against_postgres(migrated):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        health = client.get("/health")
        features = client.get("/miniapp/features")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert features.status_code == 200
    assert features.json()["success"] is True
    assert features.json()["data"]["features"] == []
