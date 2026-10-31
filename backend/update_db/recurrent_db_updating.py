import urllib.parse
import json
import random
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
from backend.utils import extract_info_from_repo, open_projects_db, get_repo_readme, repository_labeling, extract_kw, \
    save_projects_db, get_extensive_description, set_gh_token, get_domain, is_rate_limited, normalize_http_url
from data.datamodel import validate_repo_info


# projects failing the minimum stars/commits checks are removed from the db (and so from the site)
REMOVAL_FIELDS = {"stargazers_count", "star_count", "commits_count"}


def fails_minimum_thresholds(error: ValidationError) -> bool:
    # other validation errors (e.g. archived or not recently updated repos) keep the project in the db
    return any(err["loc"] and err["loc"][0] in REMOVAL_FIELDS for err in error.errors())


def get_timestamp(x):
    if x.get("last_update") is None:
        return '1970-01-01 00:00:00'
    return x["last_update"]


def update_db(db_file_path: str, gh_token: str, debug_mode: Optional[bool] = False):
    # used by data.datamodel to authenticate its requests
    set_gh_token(gh_token)
    projects = open_projects_db(db_file_path)
    projects = sorted(projects, key=get_timestamp, reverse=True)

    # providers that reached their rate limit: skip only their projects, the others can still be updated
    rate_limited = set()
    removed = set()
    # a run does not reach every project before the github rate limit:
    # random order, so the next runs check the projects skipped by this one
    for idx in random.sample(range(len(projects)), len(projects)):
        p = projects[idx]
        provider = get_domain(p["repo"])
        if provider in rate_limited:
            continue
        try:
            repo_info = extract_info_from_repo(p["repo"], gh_token)
            valid_repo = validate_repo_info(repo_info)
        except ValidationError as e:
            if fails_minimum_thresholds(e):
                print(f"[-] - {p['repo']} ==> removed: too few stars or commits")
                removed.add(idx)
            else:
                print(f"[-] - {p['repo']} ==> validation error")
            continue
        except requests.exceptions.HTTPError as e:
            if is_rate_limited(e, provider):
                print(f"HTTPError with code {e.response.status_code}: probably we reached the maximum number of requests on {provider}")
                rate_limited.add(provider)
                continue
            if e.response is not None and e.response.status_code == 404:
                # deleted repositories, or without public code (renamed/moved ones are redirected, not 404)
                print(f"[-] - {p['repo']} ==> removed: repository not found (404)")
                removed.add(idx)
                continue
            # other errors (e.g. 500 from the provider): skip only this project, it is retried in the next runs
            print(f"[-] - {p['repo']} ==> {e}")
            continue
        except Exception as e:
            # a single broken project must not make the whole run crash before saving the db
            print(f"[-] - {p['repo']} ==> {type(e).__name__}: {e}")
            continue

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
                str(valid_repo.title) + " " + (valid_repo.description or "") + " " + str(repo_readme))
            valid_repo.category = label
            # replace the short repo description with a summary of description + README
            # (the description always comes fresh from the API, so the summary does not drift between runs)
            try:
                valid_repo.description = get_extensive_description(
                    ". ".join([valid_repo.title, valid_repo.description or "", repo_readme]))
            except Exception:
                print(f"[-] - {p['repo']} ==> cannot create extensive description, keeping the original one")
            pprint(valid_repo.model_dump())
            # keep fields the API does not provide (e.g. poc) and manually curated website/image,
            # but only if they are valid links (they may come from before the validation of the issues)
            updated = {k: v for k, v in valid_repo.model_dump().items() if v is not None}
            for field, https_only in [("website", False), ("image", True)]:
                curated = normalize_http_url(p.get(field), https_only=https_only)
                updated[field] = curated or updated.get(field)
            projects[idx] = {**p, **updated}
        print(f"[*] - {valid_repo.repo} ==> {label}")

    print(f"[*] - removed {len(removed)} projects (too few stars or commits, or repository not found)")
    save_projects_db([p for idx, p in enumerate(projects) if idx not in removed], db_file_path)


if __name__ == "__main__":
    if len(sys.argv) == 2 and os.getenv("GH_TOKEN"):
        # token from the env var (used by the workflow: command line arguments are visible to the other processes)
        projects_file = sys.argv[-1]
        gh_token = os.getenv("GH_TOKEN")
        debug_mode = False
    elif len(sys.argv) == 3:
        projects_file = sys.argv[-2]
        gh_token = sys.argv[-1]
        debug_mode = False
    elif len(sys.argv) == 4:
        projects_file = sys.argv[-3]
        gh_token = sys.argv[-2]
        debug_mode = True
    else:
        print(f"python3 {__file__} <projects_file> [<gh_token>] [debug_mode]  (without <gh_token> set the GH_TOKEN env var)")
        exit(1)

    if debug_mode:
        print(f"projects file: {projects_file}")

    update_db(projects_file, gh_token, debug_mode)
