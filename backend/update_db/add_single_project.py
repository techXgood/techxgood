import json
import os
import sys

sys.path.append(os.path.abspath(os.getcwd()))

import requests
from beartype import beartype
from beartype.typing import *
from pydantic import ValidationError

from backend.utils import extract_info_from_repo, append_if_not_present, open_projects_db, save_projects_db, \
    normalize_repo_url, normalize_http_url, extract_kw
from data.datamodel import validate_repo_info


class InvalidSubmission(Exception):
    """The submitted project cannot be added: the message says why (it is printed in the workflow log)"""


# fields of the issue form (.github/ISSUE_TEMPLATE/submit-new-project.yaml): the others are ignored
ISSUE_FIELDS = ("repo", "category", "image", "website", "poc")


@beartype
def load_categories(categories_file: str = "conf/categories.json") -> List[str]:
    with open(categories_file, "r", encoding="utf-8") as cat_file:
        return [c["id"] for c in json.load(cat_file)["cat"]]


@beartype
def project_from_issue(issue: Dict, token: str) -> Dict:
    """
    Build the db entry of a project submitted with the "Submit new project" issue form
    The issue text is written by anyone: only the form fields are used, and title, description, stars...
    come from the repository API (with the same checks of the crawled projects), never from the issue
    :param issue: issue form values (output of github-issue-parser)
    :param token: github token (sent only to the github API)
    :return:
        project ready to be saved in the db
    """
    repo = issue.get("repo")
    repo_url = normalize_repo_url(repo) if isinstance(repo, str) else None
    if repo_url is None:
        raise InvalidSubmission("the repository must be a github.com, gitlab.com or bitbucket.org repository url")

    # issue form values -> db format ("open knowledge" -> "open-knowledge")
    category = issue.get("category")
    category = category.strip().lower().replace(" ", "-") if isinstance(category, str) else None
    if category not in load_categories():
        raise InvalidSubmission("unknown category")

    try:
        valid_repo = validate_repo_info(extract_info_from_repo(repo_url, token))
    except ValidationError as e:
        # e.g. too few stars or commits, not updated in the last year, archived or private repository
        reasons = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise InvalidSubmission(f"the repository does not pass the checks ({reasons})")
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            raise InvalidSubmission("repository not found (deleted or not public)")
        raise  # rate limit or provider errors: the workflow fails and can be re-run

    valid_repo.category = category
    valid_repo.keywords += extract_kw(f"{valid_repo.title} {valid_repo.description or ''}")
    project = valid_repo.model_dump()

    # optional links written in the issue ("" if not filled): they are shown on the site, so they are rebuilt
    # with only safe chars and must point to a public site (images, loaded by the browsers, only with https)
    for field, https_only, expected in [("website", False, "an http(s)"), ("image", True, "an https")]:
        if issue.get(field):
            url = normalize_http_url(issue[field], https_only=https_only)
            if url is None:
                raise InvalidSubmission(f"{field} must be {expected} url of a public site, without spaces or invisible chars")
            project[field] = url
    # checkboxes are the list of the checked labels
    poc = issue.get("poc")
    project["poc"] = isinstance(poc, list) and "PoC" in poc
    return project


@beartype
def load_issue(issue_file: str) -> Dict:
    # the file is written by the issue parser from the issue text: any content must give a clear error, not a crash
    try:
        with open(issue_file, "r", encoding="utf-8") as issue_obj:
            issue = json.load(issue_obj)
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise InvalidSubmission(f"the issue cannot be read ({type(e).__name__})")
    if not isinstance(issue, dict):
        raise InvalidSubmission("the issue is not a submission form")
    # only the names of the fields are printed (ascii() escapes any char): the values are user input
    ignored = sorted(ascii(key)[:50] for key in issue if key not in ISSUE_FIELDS)[:20]
    print(f"issue fields: {sorted(key for key in issue if key in ISSUE_FIELDS)}, ignored: {ignored}")
    return issue


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: add_single_project.py <projects_file> <issue_parser_result_json_file>")
        sys.exit(1)
    projects_file = sys.argv[1]
    issue_file = sys.argv[2]
    # the token comes from the environment: command line arguments are visible to the other processes
    gh_token = os.getenv("GH_TOKEN", "")
    print(f"projects file: {projects_file}\nissue file: {issue_file}")

    try:
        new_project = project_from_issue(load_issue(issue_file), gh_token)
    except InvalidSubmission as e:
        # the workflow fails: the maintainer sees the reason in the log
        print(f"[-] - project not added: {e}")
        sys.exit(1)

    projects = open_projects_db(projects_file)
    # append_if_not_present modifies the list in place and returns only True/False
    if append_if_not_present(projects, new_project):
        save_projects_db(projects, projects_file)
        # all values are validated: printed to let the maintainer check them in the log
        print(f"[+] - added {new_project['repo']} ({new_project['category']})")
        print(f"    website: {new_project['website']}\n    image: {new_project['image']}\n    poc: {new_project['poc']}")
