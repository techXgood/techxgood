import json
import os
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
def get_repo_readme(
        repo_url: str,
        token: str) -> str:
    provider = get_domain(repo_url)
    if provider == "github.com":
        # Replace with your GitHub repository details
        owner = repo_url.split('/')[-2]
        repo = repo_url.split('/')[-1]
        # GitHub API endpoint for repository content
        url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        # Headers (use a personal access token if required for private repos)
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"Bearer {token}"  # Uncomment if needed
        }
        # Make a GET request to the GitHub API
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return base64.b64decode(response.json()["content"]).decode("utf-8")
    elif provider == "gitlab.com":
        raise NotImplementedError
    else:
        raise NotImplementedError



@beartype
def set_gh_token(token: str, token_name: Optional[str] = "GH_TOKEN") -> None:
    os.environ["token_name"] = token


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
    url = f"https://api.github.com/search/repositories?q={query}&per_page={str(per_page_number)}&page={str(page)}"

    # Headers for authentication
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    # Make the request
    response = requests.get(url, headers=headers)
    # Parse the response
    response.raise_for_status()
    data = response.json()
    repo_list = [repo["html_url"] for repo in data["items"]]
    return repo_list


@beartype
def extract_kw(text: str, min_len=3, max_len=30, max_words=10) -> List[str]:
    rake = Rake()
    rake.extract_keywords_from_text(text)
    phrases = rake.get_ranked_phrases()

    # Extract individual keywords from phrases and apply length filter
    keywords = set()  # Using a set to avoid duplicates
    for phrase in phrases:
        words = phrase.split()
        for word in words:
            word = word.lower()  # Normalize to lowercase
            if min_len <= len(word) <= max_len:
                keywords.add(word)

    return list(keywords)[:max_words]


@beartype
def repository_labeling(
        repo_title: Optional[str] = None,
        repo_desc: Optional[str] = None,
        repo_readme: Optional[str] = None,
        threshold: Optional[float] = 0.3,
        minimun_text_lenght: Optional[int] = 1500,
) -> str:
    with open("conf/categories.json", "r") as cat_file:
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
def get_extensive_description(text: str, num_sentences: Optional[int] = 3):
    # Split the text into sentences
    sentences = text.split(". ")
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
    return ". ".join(top_sentences)


@beartype
def extract_info_from_repo(repo_url: str, token: str) -> Dict[str, Any]:
    starting_time = time()

    provider = get_domain(repo_url)

    if provider == "github.com":
        api_url = repo_url.replace("https://github.com/", "https://api.github.com/repos/")
        headers = {
            'Accept': 'application/vnd.github.mercy-preview+json',
            "Authorization": f"Bearer {token}"
        }
        star_count = "stargazers_count"
    elif provider == "gitlab.com":
        project_path = '/'.join(repo_url.strip('https://').split('/')[1:])
        encoded_project_path = urllib.parse.quote_plus(project_path)
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_project_path}"
        headers = {}
        star_count = "star_count"
    else:
        raise NotImplementedError(f"Cannot get infos from external site actually - {repo_url}.")

    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
    else:
        raise requests.HTTPError(f"{repo_url} - return this HTTP status code: {response.status_code}")

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
    for proj in db:
        if proj["repo"] == url:
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
    with open(projects_file, 'r') as db:
        return json.load(db)


@beartype
def save_projects_db(projects: List[Dict], db_file: str) -> None:
    with open(db_file, "w") as db:
        json.dump(projects, db, indent=4)


if __name__ == '__main__':
    pass