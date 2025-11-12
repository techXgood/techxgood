import json
import os
import sys
from pprint import pprint

import requests
from pydantic import ValidationError
from beartype import beartype
from beartype.typing import *

sys.path.append(os.path.abspath(os.getcwd()))
from backend.utils import search_projects_on_github, extract_info_from_repo, open_projects_db, save_projects_db, repository_labeling, get_repo_readme, already_in, extract_kw
from data.datamodel import validate_repo_info


PER_PAGE_NUMBER = 30
MAX_ITER = 5


@beartype
def main(gh_token: Optional[str] = None):
    valid_repositories = list()
    to_archive_repositories = list()
    projects = open_projects_db("data/projects.json")
    with open('backend/crawler/status.json', "r") as status_file:
        status = json.load(status_file)
    status = sorted(status, key=lambda item: item["status"])

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

            # foreach url check if is already in DB
            app_list = repository_urls_list
            repository_urls_list = []
            for url in app_list:
                if not already_in(url, projects):
                    repository_urls_list.append(url)

            # foreach url extract infos from repository and validate them
            for url in repository_urls_list:
                repo_info = extract_info_from_repo(url, gh_token)
                try:
                    valid_repo = validate_repo_info(repo_info)
                    try:
                        repo_readme = get_repo_readme(valid_repo.repo, gh_token)
                    except:
                        repo_readme = ""
                    label = repository_labeling(
                        valid_repo.title,
                        valid_repo.description,
                        repo_readme
                    )
                    if label != 'other':
                        valid_repo.keywords += extract_kw(str(valid_repo.title) + " " + str(valid_repo.description) + " " + str(repo_readme))
                        valid_repo.category = label
                        pprint(valid_repo.model_dump())
                        valid_repositories.append(valid_repo.model_dump())
                    print(f"[*] - {valid_repo.repo} ==> {label}")
                except ValidationError as e:
                    print(f"[-] - {url} ==> validation error")

            # save repo into db
            first_kw_item["status"] += 1
            status = status[1:] + [first_kw_item]
            iter += 1
        except requests.exceptions.HTTPError as e:
            print(f"HTTPError with code {e.response.status_code}: probably we reached the maximum number of requests")
            # save repo into db
            first_kw_item["status"] += 1
            status = status[1:] + [first_kw_item]
            break

    # commit
    print(status)
    print(valid_repositories)
    save_projects_db(projects + valid_repositories, "data/projects.json")
    with open('backend/crawler/status.json', "w") as status_file:
        json.dump(status, status_file)


if __name__ == '__main__':
    if len(sys.argv) > 0:
        main(gh_token=sys.argv[-1])
    else:
        print("Help: crawler.py <gh_token>")
        sys.exit(1)