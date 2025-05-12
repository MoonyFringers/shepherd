# Development

This section provides instructions for setting up the development environment
for contributors.

## Prerequisites

Ensure you have the following installed on your system:

- Python 3.12 or later
- `pip` (Python package installer)
- `virtualenv` (optional but recommended for managing dependencies)

To install these on Ubuntu, run:

```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv -y
```

## Setup Instructions

1. **Clone the Repository**

   ```bash
   git clone git@github.com:LunaticFringers/shepherd.git
   cd shepherd
   ```

2. **Create a Virtual Environment**

   Use a virtual environment to isolate dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**

   Install the required Python packages from `requirements.txt`:

   ```bash
   pip install --upgrade pip
   pip install -r src/requirements.txt -r src/requirements-dev.txt
   ```

   Ensure the necessary tools are installed locally in your Python environment:

   ```bash
   pip install black isort pyright pytest pytest-cov pre-commit
   ```

4. **Verify Installation**

   Test the CLI to ensure it works:

   ```bash
   python3 src/shepctl.py --help
   ```

   You should see the list of available commands and options.

5. **Run the CLI**

   You can now use the CLI:

   ```bash
   python3 src/shepctl.py <command> [options]
   ```

## Lints & Checks

1. **pre-commit**

   Run pre-commit manually:

   ```bash
   pre-commit run --all-files
   ```

   Install pre-commit:

   ```bash
   pre-commit install
   ```

2. **Black**

   Format your code manually:

   ```bash
   black src
   ```

3. **Isort**

   Sort imports manually by running:

   ```bash
   isort src
   ```

4. **Pyright**

   Run type checking:

   ```bash
   pyright src
   ```

5. **Pytest**

   Run tests with coverage:

   ```bash
   cd src
   pytest
   ```

## PyInstaller Build Automation Script

The `src/build.py` script automates the process of building `shepctl`
application using PyInstaller, managing versioning,
Git tagging, and resource management.

The script manages the build process for `shepctl` by:

1. Cleaning previous build files.
2. Reading the version from `src/version`.
3. Building `shepctl` with PyInstaller.
4. Copying necessary resources.
5. Optionally creating and pushing Git tags for versioning
   (still experimental).

You can run the script with various command-line arguments:

```bash
python3 src/build.py [options]
```

### Options

- `--clean`: Clean previous builds (removes `build`, `dist`, and `.spec` files).
- `--debug`: Enable debug logs for the PyInstaller build.
- `--git`: Enable Git tagging.
- `--version`: Show the application version.

### Usage

1. **Build:**

    ```bash
    python3 src/build.py
    ```

2. **Build with debug logs:**

    ```bash
    python3 src/build.py --debug
    ```

3. **Clean previous builds:**

    ```bash
    python3 src/build.py --clean
    ```

4. **Enable Git tagging:**

    ```bash
    python3 src/build.py --git
    ```

5. **Show application version:**

    ```bash
    python3 src/build.py --version
    ```
