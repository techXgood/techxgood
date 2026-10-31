import json
import os
import sys
from pprint import pprint

import requests
from pydantic import ValidationError
from beartype import beartype
from beartype.typing import *

sys.path.append(os.path.abspath(os.getcwd()))
from backend.utils import search_projects_on_github, extract_info_from_repo, open_projects_db, save_projects_db, repository_labeling, get_repo_readme, already_in, extract_kw, set_gh_token, \
    search_projects_on_gitlab, get_domain, is_rate_limited
from data.datamodel import validate_repo_info


PER_PAGE_NUMBER = 30
MAX_ITER = 5


@beartype
def main(gh_token: Optional[str] = None):
    valid_repositories = list()
    to_archive_repositories = list()
    if gh_token is not None:
        # used by data.datamodel to authenticate its requests
        set_gh_token(gh_token)
    projects = open_projects_db("data/projects.json")
    with open('backend/crawler/status.json', "r", encoding="utf-8") as status_file:
        status = json.load(status_file)
    status = sorted(status, key=lambda item: item["status"])
    # providers (other than github) that reached their rate limit
    rate_limited = set()

    iter = 0
    while iter < MAX_ITER:
        try:
            # search
            first_kw_item = status[0]
            print(f"actual kw: {first_kw_item}")
            if first_kw_item["status"] == first_kw_item["max-pages"]:
                # reset all status
                for s in status:
                    s["status"] = 0
                print("Reset all status")
            repository_urls_list = search_projects_on_github(
                keywords=first_kw_item["kw"].split(' '),
                page=int(first_kw_item["status"]),
                token=gh_token,
                per_page_number=PER_PAGE_NUMBER
            )
            if "gitlab.com" not in rate_limited:
                try:
                    repository_urls_list += search_projects_on_gitlab(
                        keywords=first_kw_item["kw"].split(' '),
                        page=int(first_kw_item["status"]),
                        per_page_number=PER_PAGE_NUMBER
                    )
                except requests.exceptions.RequestException as e:
                    # gitlab is optional: its errors must not stop the github crawling
                    print(f"[-] - gitlab search ==> {e}")

            # foreach url check if is already in DB
            app_list = repository_urls_list
            repository_urls_list = []
            for url in app_list:
                # check also the repos found in this run (different keywords can return the same repo)
                if not already_in(url, projects + valid_repositories):
                    repository_urls_list.append(url)

            # foreach url extract infos from repository and validate them
            for url in repository_urls_list:
                provider = get_domain(url)
                if provider in rate_limited:
                    continue
                try:
                    repo_info = extract_info_from_repo(url, gh_token)
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
                        valid_repo.keywords += extract_kw(str(valid_repo.title) + " " + (valid_repo.description or "") + " " + str(repo_readme))
                        valid_repo.category = label
                        pprint(valid_repo.model_dump())
                        valid_repositories.append(valid_repo.model_dump())
                    print(f"[*] - {valid_repo.repo} ==> {label}")
                except ValidationError as e:
                    print(f"[-] - {url} ==> validation error")
                except requests.exceptions.HTTPError as e:
                    if is_rate_limited(e, provider):
                        if provider == "github.com":
                            raise  # github rate limit: stop crawling
                        rate_limited.add(provider)  # gitlab rate limit: skip only its repos
                    # e.g. 404 on deleted repositories: skip only this repo
                    print(f"[-] - {url} ==> {e}")
                except Exception as e:
                    # repositories and API answers are not under our control (e.g. unexpected fields or invalid urls):
                    # skip only this repo, a crash would lose all the projects found in this run
                    print(f"[-] - {url} ==> {type(e).__name__}: {e}")

            # save repo into db
            first_kw_item["status"] += 1
            status = status[1:] + [first_kw_item]
            iter += 1
        except requests.exceptions.RequestException as e:
            # github search failed (rate limit or network error): stop crawling, the projects found are saved
            status_code = e.response.status_code if e.response is not None else None
            print(f"{type(e).__name__} with code {status_code}: probably we reached the maximum number of requests")
            # save repo into db
            first_kw_item["status"] += 1
            status = status[1:] + [first_kw_item]
            break

    # commit
    print(status)
    print(valid_repositories)
    save_projects_db(projects + valid_repositories, "data/projects.json")
    with open('backend/crawler/status.json', "w", encoding="utf-8") as status_file:
        json.dump(status, status_file)


if __name__ == '__main__':
    # sys.argv[0] is the script name, the token is the first real argument
    # or the GH_TOKEN env var (used by the workflow: command line arguments are visible to the other processes)
    token = sys.argv[-1] if len(sys.argv) > 1 else os.getenv("GH_TOKEN")
    if token:
        main(gh_token=token)
    else:
        print("Help: crawler.py <gh_token>  (or set the GH_TOKEN env var)")
        sys.exit(1)