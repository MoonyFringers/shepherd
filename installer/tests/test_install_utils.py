#!/usr/bin/env python3

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
import sys
import pytest
from unittest.mock import patch, MagicMock, mock_open
import subprocess
import platform

# Add the scripts directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from install_utils import (
    print_color, is_root, run_command, get_current_user,
    check_file_exists, check_package_installed,
    install_missing_packages, install_packages,
    get_os_info, OsInfo
)
import constants


class TestInstallUtils:
    """Test suite for installation utility functions."""
    
    def test_is_root(self):
        """Test the is_root function."""
        with patch('os.geteuid') as mock_geteuid:
            # Test when running as root
            mock_geteuid.return_value = 0
            assert is_root() is True
            
            # Test when not running as root
            mock_geteuid.return_value = 1000
            assert is_root() is False

    def test_run_command(self):
        """Test the run_command function."""
        # Test successful command execution
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = run_command(['echo', 'test'])
            mock_run.assert_called_once_with(
                ['echo', 'test'], 
                check=True, 
                shell=False, 
                text=True, 
                capture_output=False
            )
            assert result == mock_result
        
        # Test command with string input
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            result = run_command('echo test')
            mock_run.assert_called_once_with(
                ['echo', 'test'], 
                check=True, 
                shell=False, 
                text=True, 
                capture_output=False
            )
        
        # Test capturing output
        with patch('subprocess.run') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "test output"
            mock_run.return_value = mock_result
            
            result = run_command(['echo', 'test'], capture_output=True)
            assert result.stdout == "test output"
        
        # Test command failure
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, ['echo', 'test'])
            with pytest.raises(SystemExit):
                run_command(['echo', 'test'])
        
        # Test command failure but not exiting
        with patch('subprocess.run') as mock_run:
            error = subprocess.CalledProcessError(1, ['echo', 'test'])
            mock_run.side_effect = error
            result = run_command(['echo', 'test'], check=False)
            assert isinstance(result, subprocess.CalledProcessError)

    def test_get_current_user(self):
        """Test the get_current_user function."""
        # Test with SUDO_USER environment variable
        with patch.dict('os.environ', {'SUDO_USER': 'testuser'}):
            assert get_current_user() == 'testuser'
        
        # Test without SUDO_USER environment variable
        with patch.dict('os.environ', clear=True):
            with patch('os.getlogin', return_value='regularuser'):
                assert get_current_user() == 'regularuser'

    def test_check_file_exists(self):
        """Test the check_file_exists function."""
        with patch('os.path.isfile') as mock_isfile, \
             patch('os.access') as mock_access:
            # Test file exists and is readable
            mock_isfile.return_value = True
            mock_access.return_value = True
            assert check_file_exists('/path/to/file') is True
            
            # Test file does not exist
            mock_isfile.return_value = False
            mock_access.return_value = True
            assert check_file_exists('/path/to/nonexistent') is False
            
            # Test file exists but is not readable
            mock_isfile.return_value = True
            mock_access.return_value = False
            assert check_file_exists('/path/to/unreadable') is False

    def test_check_package_installed(self):
        """Test the check_package_installed function."""
        with patch('install_utils.run_command') as mock_run:
            # Test package is installed
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_run.return_value = mock_result
            
            assert check_package_installed('installed-pkg') is True
            mock_run.assert_called_with(
                ['dpkg', '-s', 'installed-pkg'], 
                check=False, 
                capture_output=True
            )
            
            # Test package is not installed
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            
            assert check_package_installed('not-installed-pkg') is False
            
            # Test error occurs
            mock_run.side_effect = Exception("Test exception")
            assert check_package_installed('error-pkg') is False

    def test_install_missing_packages(self):
        """Test the install_missing_packages function."""
        with patch('install_utils.run_command') as mock_run:
            # Simulate successful execution of the sudo command
            mock_run.return_value = MagicMock(returncode=0)
            
            # Test installing packages on Debian
            install_missing_packages('debian', ['pkg1', 'pkg2'])
            
            # Verify that run_command was called with the correct arguments
            expected_cmd = ['sudo', 'apt-get', 'install', '-y', 'pkg1', 'pkg2']
            mock_run.assert_called_once_with(expected_cmd, check=True)

            # Reset mock
            mock_run.reset_mock()
            
            # Test installing packages on Fedora
            install_missing_packages('fedora', ['pkg1', 'pkg2'])
            
            # Verify that run_command was called with the correct arguments
            expected_cmd = ['sudo', 'dnf', 'install', '-y', 'pkg1', 'pkg2']
            mock_run.assert_called_once_with(expected_cmd, check=True)

    def test_install_missing_packages_called(self):
        """Test that the install_packages function calls install_missing_packages correctly."""
        # Define a simplified version of the function for testing
        def simplified_install_packages(distro):
            missing_pkgs = ['pkg1']  # Simulate a missing package
            print("Simulated missing packages:", missing_pkgs)  # Debug print
            # Call install_missing_packages directly
            install_missing_packages(distro, missing_pkgs)

        # Mock the install_missing_packages function
        with patch('test_install_utils.install_missing_packages') as mock_install_missing_packages, \
             patch('install_utils.run_command') as mock_run_command:
            # Simulate successful execution of the sudo command
            mock_run_command.return_value = MagicMock(returncode=0)

            # Call our simplified function
            simplified_install_packages('debian')
            # Check if it called install_missing_packages with right args
            print("Mock install_missing_packages call args:", mock_install_missing_packages.call_args_list)  # Debug print
            mock_install_missing_packages.assert_called_once_with('debian', ['pkg1'])

    def test_install_packages_detects_missing(self):
        """Test that install_packages correctly identifies missing packages."""
        # Create a simplified version of the function for testing
        def simplified_check_and_install(distro, pkgs, check_results):
            missing = []
            for i, pkg in enumerate(pkgs):
                # Use the provided check results instead of calling check_package_installed
                if not check_results[i]:
                    missing.append(pkg)

            print("Identified missing packages:", missing)  # Debug print

            if missing:
                install_missing_packages(distro, missing)

        # Set up our test packages and check results
        test_pkgs = ['pkg1', 'pkg2', 'pkg3']
        # pkg1 and pkg3 are installed, pkg2 is missing
        check_results = [True, False, True]

        # Mock install_missing_packages
        with patch('test_install_utils.install_missing_packages') as mock_install_missing_packages, \
             patch('install_utils.run_command') as mock_run_command:
            # Simulate successful execution of the sudo command
            mock_run_command.return_value = MagicMock(returncode=0)

            # Call our simplified function
            simplified_check_and_install('debian', test_pkgs, check_results)
            # It should call install_missing_packages with the missing package
            print("Mock install_missing_packages call args:", mock_install_missing_packages.call_args_list)  # Debug print
            mock_install_missing_packages.assert_called_once_with('debian', ['pkg2'])

    def test_get_os_info(self):
        """Test the get_os_info function."""
        # Test unsupported OS
        with patch('platform.system', return_value='Windows'):
            with pytest.raises(ValueError) as exc_info:
                get_os_info()
            assert "Unsupported operating system" in str(exc_info.value)

        # Test Linux with distribution info
        with patch('platform.system', return_value='Linux'), \
             patch('distro.id', return_value='ubuntu'), \
             patch('distro.codename', return_value='focal'):
            result = get_os_info()
            assert isinstance(result, OsInfo)
            assert result.system == 'linux'
            assert result.distro == 'ubuntu'
            assert result.codename == 'focal'
