import os
import sys
import ast
import re

def get_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
    except Exception as e:
        pass
    return imports

def audit_dependencies():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    target_dirs = [os.path.join(base_dir, "app"), os.path.join(base_dir, "scripts")]
    
    actual_imports = set()
    for d in target_dirs:
        for root, _, files in os.walk(d):
            for file in files:
                if file.endswith(".py"):
                    actual_imports.update(get_imports_from_file(os.path.join(root, file)))

    print("Actual top-level imports in app/ and scripts/:")
    for i in sorted(actual_imports):
        print(f"  - {i}")

    req_file = os.path.join(base_dir, "requirements-core.txt")
    req_packages = set()
    try:
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    pkg = re.split(r'[=><~]', line)[0]
                    req_packages.add(pkg.lower())
    except:
        pass

    print("\nPackages in requirements.txt:")
    for i in sorted(req_packages):
        print(f"  - {i}")

if __name__ == "__main__":
    audit_dependencies()
