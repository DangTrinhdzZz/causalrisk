from pathlib import Path

import pytest

from causalrisk.data import LabelFreeItem
from causalrisk.prompts import PromptError, file_sha256, load_prompt_bundle, render_prompt

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "prompts" / "prompt_causal_yesno_v1.json"


def test_rendered_prompt_is_label_free_and_omits_item_id():
    bundle = load_prompt_bundle(BUNDLE)
    item = LabelFreeItem("opaque-local-key", "X causes Y.", "X is one.", "Is Y one?")
    rendered = render_prompt(
        bundle,
        item=item,
        role="analyst",
        output_schema="single_answer",
        final_decision=True,
    )
    assert "opaque-local-key" not in rendered
    assert "X causes Y." in rendered
    assert rendered.endswith("\n")


def test_previous_card_is_delimited_as_untrusted_text():
    bundle = load_prompt_bundle(BUNDLE)
    item = LabelFreeItem("opaque", "Background", "Given", "Question")
    rendered = render_prompt(
        bundle,
        item=item,
        role="critic",
        output_schema="critic_card",
        previous_responses=("Analyst evidence",),
        final_decision=True,
    )
    assert "BEGIN UNTRUSTED CARD 1" in rendered
    assert "Analyst evidence" in rendered


def test_serialized_protected_field_is_rejected():
    bundle = load_prompt_bundle(BUNDLE)
    item = LabelFreeItem("opaque", "graph_id: 5", "Given", "Question")
    with pytest.raises(PromptError, match="protected"):
        render_prompt(
            bundle,
            item=item,
            role="analyst",
            output_schema="single_answer",
            final_decision=True,
        )


def test_text_checksum_is_stable_across_lf_and_crlf(tmp_path):
    lf_path = tmp_path / "lf.txt"
    crlf_path = tmp_path / "crlf.txt"
    lf_path.write_bytes(b"first line\nsecond line\n")
    crlf_path.write_bytes(b"first line\r\nsecond line\r\n")

    assert file_sha256(lf_path) == file_sha256(crlf_path)
