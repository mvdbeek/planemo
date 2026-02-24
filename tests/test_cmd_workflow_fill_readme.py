"""Tests for the ``workflow_fill_readme`` command."""

import json
import os

import yaml

from planemo.io import temp_directory
from .test_utils import CliTestCase


class CmdWorkflowFillReadmeTestCase(CliTestCase):
    def test_fill_readme_gxformat2(self):
        """Test filling readme for a gxformat2 workflow."""
        with temp_directory() as test_dir:
            workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
            readme_path = os.path.join(test_dir, "README.md")
            with open(workflow_path, "w") as f:
                yaml.dump(
                    {
                        "class": "GalaxyWorkflow",
                        "doc": "A test workflow",
                        "inputs": {"the_input": {"type": "File"}},
                        "steps": {},
                    },
                    f,
                    sort_keys=False,
                )
            with open(readme_path, "w") as f:
                f.write("# My Workflow\n\nDetailed description.\n")

            fill_cmd = ["workflow_fill_readme", test_dir]
            self._check_exit_code(fill_cmd, exit_code=0)

            with open(workflow_path) as f:
                updated = yaml.safe_load(f)
            assert updated["readme"] == "# My Workflow\n\nDetailed description.\n"

    def test_fill_readme_ga_format(self):
        """Test filling readme for a native .ga workflow."""
        with temp_directory() as test_dir:
            workflow_path = os.path.join(test_dir, "workflow.ga")
            readme_path = os.path.join(test_dir, "README.md")
            with open(workflow_path, "w") as f:
                json.dump(
                    {
                        "a_galaxy_workflow": "true",
                        "annotation": "test",
                        "format-version": "0.1",
                        "name": "test",
                        "steps": {},
                    },
                    f,
                )
            with open(readme_path, "w") as f:
                f.write("# GA Workflow\n")

            fill_cmd = ["workflow_fill_readme", test_dir]
            self._check_exit_code(fill_cmd, exit_code=0)

            with open(workflow_path) as f:
                updated = json.load(f)
            assert updated["readme"] == "# GA Workflow\n"

    def test_fill_readme_skips_existing(self):
        """Test that existing readme is preserved without --force."""
        with temp_directory() as test_dir:
            workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
            readme_path = os.path.join(test_dir, "README.md")
            with open(workflow_path, "w") as f:
                yaml.dump(
                    {
                        "class": "GalaxyWorkflow",
                        "readme": "Existing readme",
                        "inputs": {"the_input": {"type": "File"}},
                        "steps": {},
                    },
                    f,
                    sort_keys=False,
                )
            with open(readme_path, "w") as f:
                f.write("# New readme\n")

            fill_cmd = ["workflow_fill_readme", test_dir]
            self._check_exit_code(fill_cmd, exit_code=0)

            with open(workflow_path) as f:
                updated = yaml.safe_load(f)
            assert updated["readme"] == "Existing readme"

    def test_fill_readme_force_overwrites(self):
        """Test that --force overwrites existing readme."""
        with temp_directory() as test_dir:
            workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
            readme_path = os.path.join(test_dir, "README.md")
            with open(workflow_path, "w") as f:
                yaml.dump(
                    {
                        "class": "GalaxyWorkflow",
                        "readme": "Existing readme",
                        "inputs": {"the_input": {"type": "File"}},
                        "steps": {},
                    },
                    f,
                    sort_keys=False,
                )
            with open(readme_path, "w") as f:
                f.write("# Updated readme\n")

            fill_cmd = ["workflow_fill_readme", "--force", test_dir]
            self._check_exit_code(fill_cmd, exit_code=0)

            with open(workflow_path) as f:
                updated = yaml.safe_load(f)
            assert updated["readme"] == "# Updated readme\n"

    def test_fill_readme_no_readme_file(self):
        """Test that missing README.md is handled gracefully."""
        with temp_directory() as test_dir:
            workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
            with open(workflow_path, "w") as f:
                yaml.dump(
                    {
                        "class": "GalaxyWorkflow",
                        "inputs": {"the_input": {"type": "File"}},
                        "steps": {},
                    },
                    f,
                    sort_keys=False,
                )

            fill_cmd = ["workflow_fill_readme", test_dir]
            self._check_exit_code(fill_cmd, exit_code=0)

            with open(workflow_path) as f:
                updated = yaml.safe_load(f)
            assert "readme" not in updated
