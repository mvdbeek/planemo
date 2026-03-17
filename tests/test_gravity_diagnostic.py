"""Diagnostic tests to investigate galaxyctl disappearing from virtualenv.

These tests are gated behind PLANEMO_DIAG_TESTS=1 since they install
packages into temporary virtualenvs and can be slow.

The goal is to determine WHY the galaxyctl binary disappears from the
Galaxy virtualenv between startup and shutdown during planemo test runs.
See: https://github.com/galaxyproject/planemo/issues/XXXX
"""

import glob
import os
import subprocess
import sys

import pytest

DIAG_SKIP = pytest.mark.skipif(
    not os.environ.get("PLANEMO_DIAG_TESTS"),
    reason="Diagnostic tests, set PLANEMO_DIAG_TESTS=1 to run",
)


def _create_venv(path):
    subprocess.check_call([sys.executable, "-m", "venv", str(path)])
    return str(path)


def _pip(venv, *args, quiet=False):
    pip_bin = os.path.join(venv, "bin", "pip")
    cmd = [pip_bin] + list(args)
    env = os.environ.copy()
    if quiet:
        env["PIP_QUIET"] = "1"
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=env)


def _galaxyctl_path(venv):
    return os.path.join(venv, "bin", "galaxyctl")


def _galaxy_bins(venv):
    bin_dir = os.path.join(venv, "bin")
    return sorted(
        glob.glob(os.path.join(bin_dir, "galaxy*")) + glob.glob(os.path.join(bin_dir, "gravity*"))
    )


@DIAG_SKIP
class TestGravityInstallation:
    """Test that galaxyctl entry point survives various pip operations."""

    def test_gravity_install_creates_galaxyctl(self, tmp_path):
        """Verify basic gravity install creates the galaxyctl binary."""
        venv = _create_venv(tmp_path / "venv")
        result = _pip(venv, "install", "gravity")
        assert result.returncode == 0, f"Failed to install gravity: {result.stderr}"

        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), (
            f"galaxyctl not found after gravity install.\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"pip output: {result.stdout[-500:]}"
        )

    def test_galaxyctl_survives_reinstall(self, tmp_path):
        """Check if galaxyctl survives pip reinstall of gravity."""
        venv = _create_venv(tmp_path / "venv")
        _pip(venv, "install", "gravity")
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed initially"

        # Force reinstall (simulating common_startup.sh running twice)
        result = _pip(venv, "install", "--force-reinstall", "gravity")
        assert os.path.exists(galaxyctl), (
            f"galaxyctl disappeared after force-reinstall!\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"pip stderr: {result.stderr[-500:]}"
        )

    def test_galaxyctl_survives_upgrade(self, tmp_path):
        """Check if galaxyctl survives pip upgrade of gravity."""
        venv = _create_venv(tmp_path / "venv")
        _pip(venv, "install", "gravity")
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed initially"

        result = _pip(venv, "install", "--upgrade", "gravity")
        assert os.path.exists(galaxyctl), (
            f"galaxyctl disappeared after upgrade!\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"pip stderr: {result.stderr[-500:]}"
        )

    def test_galaxyctl_survives_quiet_reinstall(self, tmp_path):
        """Check if PIP_QUIET=1 affects galaxyctl installation."""
        venv = _create_venv(tmp_path / "venv")
        _pip(venv, "install", "gravity")
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed initially"

        # Reinstall with PIP_QUIET=1 (matches CI environment)
        result = _pip(venv, "install", "--force-reinstall", "gravity", quiet=True)
        assert os.path.exists(galaxyctl), (
            f"galaxyctl disappeared after quiet force-reinstall!\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"pip stderr: {result.stderr[-500:]}"
        )


