from datetime import datetime
from pathlib import Path
import ast
import hashlib
import enum
import requests
from bs4 import BeautifulSoup
import selenium_utils as su
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, InvalidCookieDomainException

def scrape(url, data):
    return 'hello'

PROXY = {'Harvard': 'javascript:(function(){location.href="http://"+location.hostname+".ezp-prod1.hul.harvard.edu"+location.pathname})();'}
USE_PROXY = 'Harvard'

class FileType(enum.Enum):
    HTML = 0
    PDF = 1
    WORDDOC = 2
    SPREADSHEET = 3
    POWERPOINT = 4
    IMAGE = 5
    VIDEO = 6
    UNKNOWN = 99
    
class ArticleItem(enum.Enum):
    PDF = 0
    EXTENDED_PDF = 1
    SUPPLEMENTARY_FILE = 2
    FIGURE = 3
    SUPPLEMENTARY_FIGURE = 4
    VIDEO = 5
    SUPPLEMENTARY_VIDEO = 6
    OTHER = 99

KNOWN_EXTENSIONS = {'html': FileType.HTML,
                    'htm': FileType.HTML,
                    'jpeg': FileType.IMAGE,
                    'jpg': FileType.IMAGE,
                    'png': FileType.IMAGE,
                    'tif': FileType.IMAGE,
                    'ppt': FileType.POWERPOINT,
                    'pptx': FileType.POWERPOINT,
                    'doc': FileType.WORDDOC,
                    'docx': FileType.WORDDOC,
                    'xls': FileType.SPREADSHEET,
                    'xlsx': FileType.SPREADSHEET,
                    'vnd.openxmlformats-officedocument.spreadsheetml.sheet': FileType.SPREADSHEET,
                    'pdf': FileType.SPREADSHEET,
                    'vnd.ms-powerpoint': FileType.POWERPOINT,
                    'mp4': FileType.VIDEO,
                    'mkv': FileType.VIDEO,
                    'avi': FileType.VIDEO}

class NoDOI(Exception):
    pass

class FileChangedError(Exception):
    pass

class FileTypeError(Exception):
    pass

class RequestError(Exception):
    pass

class AuthorizationError(Exception):
    pass

class ArticleFile:
    
    def __init__(self, path=None, data=None, manifest=None, verify=False,
                 infer_type=True):
        self.data = data
        self.fhash = None
        self.name = None
        self.source = []
        self.ftype = FileType.UNKNOWN
        if isinstance(path, str):
            self.dir = Path(path)
        else:
            self.dir = path
        self.path = None
        if not manifest is None:
            self.from_manifest(manifest, verify)
        if not self.name is None:
            self.path = self.dir.joinpath(self.name)
        if infer_type and not self.name is None:
            if self.ftype is FileType.UNKNOWN:
                ext = self.path.suffix
                inferred_type = KNOWN_EXTENSIONS.get(ext)
                if not inferred_type is None:
                    self.ftype = inferred_type
        
    def __hash__(self):
        if self.fhash is None:
            if self.data is None:
                self.data = self.get_data()
            self.fhash = int.from_bytes(hashlib.sha256(self.data).digest(), 
                                        'big')
        return self.fhash
    
    def __eq__(self, other):
        return hash(self) == hash(other)
    
    def __str__(self):
        return f'{self.name}: Modified {self.date}'
    
    def __repr__(self):
        str(self)

    def get_data(self):
        if not self.data is None:
            return self.data
        if self.path is None:
            raise FileNotFoundError
        with self.path.open(mode='rb') as f:
            self.data = f.read()
        return self.data
        
    def reset(self):
        self.data = None
        self.fhash = None
        
    def changed(self):
        new_file = ArticleFile()
        new_file.data = self.get_data()
        return new_file != self
    
    def write(self, data=None):
        if data is None:
            data = self.data
        if self.path is None:
            raise FileNotFoundError
        with self.path.open(mode='wb') as f:
            f.write(data)
        self.data = data
        self.date = datetime.now()
        self.reset()
            
    def from_manifest(self, entry, verify=False):
        self.name = entry['name']
        self.source = entry['source']
        self.date = datetime.fromisoformat(entry['date'])
        ftype = entry['ftype']
        if ftype is None:
            ftype = FileType.UNKNOWN.value
        self.ftype = FileType(ftype)
        if verify:
            if 'hash' in entry and hash(self) != entry['hash']:
                raise FileChangedError
                
    def to_manifest(self, update_hash=False):
        entry = {}
        entry['name'] = self.name
        entry['source'] = self.source
        entry['date'] = self.date.isoformat()
        entry['ftype'] = self.ftype.value
        if update_hash:
            self.reset()
        entry['hash'] = hash(self)
        return entry
        
    def merge(self, other, verify=False):
        if verify:
            if other != self:
                raise FileChangedError
        self.source = list(set([*self.source, *other.source]))
        
