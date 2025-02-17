import urllib.parse
import json
from datetime import datetime
from pprint import pprint
from time import time
import sys
import os

import requests
from beartype import beartype
from beartype.typing import *
from pydantic import ValidationError

sys.path.append(os.path.abspath(os.getcwd()))
from data.datamodel import validate_repo_info
from backend.utils import extract_info_from_repo, open_projects_db, get_repo_readme, repository_labeling, extract_kw, \
    save_projects_db, get_extensive_description


def get_timestamp(x):
    if x.get("last_update") is None:
        return '1970-01-01 00:00:00'
    return x["last_update"]


def update_db(db_file_path: str, gh_token: str, debug_mode: Optional[bool] = False):
    projects = open_projects_db(db_file_path)
    projects = sorted(projects, key=get_timestamp, reverse=True)

    for idx, p in enumerate(projects):
        try:
            repo_info = extract_info_from_repo(p["repo"], gh_token)
            try:
                valid_repo = validate_repo_info(repo_info)
                try:
                    repo_readme = get_repo_readme(valid_repo.repo, gh_token)
                except Exception:
                    repo_readme = ""

                label = repository_labeling(
                    valid_repo.title,
                    valid_repo.description,
                    repo_readme
                )
                if label != 'other':
                    valid_repo.keywords += extract_kw(
                        str(valid_repo.title) + " " + str(valid_repo.description) + " " + str(repo_readme))
                    valid_repo.category = label
                    pprint(valid_repo.model_dump())
                    projects[idx] = valid_repo.model_dump()
                print(f"[*] - {valid_repo.repo} ==> {label}")
            except ValidationError as e:
                print(f"[-] - {p['repo']} ==> validation error")

            try:
                text_content = get_extensive_description(valid_repo.title + " " + valid_repo.description + " " + repo_readme)
            except Exception:
                print(f"[-] - {p['repo']} ==> cannot create extensive description")
                text_content = valid_repo.description

            valid_repo.description = text_content

        except requests.exceptions.HTTPError as e:
            print(f"HTTPError with code {e.response.status_code}: probably we reached the maximum number of requests")
            break

    save_projects_db(projects, db_file_path)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        projects_file = sys.argv[-2]
        gh_token = sys.argv[-1]
        debug_mode = False
    elif len(sys.argv) == 4:
        projects_file = sys.argv[-3]
        gh_token = sys.argv[-2]
        debug_mode = True
    else:
        print(f"python3 {__file__} <projects_file> <gh_token> [debug_mode]")
        exit(1)

    if debug_mode:
        print(f"projects file: {projects_file}")

    update_db(projects_file, gh_token, debug_mode)
