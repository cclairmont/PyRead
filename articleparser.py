from datetime import datetime
from pathlib import Path
import json
import hashlib
import enum
import requests
from bs4 import BeautifulSoup
from requests.exceptions import Timeout

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
                    'vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                        FileType.SPREADSHEET,
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


class ParserException(Exception):
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
        if manifest is not None:
            self.from_manifest(manifest, verify)
        if self.name is not None:
            self.path = self.dir.joinpath(self.name)
        if infer_type and self.name is not None:
            if self.ftype is FileType.UNKNOWN:
                ext = self.path.suffix
                inferred_type = KNOWN_EXTENSIONS.get(ext)
                if inferred_type is not None:
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
        if self.data is not None:
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
        ftype = entry.get('ftype')
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
                manifest = json.loads(m.read())
        else:
            manifest = {}
        self.manifest = manifest
        self.files = {}
        if 'files' in manifest:
            for f in manifest['files']:
                self.files[f] = ArticleFile(self.path,
                                            manifest=manifest['files'][f])

    def add_file(self, name, source, data, identity=None, overwrite=False,
                 date=None, content_type=None, content_length=None, number=0,
                 title=None, caption='', low_res=False):
        if self.files is None:
            self.files = {}
        if date is None:
            date = datetime.now().isoformat()
        if content_length is None:
            content_length = len(data)
        new_file = ArticleFile(data=data, path=self.path,
                               manifest={'name': name,
                                         'source': source,
                                         'date': date,
                                         'content_type': content_type,
                                         'content_length': content_length})
        if low_res:
            res = 'lr'
        else:
            res = 'hr'
        if name in self.files and not overwrite:
            if new_file != self.files[name]:
                raise FileExistsError
        entry = {name: {'title': title,
                        'caption': caption}}

        def do_pdf(what):
            if self.manifest.get(what) is not None:
                raise FileExistsError

        def do_files(what):
            if self.manifest.get(what) is None:
                self.manifest[what] = entry
            else:
                self.manifest[what] = {**self.manifest[what], **entry}

        def do_order(what):
            if self.manifest.get(what) is None:
                self.manifest[what] = {}
            if res not in self.manifest[what]:
                self.manifest[what][res] = []
            if number == 0:
                raise FileTypeError
            if number > len(self.manifest[what][res]):
                for i in range(number - len(self.manifest[what][res])):
                    self.manifest[what][res].append(None)
            if self.manifest[what][res][number - 1] is None or overwrite:
                self.manifest[what][res][number - 1] = entry
            else:
                raise FileExistsError

        def do_what(fun, what):
            return lambda: fun(what)

        identity_lookup = {ArticleItem.PDF: do_what(do_pdf, 'pdf'),
                           ArticleItem.EXTENDED_PDF:
                               do_what(do_pdf, 'extended'),
                           ArticleItem.SUPPLEMENTARY_FILE:
                               do_what(do_files, 'supp_files'),
                           ArticleItem.FIGURE: do_what(do_order, 'figures'),
                           ArticleItem.SUPPLEMENTARY_FIGURE:
                               do_what(do_order, 'supp_figs'),
                           ArticleItem.VIDEO: do_what(do_order, 'videos'),
                           ArticleItem.SUPPLEMENTARY_VIDEO:
                               do_what(do_order, 'supp_vids'),
                           ArticleItem.OTHER: do_what(do_files, 'other')}

        identity_lookup[identity]()
        self.files[name] = new_file
        new_file.write()
        self.update_manifest()

    def update_manifest(self):
        manifest_path = self.path.joinpath('manifest.json')
        with manifest_path.open(mode='w', encoding='utf-8') as m:
            m.write(json.dumps(self.manifest))

    def add_url(self, url):
        if self.url is None:
            self.url = []
        if url not in self.url:
            self.url.append(url)

    def meta_date(self):
        return self.manifest.get('metadate')

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
        self.manifest['title'] = title
        self.manifest['journal'] = journal
        self.manifest['date'] = date.isoformat()
        self.manifest['authors'] = authors
        self.manifest['metadate'] = datetime.now().isoformat()
        self.update_manifest()

    def print_info(self, verbosity=0):
        print(f"Title: {self.manifest['title']}")
        print(f"Journal: {self.manifest['journal']}")
        authors = self.manifest['authors']
        author_string = None
        if authors is not None:
            author_string = ''
            for a in authors:
                author_string = author_string + f'{a}, '
            author_string = author_string[:-2]
        print(f'Authors: {author_string}')
        date_str = self.manifest['date']
        if date_str:
            date_str = datetime.fromisoformat(date_str).strftime('%B %d %Y')
        else:
            date_str = ''
        print(f'Date: {date_str}')
        if verbosity > 0:
            if self.manifest['url'] is not None:
                for i, u in enumerate(self.manifest['url']):
                    print(f'Url {i}: {u}')
            for name, item in self.manifest.items():
                if name in set('pdf', 'extended', 'supp_files', 'figures',
                               'supp_figs', 'videos', 'supp_vids', 'other'):
                    if len(item) != 1:
                        print(name + 's:')
                    else:
                        print(name + ':')
                    if isinstance(item, list):
                        for num, i in enumerate(item):
                            print(f'\t{name} {num}: i.keys()[0]')
                            if verbosity > 1:
                                print('\t\t' + i[i.keys()[0]]['title'])
                    else:
                        for i in item:
                            print(f'\t {i}')
                            if verbosity > 1:
                                print('\t\t' + item[i]['title'])


