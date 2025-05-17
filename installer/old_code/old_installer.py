import platform
import os
import distro
from dataclasses import dataclass
from installer.constants import *

@dataclass
class Installer:

    def _check_os_type(self) -> str:
        self.system = platform.system().lower()
        if self.system in ("windows", "win32", "darwin"):
            raise ValueError(f"Unsupported operating system: {self.system}")
        elif self.system == "linux":
            self.distro = distro.id().lower()
            print(f"Debug: distribution={self.distro}")
            self.codename = distro.codename().lower()

    def _get_architecture(self) -> str:
        bits, linkage = platform.architecture()
        machine = platform.machine().lower()
        
        # First try the combination of bits and linkage
        if (bits, linkage) in ARCH_MAPPING:
            return ARCH_MAPPING[(bits, linkage)]
        
        # Fall back to machine type for ARM architectures
        if 'arm' in machine or 'aarch' in machine:
            return 'arm64'
        
        # Default to amd64 for 64-bit systems, i386 for others
        return 'amd64' if '64' in bits else 'i386'

    def _check_dependencies(self) -> bool:
        """Check if Docker and its components are installed on the system."""
        for program in REQUIRED_DOCKER_COMPONENTS:
            result = os.system(f"which {program} > /dev/null 2>&1")
            if result != 0:
                return False
        return True

    def _install_dependencies(self) -> None:
        """Install Docker and its components on the system, supporting multiple distributions."""
        if self.distro not in INSTALL_COMMANDS:
            raise RuntimeError(f"Unsupported distribution: {self.distro}")

        self._add_gpg_key()
        self._add_repository()
        
        install_command = INSTALL_COMMANDS[self.distro]

        for program in REQUIRED_DOCKER_COMPONENTS:
            result = os.system(f"{install_command} {program}")
            if result != 0:
                raise RuntimeError(f"Failed to install {program}. Please check your system configuration.")

    def _add_gpg_key(self) -> None:
        """Add the proper GPG key for the detected distribution."""
        if self.distro not in GPG_KEYS:
            raise RuntimeError(f"Unsupported distribution: {self.distro}")

        gpg_key_url = GPG_KEYS[self.distro]
        keyring_path = "/usr/share/keyrings/docker-archive-keyring.gpg"

        if os.path.exists(keyring_path):
            return  # Exit early if the keyring already exists

        os.system(f"curl -fsSL {gpg_key_url} | sudo gpg --dearmor -o {keyring_path}")


    def _add_repository(self) -> None:
        """Add the proper repository for the detected distribution."""
        if self.distro not in REPO_STRINGS:
            raise RuntimeError(f"Unsupported distribution: {self.distro}")
        
        repo_string = REPO_STRINGS[self.distro].format(architecture=self._get_architecture(), release=self.codename)
        repo_path = REPO_PATHS[self.distro]

        if os.path.exists(repo_path):
            return  # Exit early if the repository file already exists

        with open(repo_path, "w") as f:
            f.write(repo_string)

        update_command = UPDATE_COMMANDS[self.distro]
        os.system(update_command)

    def __init__(self):
        self._check_os_type()
