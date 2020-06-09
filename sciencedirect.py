from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
import articleparser
from bs4 import BeautifulSoup
import selenium_utils as su

class ScienceDirectParser(articleparser.SeleniumParser):
    
    def get_doi(self):
        s = self.fetch_page()
        doi_link = s.find('a', {'class': 'doi'})['href']
        doi = doi_link[doi_link.find('doi.org/')+8:]
        return doi
    
    def have_access(self, soup):
        dl_button = soup.find('span', {'class': 'pdf-download-label'})
        try:
            return dl_button.text == 'Download PDF'
        except AttributeError:
            return False

    def get_abstract(self):
        s = self.fetch_page()
        abstract_ps = s.find('div', {'class': 'abstract author'}).find_all('p')
        return ''.join(str(a) for a in abstract_ps)
    
    def clean_html(self, html):
        soup = BeautifulSoup(html, 'lxml')
        for s in soup.find_all(['span', 'a', 'figure']):
            class_attr = s.get('class')
            if class_attr == ['workspace-trigger']:
                if s['href'].startswith('#ref'):
                    s['class'] = 'reference'
                    s['href'] = '#ref' + s['href'][4:]
                elif s['href'].startswith('#fig'):
                    s['class'] = 'figure_ref'
                del s['name']
            elif s.name == 'span' or s.name == 'a':
                s.replaceWithChildren()
            elif s.name == 'figure':
                del s['class']
        return str(soup)
    
    def get_content(self):
        self.get_driver()
        success = False
        while not success:
            try:
                intro_sec = self.wait.until(ec.presence_of_element_located((By.ID, 
                                                                            'sec1')))
                html = intro_sec.get_attribute('innerHTML')
                success = True
            except StaleElementReferenceException:
                pass

        section = 1
        content = {}
        while True:
            subsect = 0
            soup = BeautifulSoup(html, 'lxml')
            if not soup.h2 is None:
                sec_title = soup.h2.text
            else:
                sec_title = None
            for elem in soup.find_all('figure'):
                elem.clear()
            sec_content = ''.join(str(a) for a in soup.find_all(['p',
                                                                 'figure']))
            if not sec_title is None:
                content[sec_title] = {}
            while True:
                if sec_title is None:
                    break
                subsect += 1
                try:
                    html = self.driver.find_element(By.ID, 
                                                    f'sec{str(section)}.{str(subsect)}')
                    html = html.get_attribute('innerHTML')
                    soup = BeautifulSoup(html, 'lxml')
                    subsect_title = soup.h3.text
                    for elem in soup.find_all('figure'):
                        elem.clear()
                    subsect_content = ''.join(str(a) for a in soup.find_all(['p',
                                                                             'figure']))
                    content[sec_title][subsect_title] = str(subsect_content)
                except NoSuchElementException:
                    if subsect == 1:
                        content[sec_title] = str(sec_content)
                    break
                except StaleElementReferenceException:
                    subsect -= 1
            section += 1
            try:
                html = self.driver.find_element(By.ID, f'sec{str(section)}')
                html = html.get_attribute('innerHTML')
            except NoSuchElementException:
                break
        ack = self.driver.find_element(By.CSS_SELECTOR, 
                                       "section[id^='ack']")
        html = ack.get_attribute('innerHTML')
        soup = BeautifulSoup(html, 'lxml')
        content['Acknowledgments'] = ''.join(str(a) for a in soup.find_all('p'))
        return content
    
    def get_references(self):
        self.get_driver()
        refs = self.driver.find_element(By.CSS_SELECTOR, 
                                        "section[class^='bibliography']")
        soup = BeautifulSoup(refs.get_attribute('innerHTML'), 'lxml')
        labels = [a.text for a in soup.find_all('dt', {'class': 'label'})]
        ref_list = []
        count = 0
        for r in soup.find_all('dd'):
            if r['id'].find('sref') != -1:
                auth_title = r.find('div', {'class': 'contribution'})
                title = auth_title.strong.text
                auth_title.strong.clear()
                authors = auth_title.text.split(', ')
                journal_year = r.find('div', {'class': 'host'}).text
                journal = journal_year[:journal_year.find(',')]
                year = journal_year[journal_year.find('(') + 1:journal_year.find(')')]
                ref_list.append({'label': labels[count],
                                 'title': title,
                                 'authors': authors,
                                 'journal': journal,
                                 'year': year})
                count += 1
        return ref_list
    
    def get_figures(self):
        self.get_driver()
        figs = self.driver.find_elements(By.TAG_NAME, 'figure')
        fig_dict = {}
        for f in figs:
            soup = BeautifulSoup(f.get_attribute('outerHTML'), 'lxml')
            fig = soup.find('figure')
            if fig['id'] == 'undfig1':
                name = 'Graphical Abstract'
            else:
                fignum = fig['id'][3:].upper()
                name = 'Figure ' + fignum
            fig_dict[name] = {}
            fig_text = fig.find_all('p')
            if len(fig_text) != 0:
                fig_dict[name]['title'] = str(fig_text[0])
                fig_dict[name]['caption'] = ''.join([str(a) for a in fig_text[1:]])
            else:
                fig_dict[name]['title'] = 'Graphical Abstract'
                fig_dict[name]['caption'] = ''
            for link in fig.find_all('a'):
                if link.text.find('high-res') != -1:
                    fig_dict[name]['hr'] = link['href']
                elif link.text.find('full-size') != -1:
                    fig_dict[name]['lr'] = link['href']
        return fig_dict
            
    def get_files(self):
        self.get_driver()
        self.driver.find_element(By.ID, 'pdfLink').click()
        button = self.driver.find_element(By.CLASS_NAME,'PdfDropDownMenu')
        link = button.find_element(By.TAG_NAME, 'a')
        link = link.get_attribute('href')
        result = {}
        result['pdf'] = link
        app = self.driver.find_element(By.CLASS_NAME, 'Appendices')
        soup = BeautifulSoup(app.get_attribute('innerHTML'), 'lxml')
        links = []
        for l in soup.find_all('a'):
            if l not in links and l['title'].find('Help (Opens in new window)') == -1:
                links.append(l['href'])
        for i,l in enumerate(soup.find_all('span', {'class': 'label'})):
            result[l.text] = links[i]
        for key in result:
            if key.find('Supplemental Information') != -1:
                result['extended'] = result.pop(key)
        self.driver.get(link)
        self.wait.until(su.url_changed(link))
        result['pdf'] = self.driver.current_url
        return result
        
    
if __name__ == '__main__':
    s = ScienceDirectParser('https://www.sciencedirect.com/science/article/abs/pii/S1097276519307294',
                            debug=True)
    with open('output.html', 'w', encoding='utf-8') as f:
        for n, sect in s.article.content.items():
            f.write(f'<h2>{n}</h2>\n')
            if isinstance(sect, dict):
                for n2, subsect in sect.items():
                    f.write(f'<h3>{n2}</h3>\n')
                    f.write(subsect)
            else:
                f.write(sect)