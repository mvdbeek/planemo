"""Abstractions for serving out development Galaxy servers."""

import contextlib
import os
import time

from planemo import (
    io,
    network_util,
)
from .config import galaxy_config
from .ephemeris_sleep import sleep
from .run import run_galaxy_command


@contextlib.contextmanager
def serve(ctx, runnables=None, **kwds):
    if runnables is None:
        runnables = []
    """Serve a Galaxy instance with artifacts defined by paths."""
    try:
        with _serve(ctx, runnables, **kwds) as config:
            yield config
    except Exception as e:
        ctx.vlog("Problem serving Galaxy", exception=e)
        raise


@contextlib.contextmanager
def _serve(ctx, runnables, **kwds):
    engine = kwds.get("engine", "galaxy")
    if engine == "docker_galaxy":
        kwds["dockerize"] = True

    daemon = kwds.get("daemon", False)
    if daemon:
        kwds["no_cleanup"] = True

    port = kwds.get("port", None)
    if port is None:
        port = network_util.get_free_port()
        kwds["port"] = port

    with galaxy_config(ctx, runnables, **kwds) as config:
        cmd = config.startup_command(ctx, **kwds)
        action = "Starting Galaxy"
        exit_code = run_galaxy_command(
            ctx,
            cmd,
            config.env,
            action,
        )
        if exit_code:
            log_contents = config.log_contents
            _print_config_log_contents(config, log_contents)
            message = "Problem running Galaxy command [%s]." % log_contents
            io.warn(message)
            raise Exception(message)
        host = kwds.get("host", "127.0.0.1")

        startup_timeout = kwds.get("galaxy_startup_timeout", 300)
        galaxy_url = f"http://{host}:{port}"
        galaxy_alive = sleep(galaxy_url, verbose=ctx.verbose, timeout=startup_timeout)
        if not galaxy_alive:
            log_contents = config.log_contents
            _print_config_log_contents(config, log_contents)
            raise Exception(
                f"Attempted to serve Galaxy at {galaxy_url}, but it failed to start in {startup_timeout} seconds."
                f"\nGalaxy log contents:\n{log_contents}"
            )
        config.install_workflows()
        if kwds.get("pid_file"):
            real_pid_file = config.pid_file
            if os.path.exists(config.pid_file):
                os.symlink(real_pid_file, kwds["pid_file"])
            else:
                io.warn("Can't find Galaxy pid file [%s] to link" % real_pid_file)
        yield config


@contextlib.contextmanager
def serve_daemon(ctx, runnables=None, **kwds):
    """Serve a daemonized Galaxy instance with artifacts defined by paths."""
    if runnables is None:
        runnables = []
    config = None
    kwds["daemon"] = True
    try:
        with serve(ctx, runnables, **kwds) as config:
            yield config
    finally:
        if config:
            if ctx.verbose:
                print("Galaxy Log:")
                print(config.log_contents)
            config.kill()
            if not kwds.get("no_cleanup", False):
                config.cleanup()


def _print_config_log_contents(config, log_contents):
    """Print Galaxy log contents to fd 2 (stderr) for diagnostics.

    Uses os.write(2, ...) to bypass click's CliRunner which globally
    replaces sys.stderr during runner.invoke(). This code runs inside
    click's invoke context, so sys.stderr points to click's buffer.
    Writing to fd 2 directly ensures output reaches pytest's capture
    or the real stderr.
    """
    gravity_state_dir = config.env.get("GRAVITY_STATE_DIR", "")
    header = f"=== Galaxy startup failure (gravity_state_dir={gravity_state_dir}) ==="

    def _log(msg):
        os.write(2, (msg + "\n").encode())

    _log(f"\n{header}")
    if log_contents:
        _log(log_contents)
    else:
        _log("(no log contents found)")
    _log("=" * len(header))


def sleep_for_serve():
    # This is bad, do something better...
    for _ in range(3600 * 24):
        time.sleep(1)


__all__ = (
    "serve",
    "serve_daemon",
)