class ArticleParser:
    def __init__(self, content, inject, fetch, debug=False, dummy=False,
                 log=None, max_retry=10):
        if log is None:
            def log(m):
                with open('aplog.txt', 'a') as f:
                    f.write(f'{m}\n')
        self.log = log
        self.soup = content
        self.debug = debug
        self.inject = inject
        self.page_url = None
        self.max_retry = 10
        self.fetch = fetch
        if dummy:
            return
        self.article = Article(self.get_doi())
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
        self.article.content = self.get_content()
        for i, section in enumerate(self.article.content):
            if isinstance(section['content'], list):
                for j, subsect in enumerate(section['content']):
                    self.article.content[i]['content'][j]['content'] = \
                        self.clean_html(BeautifulSoup(subsect['content'],
                                                      'lxml'))
            else:
                self.article.content[i]['content'] = \
                    self.clean_html(BeautifulSoup(section['content'], 'lxml'))

        self.article.references = self.get_references()
        figures = self.get_figures()
        other_files = self.get_files()
        for key, val in figures.items():
            print(key)
            for res in ['lr', 'hr']:
                if res not in val:
                    continue
                if debug:
                    self.log(f'Downloading {key} ({res}) from')
                    self.log(val[res])
                status, content, name = self.get_retry(val[res])
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
                    self.article.add_file(name, val[res], content,
                                          identity=identity, number=number,
                                          title=val['title'],
                                          caption=val['caption'],
                                          low_res=(res == 'lr'))
                except FileExistsError:
                    if debug:
                        self.log('File Exists - Not Overwriting')
        for file, link in other_files.items():
            if debug:
                self.log(f'Downloading {file} from:')
                self.log(link)
            status, content, name = self.get_retry(link)
            title = file
            if title == 'pdf':
                identity = ArticleItem.PDF
            elif title == 'extended':
                identity = ArticleItem.EXTENDED_PDF
            else:
                identity = ArticleItem.OTHER
            try:
                self.article.add_file(name, link, content, identity,
                                      title=title)
            except FileExistsError:
                if debug:
                    self.log('File Exists - Not overwriting')

    def get_retry(self, url, headers=None, timeout=10, cache=True):
        retry = 0
        while retry <= self.max_retry:
            try:
                status, content, name = self.fetch(url, headers, cache)
                break
            except Timeout:
                retry += 1
                if self.debug:
                    self.log(f'Timeout fetching {url} on attempt {retry}')
        return status, content, name

    def fetch_metadata(self):
        doi = self.article.doi
        headers = {'Accept': 'application/vnd.crossref.unixsd+xml'}
        url = 'http://dx.doi.org/' + doi
        if self.debug:
            self.log(f'Fetching metadata from: {url}')
        status, content, name = self.get_retry(url, headers=headers,
                                               cache=False)
        if status != 200:
            print(status)
            print(content)
            raise RequestError
        return content

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
