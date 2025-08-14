import time
from typing import (
    List,
    Optional,
    Protocol,
)

from .api import (
    invocation_state_terminal,
    InvocationApi,
    InvocationJobsSummary,
    JOB_ERROR_STATES,
)
from .progress import WorkflowProgressDisplay


class PollingTracker(Protocol):
    def sleep(self) -> None:
        ...


class PollingTrackerImpl(PollingTracker):
    def __init__(self, polling_backoff: int, timeout=None):
        self.polling_backoff = polling_backoff
        self.timeout = timeout
        self.delta = 0.25
        self.total_wait_time = 0

    def sleep(self):
        if self.timeout is not None and self.total_wait_time > self.timeout:
            message = "Timed out while polling Galaxy."
            raise Exception(message)
        self.total_wait_time += self.delta
        time.sleep(self.delta)
        self.delta += self.polling_backoff


def _summarize_invocation(invocation_api: InvocationApi, invocation_id: str):
    invocation = invocation_api.get_invocation(invocation_id)
    assert invocation
    invocation_jobs = invocation_api.get_invocation_summary(invocation_id)
    return invocation, invocation_jobs


def _poll_main_workflow(
    ctx,
    invocation_id: str,
    invocation_api: InvocationApi,
    workflow_progress_display: WorkflowProgressDisplay,
    fail_fast: bool,
):
    ctx.vlog(f"[DEBUG] _poll_main_workflow: checking terminal state for main workflow {invocation_id}")
    ctx.vlog(
        f"[DEBUG] _poll_main_workflow: workflow_progress.terminal = {workflow_progress_display.workflow_progress.terminal}"
    )
    ctx.vlog(
        f"[DEBUG] _poll_main_workflow: invocation_scheduling_terminal = {workflow_progress_display.workflow_progress.invocation_scheduling_terminal}"
    )
    ctx.vlog(
        f"[DEBUG] _poll_main_workflow: jobs_terminal = {workflow_progress_display.workflow_progress.jobs_terminal}"
    )
    ctx.vlog(
        f"[DEBUG] _poll_main_workflow: current invocation_state = {workflow_progress_display.workflow_progress.invocation_state}"
    )

    if workflow_progress_display.workflow_progress.terminal:
        ctx.vlog(f"[DEBUG] _poll_main_workflow: main workflow {invocation_id} is terminal, skipping poll")
        return None, None, None

    try:
        invocation, invocation_jobs = _summarize_invocation(invocation_api, invocation_id)
        ctx.vlog(f"[DEBUG] _poll_main_workflow: got invocation state = {invocation.get('state')}")
        ctx.vlog(
            f"[DEBUG] _poll_main_workflow: job summary states = {invocation_jobs.get('states', {}) if invocation_jobs else 'None'}"
        )
        workflow_progress_display.handle_invocation(invocation, invocation_jobs)
        ctx.vlog(
            f"[DEBUG] _poll_main_workflow: after handle_invocation, terminal = {workflow_progress_display.workflow_progress.terminal}"
        )
        return invocation, invocation_jobs, None
    except Exception as e:
        ctx.vlog(f"[DEBUG] _poll_main_workflow: exception polling main workflow {invocation_id}: {e}")
        print(e)
        return None, None, e


