import requests
from bs4 import BeautifulSoup

import argparse

from datetime import datetime


parser = argparse.ArgumentParser(
    description="Just an example",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument(
    '-s',
    '--start',
    type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
    help='Set a start date')
parser.add_argument(
    '-e',
    '--end',
    type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
    help='Set a start date')
args = parser.parse_args()
config = vars(args)
start_date = config['start']
if not start_date:
    start_date = datetime.min
end_date = config['end']
if not end_date:
    end_date = datetime.max
# assert end_date > start_date
print("Looking between", start_date, "and", end_date)
# todo handle for both epub or print date within range

# special_profiles = [
#     "https://www.mayoclinic.org/biographies/parney-ian-f-m-d-ph-d/bio-20055129",
#     "https://www.mayoclinic.org/biographies/lanzino-giuseppe-m-d/bio-20055067",
#     "https://www.mayoclinic.org/biographies/lee-kendall-h-m-d-ph-d/bio-20054858",
#     "https://www.mayoclinic.org/biographies/miller-david-a-m-d/bio-20053775"
# ]

use_only_pub_med = True

base_url = "https://www.mayoclinic.org"
remainder = "/departments-centers/neurosurgery/sections/doctors/drc-20117103"
suffix = "?page="

pub_med_base = "https://pubmed.ncbi.nlm.nih.gov"
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


import csv


def main():
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    doctor_to_profile_link = dict()

    doctor_names = []

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
                doctor_names.append(link.get_text().strip())
            else:
                continue

    assert len(doctor_names) == total_num_docs

    csv_path = "doctors.csv"

    with open(csv_path, "w") as opened:
        writer = csv.writer(opened)
        writer.writerow(["name"])
        for doctor in doctor_names:
            writer.writerow([doctor])

    doctor_to_pub_link = dict()
    # for each profile_link, go to publications to extract link

    all_research = []
    if use_only_pub_med:
        for name in doctor_names:
            research = process_pub_med(name, driver)
            all_research.extend(research)
    else:
        for doctor in doctor_to_profile_link.keys():
            profile_link = base_url + doctor_to_profile_link[doctor]
            # if profile_link in special_profiles:
            #     continue
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


    # remove duplicates
    duplicates_removed = []
    paper_links = set()
    for research in all_research:
        if research[1] in paper_links:
            continue
        paper_links.add(research[1])
        duplicates_removed.append(research)

    csv_path = "example_output.csv"

    with open(csv_path, "w") as opened:
        writer = csv.writer(opened)
        writer.writerow(["title", "authors", "pub_info", "link"])
        for research in duplicates_removed:
            title, paper_link, authors, pub_info = research
            writer.writerow([title, authors, pub_info, paper_link])

def process_pub_med(title, driver):
    name = title.split(",")[0]
    split_name = name.split(" ")
    for split in split_name:
        if "(" in split:
            split_name.remove(split)
    if len(split_name) == 2 or (len(split_name) == 3 and "." in name):
        html_name = f"{split_name[-1]}%2C%20{split_name[0]}"
    else:
        ind_initial = -1
        for i, split in enumerate(split_name):
            if "." in split:
                ind_initial = i
        if ind_initial == 1:
            html_name = f"{split_name[-2]}+{split_name[-1]}%2C%20{split_name[0]}"
        else:
            html_name = f"{split_name[-1]}%2C%20{split_name[0]}+{split_name[1]}"

    params = f"/?term={html_name}+mayo&sort=date"
    url = pub_med_base + params
    research = process_pub_med_pubs(url, driver)
    return research

def processor(link, driver, page_type):
    if page_type == PageType.MAYO_PUBS:
        return process_mayo_pubs(link, driver)
    elif page_type == PageType.NCBI_BIBLIOGRPAHY:
        return process_ncbi_bibliography(link, driver)
    elif page_type == PageType.PUB_MED_BASE:
        return process_pub_med_pubs(link, driver)
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
        link_div = citation.find("a")
        if not link_div:
            print("Could not find link:", citation)
            continue
        paper_link = pub_med_base + link_div.get("href")
        print(paper_link)
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

date_pattern = re.compile(" (20.*?)[;|.|:]")

def process_pub_med_pubs(query_link, driver, pageNum = 1):
    new_url = query_link + "&sort=date&page=" + str(pageNum)
    # print(new_url)
    driver.get(new_url)
    soup = BeautifulSoup(driver.page_source, "html.parser")

    research = []
    pubs = soup.find("div", class_="search-results-chunk")
    if not pubs:
        print("Invalid pub link:", new_url)
        return []

    research_articles = pubs.find_all("article", class_="full-docsum")

    # allow_some_flexibility because date ranking is weird
    flex_over = 0

    all_dates_older = True
    for research_article in research_articles:
        research_content = research_article.find("div", class_="docsum-content")
        title_and_link = research_content.find("a")
        title = title_and_link.get_text().strip()
        link = pub_med_base + title_and_link.get("href")
        citation_section = research_content.find("div", class_="docsum-citation")
        authors = citation_section.find("span", class_="docsum-authors").get_text().strip()
        citation = citation_section.find("span", class_="docsum-journal-citation").get_text().strip()

        regex_output = date_pattern.findall(citation)
        if not regex_output:
            print("Couldn't find date for", citation)
            continue

        dates = []
        for date_string in regex_output:
            try:
                dates.append(datetime.strptime(date_string, "%Y %b %d"))
            except ValueError:
                try:
                    dates.append(datetime.strptime(date_string, "%Y %b"))
                except ValueError:
                    try:
                        if "-" in date_string:
                            split_date = date_string.split(" ")
                            year = split_date[0]
                            dates.append(datetime.strptime(year + " " + split_date[1].split("-")[0], "%Y %b"))
                            dates.append(datetime.strptime(year + " " + split_date[1].split("-")[1], "%Y %b"))
                        else:
                            print("Couldn't parse date from", date_string)
                    except ValueError:
                        print("Couldn't parse date from", date_string)
                    continue

        if not dates:
            print("Could not parse date for", link)

        within_dates = False
        for date in dates:
            if start_date <= date <= end_date:
                within_dates = True

        for date in dates:
            if date >= start_date:
                all_dates_older = False

        if all_dates_older: # since starting from newest, terminate once older
            flex_over += 1
            if flex_over > 2:
                break
            continue

        if not within_dates:
            continue

        research.append((title, link, authors, citation))

    if not all_dates_older:
        research.extend(process_pub_med_pubs(query_link, driver, pageNum=pageNum + 1))

    return research

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def developing():
    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)
    #
    # link = "https://www.ncbi.nlm.nih.gov/myncbi/1j1Pm-qk6urAm/bibliography/public/"
    # result = process_ncbi_bibliography(link, driver)
    # print(result)

    # matching = date_pattern.findall("J Neurosurg Spine. 2022 Jun 3:1-9. doi: 10.3171/2022.4.SPINE22133. Online ahead of print. pine. 2022 Jun 3:1-9. doi: 10.3171/")
    # print(matching)

    research = process_pub_med("Mark K. Lyons, M.D.", driver)
    for article in research:
        print(article)

if __name__ == '__main__':
    main()
    # developing()