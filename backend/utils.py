import json
import os
import re
import unicodedata
import urllib
from os import getenv
from time import time
from urllib.parse import urlparse
import base64

import requests
from rake_nltk import Rake
import nltk
from beartype import beartype
from beartype.typing import *
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer, util


nltk.download('stopwords')
nltk.download('punkt_tab')


# load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

# seconds before giving up on an HTTP request (avoid hanging CI jobs forever)
HTTP_TIMEOUT = 30
# repository providers whose API is supported
SUPPORTED_PROVIDERS = ("github.com", "gitlab.com", "bitbucket.org")
# READMEs are written by the repository owners: bigger ones are cut (they only slow down regexes and embeddings)
MAX_README_CHARS = 100_000
MAX_URL_LENGTH = 2048
# owner, group and repository names: no "/", "?", "%", spaces or other chars that change the API url
REPO_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+")
# public hostnames: labels of letters, digits and "-", the top level domain is not a number (no IP addresses)
HOST_LABEL = re.compile(r"(?!-)[a-z0-9-]{1,63}(?<!-)")
TOP_LEVEL_DOMAIN = re.compile(r"[a-z]{2,63}|xn--[a-z0-9-]{1,59}")
# names that do not point to public sites (a visitor's browser would load them from its own network)
NOT_PUBLIC_DOMAINS = ("localhost", "local", "internal", "intranet", "lan", "home", "corp", "home.arpa",
                      "test", "example", "invalid", "onion")
# chars kept as they are when a url is rebuilt (RFC 3986), all the others are percent-encoded
URL_PATH_SAFE_CHARS = "/:@!$&*+,;=-._~%"
URL_QUERY_SAFE_CHARS = URL_PATH_SAFE_CHARS + "?"


@beartype
def remove_unsafe_chars(text: str) -> str:
    # control chars, invisible format chars (zero width spaces, bidi overrides that show a text different
    # from the real one...) and lone surrogates (they make utf-8 encoding fail) become spaces
    return "".join(" " if unicodedata.category(c) in ("Cc", "Cf", "Cs") else c for c in text)


@beartype
def has_unsafe_url_chars(url: str) -> bool:
    # urls cannot contain spaces or invisible chars (python even removes tabs and newlines silently:
    # "github.com/a/b\nc" would become "github.com/a/bc"), nor private use / unassigned chars
    return any(c.isspace() or unicodedata.category(c).startswith("C") for c in url)


@beartype
def get_domain(url: str) -> str:
    """
    Return first level domain name
    :param url: The whole http url
    :return:
        first level domain name
    """
    return '.'.join(urllib.parse.urlparse(url).netloc.split('.')[-2:])


@beartype
def get_repo_path(url: str) -> str:
    """
    Return the "<owner>/<repo>" (or "<group>/.../<repo>" for gitlab) part of a repository url
    :param url: The whole http url (e.g. https://github.com/owner/repo/)
    :return:
        path without leading/trailing slashes and without ".git" suffix
    """
    path = urllib.parse.urlparse(url).path.strip('/')
    # gitlab pages of a project (e.g. /group/repo/-/tree/main) are not part of the project path
    path = path.split('/-/')[0]
    if path.endswith('.git'):
        path = path[:-len('.git')]
    return path


@beartype
def get_repo_path_segments(provider: str, repo_path: str) -> List[str]:
    """
    Return the parts of a repository path used by the APIs, checking that they are valid names
    :param provider: github.com, gitlab.com or bitbucket.org
    :param repo_path: "<owner>/<repo>" (or "<group>/.../<repo>" for gitlab)
    :return:
        ["<owner>", "<repo>"] (or ["<group>", ..., "<repo>"] for gitlab)
    """
    segments = repo_path.split('/')
    # github and bitbucket urls can point to a page of the repo (e.g. /owner/repo/tree/main): only owner/repo count
    if provider != "gitlab.com":
        segments = segments[:2]
    # the path ends up in the API url (sent with the token): ".." would point to another API endpoint
    if len(segments) < 2 or any(not REPO_PATH_SEGMENT.fullmatch(s) or s in (".", "..") for s in segments):
        raise ValueError(f"Invalid repository path: {repo_path}")
    return segments


