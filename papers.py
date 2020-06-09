from bs4 import BeautifulSoup
import urllib.parse as up
from pathlib import Path
import tempfile
import re
import requests
import os
import difflib
import csv
import time

class JournalScraper:
    
    KNOWN_EXTENSIONS = {'html': 'HTML page',
                        'htm': 'HTML page',
                        'jpeg': 'Image',
                        'jpg': 'Image',
                        'png': 'Image',
                        'tif': 'Image',
                        'ppt': 'Powerpoint Slides',
                        'pptx': 'Powerpoint Slides',
                        'doc': 'Word Document',
                        'docx': 'Word Document',
                        'xls': 'Excel Spreadsheet',
                        'xlsx': 'Excel Spreadsheet',
                        'vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'Excel Spreadsheet',
                        'pdf': 'PDF Document',
                        'vnd.ms-powerpoint': 'Word Document'}
    
    def __init__(self, url, html=None):
        self.full_url = url
        self.url = up.urlparse(url).netloc
        self.doi = []
        self.info = {}
        self.cache = {}
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'
        if not html:
            html = self.session.get(url)
        self.soup = BeautifulSoup(html, 'html.parser')
        self.nopdf = set()
        with open('nopdf','r') as np:
            for r in np:
                self.nopdf.add(r.strip())
        
        if os.path.exists(f'cache/{self.url}.cache'):
            with open(f'cache/{self.url}.cache', 'r') as f:
                is_key = True
                for line in f:
                    if is_key:
                        key = line.strip()
                    else:
                        val = line.strip()
                        self.cache[key] = val
                    is_key = not is_key
                    
    def download_files(self, replace=False, verbose=False, 
                       exclude=set({'HTML page'}), max_retry = 10):
        manifest_path = Path('files', self.doi, 'manifest.csv')
        with manifest_path.open(newline='', mode='a') as m:
            writer = csv.writer(m, delimiter='\t')
            for ctype in self.files:
                if ctype in exclude:
                    continue
                for file in self.files[ctype]:
                    if not file['file_exists'] or replace:
                        if not file['content']:
                            if verbose:
                                print(f"Fetching {file['file_name']} from")
                                print(file['location'])
                            success = False
                            retry = 0
                            while not success and retry < max_retry + 1:
                                try:
                                    r = self.session.get(file['location'],
                                                         timeout=10)
                                    success = True
                                except:
                                    retry += 1
                                    if verbose:
                                        print(f'Failed: Retrying {retry}')
                            file['content'] = r.content
                            file_name = r.headers.get('Content-Disposition')
                            if file_name:
                                file_name = file_name[file_name.find('filename=') + 9:]
                                file['file_name'] = file_name
                            else:
                                file_name = file['file_name']
                        unique_name = False
                        count = 0
                        file_path = Path('files', self.doi, file_name)
                        base_name = file_path.stem
                        if not replace:
                            while not unique_name:
                                if count > 0:
                                    file_name = base_name + '_' + str(count) + file_path.suffix
                                    file_path = file_path.with_name(file_name)
                                if verbose:
                                    print(f'Trying to save {file_name}')
                                if file_path.exists():
                                    count += 1
                                else:
                                    unique_name = True
                        file_path.write_bytes(file['content'])
                        if verbose:
                            print(f'Saved {file_name}')
                        loc = file['location'].encode('unicode_escape').decode('utf-8')
                        writer.writerow([loc,
                                         file_name,
                                         time.strftime('%x %X', 
                                                       time.localtime())])
            
    def check_files(self):
        self.files = {}
        manifest_path = Path('files', self.doi, 'manifest.csv')
        manifest = {}
        if manifest_path.exists():
            with manifest_path.open(newline='') as m:
                reader = csv.reader(m, delimiter='\t')
                for row in reader:
                    loc = row[0].encode('utf-8').decode('unicode_escape')
                    manifest[loc] = {'file_name': row[1],
                                     'date': row[2]}
        for l in self.links:
            content_type = l['content_type']
            content_type = content_type[content_type.find('/') + 1:]
            known_content_type = self.KNOWN_EXTENSIONS.get(content_type)
            if known_content_type is not None:
                content_type = known_content_type
            file_exists = l['location'] in manifest
            file_name = l['file_name']
            if not file_name:
                if file_exists:
                    file_name = manifest[l['location']]['file_name']
                else:
                    file_name = Path(up.urlparse(l['location']).path).name
            file_data = {'location': l['location'],
                         'content': l['content'],
                         'file_exists': file_exists,
                         'file_name': file_name}
            if content_type in self.files:
                self.files[content_type].append(file_data)
            else:
                self.files[content_type] = [file_data]
                
    def show_file_status(self, show_html=False):
        for ctype in self.files:
            if not show_html and ctype == 'HTML page':
                continue
            print(f'{len(self.files[ctype])} files of type: {ctype}')
            for f in self.files[ctype]:
                saved = ''
                if f['file_exists']:
                    saved = ' - Saved'
                print(f"\t{f['file_name']}{saved}")
        
    def get_info(self, update=False):
        doi_links = set()
        for l in self.soup.find_all('a'):
            link = l.get('href')
            if link and link.find('doi.org') != -1:
                doi_links.add(link)
        title_guess = self.soup.title.text.lower()
        max_delta = 0
        best_match = ''
        match_meta = None
        for link in doi_links:
            xml_meta = self.session.get(link, 
                                        headers = {'Accept': 'application/vnd.crossref.unixsd+xml'})
            meta = BeautifulSoup(xml_meta.content, 'xml')
            title = meta.title.text
            delta = difflib.SequenceMatcher(None, title_guess, title).ratio()
            if delta > max_delta:
                best_match = link
                max_delta = delta
                match_meta = meta
            self.meta = match_meta
            self.doi = best_match[best_match.find('doi.org/')+8:]
            file_path = Path('files', self.doi)
            file_path.mkdir(parents=True, exist_ok=True)
            meta_path = file_path.joinpath('meta.xml')
            if meta_path.exists() and not update:
                return
            else:
                meta_path.write_text(match_meta.prettify())
            
    def get(self, url):
        url = url.encode('unicode_escape').decode('utf-8')
        return self.cache.get(url)
    
    def add(self, url, val):
        url = url.encode('unicode_escape').decode('utf-8')
        print(url)
        print(val)
        self.cache[url] = val
        
    def commit(self):
        with open(f'cache/{self.url}.cache', 'w') as f:
            for key,val in self.cache.items():
                f.write(f'{key}\n{val}\n')
            
    def check_link(self, url, max_retry=10, cache = True, 
                   trust_extension = True, verbose=False):
        if trust_extension:
            ext = Path(up.urlparse(url).path).suffix[1:]
            if ext in self.KNOWN_EXTENSIONS:
                return f'/{ext}'
        if cache:
            cache_hit = self.get(url)
            if cache_hit:
                return cache_hit[:cache_hit.find(';')]
        retry = 0
        success = False
        while not success and retry <= max_retry:
            try:
                if verbose:
                    print(f'Fetching from: {repr(url)}')
                r = self.session.get(url, timeout=10)
                success = True
            except:
                retry +=1
                if verbose:
                    print(f'Retrying: {retry} of {max_retry}')
        if retry < 11 and r.status_code == 200:
            content_type = r.headers['Content-Type']
        else:
            if verbose:
                print(f'Failed: {r.status_code}')
            return None
        if verbose:
            print(f'Fetched page: {content_type}')
        self.add(url, content_type)
        return r
                
    def parse_page(self, verbose=False):
        parsed_url = up.urlparse(self.full_url)
        base_url = parsed_url.scheme + '://' + parsed_url.netloc
        checked_set = set()
        self.get_info()
        self.links = []
        for l in self.soup.find_all('a'):
            link = l.get('href')
            if not link or link.startswith('mailto:'):
                continue
            if not re.match('https?://', link):
                if link.startswith('//'):
                    link = parsed_url.scheme +':' + link
                elif link.startswith('/'):
                    link = base_url + link
                else:
                    link = self.full_url + link
                    continue
            yespdf = True
            for r in self.nopdf:
                if link.startswith(r):
                    yespdf = False
                    break
            if yespdf:
                if link not in checked_set:
                    result = self.check_link(link, verbose=False)
                    if result:
                        if isinstance(result, str):
                            content_type = result
                            content = None
                            file_name = None
                        else:
                            content_type = result.headers['Content-Type']
                            content_type = content_type[:content_type.find(';')]
                            content = result.content
                            file_name = result.headers.get('Content-Disposition')
                            if file_name:
                                file_name = file_name[file_name.find('filename=') + 9:]
                        self.links.append({'location': link,
                                           'content_type': content_type,
                                           'content': content,
                                           'file_name': file_name})
                    checked_set.add(link)
        self.commit()
        self.check_files()
        if verbose:
            self.show_file_status()
            print(self.links)
            if input('Download?(y/n) ') != 'y':
                return
        self.download_files(verbose=True)

if __name__ == '__main__':
    url = 'https://www.sciencedirect.com/science/article/pii/S0092867413005904'
    with open('test2.html', encoding='utf-8') as html:
        scraper = JournalScraper(url, html)
        scraper.parse_page(verbose=True)