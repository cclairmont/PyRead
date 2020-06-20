from articleparser import ArticleParser, ParserException
from bs4 import BeautifulSoup
import re


class ScienceDirectParser(ArticleParser):

    def get_doi(self):
        doi_link = self.soup.find('a', {'class': 'doi'}).text
        doi = '/'.join(doi_link.split('/')[-2:])
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
        for s in [soup] + soup.find_all(True):
            class_attr = s.get('class')
            if class_attr == ['workspace-trigger']:
                if s['href'].startswith('#bib'):
                    rnum = s['href'][4:]
                    s.clear()
                    s.name = 'span'
                    s['data-refnum'] = rnum
                    s['class'] = 'ref'
                elif (s['href'].startswith('#fig') or
                      s['href'].startswith('#mmc')):
                    s['class'] = 'figure_ref'
                    s.name = 'span'
                    inner_html = s.string.encode('utf-8')
                    outer_html = s.encode('utf-8')
                    parent_html = s.parent.encode('utf-8')
                    s.clear()
                    fig_num = inner_html[::-1].find(b' ')
                    if fig_num == -1:
                        fig_num = inner_html[::-1].find(b'\xc2\xa0'[::-1])
                    if fig_num == -1:
                        fig_num = 0
                    fig_num = inner_html[-fig_num:]
                    fig_panel = []
                    fp_start = (parent_html.find(outer_html) +
                                len(outer_html))
                    fp_end_p = parent_html[fp_start:].find(b')')
                    fp_end_s = parent_html[fp_start:].find(b'<a')
                    fp_end_f = parent_html[fp_start:].find(b'.')
                    fp_end = -1
                    for end in [fp_end_p, fp_end_s, fp_end_f]:
                        if end != -1:
                            if fp_end == -1:
                                fp_end = end
                            else:
                                fp_end = min(end, fp_end)
                    print(fig_num)
                    print(parent_html[fp_start: fp_start + fp_end])
                    if fp_end == -1:
                        fp_end = 0
                        fig_panel = []
                        print(parent_html, fp_start)
                    for i in range(fp_start, fp_start + fp_end):
                        print(parent_html[i], parent_html[i-1])
                        if (parent_html[i] >= 65 and parent_html[i] <= 90):
                            if ((parent_html[i-1] >= 48 and
                                    parent_html[i-1] <= 57) or
                                    parent_html[i-1] == 62):
                                fig_panel.append(bytes([parent_html[i]]))
                            print(fig_panel)
                    fig_num = fig_num + b','.join(fig_panel)
                    s['data-fignum'] = fig_num.decode('utf-8')
                    if s['href'].startswith('#mmc'):
                        s['data-fignum'] = (s['data-fignum']
                                            + '-' + s['href'][1:])
                    if str(s).startswith('Table'):
                        s['data-fignum'] = 'T' + s['data-fignum']
                del s['href']
                del s['name']
            elif s.name in ['span', 'a']:
                s.replaceWithChildren()
            elif s.name in ['figure', 'p', 'div', 'tr', 'h2', 'h3']:
                del s['class']
                del s['id']
        html = str(soup)
        html = re.sub(r'<h[23]>(.*)</h[23]>', r'\1', html)
        html = re.sub(r'data-fignum="([\-mcA-Z1-9,]*)"></span>[^\)]*'
                      r'<span class="figure_ref"',
                      r'data-fignum="\1"></span><span class="figure_ref"',
                      html)
        html = re.sub(r'data-fignum="([\-mcA-Z1-9,]*)"></span>[^<]*\)',
                      r'data-fignum="\1"></span>)', html)
        html = re.sub(r' ?\(?<span', '<span', html)
        html = re.sub(r'</span>[;, ]', '</span>', html)
        html = re.sub(r'</span>\)', '</span>', html)
        html = re.sub(r'data-fignum="([\-mcA-Z1-9,]*)">'
                      r'</span>[^<^ ^\.^,]([ \.,])',
                      r'data-fignum="\1"></span>\2', html)
        return html

    def get_content(self):
        soup = None
        for s in self.soup.find_all('section'):
            if s.get('id') is not None and s['id'].startswith('ack'):
                soup = s
                break
        if soup is None:
            raise ParserException("Acknowledgments not found")
        ack = {'title': 'Acknowledgments',
                        'content': ''.join(self.clean_html(a) for a in
                                           soup.find_all('p'))}
        soup.clear()
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
                sec_title = self.clean_html(soup.h2)
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
                subsect_title = self.clean_html(subsoup.h3)
                if subsect_title is None:
                    subsect_title = ''.join(self.clean_html(a) for a in
                                            subsoup.h3.contents)
                subsect_content = ''.join(self.clean_html(a) for a in
                                          subsoup.find_all(['p', 'figure']))
                content[-1]['content'].append({'title': subsect_title,
                                               'content': subsect_content})
            if content[-1]['content'] == []:
                content[-1]['content'] = ''.join(self.clean_html(a)
                                                 for a in soup.find_all(
                                                     ['p', 'figure']))
        content.append(ack)
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
                ref = {'label': labels[count],
                       'title': title,
                       'authors': authors,
                       'journal': journal,
                       'year': year}
                for a in r.find_all('a'):
                    doi = a['href'].find('doi.org/')
                    if doi != -1:
                        ref['doi'] = a['href'][doi + 8:]
                ref_list.append(ref)
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
                fig_dict[name]['title'] = self.clean_html(fig_text[0])
                fig_dict[name]['caption'] = ''.join(self.clean_html(a) for a in
                                                    fig_text[1:])
                if fig_dict[name]['title'].startswith('<p>'):
                    fig_dict[name]['title'] = fig_dict[name]['title'][3:-4]
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
        status, content, name = self.fetch(link['href'])
        soup = BeautifulSoup(content, 'lxml')
        pdf = soup.find_all('a')
        result['pdf'] = pdf[0]['href']
        soup = self.soup.find('div', {'class': 'Appendices'})
        links = []
        for a in soup.find_all('a'):
            if (a['href'] not in links and (a.get('title') is None or not
                                            a['title'].startswith('Help'))):
                links.append(a['href'])
        for i, a in enumerate(soup.find_all('span', {'class': 'label'})):
            result[a.text] = links[i]
        for key in result:
            if key.find('Supplemental Information') != -1:
                result['extended'] = result.pop(key)
                break
        return result


if __name__ == '__main__':
    s = ScienceDirectParser('https://www.sciencedirect.com/science/article/'
                            'abs/pii/S1097276519307294', debug=True)
    with open('output.html', 'w', encoding='utf-8') as f:
        for n, sect in s.article.content.items():
            f.write(f'<h2>{n}</h2>\n')
            if isinstance(sect, dict):
                for n2, subsect in sect.items():
                    f.write(f'<h3>{n2}</h3>\n')
                    f.write(subsect)
            else:
                f.write(sect)
