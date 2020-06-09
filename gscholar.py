import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'

def gscholar_links(title, authors = [], year=None, journal=None):
    gs_url = 'https://scholar.google.com/scholar_lookup?'
    gs_url += f'title={title}'
    if year:
        gs_url += f'&publication_year={year}'
    for a in authors:
        gs_url += f'&author={a}'
    r = session.get(gs_url)
    soup = BeautifulSoup(r.content, 'lxml')
    links = soup.find_all('a')
    filtered_links = set()
    for l in links:
        if (l['href'].find('google') == -1 and 
            not l['href'].startswith('javascript') and
            l['href'][0] != '/'):
                filtered_links.add(l['href'])
    return filtered_links
    
if __name__ == '__main__':
    r = gscholar_links('53BP1 Mediates Productive and Mutagenic DNA Repair through Distinct Phosphoprotein Interactions')