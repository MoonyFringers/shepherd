# Installation Guide

This section provides instructions for installing the `shepctl`
tool on your system, both for regular use and development purposes.

---

## Standard Installation (Using Released Versions)

To install a specific released version, set the `VER`
environment variable and run the installation script:

```bash
VER=0.0.0 sh -c "$(curl -sfL https://raw.githubusercontent.com/MoonyFringers/shepherd/main/scripts/install.sh)"
```

> Replace `0.0.0` with the desired version.

## 🛠️ Development Installation (From Source)

### Prerequisites

Ensure the following tools are installed:

* **Python 3.12+**
* **pip**
* **virtualenv**

To install them on Debian-based systems:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
```

### Step 1: Clone the Repository

```bash
git clone git@github.com:MoonyFringers/shepherd.git
cd shepherd
```

### Step 2: Install from Source

Use the `source` method to install `shepctl` for development:

```bash
cd scripts
./install.sh -m source install
```

This will:

1. Copy the source files into the install directory
2. Set up a Python virtual environment
3. Install dependencies from `requirements.txt`
4. Create a `shepctl` launcher accessible from your `$PATH`

> 📌 **Skip dependency installation:** If all requirements are already
> installed, use:

```bash
./install.sh -m source --skip-deps install
```

### Step 3: Run the Tool

After installation, you can invoke the tool with:

```bash
shepctl
```
