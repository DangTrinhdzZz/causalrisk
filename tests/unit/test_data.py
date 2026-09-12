import hashlib
import json

import pytest

from causalrisk.data import (
    InferenceDataError,
    LabelFreeItem,
    load_label_free_items,
    select_smoke_canary,
    verify_inference_view,
)


def valid_record():
    return {
        "item_id": "opaque-001",
        "background": "X may cause Y.",
        "given_info": "X is set to one.",
        "question": "Is Y more likely?",
    }


def test_label_free_projection_omits_local_item_id():
    item = LabelFreeItem.from_mapping(valid_record())
    assert item.model_context() == {
        "background": "X may cause Y.",
        "given_info": "X is set to one.",
        "question": "Is Y more likely?",
    }


@pytest.mark.parametrize(
    "forbidden",
    ["answer", "label", "groundtruth", "rung", "query_type", "question_id", "split_name"],
)
def test_loader_rejects_instead_of_silently_dropping_protected_fields(forbidden):
    record = valid_record()
    record[forbidden] = "secret"
    with pytest.raises(InferenceDataError, match="forbidden"):
        LabelFreeItem.from_mapping(record)


def test_json_loader_requires_unique_item_ids(tmp_path):
    path = tmp_path / "items.json"
    path.write_text(json.dumps([valid_record(), valid_record()]), encoding="utf-8")
    with pytest.raises(InferenceDataError, match="unique"):
        load_label_free_items(path)


def test_controller_projection_cannot_access_ground_truth():
    item = LabelFreeItem.from_mapping(valid_record())
    assert "rung" not in item.model_context()
    assert not any(key in item.model_context() for key in ("answer", "label", "groundtruth"))


def test_cross_split_view_v2_has_exact_label_free_schema_and_checksum(tmp_path):
    source_hash = "a" * 64
    records = [valid_record(), {**valid_record(), "item_id": "opaque-002"}]
    document = {
        "schema_version": 2,
        "view_kind": "label_free_inference",
        "source_manifest_sha256": source_hash,
        "item_count": 2,
        "items": records,
    }
    payload = (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()
    view_path = tmp_path / "calibration.v2.json"
    view_path.write_bytes(payload)
    view_path.with_suffix(".sha256.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "view_kind": "label_free_inference",
                "source_manifest_sha256": source_hash,
                "inference_view_sha256": hashlib.sha256(payload).hexdigest(),
                "item_count": 2,
            }
        ),
        encoding="utf-8",
    )
    view = verify_inference_view(view_path, source_hash, expected_item_count=2)
    assert len(view.items) == 2
    assert set(document["items"][0]) == {"item_id", "background", "given_info", "question"}
    assert "split" not in document


def test_controller_only_canary_selector_does_not_add_rung_to_items(tmp_path):
    items = tuple(LabelFreeItem(f"item-{rung}", "background", "given", "question") for rung in (1, 2, 3))
    from causalrisk.data import VerifiedInferenceView

    view = VerifiedInferenceView(items, 2, "a" * 64, "b" * 64)
    selector_path = tmp_path / "smoke.v2.canary.json"
    selector_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "selection_kind": "controller_only_one_item_per_rung",
                "source_manifest_sha256": "a" * 64,
                "inference_view_sha256": "b" * 64,
                "item_count": 3,
                "items": [{"item_id": f"item-{rung}", "rung": rung} for rung in (1, 2, 3)],
            }
        ),
        encoding="utf-8",
    )
    selection = select_smoke_canary(view, selector_path)
    assert selection.items == items
    assert all(not hasattr(item, "rung") for item in selection.items)