@beartype
def get_api_url(repo_url: str) -> str:
    """
    Return the API url of a repository (github.com, gitlab.com or bitbucket.org)
    The url is always rebuilt from the repository path, so requests (and tokens) go only to the official APIs
    :param repo_url: The whole http url of the repository
    :return:
        API url of the repository
    """
    provider = get_domain(repo_url)
    if provider not in SUPPORTED_PROVIDERS:
        raise NotImplementedError(f"Cannot get infos from external site actually - {repo_url}.")
    segments = get_repo_path_segments(provider, get_repo_path(repo_url))
    if provider == "github.com":
        owner, repo = segments
        return f"https://api.github.com/repos/{owner}/{repo}"
    elif provider == "gitlab.com":
        # gitlab projects can be inside subgroups: the whole path is the project id
        return f"https://gitlab.com/api/v4/projects/{urllib.parse.quote_plus('/'.join(segments))}"
    else:
        workspace, repo = segments
        return f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo}"


@beartype
def normalize_repo_url(url: str) -> Optional[str]:
    """
    Check a repository url written by a user (e.g. in an issue)
    :param url: url of a github.com, gitlab.com or bitbucket.org repository
    :return:
        canonical url "https://<provider>/<path>", or None if the url is not a valid repository url
    """
    url = url.strip()
    if not url or len(url) > MAX_URL_LENGTH or has_unsafe_url_chars(url):
        return None
    if "://" not in url:
        url = f"https://{url}"
    try:
        parsed = urllib.parse.urlparse(url)
        port = parsed.port
    except ValueError:
        return None
    host = (parsed.hostname or "").removeprefix("www.")
    # only the providers themselves: no subdomains, credentials or ports
    if parsed.scheme not in ("http", "https") or host not in SUPPORTED_PROVIDERS or parsed.username or port:
        return None
    try:
        segments = get_repo_path_segments(host, get_repo_path(url))
    except ValueError:
        return None
    return f"https://{host}/{'/'.join(segments)}"


@beartype
def normalize_public_host(host: str) -> Optional[str]:
    """
    Check the hostname of a link shown on the site
    :param host: hostname of the url (e.g. "www.example.org")
    :return:
        lowercase ascii hostname (unicode domains as punycode, so look-alike letters are visible), or None if it
        is not a public domain name (IP addresses, localhost, intranet names...)
    """
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    labels = host.split(".")
    if (len(host) > 253 or len(labels) < 2 or not all(HOST_LABEL.fullmatch(label) for label in labels)
            or not TOP_LEVEL_DOMAIN.fullmatch(labels[-1])):
        return None
    if any(host == domain or host.endswith(f".{domain}") for domain in NOT_PUBLIC_DOMAINS):
        return None
    return host


@beartype
def quote_url_part(text: str, safe: str) -> str:
    # "%" not followed by two hex digits is a literal "%", existing "%XX" escapes are kept
    return urllib.parse.quote(re.sub(r"%(?![0-9A-Fa-f]{2})", "%25", text), safe=safe)


@beartype
def normalize_http_url(url: Any, https_only: bool = False) -> Optional[str]:
    """
    Check a link that will be shown on the site (e.g. project website or image) and rebuild it,
    so the saved url contains only safe ascii chars (quotes, "<", ">", spaces... are percent-encoded)
    :param url: url written by a user or returned by an API
    :param https_only: refuse http urls (images: an http image on the https site can be changed in transit)
    :return:
        the rebuilt url ("https://" is added if there is no scheme), or None if it is not a valid http(s) url
        of a public site
    """
    if not isinstance(url, str):
        return None
    url = url.strip()
    # backslashes are read as "/" by browsers but not by python: the two would see different hosts
    if not url or len(url) > MAX_URL_LENGTH or has_unsafe_url_chars(url) or "\\" in url:
        return None
    if not re.match(r"[a-z][a-z0-9+.-]*://", url, flags=re.I):
        # other schemes (javascript:, data:...) are refused, "host:port" is not a scheme
        if re.match(r"[a-z][a-z0-9+.-]*:(?!\d)", url, flags=re.I):
            return None
        # some websites are written without scheme (e.g. "www.example.org")
        url = f"https://{url}"
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port  # raises ValueError on invalid ports
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in (("https",) if https_only else ("http", "https")):
        return None
    # no credentials ("https://github.com@evil.com" goes to evil.com) and no other ports than the default one
    if "@" in parsed.netloc or port not in (None, {"http": 80, "https": 443}[scheme]):
        return None
    host = normalize_public_host(parsed.hostname or "")
    if host is None:
        return None
    rebuilt = f"{scheme}://{host}{quote_url_part(parsed.path, URL_PATH_SAFE_CHARS)}"
    if parsed.query:
        rebuilt += f"?{quote_url_part(parsed.query, URL_QUERY_SAFE_CHARS)}"
    if parsed.fragment:
        rebuilt += f"#{quote_url_part(parsed.fragment, URL_QUERY_SAFE_CHARS)}"
    return rebuilt if len(rebuilt) <= MAX_URL_LENGTH else None


