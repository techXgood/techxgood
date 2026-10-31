import os
import urllib
from pprint import pprint
from datetime import datetime, timedelta
from urllib.parse import urlparse

from beartype import beartype
from beartype.typing import *
from pydantic import BaseModel, ConfigDict, Field, field_validator, EmailStr, model_validator
import requests

from backend.utils import get_domain, get_api_url, normalize_repo_url, normalize_http_url, clean_text


MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1500
MAX_LANGUAGE_LENGTH = 50
MAX_KEYWORD_LENGTH = 50
MAX_KEYWORDS = 40


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
    # with a token that can read private repos, their data must not end up on the site
    visibility: Literal["public"]
    watchers_count: int
    commits_url: str

    @field_validator('created_at', 'pushed_at', 'updated_at', mode="before")
    def parse_datetime(cls, value):
        if value is None:
            return None
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    @model_validator(mode="after")
    def get_commits_count(cls, values):
      # url rebuilt from the repository path (not taken from the response): the token goes only to api.github.com
      commits_url = f"{get_api_url(values.url)}/commits"
      # authenticated call: anonymous requests are limited to 60/hour (set with backend.utils.set_gh_token)
      token = os.getenv("GH_TOKEN")
      headers = {"Authorization": f"Bearer {token}"} if token else {}
      res = requests.get(commits_url, headers=headers, timeout=30)
      if res.status_code == 409:
          # github answers 409 for empty repositories: 0 commits, so they fail the minimum commits check
          values.commits_count = 0
          return values
      res.raise_for_status()
      res = res.json()
      commits_count = len(res)
      values.commits_count = commits_count
      return values

    @model_validator(mode="after")
    def create_avatar_url(cls, values):
        avatar = values.avatar_url
        new_avatar_url = values.owner.get("avatar_url")
        values.avatar_url = avatar if avatar is not None else new_avatar_url
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
    avatar_url: str | None = None
    namespace: dict | None = None
    language: str | None = None
    commits_count: int | None = None
    stargazers_count: int = Field(alias='star_count')
    updated_at: datetime = Field(alias='last_activity_at', ge=datetime.now() - timedelta(days=int(6 * 365)))  # 6 years

    @field_validator('created_at', 'updated_at', mode="before")
    def parse_datetime(cls, value):
        return datetime.fromisoformat(value.replace('Z', '+00:00'))

    @model_validator(mode="after")
    def get_commits_count(cls, values):
        proj_encoded_name = urllib.parse.quote_plus(values.name)
        api_url = f"https://gitlab.com/api/v4/projects/{proj_encoded_name}/repository/commits"
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        commits_count = len(response.json())
        values.commits_count = commits_count
        return values

    @model_validator(mode="after")
    def get_language(self):
        # the project api does not return the language: take the main one from the languages stats
        proj_encoded_name = urllib.parse.quote_plus(self.name)
        response = requests.get(f"https://gitlab.com/api/v4/projects/{proj_encoded_name}/languages", timeout=30)
        response.raise_for_status()
        languages = response.json()  # e.g. {"PHP": 56.47, "Vue": 26.78}
        self.language = max(languages, key=languages.get) if languages else None
        return self

    @model_validator(mode="after")
    def create_avatar_url(self):
        # most projects have no avatar: use the group/user one (often a relative url)
        if self.avatar_url is None and self.namespace and self.namespace.get("avatar_url"):
            self.avatar_url = urllib.parse.urljoin("https://gitlab.com", self.namespace["avatar_url"])
        return self