def _poll_subworkflow(
    ctx,
    invocation_id: str,
    invocation_api: InvocationApi,
    workflow_progress_display: WorkflowProgressDisplay,
    fail_fast: bool,
):
    ctx.vlog(f"[DEBUG] _poll_subworkflow: checking if all subworkflows complete for main {invocation_id}")
    ctx.vlog(
        f"[DEBUG] _poll_subworkflow: all_subworkflows_complete = {workflow_progress_display.all_subworkflows_complete()}"
    )
    ctx.vlog(
        f"[DEBUG] _poll_subworkflow: subworkflows seen = {len(workflow_progress_display.subworkflow_invocation_ids_seen)}"
    )
    ctx.vlog(
        f"[DEBUG] _poll_subworkflow: subworkflows completed = {len(workflow_progress_display.subworkflow_invocation_ids_completed)}"
    )

    if workflow_progress_display.all_subworkflows_complete():
        ctx.vlog(f"[DEBUG] _poll_subworkflow: all subworkflows complete for main {invocation_id}")
        return None, None, None

    try:
        subworkflow_id = workflow_progress_display.an_incomplete_subworkflow_id()
        ctx.vlog(f"[DEBUG] _poll_subworkflow: polling subworkflow {subworkflow_id}")
        invocation, invocation_jobs = _summarize_invocation(invocation_api, subworkflow_id)
        ctx.vlog(f"[DEBUG] _poll_subworkflow: subworkflow {subworkflow_id} state = {invocation.get('state')}")
        ctx.vlog(
            f"[DEBUG] _poll_subworkflow: subworkflow {subworkflow_id} job states = {invocation_jobs.get('states', {}) if invocation_jobs else 'None'}"
        )
        workflow_progress_display.handle_subworkflow_invocation(invocation, invocation_jobs)
        ctx.vlog(
            f"[DEBUG] _poll_subworkflow: after handling subworkflow {subworkflow_id}, terminal = {workflow_progress_display.subworkflow_progress.terminal}"
        )
        return invocation, invocation_jobs, None
    except Exception as e:
        ctx.vlog(f"[DEBUG] _poll_subworkflow: exception polling subworkflow: {e}")
        return None, None, e


def _check_for_errors(
    ctx,
    invocation_id: str,
    exception: Optional[Exception],
    invocation,
    invocation_jobs,
    invocation_api: InvocationApi,
    workflow_progress_display: WorkflowProgressDisplay,
    fail_fast: bool,
):
    invocation_state = "new" if not invocation else invocation["state"]
    job_state = summary_job_state(invocation_jobs)
    ctx.vlog(f"[DEBUG] _check_for_errors: checking errors for invocation {invocation_id}")
    ctx.vlog(f"[DEBUG] _check_for_errors: invocation_state = {invocation_state}")
    ctx.vlog(f"[DEBUG] _check_for_errors: job_state = {job_state}")
    ctx.vlog(f"[DEBUG] _check_for_errors: exception = {exception}")
    ctx.vlog(f"[DEBUG] _check_for_errors: fail_fast = {fail_fast}")

    error_message = workflow_in_error_message(
        ctx,
        invocation_id,
        exception,
        invocation,
        invocation_jobs,
        invocation_api=invocation_api,
        workflow_progress_display=workflow_progress_display,
        fail_fast=fail_fast,
    )
    ctx.vlog(f"[DEBUG] _check_for_errors: workflow_in_error_message returned = '{error_message}'")

    if error_message:
        final_state = "new" if not invocation else invocation["state"]
        job_state = summary_job_state(invocation_jobs)
        ctx.vlog(
            f"[DEBUG] _check_for_errors: ERROR DETECTED - returning final_state={final_state}, job_state={job_state}"
        )
        return final_state, job_state, error_message

    ctx.vlog("[DEBUG] _check_for_errors: no errors detected")
    return None


def _is_polling_complete(workflow_progress_display: WorkflowProgressDisplay) -> bool:
    terminal = workflow_progress_display.workflow_progress.terminal
    all_sub_complete = workflow_progress_display.all_subworkflows_complete()
    result = terminal and all_sub_complete
    # Note: Using print instead of ctx.vlog since we don't have ctx here
    print(
        f"[DEBUG] _is_polling_complete: terminal={terminal}, all_subworkflows_complete={all_sub_complete}, result={result}"
    )
    return result