class Article:
    
    def __init__(self, doi):
        self.doi = doi
        self.path = Path('files', doi)
        if not self.path.exists():
            self.path.mkdir(parents=True)
        manifest_path = self.path.joinpath('manifest.json')
        if manifest_path.exists():
            with manifest_path.open(mode='r', encoding='utf-8') as m:
                manifest = ast.literal_eval(m.read())
        else:
            manifest = {}
        self.files = {}
        if 'files' in manifest:
            for f in manifest['files']:
                self.files[f] = ArticleFile(self.path, 
                                            manifest=manifest['files'][f])
            self.title = manifest.get('title')
        
        self.title = manifest.get('title')
        self.url = manifest.get('url')
        self.journal = manifest.get('journal')
        self.authors = manifest.get('authors')
        self.date = manifest.get('date')
        self.metadate = manifest.get('metadate')
        self.abstract = manifest.get('abstract')
        self.content = manifest.get('content')
        self.references = manifest.get('references')
        self.pdf = manifest.get('pdf')
        self.extended = manifest.get('extended')
        self.figures = manifest.get('figures')
        self.supp_files = manifest.get('supp_files')
        self.supp_figures = manifest.get('supp_figures')
        self.movies = manifest.get('movies')
        self.supp_movies = manifest.get('supp_movies')
        self.other = manifest.get('other')

    def add_file(self, name, source, data, identity=None, overwrite=False, 
                 date=None, ftype=None, number=0, title=None, caption='',
                 low_res=False):
        if self.files is None:
            self.files = {}
        if not ftype is None:
            ftype = ftype.value
        if date is None:
            date = datetime.now().isoformat()
        new_file = ArticleFile(data=data, path=self.path,
                               manifest={'name': name,
                                         'source': source,
                                         'date': date,
                                         'ftype': ftype})
        if low_res:
            res = 'lr'
        else:
            res = 'hr'
        if name in self.files and not overwrite:
            if new_file != self.files[name]:
                raise FileExistsError
        entry = {name: {'title': title,
                        'caption': caption}}
        if identity is ArticleItem.PDF:
            if not self.pdf is None:
                raise FileExistsError
            self.pdf = entry
        elif identity is ArticleItem.EXTENDED_PDF:
            if not self.extended is None:
                raise FileExistsError
            self.extended = entry
        elif identity is ArticleItem.SUPPLEMENTARY_FILE:
            if self.supp_files is None:
                self.supp_files = entry
            else:
                self.supp_files = {**self.supp_files, **entry}
        elif identity is ArticleItem.FIGURE:
            if self.figures is None:
                self.figures = {}
            if res not in self.figures:
                self.figures[res] = []
            if number == 0:
                raise FileTypeError
            if number < len(self.figures[res]):
                for i in range(number - len(self.figures[res])):
                    self.figures[res].append(None)
                if self.figures[res][number - 1] is None or overwrite:
                    self.figures[res][number -1] = entry
                else:
                    raise FileExistsError
        elif identity is ArticleItem.SUPPLEMENTARY_FIGURE:
            if self.supp_figures is None:
                self.supp_figures = {}
            if res not in self.supp_figures:
                self.supp_figures[res] = []
            if number == 0:
                raise FileTypeError
            if number < len(self.supp_figures[res]):
                for i in range(number - len(self.supp_figures[res])):
                    self.supp_figures[res].append(None)
                if self.supp_figures[res][number - 1] is None or overwrite:
                    self.supp_figures[res][number - 1] = entry
                else:
                    raise FileExistsError
        elif identity is ArticleItem.VIDEO:
            if self.movies is None:
                self.movies = {}
            if res not in self.movies:
                self.movies[res] = []
            if number == 0:
                raise FileTypeError
            if number < len(self.movies[res]):
                for i in range(number - len(self.movies[res])):
                    self.movies[res].append(None)
                if self.movies[res][number - 1] is None or overwrite:
                    self.movies[res][number - 1] = entry
                else:
                    raise FileExistsError
        elif identity is ArticleItem.SUPPLEMENTARY_VIDEO:
            if self.supp_movies is None:
                self.supp_movies = {}
            if res not in self.supp_movies:
                self.supp_movies[res] = []
            if number == 0:
                raise FileTypeError
            if number < len(self.supp_movies[res]):
                for i in range(number - len(self.supp_movies[res])):
                    self.supp_movies[res].append(None)
                if self.supp_movies[res][number - 1] is None or overwrite:
                    self.supp_movies[res][number - 1] = entry
                else:
                    raise FileExistsError
        else:
            if self.other is None:
                self.other = entry
            else:
                self.other = {**self.other, **entry}
        if name in self.files and not overwrite:
            self.files[name].merge(new_file)
        else:
            self.files[name] = new_file
        new_file.write()
        self.update_manifest()

    def update_manifest(self):
        manifest = {'title': self.title,
                    'url': self.url,
                    'journal': self.journal,
                    'authors': self.authors,
                    'date': self.date,
                    'metadate': self.metadate,
                    'abstract': self.abstract,
                    'content': self.content,
                    'figures': self.figures,
                    'references': self.references,
                    'files': {k:v.to_manifest() for k,v in self.files.items()},
                    'pdf': self.pdf,
                    'extended': self.extended,
                    'supp_files': self.supp_files,
                    'supp_figures': self.supp_figures,
                    'movies': self.movies,
                    'supp_movies': self.supp_movies,
                    'other': self.other}
        manifest_path = self.path.joinpath('manifest.json')
        with manifest_path.open(mode='w', encoding='utf-8') as m:
            m.write(str(manifest))

    def add_url(self, url):
        if self.url is None:
            self.url = []
        if not url in self.url:
            self.url.append(url)
            
    def meta_date(self):
        return self.metadate
            
    def update_metadata(self, xml):
        s = BeautifulSoup(xml, 'xml')
        title = s.title.text
        journal = s.journal_metadata.full_title.text
        for i in s.find_all('crm-item'):
            if i['name'] == 'created':
                date = datetime.fromisoformat(i.text[:-1])
        authors = []
        for a in s.find_all('person_name'):
            if a['contributor_role'] == 'author':
                name = a.given_name.text + ' ' + a.surname.text
                authors.append(name)
        self.title = title
        self.journal = journal
        self.date = date.isoformat()
        self.authors = authors
        self.metadate = datetime.now().isoformat()
        self.update_manifest()
             
    def print_info(self, verbosity=0):
        print(f'Title: {self.title}')
        print(f'Journal: {self.journal}')
        authors = self.authors
        author_string = None
        if not authors is None:
            author_string = ''
            for a in authors:
                author_string = author_string + f'{a}, '
            author_string = author_string[:-2]
        print(f'Authors: {author_string}')
        date_str = self.date
        if date_str:
            date_str = datetime.fromisoformat(date_str).strftime('%B %d %Y')
        else:
            date_str = ''
        print(f'Date: {date_str}')
        if verbosity > 0:
            if not self.url is None:
                for i,u in enumerate(self.url):
                    print(f'Url {i}: {u}')
            if not self.pdf is None:
                for name,item in {'PDF': self.pdf, 
                                  'Extended PDF': self.extended,
                                  'Figure': self.figures,
                                  'Supplementary Figure': self.supp_figures,
                                  'Video': self.movies,
                                  'Supplementary Video': self.supp_movies,
                                  'Supplementary File': self.supp_files,
                                  'Other': self.supp_files}.items():
                    if len(item) != 1:
                        print(name + 's:')
                    else:
                        print(name + ':')
                    if isinstance(item, list):
                        for num,i in enumerate(item):
                            print(f'\t{name} {num}: i.keys()[0]')
                            if verbosity > 1:
                                print('\t\t' + i[i.keys()[0]]['title'])
                    else:
                        for i in item:
                            print(f'\t {i}')
                            if verbosity > 1:
                                print('\t\t' + item[i]['title'])
                                
                        
