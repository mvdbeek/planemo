"""Module describing the planemo ``workflow_fill_readme`` command."""

import json
import os

import click
from gxformat2.yaml import (
    ordered_dump,
    ordered_load_path,
)

from planemo import options
from planemo.cli import command_function
from planemo.io import (
    error,
    info,
)
from planemo.workflow_lint import (
    find_workflow_descriptions,
    load_workflow_readme,
)


@click.command("workflow_fill_readme")
@options.optional_tools_or_packages_arg(multiple=True)
@options.force_option("the readme field in workflow files")
@command_function
def cli(ctx, paths, **kwds):
    """Fill the readme field of workflow files from a README.md file.

    For each workflow found in the given paths, look for a README.md file
    in the same directory and populate the workflow's ``readme`` field with
    its contents.  If the workflow already has a ``readme`` field, use
    ``--force`` to overwrite it.
    """
    force = kwds.get("force", False)
    found_any = False
    for path in paths:
        for workflow_path in find_workflow_descriptions(path):
            found_any = True
            _fill_readme(ctx, workflow_path, force)
    if not found_any:
        error("No workflow files found in the given paths.")
        ctx.exit(1)


def _fill_readme(ctx, workflow_path, force):
    """Fill the readme field for a single workflow file."""
    readme_path = os.path.join(os.path.dirname(workflow_path), "README.md")
    if not os.path.exists(readme_path):
        info(f"No README.md found next to {workflow_path}, skipping.")
        return

    if workflow_path.endswith(".ga"):
        with open(workflow_path) as f:
            workflow = json.load(f)
        had_readme = bool(workflow.get("readme"))
        load_workflow_readme(workflow_path, workflow, force=force)
        if had_readme and not force:
            info(f"{workflow_path} already has a readme field, skipping (use --force to overwrite).")
            return
        with open(workflow_path, "w") as f:
            json.dump(workflow, f, ensure_ascii=False, indent=4, sort_keys=True)
    else:
        workflow = ordered_load_path(workflow_path)
        had_readme = bool(workflow.get("readme"))
        load_workflow_readme(workflow_path, workflow, force=force)
        if had_readme and not force:
            info(f"{workflow_path} already has a readme field, skipping (use --force to overwrite).")
            return
        with open(workflow_path, "w") as f:
            ordered_dump(workflow, f)
    info(f"Updated readme field in {workflow_path}.")
