import csv

import requests
from bs4 import BeautifulSoup


# URL of the website
url = "https://<something>/"
csv_file = "crawled_projects.csv"
CATEGORY = "environment"

# CHange me to crawl new site
def extract_repo_url_from_html(html_file: BeautifulSoup, csv_writer):
    # Extract project name and GitHub URL
    preview_image = ""
    category = CATEGORY
    for a_tag in html_file.find_all("a", href=True):
        link_text = a_tag.get_text(strip=True)
        href = a_tag['href']
        if "github.com" in href or "gitlab.com" in href:
            csv_writer.writerow([link_text, href, category, preview_image])


if __name__ == '__main__':
    # Fetch the page content
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")

    # Prepare CSV output
    with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, delimiter=';')
        writer.writerow(["Project Name", "GitHub URL", "Category", "Preview Image"])  # Header row
        extract_repo_url_from_html(soup, writer)

    print(f"Data extracted and saved to {csv_file}.")