class ArticleParser:
    
    def __init__(self, url, debug=False, dummy=False, log=None, max_retry=10):
        if log is None:
            self.log = print
        self.debug = debug
        self.url = url
        self.page_url = None
        self.max_retry = 10
        self.session = requests.Session()
        self.session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:74.0) Gecko/20100101 Firefox/74.0'
        if dummy:
            return
        self.article = Article(self.get_doi())
        self.article.add_url(url)
        if debug:
            self.log(f'Checking metadata for {self.article.doi}')
        meta_date = self.article.meta_date()
        if meta_date is None:
            if debug:
                self.log('Local metadata not found, fetching...')
            self.article.update_metadata(self.fetch_metadata())
        else:
            if debug:
                self.log(f'Found local metadata from {meta_date}')
        if debug:
            self.article.print_info()
        self.article.abstract = self.get_abstract()
        self.fetch_page()
        if not self.have_access(self.soup):
            if debug:
                self.log('Closed Acess: Trying Proxy')
            self.proxy_auth()
        else:
            self.cookies = []
            if debug:
                self.log('Open Acess Article')
        self.article.content = self.get_content()
        for section in self.article.content:
            if isinstance(self.article.content[section], dict):
                for subsect in self.article.content[section]:
                    self.article.content[section][subsect] = self.clean_html(self.article.content[section][subsect])
            else:
                self.article.content[section] = self.clean_html(self.article.content[section])
        
        self.article.references = self.get_references()
        figures = self.get_figures()
        for key,val in figures.items():
            for res in ['lr', 'hr']:
                if debug:
                    self.log(f'Downloading {key} ({res}) from')
                    self.log(val[res])
                data = self.get_retry(val[res])
                name = Path(val[res]).name
                if key.startswith('Figure S'):
                    identity = ArticleItem.SUPPLEMENTARY_FIGURE
                    number = int(key[8:])
                elif key.startswith('Figure'):
                    identity = ArticleItem.FIGURE
                    number = int(key[7:])
                else:
                    identity = ArticleItem.OTHER
                    number = 0
                try:
                    self.article.add_file(name, val[res], data.content, 
                                          identity=identity, number=number, 
                                          title=val['title'], 
                                          caption=val['caption'],
                                          low_res=(res == 'lr'))
                except FileExistsError:
                    if debug:
                        self.log('File Exists - Not Overwriting')
        other_files = self.get_files()
        for file,link in other_files.items():
            if debug:
                self.log(f'Downloading {file} from:')
                self.log(link)
            data = self.get_retry(link)
            name = Path(link).name
            info = data.headers.get('Content-Disposition')
            if not info is None:
                name = info[info.find('filename=') + 9:]
            link = link
            title = file
            if title == 'pdf':
                identity = ArticleItem.PDF
            elif title == 'extended':
                identity = ArticleItem.EXTENDED_PDF
            else:
                identity = ArticleItem.OTHER
            try:
                self.article.add_file(name, link, data.content, identity, 
                                      title=title)
            except FileExistsError:
                if debug:
                    self.log('File Exists - Not overwriting')
                    
    def get_retry(self, url, timeout=10):
        retry = 0
        while retry <= self.max_retry:
            try:
                r = self.session.get(url, timeout=timeout)
                break
            except TimeoutException:
                retry += 1
                if self.debug:
                    self.log(f'Timeout fetching {url} on attempt {retry}')
        return r
            
    def fetch_page(self, refresh=False):
        if refresh or self.url != self.page_url:
            r = self.get_retry(self.url)
            self.soup = BeautifulSoup(r.content, 'lxml')
            self.page_url = self.url
        return self.soup
    
    def fetch_metadata(self):
        doi = self.article.doi
        headers = {'Accept': 'application/vnd.crossref.unixsd+xml'}
        url = 'http://dx.doi.org/' + doi
        if self.debug:
            self.log(f'Fetching metadata from: {url}')
        r = self.get_retry(url, headers=headers)
        if r.status_code != 200:
            raise RequestError
        return r.content
    
    def proxy_auth(self):
        options = su.driver_options('firefox')
        options.headless = True
        try:
            with open('cookies.json','r') as cookie_file:
                cookies = ast.literal_eval(cookie_file.read())
        except FileNotFoundError:
            cookies = []
        self.cookies = cookies
        self.session.cookies = su.make_cookiejar(cookies=cookies)
        self.fetch_page()
        if self.have_access(self.soup):
            return
        driver = su.spawn_driver('firefox', options)
        driver.get(self.url)
        wait = WebDriverWait(driver, 5)
        wait.until(su.page_is_ready)
        driver.execute_script(PROXY[USE_PROXY])
        wait.until(su.url_changed(self.url))
        for c in cookies:
            try:
                driver.add_cookie(c)
                if self.debug:
                    self.log(f"Added Cookie: {c['name']}")
            except InvalidCookieDomainException:
                if self.debug:
                    self.log(f"Failed Cookie: {c['name']}")
        driver.refresh()
        try:
            wait.until(self.access)
            self.url = driver.current_url
            driver.quit()
            return
        except TimeoutException:
            pass
        driver.quit()
        driver = su.spawn_driver('firefox')
        wait = WebDriverWait(driver, 300)
        driver.get(self.url)
        wait.until(su.page_is_ready)
        driver.execute_script(PROXY[USE_PROXY])
        cookies = []
        while True:
            try:
                current = driver.current_url
                if current != self.url:
                    cookies = cookies + driver.get_cookies()
                    self.url = current
                    self.log(self.url)
                    self.log(cookies)
                if self.access(driver):
                    break
            except:
                pass
        self.cookies = cookies
        self.session.cookies = su.make_cookiejar(cookies=self.cookies)
        self.url = driver.current_url
        with open('cookies.json','w') as cookie_file:
            cookie_file.write(str(self.cookies))
        driver.quit()
        return
        
    def have_access(self):
        raise NotImplementedError
        
    def get_doi(self):
        raise NotImplementedError

    def get_abstract(self):
        raise NotImplementedError
        
    def get_content(self):
        raise NotImplementedError
    
    def get_references(self):
        raise NotImplementedError
        
    def clean_html(self, html):
        raise NotImplementedError
        
    @classmethod
    def doi_from_url(cls, url):
        dummy = cls(url, dummy=True)
        return dummy.get_doi()
    
    @classmethod
    def access(cls, driver):
        dummy = cls('', dummy=True)
        soup = BeautifulSoup(driver.page_source, 'lxml')
        return dummy.have_access(soup)
        
class SeleniumParser(ArticleParser):
    
    def __init__(self, *args, browser='firefox', **kwargs):
        self.browser = browser
        self.driver = None
        super().__init__(*args, **kwargs)
    
    def get_driver(self):
        if self.driver is None:
            options = su.driver_options(self.browser)
            if not self.debug:
                options.headless = True
            self.driver = su.spawn_driver(self.browser, options=options)
            self.wait = WebDriverWait(self.driver, 10)
            self.driver.get(self.url)
            self.wait.until(su.page_is_ready)
            for c in self.cookies:
                try:
                    self.driver.add_cookie(c)
                    if self.debug:
                        self.log(f"Added Cookie: {c['name']}")
                except:
                    if self.debug:
                        self.log(f"Failed Cookie: {c['name']}")
                    pass
            self.driver.get(self.url)