import os
import re

import yaml
from galaxy.tool_util.loader_directory import EXCLUDE_WALK_DIRS
from gxformat2._yaml import ordered_load
from gxformat2.lint import lint_format2, lint_ga
from gxformat2.linting import LintContext as WorkflowLintContext

from planemo.exit_codes import (
    EXIT_CODE_GENERIC_FAILURE,
    EXIT_CODE_OK,
)
from planemo.galaxy.workflows import input_labels, required_input_labels
from planemo.runnable import cases, for_path

POTENTIAL_WORKFLOW_FILES = re.compile(r'^.*(\.yml|\.yaml|\.ga)$')
DOCKSTORE_REGISTRY_CONF = ".dockstore.yml"
DOCKSTORE_REGISTRY_CONF_VERSION = "1.2"


def generate_dockstore_yaml(directory):
    workflows = []
    for workflow_path in find_workflow_descriptions(directory):
        workflows.append({
            # TODO: support CWL
            "subclass": "Galaxy",
            "primaryDescriptorPath": os.path.relpath(workflow_path, directory)
        })
    # Force version to the top of file but serializing rest of config seprately
    contents = "version: %s\n" % DOCKSTORE_REGISTRY_CONF_VERSION
    contents += yaml.dump({"workflows": workflows})
    return contents


def lint_workflow_artifacts_on_paths(ctx, paths, lint_args, **kwds):
    lint_context = WorkflowLintContext()
    for path in paths:
        _lint_workflow_artifacts_on_path(lint_context, path, lint_args, **kwds)

    lint_context.print_messages()
    if lint_context.found_errors or lint_context.found_warns:
        return EXIT_CODE_GENERIC_FAILURE
    else:
        return EXIT_CODE_OK


def _lint_workflow_artifacts_on_path(lint_context, path, lint_args, **kwds):
    for potential_workflow_artifact_path in find_potential_workflow_files(path):
        if os.path.basename(potential_workflow_artifact_path) == DOCKSTORE_REGISTRY_CONF:
            _lint_dockstore_config(lint_context, potential_workflow_artifact_path, **kwds)

        elif looks_like_a_workflow(potential_workflow_artifact_path):
            with open(potential_workflow_artifact_path, "r") as f:
                workflow_dict = ordered_load(f)
            workflow_class = workflow_dict.get("class")
            lint_func = lint_format2 if workflow_class == "GalaxyWorkflow" else lint_ga
            lint_func(lint_context, workflow_dict, path=potential_workflow_artifact_path)

            # Lint tests...
            skip_tests = "tests" in (kwds.get("skip") or "")
            if not skip_tests:
                runnable = for_path(potential_workflow_artifact_path)
                test_cases = cases(runnable)
                if len(test_cases) == 0:
                    lint_context.warn("Workflow missing test cases.")
                for test_case in test_cases:
                    job = test_case._job

                    i_labels = input_labels(workflow_path=potential_workflow_artifact_path)
                    job_keys = list(job.keys())
                    for key in job_keys:
                        if key not in i_labels:
                            # consider an error instead?
                            lint_context.warn("Unknown workflow input in test job definition [%s], workflow inputs are [%s]" % (key, i_labels))

                    # check non-optional parameters are set
                    for required_label in required_input_labels(potential_workflow_artifact_path):
                        if required_label not in job_keys:
                            template = "Non-optional input has no value specified in workflow test job [%s], job specifies inputs [%s]"
                            lint_context.error(template % (required_label, job_keys))

                    # TODO: check input locations

                    # TODO: check output labels in job

        # Allow linting ro crates and such also


def _lint_dockstore_config(lint_context, path, **kwds):
    skip_dockstore = "dockstore" in (kwds.get("skip") or "")
    if skip_dockstore:
        return

    dockstore_yaml = None
    try:
        with open(path, "r") as f:
            dockstore_yaml = yaml.safe_load(f)
    except Exception:
        lint_context.error("Invalid YAML found in %s" % DOCKSTORE_REGISTRY_CONF)
        return

    if not isinstance(dockstore_yaml, dict):
        lint_context.error("Invalid YAML contents found in %s" % DOCKSTORE_REGISTRY_CONF)
        return

    if "workflows" not in dockstore_yaml:
        lint_context.error("Invalid YAML contents found in %s, no workflows defined" % DOCKSTORE_REGISTRY_CONF)
        return

    workflow_entries = dockstore_yaml.get("workflows")
    if not isinstance(workflow_entries, list):
        lint_context.error("Invalid YAML contents found in %s, workflows not a list" % DOCKSTORE_REGISTRY_CONF)
        return

    for workflow_entry in workflow_entries:
        _lint_dockstore_workflow_entry(lint_context, os.path.dirname(path), workflow_entry)


def _lint_dockstore_workflow_entry(lint_context, directory, workflow_entry):
    if not isinstance(workflow_entry, dict):
        lint_context.error("Invalid YAML contents found in %s, workflow entry not a dict" % DOCKSTORE_REGISTRY_CONF)
        return

    found_errors = False
    for required_key in ["primaryDescriptorPath", "subclass"]:
        if required_key not in workflow_entry:
            lint_context.error("%s workflow entry missing required key %s" % (DOCKSTORE_REGISTRY_CONF, required_key))
            found_errors = True

    for recommended_key in ["testParameterFiles"]:
        if recommended_key not in workflow_entry:
            lint_context.warn("%s workflow entry missing recommended key %s" % (DOCKSTORE_REGISTRY_CONF, recommended_key))

    if found_errors:
        # Don't do the rest of the validation for a broken file.
        return

    # TODO: validate subclass
    descriptor_path = workflow_entry["primaryDescriptorPath"]
    test_files = workflow_entry.get("testParameterFiles", [])

    for referenced_file in [descriptor_path] + test_files:
        referenced_path = os.path.join(directory, referenced_file[1:])
        if not os.path.exists(referenced_path):
            lint_context.error("%s workflow entry references absent file %s" % (DOCKSTORE_REGISTRY_CONF, referenced_file))


def looks_like_a_workflow(path):
    """Return boolean indicating if this path looks like a workflow."""
    if POTENTIAL_WORKFLOW_FILES.match(os.path.basename(path)):
        with open(path, "r") as f:
            workflow_dict = ordered_load(f)
        if not isinstance(workflow_dict, dict):
            # Not exactly right - could have a #main def - do better and sync with Galaxy.
            return False
        return workflow_dict.get("class") == "GalaxyWorkflow" or workflow_dict.get("a_galaxy_workflow")
    return False


def find_workflow_descriptions(directory):
    for potential_workflow_artifact_path in find_potential_workflow_files(directory):
        if looks_like_a_workflow(potential_workflow_artifact_path):
            yield potential_workflow_artifact_path


def find_potential_workflow_files(directory):
    """Return a list of potential workflow files in a directory."""
    if not os.path.exists(directory):
        raise ValueError("Directory not found {}".format(directory))

    matches = []
    for root, dirnames, filenames in os.walk(directory):
        # exclude some directories (like .hg) from traversing
        dirnames[:] = [dir for dir in dirnames if dir not in EXCLUDE_WALK_DIRS]
        for filename in filenames:
            if POTENTIAL_WORKFLOW_FILES.match(filename):
                matches.append(os.path.join(root, filename))
    return matches
