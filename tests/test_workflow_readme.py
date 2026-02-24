import os

from planemo.io import temp_directory
from planemo.workflow_lint import load_workflow_readme


def test_load_workflow_readme_populates_empty_readme():
    with temp_directory() as test_dir:
        workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
        readme_path = os.path.join(test_dir, "README.md")
        with open(workflow_path, "w") as f:
            f.write("")
        with open(readme_path, "w") as f:
            f.write("# My Workflow\n\nA description.\n")
        workflow = {}
        load_workflow_readme(workflow_path, workflow)
        assert workflow["readme"] == "# My Workflow\n\nA description.\n"


def test_load_workflow_readme_preserves_existing_readme():
    with temp_directory() as test_dir:
        workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
        readme_path = os.path.join(test_dir, "README.md")
        with open(workflow_path, "w") as f:
            f.write("")
        with open(readme_path, "w") as f:
            f.write("# From file\n")
        workflow = {"readme": "Already set"}
        load_workflow_readme(workflow_path, workflow)
        assert workflow["readme"] == "Already set"


def test_load_workflow_readme_no_readme_file():
    with temp_directory() as test_dir:
        workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
        with open(workflow_path, "w") as f:
            f.write("")
        workflow = {}
        load_workflow_readme(workflow_path, workflow)
        assert "readme" not in workflow


def test_load_workflow_readme_empty_string_readme():
    with temp_directory() as test_dir:
        workflow_path = os.path.join(test_dir, "workflow.gxwf.yml")
        readme_path = os.path.join(test_dir, "README.md")
        with open(workflow_path, "w") as f:
            f.write("")
        with open(readme_path, "w") as f:
            f.write("# Content\n")
        workflow = {"readme": ""}
        load_workflow_readme(workflow_path, workflow)
        assert workflow["readme"] == "# Content\n"
