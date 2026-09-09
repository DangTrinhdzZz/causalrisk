import json

import pytest

from causalrisk.data import InferenceDataError, LabelFreeItem, load_label_free_items


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


@pytest.mark.parametrize("forbidden", ["answer", "rung", "query_type", "question_id", "split_name"])
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