def wait_for_invocation_and_jobs(
    ctx,
    invocation_id: str,
    invocation_api: InvocationApi,
    polling_tracker: PollingTracker,
    workflow_progress_display: WorkflowProgressDisplay,
    fail_fast: bool = False,
):
    ctx.vlog("Waiting for invocation [%s]" % invocation_id)

    last_invocation = None
    last_invocation_jobs = None
    error_message: Optional[str] = None
    polling_iteration = 0

    while not _is_polling_complete(workflow_progress_display):
        polling_iteration += 1
        ctx.vlog(f"[DEBUG] Polling iteration {polling_iteration} for invocation {invocation_id}")
        ctx.vlog(f"[DEBUG] _is_polling_complete = {_is_polling_complete(workflow_progress_display)}")
        # Poll main workflow
        main_invocation, main_jobs, main_exception = _poll_main_workflow(
            ctx, invocation_id, invocation_api, workflow_progress_display, fail_fast
        )

        if main_invocation:
            last_invocation = main_invocation
            last_invocation_jobs = main_jobs
            ctx.vlog(f"[DEBUG] Updated last_invocation state to {main_invocation.get('state')}")
        else:
            ctx.vlog("[DEBUG] No main_invocation data in this iteration")

        error_result = _check_for_errors(
            ctx,
            invocation_id,
            main_exception,
            main_invocation,
            main_jobs,
            invocation_api=invocation_api,
            workflow_progress_display=workflow_progress_display,
            fail_fast=fail_fast,
        )
        if error_result:
            ctx.vlog(f"[DEBUG] MAIN WORKFLOW ERROR DETECTED - returning {error_result}")
            return error_result

        # Poll subworkflow
        sub_invocation, sub_jobs, sub_exception = _poll_subworkflow(
            ctx, invocation_id, invocation_api, workflow_progress_display, fail_fast
        )

        error_result = _check_for_errors(
            ctx,
            invocation_id,
            sub_exception,
            sub_invocation,
            sub_jobs,
            invocation_api,
            workflow_progress_display,
            fail_fast,
        )
        if error_result:
            ctx.vlog(f"[DEBUG] SUBWORKFLOW ERROR DETECTED - returning {error_result}")
            return error_result

        if not _is_polling_complete(workflow_progress_display):
            ctx.vlog("[DEBUG] Polling not complete, sleeping...")
            polling_tracker.sleep()
        else:
            ctx.vlog("[DEBUG] Polling complete detected, will exit loop")

    ctx.vlog(f"[DEBUG] Polling loop completed after {polling_iteration} iterations")
    ctx.vlog(f"The final state of all jobs and subworkflow invocations for invocation [{invocation_id}] is 'ok'")
    job_state = summary_job_state(last_invocation_jobs)
    assert last_invocation

    ctx.vlog(f"[DEBUG] Final last_invocation state = {last_invocation.get('state')}")
    ctx.vlog(f"[DEBUG] Final job_state = {job_state}")

    # Final check for job errors when fail_fast is enabled
    if fail_fast and job_state in JOB_ERROR_STATES and not error_message:
        ctx.vlog("[DEBUG] Final check: fail_fast enabled and job errors detected")
        error_message = workflow_in_error_message(
            ctx,
            invocation_id,
            None,
            last_invocation,
            last_invocation_jobs,
            fail_fast=fail_fast,
            invocation_api=invocation_api,
            workflow_progress_display=workflow_progress_display,
        )
        ctx.vlog(f"[DEBUG] Final check error_message = '{error_message}'")

    ctx.vlog(f"[DEBUG] FINAL RESULT: state={last_invocation['state']}, job_state={job_state}, error='{error_message}'")
    return last_invocation["state"], job_state, error_message


