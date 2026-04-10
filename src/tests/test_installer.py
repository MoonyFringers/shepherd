# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.net.

import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, call, patch

import pytest

# Import the module under test
from installer import install
from installer.install import get_script_completion_src
from installer.repository_manager import RepositoryManager
from util import Util


class TestInstallScript:
    def test_get_script_completion_src(self) -> None:
        """
        Test get_script_completion_src returns correct path and file exists.
        """
        path: Path
        filename: str
        path, filename = get_script_completion_src()
        assert filename == "shepctl_completion.sh"
        assert path.parent.name == "scripts"
        assert path.exists(), f"Completion script not found: {path}"

    @patch("os.chmod")
    @patch("shutil.copy2")
    @patch("pathlib.Path.is_dir")
    def test_install_completion_success(
        self,
        mock_is_dir: MagicMock,
        mock_copy2: MagicMock,
        mock_chmod: MagicMock,
    ) -> None:
        """
        Test install_completion when the destination directory exists.
        """
        mock_is_dir.return_value = True

        with (
            patch("installer.install.Util.console.print") as mock_print,
            patch(
                "installer.install.Util.get_os_info",
                return_value=Util.OsInfo(system="linux"),
            ),
        ):
            install.install_completion()

            dest = Path("/etc/bash_completion.d/shepctl_completion.sh")
            src, _ = get_script_completion_src()
            assert isinstance(src, Path)
            assert isinstance(src, Path)
            # Validate that the source file exists
            assert src.exists(), f"Source completion script not found: {src}"
            mock_copy2.assert_called_once_with(src, dest)
            mock_chmod.assert_called_once_with(dest, 0o755)
            mock_print.assert_any_call(
                "Shell completion script installed.", style="green"
            )

    @patch("shutil.rmtree")
    def test_uninstall(self, mock_rmtree: MagicMock) -> None:
        """
        Test uninstall: removes install dir, symlink, and completion script.
        """
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink") as mock_unlink,
            patch(
                "installer.install.Util.get_os_info",
                return_value=Util.OsInfo(system="linux"),
            ),
        ):
            install.uninstall_shepctl()

            # Check installation directory was removed
            mock_rmtree.assert_called_once_with(install.install_shepctl_dir)

            # Check that both symlink and autocompletion script were removed
            assert mock_unlink.call_count == 2
            # NOTE: it is not possible to directly check the paths passed to
            # unlink. Patching "pathlib.Path.unlink" at the class level means
            # the mock does not receive the Path instance as an argument. For
            # more precise checks, you would need to patch the individual Path
            # objects with patch.object.

            # ...existing code...

    @patch("pathlib.Path.is_dir")
    def test_install_completion_no_dir(self, mock_is_dir: MagicMock) -> None:
        # Simulate /etc/bash_completion.d does not exist
        mock_is_dir.return_value = False

        with (
            patch("installer.install.Util.console.print") as mock_print,
            patch(
                "installer.install.Util.get_os_info",
                return_value=Util.OsInfo(system="linux"),
            ),
        ):
            install.install_completion()
            mock_print.assert_any_call(
                "Bash completion directory not found. Please install "
                "manually.",
                style="yellow",
            )

    @patch("os.chmod")
    @patch("shutil.copy2")
    @patch("pathlib.Path.is_dir")
    def test_install_completion_success_macos(
        self,
        mock_is_dir: MagicMock,
        mock_copy2: MagicMock,
        mock_chmod: MagicMock,
    ) -> None:
        mock_is_dir.return_value = True

        with (
            patch("installer.install.Util.console.print"),
            patch(
                "installer.install.Util.get_os_info",
                return_value=Util.OsInfo(system="darwin"),
            ),
            patch(
                "installer.install.Util.get_default_install_paths",
                return_value=Util.InstallPaths(
                    install_dir=Path("/opt/homebrew/opt/shepctl"),
                    symlink_dir=Path("/opt/homebrew/bin"),
                ),
            ),
        ):
            install.install_completion()

            dest = Path(
                "/opt/homebrew/etc/bash_completion.d/" "shepctl_completion.sh"
            )
            src, _ = get_script_completion_src()
            mock_copy2.assert_called_once_with(src, dest)
            mock_chmod.assert_called_once_with(dest, 0o755)

    """Test suite for the main installation script."""

    def setup_method(self) -> None:
        """Set up test environment before each test."""
        # Reset global variables before each test
        install.verbose = False
        install.skip_ensure_deps = False
        install.install_method = "binary"

        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.install_dir = Path(self.temp_dir) / "shepctl"
        self.install_dir.mkdir(exist_ok=True)

        # Mock environment variables
        self.env_patcher = patch.dict(
            os.environ,
            {
                "INSTALL_SHEPCTL_DIR": str(self.install_dir),
                "SYMLINK_DIR": str(Path(self.temp_dir) / "bin"),
                "VER": "1.0.0",
            },
        )
        self.env_patcher.start()

        # Update paths after environment variable changes
        install.install_shepctl_dir = Path(
            os.environ["INSTALL_SHEPCTL_DIR"]
        ).resolve()
        install.symlink_dir = Path(os.environ["SYMLINK_DIR"])

    def teardown_method(self) -> None:
        """Clean up after each test."""
        self.env_patcher.stop()
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)

    def test_cli_help(self) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(install.cli, ["--help"])
        assert result.exit_code == 0
        assert "Shepherd Control Tool Installer" in result.output

    def test_cli_install_command(self) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(install.cli, ["install", "--help"])
        assert result.exit_code == 0
        assert "Install shepctl" in result.output

    def test_cli_uninstall_command(self) -> None:
        from click.testing import CliRunner

        runner = CliRunner()
        result = runner.invoke(install.cli, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Uninstall shepctl" in result.output

    @patch("util.Util.is_root")
    def test_cli_install_not_root(self, mock_is_root: MagicMock) -> None:
        from click.testing import CliRunner

        mock_is_root.return_value = False  # Simulate not running as root

        runner = CliRunner()
        result = runner.invoke(install.cli, ["install"])

        # Should exit with code 1
        assert result.exit_code == 1

    @patch("util.Util.is_root")
    @patch("util.Util.get_os_info")
    @patch("installer.install.install_shepctl")
    def test_cli_install_not_root_macos(
        self,
        mock_install_shepctl: MagicMock,
        mock_get_os_info: MagicMock,
        mock_is_root: MagicMock,
    ) -> None:
        from click.testing import CliRunner

        mock_is_root.return_value = False
        mock_get_os_info.return_value = Util.OsInfo(system="darwin")

        runner = CliRunner()
        result = runner.invoke(install.cli, ["install"])

        assert result.exit_code == 0
        mock_install_shepctl.assert_called_once()

    @patch("shutil.rmtree")
    @patch("os.makedirs")
    @patch("util.Util.is_root")
    @patch("installer.install.install_shepctl")
    def test_cli_install_as_root(
        self,
        mock_install_shepctl: MagicMock,
        mock_is_root: MagicMock,
        mock_makedirs: MagicMock,
        mock_rmtree: MagicMock,
    ) -> None:
        from click.testing import CliRunner

        mock_is_root.return_value = True

        runner = CliRunner()
        result = runner.invoke(
            install.cli,
            ["-m", "source", "-v", "--skip-deps", "install"],
        )

        # Should succeed
        assert result.exit_code == 0

        # Check install_shepctl was called
        mock_install_shepctl.assert_called_once()

    @patch("shutil.rmtree")
    @patch("os.makedirs")
    @patch("util.Util.is_root")
    @patch("installer.install.uninstall_shepctl")
    def test_cli_uninstall_as_root(
        self,
        mock_uninstall_shepctl: MagicMock,
        mock_is_root: MagicMock,
        mock_makedirs: MagicMock,
        mock_rmtree: MagicMock,
    ) -> None:
        """Test uninstall command when running as root."""
        from click.testing import CliRunner

        mock_is_root.return_value = True

        runner = CliRunner()
        result = runner.invoke(install.cli, ["uninstall"])

        # Should succeed
        assert result.exit_code == 0

        # Check uninstall_shepctl was called
        mock_uninstall_shepctl.assert_called_once()

    @patch("installer.install.RepositoryManager.install_packages")
    @patch("util.Util.get_os_info")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    @patch("installer.install.install_binary")
    @patch("installer.install.install_completion")
    @patch("util.Util.run_command")  # Patch the static method directly
    def test_install_with_dependencies(
        self,
        mock_run_command: MagicMock,
        mock_install_completion: MagicMock,
        mock_install_binary: MagicMock,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
        mock_get_os_info: MagicMock,
        mock_install_packages: MagicMock,
    ) -> None:
        """Test install function with dependency installation."""
        # Mock skip_ensure_deps
        install.skip_ensure_deps = False
        install.install_method = "binary"

        # Mock OS info
        mock_os_info = Util.OsInfo(
            system="linux",
            distro="ubuntu",
            codename="focal",
        )
        mock_get_os_info.return_value = mock_os_info

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            install.install_shepctl()

        # Check dependencies were installed
        mock_get_os_info.assert_called_once()
        mock_install_packages.assert_called_once_with(
            mock_os_info.system,
            mock_os_info.distro,
            mock_os_info.codename,
            False,
        )

        # Check directory was recreated
        mock_rmtree.assert_called_once_with(install.install_shepctl_dir)
        mock_makedirs.assert_called_once_with(
            install.install_shepctl_dir, exist_ok=True
        )

        # Verify the binary installation was called
        mock_install_binary.assert_called_once()

    @patch("util.Util.get_os_info")
    @patch("installer.install.RepositoryManager.install_packages")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    @patch("installer.install.install_binary")
    @patch("installer.install.install_completion")
    def test_install_skip_dependencies(
        self,
        mock_install_completion: MagicMock,
        mock_install_binary: MagicMock,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
        mock_get_os_info: MagicMock,
        mock_install_packages: MagicMock,
    ) -> None:
        """Test install function while skipping dependencies."""
        # Mock skip_ensure_deps
        install.skip_ensure_deps = True
        install.install_method = "binary"

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            install.install_shepctl()

        # Check dependencies were not installed
        mock_get_os_info.assert_not_called()
        mock_install_packages.assert_not_called()

        # Check directory was recreated
        mock_rmtree.assert_called_once_with(install.install_shepctl_dir)
        mock_makedirs.assert_called_once_with(
            install.install_shepctl_dir, exist_ok=True
        )

        # Verify the binary installation was called
        mock_install_binary.assert_called_once()

    @patch("os.makedirs")
    @patch("shutil.rmtree")
    def test_install_unknown_method(
        self,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
    ) -> None:
        """Test install function with unknown install method."""
        # Set unknown install method
        install.install_method = "unknown"
        install.skip_ensure_deps = True

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(SystemExit):
                install.install_shepctl()

    @patch("installer.install.Util.print_error_and_die")
    @patch("installer.install.Util.get_os_info")
    @patch("shutil.rmtree", side_effect=PermissionError)
    def test_install_permission_error_macos(
        self,
        mock_rmtree: MagicMock,
        mock_get_os_info: MagicMock,
        mock_print_error_and_die: MagicMock,
    ) -> None:
        install.skip_ensure_deps = True
        install.install_method = "binary"
        mock_get_os_info.return_value = Util.OsInfo(system="darwin")
        mock_print_error_and_die.side_effect = SystemExit(1)

        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(SystemExit):
                install.install_shepctl()

        mock_print_error_and_die.assert_called_once()
        assert "previous macOS install was created with sudo" in (
            mock_print_error_and_die.call_args.args[0]
        )

    @patch("installer.install.Util.print_error_and_die")
    @patch("installer.install.Util.get_os_info")
    @patch("shutil.rmtree", side_effect=PermissionError)
    def test_uninstall_permission_error_macos(
        self,
        mock_rmtree: MagicMock,
        mock_get_os_info: MagicMock,
        mock_print_error_and_die: MagicMock,
    ) -> None:
        mock_get_os_info.return_value = Util.OsInfo(system="darwin")
        mock_print_error_and_die.side_effect = SystemExit(1)

        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(SystemExit):
                install.uninstall_shepctl()

        mock_print_error_and_die.assert_called_once()
        assert "previous macOS install was created with sudo" in (
            mock_print_error_and_die.call_args.args[0]
        )

    # ...existing code...

    @patch("util.Util.check_file_exists", return_value=False)
    @patch("util.Util.run_command")
    @patch("util.Util.get_current_user", return_value="testuser")
    @patch(
        "installer.repository_manager.RepositoryManager."
        "check_package_installed"
    )
    @patch(
        "installer.repository_manager.RepositoryManager.add_docker_repository"
    )
    @patch(
        "installer.repository_manager.RepositoryManager."
        "install_missing_packages"
    )
    def test_install_docker_packages(
        self,
        mock_install_missing_packages: MagicMock,
        mock_add_docker_repository: MagicMock,
        mock_check_package_installed: MagicMock,
        mock_get_current_user: MagicMock,
        mock_run_command: MagicMock,
        mock_check_file_exists: MagicMock,
    ) -> None:
        """Test the installation of Docker packages."""
        # Simulate Docker not being installed
        mock_check_package_installed.return_value = False

        # Simulate successful command execution
        mock_run_command.return_value = MagicMock(
            stdout="Docker version 20.10.7"
        )

        # Call the function under test
        RepositoryManager.install_docker_packages("linux", "debian", "buster")

        # Verify that add_docker_repository was called with correct arguments
        mock_add_docker_repository.assert_called_once_with("debian", "buster")

        # Verify that install_missing_packages was called for Docker packages
        mock_install_missing_packages.assert_called()

        # Verify that the required commands were called
        expected_calls = [
            call(["docker", "--version"], check=False, capture_output=True),
            call(
                ["docker", "compose", "version"],
                check=False,
                capture_output=True,
            ),
            call(["sudo", "systemctl", "enable", "docker"], check=True),
            call(["sudo", "groupadd", "-f", "docker"], check=True),
            call(["usermod", "-aG", "docker", "testuser"], check=True),
        ]
        mock_run_command.assert_has_calls(expected_calls, any_order=True)

        # Verify that the package installation function was called
        expected_package = "docker-compose-plugin"
        mock_check_package_installed.assert_called_with(expected_package)

    @patch("installer.repository_manager.Util.console.print")
    @patch("installer.repository_manager.Util.run_command")
    @patch(
        "installer.repository_manager.RepositoryManager."
        "install_missing_brew_packages"
    )
    @patch(
        "installer.repository_manager.RepositoryManager."
        "check_brew_package_installed"
    )
    def test_install_docker_packages_macos_warns_without_daemon(
        self,
        mock_check_brew_package_installed: MagicMock,
        mock_install_missing_brew_packages: MagicMock,
        mock_run_command: MagicMock,
        mock_print: MagicMock,
    ) -> None:
        mock_check_brew_package_installed.return_value = False
        mock_run_command.side_effect = [
            MagicMock(stdout="Docker version 27.0.0", returncode=0),
            MagicMock(stderr="compose missing", returncode=1),
            MagicMock(stdout="Docker Compose version v2.0.0", returncode=0),
            MagicMock(stderr="daemon unavailable", returncode=1),
        ]

        RepositoryManager.install_docker_packages("darwin", None, None)

        mock_check_brew_package_installed.assert_called_once_with("docker")
        mock_install_missing_brew_packages.assert_any_call(["docker"])
        mock_install_missing_brew_packages.assert_any_call(["docker-compose"])
        mock_run_command.assert_has_calls(
            [
                call(
                    ["docker", "--version"],
                    check=False,
                    capture_output=True,
                ),
                call(
                    ["docker", "compose", "version"],
                    check=False,
                    capture_output=True,
                ),
                call(
                    ["docker", "compose", "version"],
                    check=False,
                    capture_output=True,
                ),
                call(["docker", "info"], check=False, capture_output=True),
            ]
        )
        mock_print.assert_any_call(
            "Docker CLI installed, but no Docker daemon is reachable. "
            "Install and start Docker Desktop before using shepctl.",
            style="yellow",
        )

    @patch("installer.repository_manager.Util.run_command")
    @patch(
        "installer.repository_manager.RepositoryManager."
        "install_missing_brew_packages"
    )
    @patch(
        "installer.repository_manager.RepositoryManager."
        "check_brew_package_installed"
    )
    def test_install_docker_packages_macos_skips_redundant_compose_install(
        self,
        mock_check_brew_package_installed: MagicMock,
        mock_install_missing_brew_packages: MagicMock,
        mock_run_command: MagicMock,
    ) -> None:
        mock_check_brew_package_installed.return_value = True
        mock_run_command.side_effect = [
            MagicMock(stdout="Docker version 27.0.0", returncode=0),
            MagicMock(stdout="Docker Compose version v2.0.0", returncode=0),
            MagicMock(stdout="daemon reachable", returncode=0),
        ]

        RepositoryManager.install_docker_packages("darwin", None, None)

        mock_check_brew_package_installed.assert_called_once_with("docker")
        mock_install_missing_brew_packages.assert_not_called()

    @patch(
        "installer.repository_manager.RepositoryManager."
        "install_missing_brew_packages"
    )
    @patch(
        "installer.repository_manager.RepositoryManager."
        "check_brew_package_installed"
    )
    def test_install_required_packages_macos(
        self,
        mock_check_brew_package_installed: MagicMock,
        mock_install_missing_brew_packages: MagicMock,
    ) -> None:
        mock_check_brew_package_installed.side_effect = [
            False,
            True,
            False,
            True,
        ]

        RepositoryManager.install_required_packages("darwin", None)

        mock_install_missing_brew_packages.assert_called_once_with(
            ["bc", "curl"]
        )

    @patch("util.Util.run_command")
    def test_install_binary(self, mock_run_command: MagicMock) -> None:
        """Test binary installation method."""
        # Mock successful command execution
        mock_run_command.return_value = MagicMock(returncode=0)

        with patch.dict(os.environ, {"VER": "1.0.0"}):
            with (
                patch("os.chmod") as mock_chmod,
                patch("os.symlink") as mock_symlink,
            ):
                install.install_binary()

                expected_url = (
                    "https://github.com/MoonyFringers/shepherd/"
                    "releases/download/v1.0.0/shepctl-1.0.0.tar.gz"
                )

                # Verify the sequence of commands
                expected_calls = [
                    # First, the curl command
                    mock.call(
                        [
                            "curl",
                            "-fsSL",
                            expected_url,
                            "-o",
                            f"{self.install_dir}/shepctl-1.0.0.tar.gz",
                        ],
                        check=True,
                    ),
                    # Then, the tar command
                    mock.call(
                        [
                            "tar",
                            "-xzf",
                            f"{self.install_dir}/shepctl-1.0.0.tar.gz",
                            "-C",
                            str(self.install_dir),
                        ],
                        check=True,
                    ),
                ]
                mock_run_command.assert_has_calls(
                    expected_calls, any_order=False
                )  # Enforce the order of calls

                mock_chmod.assert_called_with(
                    f"{self.install_dir}/shepctl", 0o755
                )

                mock_symlink.assert_called_with(
                    f"{self.install_dir}/shepctl",
                    Path(os.environ["SYMLINK_DIR"]).resolve() / "shepctl",
                )


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
