import urllib.parse
import json
from datetime import datetime
from time import time
import sys

import requests
from rake_nltk import Rake
import nltk
from beartype import beartype
from beartype.typing import *

nltk.download('stopwords')
nltk.download('punkt_tab')


@beartype
def extract_topics_from_repo(desc: str) -> List[str]:
    def extract_keywords(text, min_len=3, max_len=30, max_words=10):
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
    
    keywords = extract_keywords(desc)
    print("Extracted Keywords:", keywords)
    return keywords


@beartype
def extract_info_from_repo(proj: Dict[str, Any]) -> Dict[str, Any]:
    starting_time = time()
    provider = urllib.parse.urlparse(proj["repo"]).netloc
    if provider == "github.com":
        api_url = proj["repo"].replace("https://github.com/", "https://api.github.com/repos/")
        headers = {
            'Accept': 'application/vnd.github.mercy-preview+json'
        }
        star_count = "stargazers_count"
    elif provider == "gitlab.com":
        project_path = '/'.join(proj["repo"].strip('https://').split('/')[1:])
        encoded_project_path = urllib.parse.quote_plus(project_path)
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_project_path}"
        headers = {}
        star_count = "star_count"
    else:
        raise NotImplementedError(f"Cannot get infos from external site actually - {proj['repo']}.")
    
    response = requests.get(api_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
    else:
        raise requests.HTTPError(f"{proj['repo']} - return this HTTP status code: {response.status_code}")

    proj["title"] = '/'.join(proj["repo"].split('/')[-2:])
    proj["description"] = data.get("description")
    proj["language"] = data.get("language")
    proj["stars"] = data.get(star_count)
    proj["image"] = data.get('owner').get('avatar_url') if proj.get("image") is None else proj["image"]
    if proj.get("website") is None or proj["website"] == '':
        if data.get("homepage") is not None and data["homepage"] != proj["repo"]:
            proj["website"] = data["homepage"]
        elif data.get("html_url") is not None and data["html_url"] != proj["repo"]:
            proj["website"] = data["html_url"]
        elif data.get("web_url") is not None and data["web_url"] != proj["repo"]:
            proj["website"] = data["web_url"]
        else:
            proj["website"] = ""
    if proj.get("description") is not None:
        topics = extract_topics_from_repo(proj["description"])
    else:
        topics = []
    proj["keywords"] = data.get("topics") + topics
    proj["last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[+] {proj['title']} - processing time: {time() - starting_time}")
    return proj


def main():
    print(sys.argv)
    if len(sys.argv) > 1:
        projects_file = sys.argv[1]
    else: 
        print(f"python3 {__file__} <projects_file> [debug_mode]")
        exit(1)
    debug_mode = True if len(sys.argv) >= 3 else False
    if debug_mode:
        print(projects_file)
        print(debug_mode)
    with open(projects_file, 'r') as f:
        projects = json.load(f)

    # "repo" is the key of dictionary
    def get_timestamp(x):
        if x.get("last_update") is None:
            return '1970-01-01 00:00:00'
        return x["last_update"]
    projects = sorted(projects, key=get_timestamp, reverse=True)
    results = []
    for proj in projects:
        try:
            info = extract_info_from_repo(proj)
            if info:
                results.append(info)
        except requests.HTTPError as e:
            print(f"[-] {proj['repo'].split('/')[-1]} - code: {str(e)}")
            results.append(proj)
    
    # Salva i risultati in un file JSON
    if debug_mode:
        projects_file = projects_file.replace(".old", ".new")
    with open(projects_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