@beartype
def clean_text(text: Optional[str], max_length: int) -> Optional[str]:
    """
    Make a text written by repository owners safe to show: single line, no control or invisible chars, limited length
    :param text: e.g. title or description of a repository
    :param max_length: longer texts are cut
    :return:
        cleaned text, or None if nothing is left
    """
    if text is None:
        return None
    text = re.sub(r"\s+", " ", remove_unsafe_chars(text)).strip()
    return text[:max_length].strip() or None


@beartype
def is_rate_limited(error: requests.HTTPError, provider: str) -> bool:
    status_code = error.response.status_code if error.response is not None else None
    # github answers 403 when the rate limit is reached, gitlab and bitbucket 429 (403 there is a forbidden repo)
    return status_code == 429 or (status_code == 403 and provider == "github.com")


@beartype
def get_limited_text(url: str, params: Optional[Dict] = None, max_chars: int = MAX_README_CHARS) -> str:
    # files are written by the repository owners: download only the first part, a huge file must not fill the memory
    # (iter_content returns decompressed data, so this also stops gzip bombs)
    max_bytes = 4 * max_chars  # utf-8 chars are up to 4 bytes
    content = b""
    with requests.get(url, params=params, timeout=HTTP_TIMEOUT, stream=True) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=64 * 1024):
            content += chunk
            if len(content) >= max_bytes:
                break
    return content[:max_bytes].decode("utf-8", errors="replace")[:max_chars]


