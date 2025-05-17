REQUIRED_DOCKER_COMPONENTS = ["docker", "docker-ce", "docker-ce-cli", "containerd"]

REQUIRED_PKGS = [
    "bc",
    "jq",
    "curl",
    "rsync",
    "apt-transport-https",
    "ca-certificates",
    "software-properties-common",
    "gnupg",
    "lsb-release"
]

REQUIRED_PYTHON_PKGS = [
    "python3-venv",
    "python3-pip"
]

REQUIRED_DOCKER_PKGS = [
    "docker.io",
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-compose",
    "docker-compose-plugin",
]

INSTALL_COMMANDS = {
    "debian": ["sudo", "apt-get", "install", "-y"],
    "ubuntu": ["sudo", "apt-get", "install", "-y"],
    "fedora": ["sudo", "dnf", "install", "-y"],
    "centos": ["sudo", "yum", "install", "-y"],
    "arch": ["sudo", "pacman", "-S", "--noconfirm"],
}

UPDATE_COMMANDS = {
    "debian": "sudo apt update",
    "ubuntu": "sudo apt update",
    "fedora": "sudo dnf update",
    "centos": "sudo yum update",
    "arch": "sudo pacman -Syu",
}

GPG_KEYS = {
    "debian": "https://download.docker.com/linux/debian/gpg",
    "ubuntu": "https://download.docker.com/linux/ubuntu/gpg",
    "fedora": "https://download.docker.com/linux/fedora/gpg",
    "centos": "https://download.docker.com/linux/centos/gpg",
    "arch": "https://download.docker.com/linux/archlinux/gpg",
}

REPO_PATHS = {
    "debian": "/etc/apt/sources.list.d/docker.list",
    "ubuntu": "/etc/apt/sources.list.d/docker.list",
    "fedora": "/etc/yum.repos.d/docker.repo",
    "centos": "/etc/yum.repos.d/docker.repo",
    "arch": "/etc/pacman.d/mirrorlist.d/docker.list",
}

REPO_STRINGS = {
    "debian": "deb [arch={architecture} signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian {release} stable",
    "ubuntu": "deb [arch={architecture} signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu {release} stable",
    "fedora": """[docker]
name=Docker CE Stable - $basearch
baseurl=https://download.docker.com/linux/fedora/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=/etc/pki/rpm-gpg/RPM-GPG-KEY-docker""",
    "centos": """[docker]
name=Docker CE Stable - $basearch
baseurl=https://download.docker.com/linux/centos/$releasever/$basearch/stable
enabled=1
gpgcheck=1
gpgkey=/etc/pki/rpm-gpg/RPM-GPG-KEY-docker""",
    "arch": "Server = https://download.docker.com/linux/archlinux/$arch/stable",
}

KEYRING_PATH = "/usr/share/keyrings/docker-archive-keyring.gpg"

ARCH_MAPPING = {
    ('32bit', 'ELF'): 'i386',
    ('64bit', 'ELF'): 'amd64',
    ('32bit', 'WindowsPE'): 'i386',
    ('64bit', 'WindowsPE'): 'amd64',
    ('64bit', 'Mach-O'): 'amd64',
    ('arm', ''): 'arm64',
    ('aarch64', ''): 'arm64',
}