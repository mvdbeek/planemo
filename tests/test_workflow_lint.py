import os

import pytest

from planemo.workflow_lint import (
    input_labels,
    is_valid_output_expectations,
    WorkflowLintContext,
)
from .test_utils import TEST_DATA_DIR


def test_input_labels():
    wf_example_1 = os.path.join(TEST_DATA_DIR, "wf_repos", "basic_format2_ok", "basic_format2.gxwf.yml")
    labels = input_labels(wf_example_1)
    assert "the_input" in labels
    # verify non-input labels excluded
    assert "cat" not in labels

    wf_example_1 = os.path.join(TEST_DATA_DIR, "wf_repos", "basic_native_ok", "basic_native.yml")
    labels = input_labels(wf_example_1)
    assert "the_input" in labels
    # verify non-input labels excluded
    assert "cat" not in labels


BAD_ASSERTS = {"asserts": {"has_text": {"non_existent_attribute": "x"}}}
GOOD_ASSERTS = {"asserts": {"has_text": {"text": "x"}}}


@pytest.mark.parametrize(
    "output_expectations",
    [
        {"element_tests": {"el1": BAD_ASSERTS}},
        {"class": "Collection", "elements": {"el1": BAD_ASSERTS}},
        {"class": "Collection", "element_tests": {"inner": {"elements": {"el1": BAD_ASSERTS}}}},
        {"class": "Collection", "elements": {"inner": {"element_tests": {"el1": BAD_ASSERTS}}}},
    ],
)
def test_collection_element_assertions_linted(output_expectations):
    lint_context = WorkflowLintContext("all")
    assert not is_valid_output_expectations(lint_context, output_expectations)
    assert "Invalid assertion in tests: assert_has_text" in lint_context.error_messages[0].message


@pytest.mark.parametrize(
    "output_expectations",
    [
        {"class": "Collection", "elements": {"el1": GOOD_ASSERTS}},
        {"class": "Collection", "elements": {"inner": {"elements": {"el1": GOOD_ASSERTS}}}},
        {"class": "Collection", "collection_type": "list", "element_count": 2},
        # malformed: elements given as a list; nothing to lint, but must not crash
        {"class": "Collection", "elements": [{"identifier": "el1"}]},
    ],
)
def test_collection_element_assertions_valid(output_expectations):
    lint_context = WorkflowLintContext("all")
    assert is_valid_output_expectations(lint_context, output_expectations)
    assert not lint_context.error_messages