def workflow_in_error_message(
    ctx,
    invocation_id,
    last_exception,
    last_invocation,
    last_invocation_jobs,
    invocation_api: InvocationApi,
    workflow_progress_display: WorkflowProgressDisplay,
    fail_fast=False,
) -> Optional[str]:
    """Return an error message if workflow is in an error state."""

    invocation_state = "new" if not last_invocation else last_invocation["state"]
    job_state = summary_job_state(last_invocation_jobs)

    ctx.vlog(f"[DEBUG] workflow_in_error_message: invocation {invocation_id}")
    ctx.vlog(f"[DEBUG] workflow_in_error_message: invocation_state = {invocation_state}")
    ctx.vlog(f"[DEBUG] workflow_in_error_message: job_state = {job_state}")
    ctx.vlog(f"[DEBUG] workflow_in_error_message: last_exception = {last_exception}")
    ctx.vlog(f"[DEBUG] workflow_in_error_message: fail_fast = {fail_fast}")
    ctx.vlog(
        f"[DEBUG] workflow_in_error_message: invocation_state_terminal({invocation_state}) = {invocation_state_terminal(invocation_state)}"
    )
    ctx.vlog(f"[DEBUG] workflow_in_error_message: job_state in JOB_ERROR_STATES = {job_state in JOB_ERROR_STATES}")

    error_message = None
    if last_exception:
        ctx.vlog("[DEBUG] workflow_in_error_message: Exception detected")
        ctx.vlog(f"Problem waiting on invocation: {str(last_exception)}")
        error_message = f"Final state of invocation {invocation_id} is [{invocation_state}]"
        ctx.vlog(f"[DEBUG] workflow_in_error_message: error_message from exception = '{error_message}'")

    if invocation_state_terminal(invocation_state) and invocation_state != "scheduled":
        msg = f"Failed to run workflow, invocation ended in [{invocation_state}] state."
        ctx.vlog("[DEBUG] workflow_in_error_message: Terminal non-scheduled state detected")
        ctx.vlog(msg)
        error_message = msg if not error_message else f"{error_message}. {msg}"
        ctx.vlog(f"[DEBUG] workflow_in_error_message: error_message from terminal state = '{error_message}'")

    # Print job errors when detected, regardless of fail_fast setting
    if job_state in JOB_ERROR_STATES:
        ctx.vlog("[DEBUG] workflow_in_error_message: Job errors detected")
        # Print failed job details when we detect job failures, using WorkflowProgress to avoid duplicates
        if invocation_api and workflow_progress_display:
            # Pass the Live display to print errors above the live panel
            workflow_progress_display.workflow_progress.print_job_errors_once(
                ctx, invocation_api, invocation_id, workflow_progress_display=workflow_progress_display
            )

        # Only return error message (which stops execution) when fail_fast is enabled
        if fail_fast:
            msg = f"Failed to run workflow, at least one job is in [{job_state}] state."
            ctx.vlog("[DEBUG] workflow_in_error_message: fail_fast enabled, setting error message")
            ctx.vlog(msg)
            error_message = msg if not error_message else f"{error_message}. {msg}"
            ctx.vlog(f"[DEBUG] workflow_in_error_message: error_message from job state = '{error_message}'")
        else:
            ctx.vlog("[DEBUG] workflow_in_error_message: fail_fast disabled, not setting error from job state")
    else:
        ctx.vlog("[DEBUG] workflow_in_error_message: No job errors detected")

    ctx.vlog(f"[DEBUG] workflow_in_error_message: final error_message = '{error_message}'")
    return error_message


# we're still mocking out the old history state by just picking out a random
# job state of interest. Seems like we should drop this.
def summary_job_state(job_states_summary: Optional[InvocationJobsSummary]):
    states = (job_states_summary or {"states": {}}).get("states", {}).copy()
    states.pop("ok", None)
    states.pop("skipped", None)
    if states:
        return next(iter(states.keys()))
    else:
        return "ok"


def subworkflow_invocation_ids(invocation_api: InvocationApi, invocation_id: str) -> List[str]:
    invocation = invocation_api.get_invocation(invocation_id)
    subworkflow_invocation_ids = []
    for step in invocation["steps"]:
        subworkflow_invocation_id = step.get("subworkflow_invocation_id")
        if subworkflow_invocation_id:
            subworkflow_invocation_ids.append(subworkflow_invocation_id)
    return subworkflow_invocation_ids
