import os
import urllib
from pprint import pprint
from datetime import datetime, timedelta
from urllib.parse import urlparse

from beartype import beartype
from beartype.typing import *
from pydantic import BaseModel, Field, field_validator, EmailStr, model_validator
import requests

from backend.utils import get_domain


class GithubValidator(BaseModel):
    """
    # Example usage (assuming repo_info is defined as in your original code):
    try:
      model_gh = GithubValidator(**repo_gh_info)
      print("GH Validation successful!")
      # pprint(model)
    except Exception as e:
      print(f"Validation failed: {e}")
    """
    archived: bool = Field(lt=True)
    created_at: datetime
    description: str | None = None
    disabled: bool = Field(lt=True)
    forks_count: int = Field(ge=0)
    name: str = Field(alias="full_name")
    has_discussions: bool
    has_downloads: bool
    has_issues: bool = Field(ge=True)
    has_pages: bool
    has_projects: bool
    has_wiki: bool
    homepage: str | None = None
    language: str | None = None
    license: dict | None = None
    merges_url: str
    open_issues_count: int
    owner: dict
    avatar_url: str | None = None
    pushed_at: datetime # = Field(ge=datetime.now()- timedelta(days=int(1.5 * 365))) # 1 and 1/2 years
    size: int = Field(ge=0)
    stargazers_count: int = Field(ge=10)
    subscribers_count: int = Field(ge=1)
    tags_url: str | None = None
    topics: list | None = None
    commits_count: int | None = None
    updated_at: datetime
    url: str = Field(alias="html_url")
    visibility: str
    watchers_count: int
    commits_url: str

    @field_validator('created_at', 'pushed_at', 'updated_at', mode="before")
    def parse_datetime(cls, value):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    @model_validator(mode="after")
    def get_commits_count(cls, values):
      commits_url = values.commits_url.split('{')[0]
      res = requests.get(commits_url)
      res.raise_for_status()
      res = res.json()
      commits_count = len(res)
      values.commits_count = commits_count
      return values

    @model_validator(mode="after")
    def create_avatar_url(cls, values):
        avatar = values.avatar_url
        new_avatar_url = values.owner.get("avatar_url")
        cls.avatar_url = avatar if avatar is not None else new_avatar_url
        return values


class GitlabValidator(BaseModel):
    """
    try:
      model_gl = GitlabValidator(**repo_gitlab_info)
      print("Gitlab Validation successful!")
      # pprint(model)
    except Exception as e:
      print(f"Validation failed: {e}")
    """
    id: int
    description: str | None = None
    name: str = Field(alias="path_with_namespace")
    created_at: datetime
    topics: list | None = None
    url: str = Field(alias='web_url')
    forks_count: int
    avatar_url: str
    commits_count: int | None = None
    stargazers_count: int = Field(alias='star_count')
    updated_at: datetime = Field(alias='last_activity_at', ge=datetime.now() - timedelta(days=int(6 * 365)))  # 6 years

    @field_validator('created_at', 'updated_at', mode="before")
    def parse_datetime(cls, value):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    @model_validator(mode="after")
    def get_commits_count(cls, values):
        proj_encoded_name = urllib.parse.quote_plus(values.name)
        api_url = f"https://gitlab.com/api/v4/projects/{proj_encoded_name}"
        response = requests.get(api_url)
        response.raise_for_status()
        commits_count = len(response.json())
        values.commits_count = commits_count
        return values


class ValidatorModel(BaseModel):
    old_years: int = 1
    name: str
    created_at: datetime
    topics: list | None = None
    url: str
    forks_count: int
    avatar_url: str | None = None
    stargazers_count: int = Field(ge=25)
    language: str | None = None
    website: str | None = None
    commits_count: int | None = Field(default=None, ge=10)
    updated_at: datetime = Field(ge=datetime.now() - timedelta(days=int(old_years * 365))) # 1 year


class ProjectDataModel(BaseModel):
    category: str | None = None
    keywords: list = Field(default=[], alias='topics')
    title: str = Field(alias="name")
    description: str | None = None
    repo: str = Field(alias='url')
    forks_count: int
    language: str | None = None
    website: str | None = None
    image: str | None = Field(default=None, alias="avatar_url")
    stars: int = Field(alias='stargazers_count')
    last_update: str | None = Field(default=None, alias='updated_at')

    @field_validator('last_update', mode="before")
    def dt_to_str(cls, value):
      return value.strftime("%Y-%m-%d %H:%M:%S")


@beartype
def validate_repo_info(repo: Dict) -> ProjectDataModel:
    repo_url = repo.get("url")
    if repo_url is None:
        raise ValueError(f"URL cannot be None: \n{repo}")

    provider = get_domain(repo_url)
    if provider == "github.com":
        repo_model = GithubValidator(**repo)
    elif provider == "gitlab.com":
        repo_model = GitlabValidator(**repo)
    else:
        raise NotImplementedError

    validated_model = ValidatorModel(**repo_model.model_dump())

    return ProjectDataModel(**validated_model.model_dump())
