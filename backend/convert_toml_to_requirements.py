from typing import *
import tomllib


def convert_toml_to_requirements_txt(cwd: Optional[str] = '.'):
    with open(f"{cwd}/pyproject.toml", "r") as file:
        pyproject = tomllib.load(file)

    # Extract dependencies
    dependencies = pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    dev_dependencies = pyproject.get("tool", {}).get("poetry", {}).get("dev-dependencies", {})

    # Remove Python version constraint from dependencies
    if "python" in dependencies:
        del dependencies["python"]

    # Write to requirements.txt
    with open(f"{cwd}/requirements.txt", "w") as req_file:
        for package, version in dependencies.items():
            if version[0] == '^':
                version = version[1:]
            req_file.write(f"{package}=={version}\n")


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        cwd = sys.argv[-1]
    else:
        cwd = '.'
    convert_toml_to_requirements_txt(cwd)
