import urllib.parse
import json
from datetime import datetime
from time import time
import sys

import requests
from beartype import beartype
from beartype.typing import *

from utils import extract_kw, extract_info_from_repo


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
    hit_403_error_code = 0
    for proj in projects:
        try:
            if hit_403_error_code < 10:
                info = extract_info_from_repo(proj)
                if info:
                    results.append(info)
            else:
                results.append(proj)
        except requests.HTTPError as e:
            print(f"[-] {proj['repo'].split('/')[-1]} - code: {str(e)}")
            if str(e) != '404':  # remove proj from project.json if error 404
                results.append(proj)
            if str(e) == '403':
                hit_403_error_code += 1
    
    # Salva i risultati in un file JSON
    if debug_mode:
        projects_file = projects_file.replace(".old", ".new")
    with open(projects_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
