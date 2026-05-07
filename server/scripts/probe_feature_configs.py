"""Probe CloudBase NoSQL REST reads and writes against feature_configs.

This touches production feature config data. It restores the edited field before
exiting, but still requires explicit confirmation.
"""
from __future__ import annotations

import os
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cloudbase.nosql import FEATURE_CONFIG_COLLECTION, get_feature_store


def main() -> None:
    if os.getenv("CONFIRM_PRODUCTION_FEATURE_PROBE") != "yes":
        raise RuntimeError("Refusing to probe production feature_configs without CONFIRM_PRODUCTION_FEATURE_PROBE=yes")
    doc_id = os.getenv("FEATURE_PROBE_DOC_ID", "palm")
    store = get_feature_store()
    before = store.get_feature(doc_id)
    original = before.get("public", {}).get("shortTitle", "")
    probe_value = f"测试探针-{int(time.time())}"

    print(f"collection={FEATURE_CONFIG_COLLECTION}")
    print(f"doc_id={doc_id}")
    print(f"before.public.shortTitle={original}")

    update_result = store.update_feature(doc_id, {"public.shortTitle": probe_value})
    print(f"patch_result={update_result}")

    after = store.get_feature(doc_id)
    changed = after.get("public", {}).get("shortTitle", "")
    print(f"after.public.shortTitle={changed}")
    if changed != probe_value:
        raise RuntimeError("PATCH returned success but document did not change")

    store.update_feature(doc_id, {"public.shortTitle": original})
    restored = store.get_feature(doc_id).get("public", {}).get("shortTitle", "")
    print(f"restored.public.shortTitle={restored}")


if __name__ == "__main__":
    main()
