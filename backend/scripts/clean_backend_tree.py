#!/usr/bin/env python3
import os
import shutil
import sys
import glob

def clean_backend_tree(dry_run=True):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"Cleaning backend tree: {base_dir}")

    # Patterns to delete
    patterns = [
        "**/__pycache__",
        "**/.pytest_cache",
        "**/.mypy_cache",
        "**/.ruff_cache",
        "**/.coverage",
        "**/htmlcov",
        "**/*.pyc",
        "**/*.pyo",
        "**/*.tmp",
        "**/*.log",
        "**/*_extract.py",
    ]

    # Specific environment/package directories misinstalled in backend
    env_dirs = [
        "PIL", "bin", "contourpy", "cycler", "dateutil", "fontTools", 
        "kiwisolver", "libs", "matplotlib", "mpl_toolkits", "numpy", 
        "numpy.libs", "packaging", "pillow.libs", "pycwt", "pyparsing", 
        "scipy", "scipy.libs", "share", "six.py", "tqdm", "pylab.py"
    ]

    # Add .dist-info directories
    dist_infos = glob.glob(os.path.join(base_dir, "*.dist-info"))
    
    to_delete = []

    for pattern in patterns:
        matches = glob.glob(os.path.join(base_dir, pattern), recursive=True)
        to_delete.extend(matches)
        
    for ed in env_dirs:
        p = os.path.join(base_dir, ed)
        if os.path.exists(p):
            to_delete.append(p)
            
    for di in dist_infos:
        to_delete.append(di)

    to_delete = list(set(to_delete))

    for path in sorted(to_delete):
        if not os.path.exists(path):
            continue
        print(f"{'[DRY RUN] ' if dry_run else ''}Deleting: {path}")
        if not dry_run:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)

if __name__ == "__main__":
    dry_run = "--force" not in sys.argv
    clean_backend_tree(dry_run)
    if dry_run:
        print("\nRun with --force to actually delete these files.")