class BitbucketValidator(BaseModel):
    """
    Bitbucket has no stars: watchers are used instead (on github they were the same thing until 2012)
    try:
      model_bb = BitbucketValidator(**repo_bitbucket_info)
      print("Bitbucket Validation successful!")
    except Exception as e:
      print(f"Validation failed: {e}")
    """
    name: str = Field(alias="full_name")
    description: str | None = None
    created_at: datetime = Field(alias="created_on")
    updated_at: datetime = Field(alias="updated_on")
    language: str | None = None
    website: str | None = None
    links: dict
    url: str | None = None
    avatar_url: str | None = None
    stargazers_count: int | None = None
    forks_count: int | None = None
    commits_count: int | None = None

    @field_validator('description', 'language', 'website', mode="before")
    def empty_to_none(cls, value):
        # bitbucket returns "" instead of null
        return value or None

    @model_validator(mode="after")
    def get_links_and_counts(self):
        self.url = self.links["html"]["href"]
        self.avatar_url = self.links.get("avatar", {}).get("href")
        # the repository api does not return counts: "size" of a paginated list is its total length
        api_url = get_api_url(self.url)
        counts = dict()
        for endpoint, params in [("watchers", {"pagelen": 1}), ("forks", {"pagelen": 1}), ("commits", {"pagelen": 30})]:
            response = requests.get(f"{api_url}/{endpoint}", params=params, timeout=30)
            response.raise_for_status()
            counts[endpoint] = response.json()
        self.stargazers_count = counts["watchers"]["size"]
        self.forks_count = counts["forks"]["size"]
        # commits have no "size" (too expensive for bitbucket): count the first page, like github and gitlab
        self.commits_count = len(counts["commits"]["values"])
        return self


class ValidatorModel(BaseModel):
    old_years: int = 1
    name: str
    description: str | None = None  # without this field the description was dropped before ProjectDataModel
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
    # every field comes from repositories (written by their owners) and is shown on the site:
    # validate also later assignments (e.g. description replaced by the README summary)
    model_config = ConfigDict(validate_assignment=True)

    category: str | None = None
    keywords: list = Field(default_factory=list, alias='topics')
    title: str = Field(alias="name")
    description: str | None = None
    repo: str = Field(alias='url')
    forks_count: int
    language: str | None = None
    website: str | None = None
    image: str | None = Field(default=None, alias="avatar_url")
    stars: int = Field(alias='stargazers_count')
    last_update: str | None = Field(default=None, alias='updated_at')

    @field_validator('keywords', mode="before")
    def clean_keywords(cls, value):
      # repositories without topics come with topics=None; gitlab topics are free text without limits
      keywords = (clean_text(k, len(k)) for k in (value or []) if isinstance(k, str))
      # longer ones are sentences, not keywords
      return list(dict.fromkeys(k for k in keywords if k and len(k) <= MAX_KEYWORD_LENGTH))[:MAX_KEYWORDS]

    @field_validator('title', mode="after")
    def clean_title(cls, value):
      value = clean_text(value, MAX_TITLE_LENGTH)
      if value is None:
        raise ValueError("empty title")
      return value

    @field_validator('description', mode="after")
    def clean_description(cls, value):
      return clean_text(value, MAX_DESCRIPTION_LENGTH)

    @field_validator('language', mode="after")
    def clean_language(cls, value):
      return clean_text(value, MAX_LANGUAGE_LENGTH)

    @field_validator('repo', mode="after")
    def check_repo(cls, value):
      repo = normalize_repo_url(value)
      if repo is None:
        raise ValueError(f"not a github.com, gitlab.com or bitbucket.org repository url: {value}")
      return repo

    @field_validator('website', mode="after")
    def check_website(cls, value):
      # only http(s) links to public sites (no "javascript:" or "data:" urls, no IP addresses)
      return normalize_http_url(value)

    @field_validator('image', mode="after")
    def check_image(cls, value):
      # images are loaded by the visitors' browsers: only https links to public sites
      return normalize_http_url(value, https_only=True)

    @field_validator('last_update', mode="before")
    def dt_to_str(cls, value):
      return value.strftime("%Y-%m-%d %H:%M:%S")


@beartype
def validate_repo_info(repo: Dict) -> ProjectDataModel:
    # github api returns "url", gitlab api returns "web_url", bitbucket api returns "links"
    repo_url = repo.get("url") or repo.get("web_url") or repo.get("links", {}).get("html", {}).get("href")
    if repo_url is None:
        raise ValueError(f"URL cannot be None: \n{repo}")

    provider = get_domain(repo_url)
    if provider == "github.com":
        repo_model = GithubValidator(**repo)
    elif provider == "gitlab.com":
        repo_model = GitlabValidator(**repo)
    elif provider == "bitbucket.org":
        repo_model = BitbucketValidator(**repo)
    else:
        raise NotImplementedError

    validated_model = ValidatorModel(**repo_model.model_dump())

    return ProjectDataModel(**validated_model.model_dump())
