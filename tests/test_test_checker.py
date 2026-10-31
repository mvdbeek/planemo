"""Unit tests for runnable test case checking and related functionality."""

import os

from planemo.runnable import (
    cases,
    for_path,
    SuccessfulRunResponse,
    TestCase,
)
from .test_utils import TEST_DATA_DIR


def test_non_file_case_checker():
    """Verify simply usage of :func:`planemo.runnable.TestCase.check`."""
    int_tool_path = os.path.join(TEST_DATA_DIR, "int_tool.cwl")
    test_cases = cases(for_path(int_tool_path))
    assert len(test_cases) == 1
    test_case = test_cases[0]
    outputs_dict = {
        "output": 4,
    }

    sd = test_case.structured_test_data(MockRunResponse(outputs_dict))
    assert sd["data"]["status"] == "success"

    bad_outputs_dict = {
        "output": 5,
    }
    sd = test_case.structured_test_data(MockRunResponse(bad_outputs_dict))
    assert sd["data"]["status"] == "failure"


def test_file_case_checker():
    hello_txt_path = os.path.join(TEST_DATA_DIR, "hello.txt")
    int_tool_path = os.path.join(TEST_DATA_DIR, "cat_tool.cwl")
    test_cases = cases(for_path(int_tool_path))
    assert len(test_cases) == 1
    test_case = test_cases[0]
    outputs_dict = {
        "output_file": {
            "path": hello_txt_path,
        }
    }

    sd = test_case.structured_test_data(MockRunResponse(outputs_dict))
    assert sd["data"]["status"] == "success"

    not_hello_txt_path = os.path.join(TEST_DATA_DIR, "int_tool_job.json")
    bad_outputs_dict = {
        "output_file": {
            "path": not_hello_txt_path,
        }
    }
    sd = test_case.structured_test_data(MockRunResponse(bad_outputs_dict))
    assert sd["data"]["status"] == "failure"


def test_class_only_collection_case_checker():
    """A ``class: Collection`` expectation without element tests is checked as a collection.

    Before, ``TestCase._check_output`` sent it down the file branch, which failed with
    "No path specified for expected output file" whatever the collection held.
    """
    workflow_path = os.path.join(TEST_DATA_DIR, "wf_repos", "basic_format2_ok_collection", "basic_format2.gxwf.yml")
    test_case = TestCase(
        runnable=for_path(workflow_path),
        tests_directory=os.path.dirname(workflow_path),
        output_expectations={"the_output": {"class": "Collection", "collection_type": "list", "element_count": 2}},
        job_path=None,
        job={},
        index=0,
        doc=None,
    )

    def collection(n):
        elements = [{"element_identifier": f"e{i}", "element_type": "hda"} for i in range(n)]
        return {"the_output": {"collection_type": "list", "elements": elements}}

    sd = test_case.structured_test_data(MockRunResponse(collection(2)))
    assert sd["data"]["status"] == "success"

    sd = test_case.structured_test_data(MockRunResponse(collection(1)))
    assert sd["data"]["status"] == "failure"
    assert sd["data"]["output_problems"] == [
        "Output collection 'the_output': expected to have 2 elements, but it had 1."
    ]


class MockRunResponse(SuccessfulRunResponse):
    start_datetime = None
    end_datetime = None

    def __init__(self, outputs_dict):
        self._outputs_dict = outputs_dict

    @property
    def log(self):
        return "My Log"

    @property
    def job_info(self):
        return {"command_line": "cat /tmp/1.txt > /tmp/2.out", "stdout": "Cat output", "stderr": "Cat problems..."}

    @property
    def outputs_dict(self):
        return self._outputs_dict

    @property
    def invocation_details(self):
        return None


__all__ = (
    "test_non_file_case_checker",
    "test_file_case_checker",
    "test_class_only_collection_case_checker",
)
