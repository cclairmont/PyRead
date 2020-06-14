from bs4 import BeautifulSoup
import sciencedirect
from articleparser import ParserException


def scrape(data, inject, fetch):
    soup = BeautifulSoup(data, 'lxml')
    if soup.title is None:
        return None
    print(soup.title)
    if soup.title.text.endswith('ScienceDirect'):
        try:
            article = sciencedirect.ScienceDirectParser(soup, inject, fetch,
                                                        debug=True).article
            return article.doi
        except ParserException as e:
            print(e)
            return None
