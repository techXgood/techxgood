import json
import os
import sys

sys.path.append(os.path.abspath(os.getcwd()))

from beartype import beartype
from beartype.typing import *

from utils import extract_info_from_repo, append_if_not_present, open_projects_db, save_projects_db


if __name__ == '__main__':
    if len(sys.argv) == 3:
        projects_file = sys.argv[1]
        new_object_file = sys.argv[2]
        with open(new_object_file, "r") as new_obj:
            new_project = json.load(new_obj)
        print(f"projects file: {projects_file}\nnew project file: {new_object_file}")
        projects = open_projects_db(projects_file)
        projects = append_if_not_present(projects, new_project)
        save_projects_db(projects, projects_file)
    else:
        print(f"Usage: add_new_project <projects_file> <new_project_json_file>")
        exit(1)

""" # test
projects_file = 'data/projects.json'
new_project = {
    "title": "Progetto 1",
    "description": "Track emissions from Compute and recommend ways to reduce their impact on the environment.",
    "image": "https://via.placeholder.com/300x200",
    "repo": "https://github.com/mlco2/codecarbon",
    "category": "environment",
    "language": "python",
    "stars": 500,
    "website": "https://via.placeholder.com/300x200",
    "poc": True
}
ret = append_if_not_present(projects_file, new_project) """
