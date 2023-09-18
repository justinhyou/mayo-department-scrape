import requests
from bs4 import BeautifulSoup

import argparse

parser = argparse.ArgumentParser(
    description="Just an example",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument(
    '-s',
    '--start',
    type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date(),
    help='Set a start date')
parser.add_argument(
    '-e',
    '--end',
    type=lambda d: datetime.datetime.strptime(d, '%Y-%m-%d').date(),
    help='Set a start date')
args = parser.parse_args()
config = vars(args)
start_date = config['start']
end_date = config['end']
# assert end_date > start_date
print("Looking between", start_date, "and", end_date)
# todo handle for both epub or print date within range

special_profiles = [
    "https://www.mayoclinic.org/biographies/parney-ian-f-m-d-ph-d/bio-20055129",
    "https://www.mayoclinic.org/biographies/lanzino-giuseppe-m-d/bio-20055067",
    "https://www.mayoclinic.org/biographies/lee-kendall-h-m-d-ph-d/bio-20054858",
    "https://www.mayoclinic.org/biographies/miller-david-a-m-d/bio-20053775"
]

base_url = "https://www.mayoclinic.org"
remainder = "/departments-centers/neurosurgery/sections/doctors/drc-20117103"
suffix = "?page="

pub_med_base = "https://pubmed.ncbi.nlm.nih.gov/"
ncbi_base = "www.ncbi.nlm.nih.gov"

URL = base_url + remainder + suffix

# go through each page of the doctor list
num_pages = 6  # todo, scrape this from search result

total_num_docs = 53  # todo, scrape this from search result


import re


pattern = re.compile("(.*?\.) (.*?(\.|\?)) (.*)")


from enum import Enum

class PageType(Enum):
    MAYO_PUBS = 1
    NCBI_BIBLIOGRPAHY = 2
    PUB_MED_BASE = 3

def main():
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    doctor_to_profile_link = dict()

    for i in range(num_pages):
        page_num = i + 1
        driver.get(URL + str(page_num))
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # find the result items div
        result_items_divs = soup.find_all("ol", class_="result-items")
        assert len(result_items_divs) == 1
        result_items = result_items_divs[0].find_all("li")

        # within result items, go through each result item: for now, ignore things like location and title
        for result_item in result_items:
            link = result_item.find('a')
            if link:
                doctor_to_profile_link[link.string] = link.get("href")
            else:
                continue

    assert len(doctor_to_profile_link.keys()) == total_num_docs


    doctor_to_pub_link = dict()
    # for each profile_link, go to publications to extract link

    all_research = []

    for doctor in doctor_to_profile_link.keys():
        profile_link = base_url + doctor_to_profile_link[doctor]
        if profile_link in special_profiles:
            continue
        driver.get(profile_link)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        link_element = soup.find("a", string="See my publications")
        link = link_element.get("href")
        doctor_to_pub_link[doctor] = link
        page_type = None
        if base_url in link:
            page_type = PageType.MAYO_PUBS
        elif ncbi_base in link and "bibliography" in link:
            page_type = PageType.NCBI_BIBLIOGRPAHY
        elif pub_med_base in link or ncbi_base in link:
            page_type = PageType.PUB_MED_BASE
        research = processor(link, driver, page_type)
        all_research.extend(research)

    driver.quit()

    # for research in all_research:
    #     print(research)


def processor(link, driver, page_type):
    if page_type == PageType.MAYO_PUBS:
        return process_mayo_pubs(link, driver)
    elif page_type == PageType.NCBI_BIBLIOGRPAHY:
        return process_ncbi_bibliography(link, driver)
    elif page_type == PageType.PUB_MED_BASE:
        return process_pub_med_pubs(link)
    else:
        raise Exception("No processor for url:", link)

CLEANR = re.compile('<.*?>')

def process_ncbi_bibliography(link, driver): #handle multiple pages?

    driver.get(link)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    research = []
    citations = soup.find("div", class_="citations")
    individual_citations = citations.find_all("div", class_="ncbi-docsum")
    for citation in individual_citations:
        clean_text = BeautifulSoup(citation.get_text(), "lxml").text.strip()
        text = ' '.join(clean_text.split())
        regex_output = pattern.match(text)
        if not regex_output:
            print("Could not parse:", citation)
            continue
        authors = regex_output.group(1)
        title = regex_output.group(2)
        link_div = citation.get("a")
        print(link_div)
        if not link_div:
            continue
        paper_link = link_div.get("href")
        pub_info = regex_output.group(3)
        research.append((title, paper_link, authors, pub_info))

    return research


def process_mayo_pubs(link, driver):
    # page = requests.get(link, headers={'Cache-Control': 'no-cache'})
    # soup = BeautifulSoup(page.content, "html.parser")

    driver.get(link)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    research = []
    # find the result items div
    pubs = soup.find("ol", class_="publist")
    research_articles = pubs.find_all("li")
    for research_article in research_articles:
        text = research_article.get_text().strip()
        regex_output = pattern.match(text)
        if not regex_output:
            print("Could not parse:", research_article)
            continue
        authors = regex_output.group(1)
        title = regex_output.group(2)
        link_div = research_article.a
        if not link_div:
            continue
        paper_link = research_article.a.get("href")
        pub_info = regex_output.group(3)
        research.append((title, paper_link, authors, pub_info))

    return research

def process_pub_med_pubs(link): # todo : handle multiple pages, use driver?
    page = requests.get(link + "&sort=date")
    soup = BeautifulSoup(page.content, "html.parser")

    research = []
    pubs = soup.find("div", class_="search-results-chunks")
    if not pubs:
        print("Invalid pub link:", link)
        return []
    research_articles = pubs.find_all("article", class_="full-docsum")

    for research_article in research_articles:
        research_content = research_article.find("div", class_="docsum-content")
        title_and_link = research_content.find("a")
        title = title_and_link.get_text().strip()
        link = pub_med_base + title_and_link.get("href")
        citation_section = research_content.find("div", class_="docsum-citation")
        authors = citation_section.find("span", class_="docsum-authors").get_text().strip()
        citation = citation_section.find("span", class_="docsum-journal-citation").get_text().strip()
        research.append((title, link, authors, citation))

    return research

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def developing():
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    link = "https://www.ncbi.nlm.nih.gov/myncbi/1j1Pm-qk6urAm/bibliography/public/"
    result = process_ncbi_bibliography(link, driver)
    print(result)

if __name__ == '__main__':
    # main()
    developing()