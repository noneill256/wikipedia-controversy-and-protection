# Create directories needed for project

from pathlib import Path

ROOT = Path.cwd() # Goes to my Python folder

# List of needed directories
dirs_to_create = [
    ROOT / "conf",
    ROOT / "data" / "cache",
    ROOT / "data" / "raw",
    ROOT / "data" / "processed",
    ROOT / "notebooks",
    ROOT / "py_files"]

# Loop and create each directory
for dir_path in dirs_to_create:
    # mkdir creates a new directory
    # parents=True creates any needed parent folders, like 'data'
    # exist_ok=True prevents an error if the folder already exists
    dir_path.mkdir(parents=True, exist_ok=True)
    print(f"Created or verified: {dir_path}")