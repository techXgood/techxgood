import json
import os
import sys
sys.path.append(os.path.abspath(os.getcwd()))

from beartype import beartype
from beartype.typing import *

from scripts.update_db import extract_info_from_repo


def already_in(db, obj):
   # change this function to change criteria to select if project is already present or not
    obj = extract_info_from_repo(obj)
    print(obj)
    for proj in db:
        if any(proj[field] == obj[field] for field in ["title", "description", "repo"]):
            return True
        else:
            return False


@beartype
def append_if_not_present(projects_file: str, new_project: Dict) -> int:
    try:
        # Read the existing JSON data from the file
        with open(projects_file, 'r') as db:
            data = json.load(db)
        
        # Check if the object is not in the data
        if not already_in(data, new_project):
            data.append(new_project)  # Append the new object if not present

            # Write the updated data back to the file
            with open(projects_file, 'w') as file:
                json.dump(data, file, indent=4)
            print("New object appended successfully.")
            return 0
        else:
            print("Object already present in the file.")
            return 1
    
    except FileNotFoundError:
        # If the file doesn't exist, create it with the new object
        with open(projects_file, 'w') as file:
            json.dump([new_project], file, indent=4)
        print("File created and object added.")
        return 0
    except json.JSONDecodeError:
        # If the file is empty or has invalid JSON, write the new object
        #with open(projects_file, 'w') as file:
        #    json.dump([new_project], file, indent=4)
        print("File had invalid JSON!")
        return 2


if __name__ == '__main__':
    if len(sys.argv) == 3:
        projects_file = sys.argv[1]
        new_object_file = sys.argv[2]
        print(f"projects file: {projects_file}\nnew project file: {new_object_file}")
        with open(new_object_file, "r") as new_object_file:
            new_project = json.load(new_object_file)
        append_if_not_present(projects_file, new_project)
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
