# Copyright (c) 2025 Lunatic Fringers
#
# This file is part of Shepherd Core Stack
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import shutil
import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, call, patch

import pytest

# Import the module under test
from installer import install, install_utils
from installer.install_utils import OsInfo


class TestInstallScript:
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

    def test_parse_arguments_install(self) -> None:
        """Test argument parsing with install command."""
        with patch("sys.argv", ["installer.install.py", "install"]):
            args = install.parse_arguments()
            assert args.command == "install"
            assert args.install_method == "binary"
            assert not args.verbose
            assert not args.skip_deps

    def test_parse_arguments_uninstall(self) -> None:
        """Test argument parsing with uninstall command."""
        with patch("sys.argv", ["installer.install.py", "uninstall"]):
            args = install.parse_arguments()
            assert args.command == "uninstall"
            assert args.install_method == "binary"
            assert not args.verbose
            assert not args.skip_deps

    def test_parse_arguments_with_options(self) -> None:
        """Test argument parsing with additional options."""
        with patch(
            "sys.argv",
            [
                "installer.install.py",
                "-m",
                "source",
                "-v",
                "--skip-deps",
                "install",
            ],
        ):
            args = install.parse_arguments()
            assert args.command == "install"
            assert args.install_method == "source"
            assert args.verbose
            assert args.skip_deps

    @patch("installer.install.is_root")
    def test_main_not_root(self, mock_is_root: MagicMock) -> None:
        """Test main function when not running as root."""
        mock_is_root.return_value = False  # Simulate not running as root

        # Catch the SystemExit exception
        with pytest.raises(SystemExit) as excinfo:
            install.main()  # Call the original main function

        # Verify the exit code
        assert excinfo.value.code == 1

    @patch("installer.install.is_root")
    @patch("installer.install.parse_arguments")
    @patch("installer.install.install")
    def test_main_install(
        self,
        mock_installer: MagicMock,
        mock_parse_args: MagicMock,
        mock_is_root: MagicMock,
    ) -> None:
        """Test main function with install command."""
        mock_is_root.return_value = True

        # Mock the argument parser
        args = MagicMock()
        args.command = "install"
        args.verbose = True
        args.skip_deps = False
        args.install_method = "binary"
        mock_parse_args.return_value = args

        install.main()

        # Check global variables were set correctly
        assert install.verbose is True
        assert install.skip_ensure_deps is False
        assert install.install_method == "binary"

        # Check install was called
        mock_installer.assert_called_once()

    @patch("installer.install.is_root")
    @patch("installer.install.parse_arguments")
    @patch("installer.install.uninstall")
    def test_main_uninstall(
        self,
        mock_uninstaller: MagicMock,
        mock_parse_args: MagicMock,
        mock_is_root: MagicMock,
    ) -> None:
        """Test main function with uninstall command."""
        mock_is_root.return_value = True

        # Mock the argument parser
        args = MagicMock()
        args.command = "uninstall"
        args.verbose = False
        args.skip_deps = True
        args.install_method = "source"
        mock_parse_args.return_value = args

        install.main()

        # Check global variables were set correctly
        assert install.verbose is False
        assert install.skip_ensure_deps is True
        assert install.install_method == "source"

        # Check uninstall was called
        mock_uninstaller.assert_called_once()

    @patch("installer.install.is_root")
    @patch("installer.install.parse_arguments")
    def test_main_unknown_command(
        self, mock_parse_args: MagicMock, mock_is_root: MagicMock
    ) -> None:
        """Test main function with unknown command."""
        mock_is_root.return_value = True

        # Mock the argument parser
        args = MagicMock()
        args.command = "unknown"
        mock_parse_args.return_value = args

        with patch("sys.exit") as mock_exit:
            install.main()
            mock_exit.assert_called_once_with(1)

    @patch("installer.install_utils.print_color")
    @patch("installer.install.get_os_info")
    @patch("installer.install.install_packages")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    @patch("installer.install.install_binary")  # Mock binary installation
    @patch(
        "installer.install_utils.run_command"
    )  # Mock run_command to prevent real system calls
    def test_install_with_dependencies(
        self,
        mock_run_command: MagicMock,
        mock_install_binary: MagicMock,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
        mock_install_pkgs: MagicMock,
        mock_get_os_info: MagicMock,
        mock_print: MagicMock,
    ) -> None:
        """Test install function with dependency installation."""
        # Mock skip_ensure_deps
        install.skip_ensure_deps = False
        install.install_method = "binary"

        # Mock OS info
        mock_os_info = OsInfo(system="linux", distro="ubuntu", codename="focal")
        mock_get_os_info.return_value = mock_os_info

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            install.install()

        # Check dependencies were installed
        mock_get_os_info.assert_called_once()
        mock_install_pkgs.assert_called_once_with(
            mock_os_info.distro, mock_os_info.codename, False
        )

        # Check directory was recreated
        mock_rmtree.assert_called_once_with(install.install_shepctl_dir)
        mock_makedirs.assert_called_once_with(
            install.install_shepctl_dir, exist_ok=True
        )

        # Verify the binary installation was called
        mock_install_binary.assert_called_once()

    @patch("installer.install.print_color")
    @patch("installer.install.get_os_info")
    @patch("installer.install.install_packages")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    @patch("installer.install.install_binary")  # Mock binary installation
    def test_install_skip_dependencies(
        self,
        mock_install_binary: MagicMock,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
        mock_install_pkgs: MagicMock,
        mock_get_os_info: MagicMock,
        mock_print: MagicMock,
    ) -> None:
        """Test install function while skipping dependencies."""
        # Mock skip_ensure_deps
        install.skip_ensure_deps = True
        install.install_method = "binary"

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            install.install()

        # Check dependencies were not installed
        mock_get_os_info.assert_not_called()
        mock_install_pkgs.assert_not_called()

        # Check directory was recreated
        mock_rmtree.assert_called_once_with(install.install_shepctl_dir)
        mock_makedirs.assert_called_once_with(
            install.install_shepctl_dir, exist_ok=True
        )

        # Verify the binary installation was called
        mock_install_binary.assert_called_once()

    @patch("installer.install.print_color")
    @patch("os.makedirs")
    @patch("shutil.rmtree")
    def test_install_unknown_method(
        self,
        mock_rmtree: MagicMock,
        mock_makedirs: MagicMock,
        mock_print: MagicMock,
    ) -> None:
        """Test install function with unknown install method."""
        # Set unknown install method
        install.install_method = "unknown"
        install.skip_ensure_deps = True

        # Mock install_shepctl_dir exists
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(SystemExit):
                install.install()

    @patch("installer.install.print_color")
    @patch("shutil.rmtree")
    def test_uninstall(
        self, mock_rmtree: MagicMock, mock_print: MagicMock
    ) -> None:
        """Test uninstall function."""
        # Mock Path.exists and Path.unlink
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink") as mock_unlink,
        ):
            install.uninstall()

            # Check installation directory was removed
            mock_rmtree.assert_called_once_with(install.install_shepctl_dir)

            # Check symlink was removed
            mock_unlink.assert_called_once()

    @patch("installer.install_utils.check_file_exists", return_value=False)
    @patch("installer.install_utils.run_command")
    @patch("installer.install_utils.check_package_installed")
    @patch("installer.install_utils.add_docker_repository")
    @patch("installer.install_utils.install_missing_packages")
    def test_install_docker_packages(
        self,
        mock_install_missing_packages: MagicMock,
        mock_add_docker_repository: MagicMock,
        mock_check_package_installed: MagicMock,
        mock_run_command: MagicMock,
        mock_check_file_exists: MagicMock,
    ) -> None:
        """Test the installation of Docker packages."""
        current_user = os.getenv("USER")

        # Simulate Docker not being installed
        mock_check_package_installed.return_value = False

        # Simulate successful command execution
        mock_run_command.return_value = MagicMock(
            stdout="Docker version 20.10.7"
        )

        # Call the function under test
        install_utils.install_docker_packages("debian", "buster")

        # Verify that add_docker_repository was called with correct arguments
        mock_add_docker_repository.assert_called_once_with("debian", "buster")

        # Verify that install_missing_packages was called for Docker packages
        mock_install_missing_packages.assert_called()

        # Verify that the required commands were called
        expected_calls = [
            call(["docker", "--version"], check=False, capture_output=True),
            call(
                ["docker-compose", "--version"],
                check=False,
                capture_output=True,
            ),
            call(["sudo", "systemctl", "enable", "docker"], check=True),
            call(["sudo", "groupadd", "-f", "docker"], check=True),
            call(["usermod", "-aG", "docker", current_user], check=True),
        ]
        mock_run_command.assert_has_calls(expected_calls, any_order=True)

        # Verify that the package installation function was called
        mock_check_package_installed.assert_called_with("docker-compose-plugin")

    @patch("installer.install_utils.run_command")
    @patch("installer.install.print_color")
    def test_install_binary(
        self, mock_print: MagicMock, mock_run_command: MagicMock
    ) -> None:
        """Test binary installation method."""
        # Mock successful command execution
        mock_run_command.return_value = MagicMock(returncode=0)

        # Set the VER environment variable for the test
        with patch.dict(os.environ, {"VER": "1.0.0"}):
            # Create a temporary URL for testing
            url = (
                "https://github.com/LunaticFringers/shepherd/releases/download/"
                "v1.0.0/shepctl-1.0.0.tar.gz"
            )

            with (
                patch("installer.install.url", url),
                patch("os.chmod") as mock_chmod,
                patch("os.symlink") as mock_symlink,
            ):

                install.install_binary()

                # Verify the sequence of commands
                expected_calls = [
                    # First, the curl command
                    mock.call(
                        [
                            "curl",
                            "-fsSL",
                            url,
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
                            Path(self.install_dir),
                        ],
                        check=True,
                    ),
                ]
                mock_run_command.assert_has_calls(
                    expected_calls, any_order=False
                )  # Enforce the order of calls

                # Check executable permissions were set
                mock_chmod.assert_called_with(
                    f"{self.install_dir}/shepctl", 0o755
                )

                # Check symlink was created
                mock_symlink.assert_called_with(
                    f"{self.install_dir}/shepctl",
                    Path(f"{os.environ['SYMLINK_DIR']}/shepctl"),
                )

    @patch("installer.install_utils.run_command")
    @patch("installer.install.print_color")
    def test_install_source(
        self, mock_print: MagicMock, mock_run_command: MagicMock
    ) -> None:
        """Test source installation method."""
        # Mock successful command execution
        mock_run_command.return_value = MagicMock(returncode=0)

        # Set the VER environment variable for the test
        with patch.dict(os.environ, {"VER": "1.0.0"}):
            # Create expected source URL
            source_url = (
                "https://github.com/LunaticFringers/shepherd/archive/refs/tags/"
                "v1.0.0.tar.gz"
            )

            with (
                patch("os.symlink") as mock_symlink,
                # Symlink doesn't exist initially
                patch("pathlib.Path.exists", return_value=False),
                patch(
                    "installer.install.manage_python_dependencies"
                ) as mock_manage_deps,
            ):
                # Set skip_ensure_deps to False to test dependency management
                install.skip_ensure_deps = False

                install.install_source()

                # Verify the sequence of commands (download and extract)
                expected_calls = [
                    # First, the download command (curl)
                    mock.call(
                        [
                            "curl",
                            "-fsSL",
                            source_url,
                            "-o",
                            f"{self.install_dir}/shepctl-1.0.0.tar.gz",
                        ],
                        check=True,
                    ),
                    # Then, the extract command (tar)
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

                # Verify Python dependencies were managed
                mock_manage_deps.assert_called_once()

                # Check symlink was created
                mock_symlink.assert_called_with(
                    str(self.install_dir / "bin" / "shepctl"),
                    Path(f"{os.environ['SYMLINK_DIR']}/shepctl"),
                )


if __name__ == "__main__":
    pytest.main(["-xvs", __file__])
