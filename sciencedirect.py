from articleparser import ArticleParser, ParserException
from bs4 import BeautifulSoup

class ScienceDirectParser(ArticleParser):

    def get_doi(self):
        doi_link = self.soup.find('a', {'class': 'doi'}).text
        doi = '/'.join(doi_link.split('/')[-2:])
        print(doi)
        return doi

    def have_access(self):
        dl_button = self.soup.find('span', {'class': 'pdf-download-label'})
        try:
            return dl_button.text == 'Download PDF'
        except AttributeError:
            return False

    def get_abstract(self):
        abstract = self.soup.find('div', {'class':
                                          'abstract author'}).find_all('p')
        if abstract is None:
            raise ParserException("Abstract not found")
        return ''.join(str(a) for a in abstract)

    def clean_html(self, soup):
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
        section = 0
        content = []
        while True:
            section += 1
            soup = self.soup.find('section', {'id': f'sec{str(section)}'})
            if soup is None:
                if section == 1:
                    raise ParserException("No content found")
                break
            soup = BeautifulSoup(soup.encode('utf-8'), 'lxml')
            if soup.h2 is not None:
                sec_title = soup.h2.string
            else:
                sec_title = None
            for elem in soup.find_all('figure'):
                elem.clear()
            content.append({'title': sec_title,
                            'content': []})
            subsect = 0
            while True:
                if sec_title is None:
                    break
                subsect += 1
                subsoup = soup.find('section',
                                    {'id':
                                     f'sec{str(section)}.{str(subsect)}'})
                if subsoup is None:
                    break
                subsect_title = subsoup.h3.text
                subsect_content = ''.join(str(a) for a in
                                          soup.find_all(['p', 'figure']))
                content[-1]['content'].append({'title': subsect_title,
                                               'content': subsect_content})
            if content[-1]['content'] == []:
                content[-1]['content'] = ''.join(str(a) for a in
                                                 soup.find_all(
                                                     ['p', 'figure']))
        soup = None
        for s in self.soup.find_all('section'):
            if s.get('id') is not None and s['id'].startswith('ack'):
                soup = s
                break
        if soup is None:
            raise ParserException("Acknowledgments not found")
        content.append({'title': 'Acknowledgments',
                        'content': ''.join(str(a) for a in
                                           soup.find_all('p'))})
        return content

    def get_references(self):
        soup = None
        for soup in self.soup.find_all('section'):
            css_class = soup.get('class')
            if isinstance(css_class, list) and css_class[0] == 'bibliography':
                break
        if soup is None:
            raise ParserException("References Not Found")
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
                year = journal_year[journal_year.find('(') + 1:
                                    journal_year.find(')')]
                ref_list.append({'label': labels[count],
                                 'title': title,
                                 'authors': authors,
                                 'journal': journal,
                                 'year': year})
                count += 1
        return ref_list

    def get_figures(self):
        figs = self.soup.find_all('figure')
        if len(figs) == 0:
            raise ParserException("Figures not found")
        fig_dict = {}
        for fig in figs:
            if fig['id'] == 'undfig1':
                name = 'Graphical Abstract'
            else:
                fignum = fig['id'][3:].upper()
                name = 'Figure ' + fignum
            fig_dict[name] = {}
            fig_text = fig.find_all('p')
            if len(fig_text) != 0:
                fig_dict[name]['title'] = str(fig_text[0])
                fig_dict[name]['caption'] = ''.join([str(a) for a in
                                                     fig_text[1:]])
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
        soup = self.soup.find('div', {'class': 'PdfDownloadButton'})
        link = soup.find('a')
        if link is None:
            self.inject('script', 'document.getElementById("pdfLink").click()')
            raise ParserException("Clicked PDF download button")
        result = {}
        print(link['href'])
        status, content, name = self.fetch(link['href'])
        soup = BeautifulSoup(content, 'lxml')
        pdf = soup.find_all('a')
        print(pdf)
        result['pdf'] = pdf[0]['href']
        soup = self.soup.find('div', {'class': 'Appendices'})
        links = []
        for a in soup.find_all('a'):
            if (a not in links and
                    a['title'].find('Help (Opens in new window)') == -1):
                links.append(a['href'])
        for i, a in enumerate(soup.find_all('span', {'class': 'label'})):
            result[a.text] = links[i]
        for key in result:
            if key.find('Supplemental Information') != -1:
                result['extended'] = result.pop(key)
                break
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
