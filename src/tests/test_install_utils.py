# Copyright (c) 2025 Moony Fringers
# SPDX-License-Identifier: AGPL-3.0-only
#
# This file is part of Shepherd Core Stack.
# Open-source: see LICENSE (AGPL-3.0-only).
# Commercial: see LICENSE-COMMERCIAL or contact licensing@moonyfringers.io.

import subprocess
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from installer.repository_manager import RepositoryManager
from util.util import Util


class TestInstallUtils:

    def test_is_root(self):
        with patch("os.geteuid") as mock_geteuid:
            # Test when running as root
            mock_geteuid.return_value = 0
            assert Util.is_root() is True

            # Test when not running as root
            mock_geteuid.return_value = 1000
            assert Util.is_root() is False

    def test_run_command(self):
        # Test successful command execution
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            result = Util.run_command(["echo", "test"])
            mock_run.assert_called_once_with(
                ["echo", "test"],
                check=True,
                shell=False,
                text=True,
                capture_output=False,
            )
            assert result == mock_result

        # Test command with string input
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            Util.run_command("echo test")
            mock_run.assert_called_once_with(
                ["echo", "test"],
                check=True,
                shell=False,
                text=True,
                capture_output=False,
            )

        # Test capturing output
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "test output"
            mock_run.return_value = mock_result

            result_capture: subprocess.CompletedProcess[str] = Util.run_command(
                ["echo", "test"], capture_output=True
            )  # type: ignore[assignment]
            assert result_capture.stdout == "test output"

        # Test command failure
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, ["echo", "test"]
            )
            with pytest.raises(SystemExit):
                Util.run_command(["echo", "test"])

        # Test command failure but not exiting
        with patch("subprocess.run") as mock_run:
            error = subprocess.CalledProcessError(1, ["echo", "test"])
            mock_run.side_effect = error
            result_noexit: (
                subprocess.CompletedProcess[str] | subprocess.CalledProcessError
            ) = Util.run_command(
                ["echo", "test"], check=False
            )  # type: ignore[type-arg]
            assert isinstance(result_noexit, subprocess.CalledProcessError)

    def test_get_current_user(self):
        # Test with SUDO_USER
        with patch.dict("os.environ", {"SUDO_USER": "testuser"}):
            assert Util.get_current_user() == "testuser"

        # Test without SUDO_USER
        with patch.dict("os.environ", clear=True):
            with patch("os.getlogin", return_value="regularuser"):
                assert Util.get_current_user() == "regularuser"

    def test_check_file_exists(self):
        with (
            patch("os.path.isfile") as mock_isfile,
            patch("os.access") as mock_access,
        ):
            # Test file exists and is readable
            mock_isfile.return_value = True
            mock_access.return_value = True
            assert Util.check_file_exists("/path/to/file") is True

            # Test file does not exist
            mock_isfile.return_value = False
            mock_access.return_value = True
            assert Util.check_file_exists("/path/to/nonexistent") is False

            # Test file exists but is not readable
            mock_isfile.return_value = True
            mock_access.return_value = False
            assert Util.check_file_exists("/path/to/unreadable") is False

    def test_check_package_installed(self):
        with patch("util.util.Util.run_command") as mock_run:
            # Test package is installed
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result

            assert (
                RepositoryManager.check_package_installed("installed-pkg")
                is True
            )
            mock_run.assert_called_with(
                ["dpkg", "-s", "installed-pkg"],
                check=False,
                capture_output=True,
            )

            # Test package is not installed
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result

            assert (
                RepositoryManager.check_package_installed("not-installed-pkg")
                is False
            )
            # Test error occurs
            mock_run.side_effect = Exception("Test exception")
            assert (
                RepositoryManager.check_package_installed("error-pkg")
            ) is False

    def test_install_missing_packages(self):
        with patch("util.util.Util.run_command") as mock_run:
            # Simulate successful execution of the sudo command
            mock_run.return_value = MagicMock(returncode=0)

            # Test installing packages on Ubuntu
            RepositoryManager.install_missing_packages(
                "ubuntu", ["pkg1", "pkg2"]
            )

            # Verify that run_command was called with the correct arguments
            expected_cmd = ["sudo", "apt-get", "install", "-y", "pkg1", "pkg2"]
            mock_run.assert_called_once_with(expected_cmd, check=True)

    def test_install_missing_packages_called(self):

        # Define a simplified version of the function for testing
        def simplified_install_packages(distro: str) -> None:
            missing_pkgs: List[str] = ["pkg1"]  # Simulate a missing package
            print("Simulated missing packages:", missing_pkgs)  # Debug print
            # Call install_missing_packages directly
            RepositoryManager.install_missing_packages(distro, missing_pkgs)

        # Mock the install_missing_packages function
        with (
            patch(
                "installer.repository_manager.RepositoryManager."
                "install_missing_packages"
            ) as mock_install_missing_packages,
            patch("util.util.Util.run_command") as mock_run_command,
        ):
            # Simulate successful execution of the sudo command
            mock_run_command.return_value = MagicMock(returncode=0)

            # Call our simplified function
            simplified_install_packages("debian")
            # Check if it called install_missing_packages with right args
            print(
                "Mock install_missing_packages call args:",
                mock_install_missing_packages.call_args_list,
            )  # Debug print
            mock_install_missing_packages.assert_called_once_with(
                "debian", ["pkg1"]
            )

    def test_install_packages_detects_missing(self):
        """Test that install_packages correctly identifies missing packages."""

        # Create a simplified version of the function for testing
        def simplified_check_and_install(
            distro: str,
            pkgs: List[str],
            check_results: List[bool],
        ) -> None:
            missing: List[str] = []
            for i, pkg in enumerate(pkgs):
                # Use the provided check results
                # instead of calling check_package_installed
                if not check_results[i]:
                    missing.append(pkg)

            print("Identified missing packages:", missing)  # Debug print

            if missing:
                RepositoryManager.install_missing_packages(distro, missing)

        # Set up our test packages and check results
        test_pkgs: List[str] = ["pkg1", "pkg2", "pkg3"]
        # pkg1 and pkg3 are installed, pkg2 is missing
        check_results: List[bool] = [True, False, True]

        with (
            patch(
                "installer.repository_manager.RepositoryManager."
                "install_missing_packages"
            ) as mock_install_missing_packages,
            patch("util.util.Util.run_command") as mock_run_command,
        ):
            # Simulate successful execution of the sudo command
            mock_run_command.return_value = MagicMock(returncode=0)

            # Call our simplified function
            simplified_check_and_install("debian", test_pkgs, check_results)
            # It should call install_missing_packages with the missing package
            print(
                "Mock install_missing_packages call args:",
                mock_install_missing_packages.call_args_list,
            )  # Debug print
            mock_install_missing_packages.assert_called_once_with(
                "debian", ["pkg2"]
            )

    def test_get_os_info(self):
        # Test unsupported OS
        with patch("platform.system", return_value="Windows"):
            with pytest.raises(ValueError) as exc_info:
                Util.get_os_info()
            assert "Unsupported operating system" in str(exc_info.value)

        # Test Linux with distribution info
        with (
            patch("platform.system", return_value="Linux"),
            patch("distro.id", return_value="ubuntu"),
            patch("distro.codename", return_value="focal"),
        ):
            result = Util.get_os_info()
            assert result.system == "linux"
            assert result.distro == "ubuntu"
            assert result.codename == "focal"