@DIAG_SKIP
class TestGravityWithGalaxyDeps:
    """Test galaxyctl survival when Galaxy dependencies are installed alongside."""

    def test_galaxyctl_survives_galaxy_app_install(self, tmp_path):
        """Check if galaxyctl survives installing galaxy-app (which depends on gravity)."""
        venv = _create_venv(tmp_path / "venv")

        # Install gravity first
        _pip(venv, "install", "gravity")
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed initially"

        # Install galaxy-app which pulls in gravity as a dependency
        result = _pip(venv, "install", "galaxy-app")

        survived = os.path.exists(galaxyctl)
        bins = _galaxy_bins(venv)
        pip_show = _pip(venv, "show", "gravity")

        assert survived, (
            f"galaxyctl disappeared after galaxy-app install!\n"
            f"galaxy/gravity bins: {bins}\n"
            f"pip show gravity: {pip_show.stdout}\n"
            f"pip install stderr: {result.stderr[-1000:]}"
        )

    def test_galaxyctl_survives_concurrent_pip(self, tmp_path):
        """Check if concurrent pip operations can remove galaxyctl.

        This simulates the scenario where common_startup.sh runs twice
        (once in _install_with_command, once in run.sh).
        """
        venv = _create_venv(tmp_path / "venv")
        _pip(venv, "install", "gravity")
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed initially"

        # Run two pip installs concurrently
        env = os.environ.copy()
        pip_bin = os.path.join(venv, "bin", "pip")
        procs = []
        for _ in range(2):
            p = subprocess.Popen(
                [pip_bin, "install", "--force-reinstall", "gravity"],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            procs.append(p)

        outputs = []
        for p in procs:
            stdout, stderr = p.communicate(timeout=300)
            outputs.append((p.returncode, stdout.decode(), stderr.decode()))

        survived = os.path.exists(galaxyctl)
        bins = _galaxy_bins(venv)

        assert survived, (
            f"galaxyctl disappeared after concurrent pip installs!\n"
            f"galaxy/gravity bins: {bins}\n"
            f"Process results: {[(rc, err[-200:]) for rc, _, err in outputs]}"
        )


@DIAG_SKIP
class TestGravityWithUv:
    """Test galaxyctl survival when uv is used instead of pip.

    Galaxy's common_startup.sh uses uv if available:
      if command -v uv >/dev/null; then PIP_CMD="$(command -v uv) pip"
    """

    def test_galaxyctl_survives_uv_install(self, tmp_path):
        """Check if galaxyctl survives when gravity is installed via uv pip."""
        import shutil

        uv_bin = shutil.which("uv")
        if not uv_bin:
            pytest.skip("uv not available")

        venv = _create_venv(tmp_path / "venv")
        # Install gravity with uv pip (as Galaxy's common_startup.sh would)
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = venv
        result = subprocess.run(
            [uv_bin, "pip", "install", "gravity"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), (
            f"galaxyctl not found after uv pip install.\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"uv output: {result.stdout[-500:]}\n"
            f"uv stderr: {result.stderr[-500:]}"
        )

    def test_galaxyctl_survives_uv_then_pip_reinstall(self, tmp_path):
        """Check if galaxyctl survives mixed uv/pip usage.

        common_startup.sh may install with uv, but planemo's
        _install_with_command may use pip. Check for conflicts.
        """
        import shutil

        uv_bin = shutil.which("uv")
        if not uv_bin:
            pytest.skip("uv not available")

        venv = _create_venv(tmp_path / "venv")
        env = os.environ.copy()
        env["VIRTUAL_ENV"] = venv

        # First install with uv (as Galaxy would)
        subprocess.run(
            [uv_bin, "pip", "install", "gravity"],
            capture_output=True, text=True, timeout=300, env=env,
        )
        galaxyctl = _galaxyctl_path(venv)
        assert os.path.exists(galaxyctl), "galaxyctl not installed via uv"

        # Then reinstall with regular pip (as a second common_startup.sh run might)
        result = _pip(venv, "install", "--force-reinstall", "gravity")
        assert os.path.exists(galaxyctl), (
            f"galaxyctl disappeared after pip reinstall over uv install!\n"
            f"Bins: {_galaxy_bins(venv)}\n"
            f"pip stderr: {result.stderr[-500:]}"
        )
