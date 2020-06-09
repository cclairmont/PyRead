from bs4 import BeautifulSoup

def science_direct(bs):
    for s in bs.find_all('script'):
        if s.get('type') == 'application/json':
            print(s)
    
if __name__ == '__main__':
    html = open('test2.html')
    soup = BeautifulSoup(html, 'lxml')
    science_direct(soup)