@beartype
def get_repo_readme(
        repo_url: str,
        token: str) -> str:
    provider = get_domain(repo_url)
    api_url = get_api_url(repo_url)
    if provider == "github.com":
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = requests.get(f"{api_url}/readme", headers=headers, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        # the api returns the content of files up to 1 MB (bigger ones have no content)
        readme = base64.b64decode(response.json().get("content") or "").decode("utf-8", errors="replace")
        return readme[:MAX_README_CHARS]
    elif provider == "gitlab.com":
        # public projects do not need a token
        response = requests.get(api_url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        project = response.json()
        if not project.get("readme_url"):
            return ""
        # readme_url is https://gitlab.com/<project>/-/blob/<default branch>/<readme path>
        branch = project["default_branch"]
        readme_path = project["readme_url"].split(f"/-/blob/{branch}/", 1)[-1]
        return get_limited_text(f"{api_url}/repository/files/{urllib.parse.quote_plus(readme_path)}/raw",
                                params={"ref": branch})
    elif provider == "bitbucket.org":
        # bitbucket has no readme endpoint: look for it in the root folder of the main branch
        response = requests.get(f"{api_url}/src/HEAD/", params={"pagelen": 100}, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        readme = next((f for f in response.json()["values"]
                       if f["type"] == "commit_file" and f["path"].lower().startswith("readme")), None)
        if readme is None:
            return ""
        return get_limited_text(f"{api_url}/src/HEAD/{urllib.parse.quote(readme['path'])}")
    else:
        raise NotImplementedError



@beartype
def set_gh_token(token: str, token_name: Optional[str] = "GH_TOKEN") -> None:
    os.environ[token_name] = token


@beartype
def search_projects_on_github(
        keywords: List[str],
        page: int,
        query: Optional[str] = "{} in:description",
        token: Optional[str] = None,
        per_page_number: Optional[int] = 100
) -> List[str]:

    query = query.format(' '.join(keywords))
    if token is None:
        token = getenv("GH_TOKEN")
    url = "https://api.github.com/search/repositories"
    # let requests url-encode the query (keywords may contain spaces or special chars)
    params = {"q": query, "per_page": per_page_number, "page": page}

    # Headers for authentication (without a token the request is anonymous, not "Bearer None")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Make the request
    response = requests.get(url, headers=headers, params=params, timeout=HTTP_TIMEOUT)
    # Parse the response
    response.raise_for_status()
    data = response.json()
    repo_list = [repo["html_url"] for repo in data["items"]]
    return repo_list


@beartype
def search_projects_on_gitlab(
        keywords: List[str],
        page: int,
        per_page_number: Optional[int] = 100
) -> List[str]:
    # bitbucket has no public search API: only github and gitlab can be crawled
    url = "https://gitlab.com/api/v4/projects"
    params = {
        "search": ' '.join(keywords),
        "order_by": "star_count",
        "sort": "desc",
        "simple": "true",
        "per_page": per_page_number,
        "page": page
    }
    # public projects can be searched without a token
    response = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    response.raise_for_status()
    return [repo["web_url"] for repo in response.json()]


@beartype
def extract_kw(text: str, min_len=3, max_len=30, max_words=10) -> List[str]:
    rake = Rake()
    rake.extract_keywords_from_text(text)
    phrases = rake.get_ranked_phrases()

    # Extract individual keywords from phrases and apply length filter
    keywords = dict()  # Using dict keys to avoid duplicates while keeping the RAKE ranking order
    for phrase in phrases:
        words = phrase.split()
        for word in words:
            word = word.lower()  # Normalize to lowercase
            if min_len <= len(word) <= max_len:
                keywords[word] = None

    return list(keywords)[:max_words]


@beartype
def repository_labeling(
        repo_title: Optional[str] = None,
        repo_desc: Optional[str] = None,
        repo_readme: Optional[str] = None,
        threshold: Optional[float] = 0.3,
        minimun_text_lenght: Optional[int] = 1500,
) -> str:
    with open("conf/categories.json", "r", encoding="utf-8") as cat_file:
        cat = json.load(cat_file)
    categories = dict()
    for c in cat["cat"]:
        categories[c["id"]] = c["long_description"]
    #categories["other"] = "Miscellaneous topics not related to altruism/humanitarian or the environment. Strictly commercial and/or recreational, for fun."

    # Load the pre-trained model and tokenizer
    #tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
    #model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


    if repo_title is None:
        repo_title = ""
    if repo_desc is None:
        repo_desc = ""
    if repo_readme is None:
        repo_readme = ""
    combined_text = " ".join([repo_title, repo_desc, repo_readme])
    if len(combined_text) < minimun_text_lenght:
        return "other"
    input_embedding = model.encode([combined_text])
    category_descriptions = [v for k, v in categories.items()]
    category_embeddings = model.encode(category_descriptions)
    similarities = cosine_similarity(input_embedding, category_embeddings)
    best_match_idx = similarities.argmax()
    best_similarity_score = similarities[0, best_match_idx]

    # Return the best match if above threshold, otherwise 'other'
    if best_similarity_score >= threshold:
        return list(categories.keys())[best_match_idx]
    else:
        return "other"

    # # Compute cosine similarity
    # similarities = {cat: torch.nn.functional.cosine_similarity(repo_embedding, emb, dim=1).item()
    #                 for cat, emb in category_embeddings.items()}
    #
    # # Return the category with the highest similarity
    # return max(similarities, key=similarities.get)


@beartype
def clean_markdown(text: str) -> str:
    """
    Convert README markdown/html into plain prose (no code, badges, links, tables, headers)
    :param text: raw README content
    :return:
        plain text on a single line
    """
    text = re.sub(r"```.*?```|~~~.*?~~~", " ", text, flags=re.S)       # code blocks
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)                 # html comments
    # READMEs are written by the repository owners: quantifiers are bounded, so a crafted text
    # (e.g. "![![![..." without "]") cannot make the regexes take quadratic time
    text = re.sub(r"!\[[^\]]{0,500}\]\([^)]{0,2000}\)", " ", text)     # images and badges
    text = re.sub(r"\[([^\]]{0,500})\]\([^)]{0,2000}\)", r"\1", text)  # links -> link text
    text = re.sub(r"^[ \t]*\[[^\]\n]{1,500}\]:[ \t]*\S+.*$", " ", text, flags=re.M)  # reference link definitions
    text = re.sub(r"\[([^\]]{0,500})\]\[[^\]]{0,500}\]", r"\1", text)  # reference links -> link text
    text = re.sub(r"<[^>]{1,1000}>", " ", text)                        # html tags
    text = re.sub(r"https?://\S+", " ", text)                           # bare urls
    text = re.sub(r"\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]", " ", text, flags=re.I)  # github alerts
    lines = []
    for line in text.splitlines():
        line = line.strip().lstrip("> ").strip()                        # blockquotes
        # skip headers, tables and horizontal rules: they are not sentences
        if line.startswith(("#", "|", "---", "===", "***")):
            continue
        line = re.sub(r"^([-*+]|\d+\.)\s+", "", line)                   # list markers
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"[`*_]{1,3}([^`*_]+)[`*_]{1,3}", r"\1", text)        # inline code / emphasis
    return re.sub(r"\s+", " ", remove_unsafe_chars(text)).strip()


@beartype
def get_extensive_description(
        text: str,
        num_sentences: Optional[int] = 3,
        min_sentence_len: Optional[int] = 30,
        max_sentence_len: Optional[int] = 400):
    # Split the text into sentences, ignoring fragments (titles, badges...) and walls of text without periods
    sentences = [s.strip() for s in clean_markdown(text).split(". ")]
    sentences = [s for s in sentences if min_sentence_len <= len(s) <= max_sentence_len]
    # remove duplicated sentences (e.g. repo description repeated in the README), keeping the order
    sentences = list(dict.fromkeys(sentences))
    if len(sentences) <= num_sentences:
        raise Exception("text too short")

    # Encode sentences into embeddings
    sentence_embeddings = model.encode(sentences, convert_to_tensor=True)

    # Compute the embedding of the entire text (mean of sentence embeddings)
    text_embedding = sentence_embeddings.mean(dim=0)

    # Compute similarity of each sentence to the overall text embedding
    similarities = util.pytorch_cos_sim(sentence_embeddings, text_embedding).squeeze()

    # Rank sentences by similarity and pick the top ones
    top_sentence_indices = similarities.argsort(descending=True)[:num_sentences]
    top_sentences = [sentences[i] for i in top_sentence_indices]

    # Sort sentences by their original order in the text
    top_sentences.sort(key=lambda s: sentences.index(s))

    # Return the summary as a single string
    summary = ". ".join(top_sentences)
    return summary if summary.endswith((".", "!", "?")) else summary + "."


@beartype
def extract_info_from_repo(repo_url: str, token: str) -> Dict[str, Any]:
    starting_time = time()

    provider = get_domain(repo_url)
    api_url = get_api_url(repo_url)

    if provider == "github.com":
        headers = {'Accept': 'application/vnd.github.mercy-preview+json'}
        # without a token the request is anonymous (github refuses an empty "Bearer")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    else:
        # the token is a github one: never send it to gitlab or bitbucket (public repos do not need it)
        headers = {}

    response = requests.get(api_url, headers=headers, timeout=HTTP_TIMEOUT)
    if response.status_code == 200:
        data = response.json()
    else:
        # attach the response, callers read e.response.status_code
        raise requests.HTTPError(f"{repo_url} - return this HTTP status code: {response.status_code}",
                                 response=response)

    return data

    # proj = dict()
    # proj["repo"] = repo_url
    # proj["title"] = '/'.join(repo_url.split('/')[-2:])
    # proj["description"] = data.get("description")
    # proj["language"] = data.get("language")
    # proj["stars"] = data.get(star_count)
    # proj["image"] = data.get('owner').get('avatar_url')
    # if proj.get("website") is None or proj["website"] == '':
    #     if data.get("homepage") is not None and data["homepage"] != repo_url:
    #         proj["website"] = data["homepage"]
    #     elif data.get("html_url") is not None and data["html_url"] != repo_url:
    #         proj["website"] = data["html_url"]
    #     elif data.get("web_url") is not None and data["web_url"] != repo_url:
    #         proj["website"] = data["web_url"]
    #     else:
    #         proj["website"] = ""
    # if proj.get("description") is not None:
    #     topics = extract_kw(proj["description"])
    # else:
    #     topics = []
    # proj["keywords"] = data.get("topics") + topics
    # proj["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # print(f"[+] {proj['title']} - processing time: {time() - starting_time}")
    # return proj


def already_in(url: str, db: List[Dict]):
    # change this function to change criteria to select if project is already present or not
    """
    obj = extract_info_from_repo(obj)
    print(obj)
    for proj in db:
        if any(proj[field] == obj[field] for field in ["title", "description", "repo"]):
            return True
        else:
            return False
    """
    # repository urls are case insensitive (github.com/Owner/Repo is github.com/owner/repo)
    url = url.rstrip('/').lower()
    for proj in db:
        if proj.get("repo", "").rstrip('/').lower() == url:
            return True
    return False


@beartype
def append_if_not_present(projects: list, new_project: Dict) -> bool:
    # Check if the object is not in the data
    if not already_in(new_project["repo"], projects):
        projects.append(new_project)  # Append the new object if not present
        return True
    else:
        print("Object already present in the file.")
        return False


@beartype
def open_projects_db(projects_file: str) -> List[Dict]:
    with open(projects_file, 'r', encoding="utf-8") as db:
        return json.load(db)


@beartype
def save_projects_db(projects: List[Dict], db_file: str) -> None:
    with open(db_file, "w", encoding="utf-8") as db:
        json.dump(projects, db, indent=4)


if __name__ == '__main__':
    pass