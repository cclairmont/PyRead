from datetime import datetime
from pathlib import Path
import json
import hashlib
import enum
from bs4 import BeautifulSoup
import aiofiles
import aiohttp
from difflib import SequenceMatcher


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


class ArticleError(Exception):
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
            self.from_manifest(manifest)
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
                return 0
            self.fhash = int.from_bytes(hashlib.sha256(self.data).digest(),
                                        'big')
        return self.fhash

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __str__(self):
        return f'{self.name}: Modified {self.date}'

    def __repr__(self):
        str(self)

    async def get_data(self):
        if self.data is not None:
            return self.data
        if self.path is None:
            raise FileNotFoundError
        async with aiofiles.open(str(self.path), 'rb') as f:
            self.data = await f.read()
        return self.data

    def reset(self):
        self.data = None
        self.fhash = None

    async def changed(self):
        new_file = ArticleFile()
        new_file.data = await self.get_data()
        return new_file != self

    async def write(self, data=None):
        if data is None:
            data = self.data
        if self.path is None:
            raise FileNotFoundError
        async with aiofiles.open(str(self.path), 'wb') as f:
            await f.write(data)
        self.date = datetime.now()
        self.reset()
        self.data = data

    def from_manifest(self, entry):
        self.name = entry['name']
        self.source = entry['source']
        self.date = datetime.fromisoformat(entry['date'])
        ftype = entry.get('ftype')
        if ftype is None:
            ftype = FileType.UNKNOWN.value
        self.ftype = FileType(ftype)

    async def verify_from_manifest(self, entry):
        self.name = entry['name']
        self.source = entry['source']
        self.date = datetime.fromisoformat(entry['date'])
        ftype = entry.get('ftype')
        if ftype is None:
            ftype = FileType.UNKNOWN.value
        self.ftype = FileType(ftype)
        await self.get_data()
        if 'hash' in entry and hash(self) != entry['hash']:
            raise FileChangedError

    def to_manifest(self, update_hash=False):
        entry = {}
        entry['name'] = self.name
        entry['source'] = self.source
        entry['date'] = self.date.isoformat()
        entry['ftype'] = self.ftype.value
        entry['hash'] = hash(self)
        return entry

    async def merge(self, other, verify=False):
        if verify:
            if other.data is None:
                await other.get_data()
            if self.data is None:
                await self.get_data()
            if other != self:
                raise FileChangedError
        self.source = list(set([*self.source, *other.source]))


class Article:

    headers = {'User-Agent':
               'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:77.0) '
               'Gecko/20100101 Firefox/77.0'}

    async def fetch_metadata(self, doi=None, pmid=None, title=None):
        if not Path('files/database.json').exists():
            async with aiofiles.open('files/database.json', 'w') as f:
                await f.write(json.dumps({'doi': {},
                                          'pmid': {},
                                          'title': {}}))
        async with aiohttp.ClientSession() as session:
            if doi is None:
                if pmid is None:
                    if title is None:
                        raise ArticleError("Must provide doi, pmid or title"
                                           " to set article metadata")
                    async with aiofiles.open('files/database.json', 'r') as f:
                        db = json.loads(await f.read())
                        entry = db['title'].get(title)
                        if entry is not None:
                            return entry
                    entry = {'title': title}
                    # Search pubmed by title to get DOI and PMID
                    async with session.get('https://pubmed.ncbi.nlm.nih.gov/'
                                           '?term="' +
                                           title.replace(' ', '+') + '"',
                                           headers=self.headers) as response:
                        soup = BeautifulSoup(await response.read(), 'lxml')
                    d_soup = soup.find('span', {'class': 'doi'})
                    if d_soup is None:
                        # This means there was more than one search result,
                        # so we compare the titles of all of the search results
                        # to our title and pick the closest one that is more
                        # than 90% similar
                        d_soup = soup.find_all('a',
                                               {'class':
                                                'labs-docsum-title'})
                        max_score = 0
                        max_link = ''
                        for d in d_soup:
                            score = SequenceMatcher(None, title,
                                                    d.text.strip()).ratio()
                            if score > max_score:
                                max_score = score
                                max_link = d['href']
                        if max_score > 0.9:
                            async with session.get('https://pubmed.ncbi.nlm.'
                                                   'nih.gov' + max_link,
                                                   headers=self.headers)\
                                    as response:
                                soup = BeautifulSoup(await response.read(),
                                                     'lxml')
                            d_soup = soup.find('span', {'class': 'doi'})
                        else:
                            d_soup = None
                            soup = None
                    if d_soup is None:
                        entry['doi'] = None
                        entry['pmid'] = None
                    else:
                        entry['doi'] = d_soup.find('a').text.strip()
                        entry['pmid'] = soup.find('strong',
                                                  {'class':
                                                   'current-id'}).text.strip()
                else:
                    async with aiofiles.open('files/database.json', 'r') as f:
                        db = json.loads(await f.read())
                        entry = db['pmid'].get(pmid)
                        if entry is not None:
                            return entry
                        entry = {'pmid': pmid}
                        # Use the PMID to fetch the DOI from Pubmed
                        async with session.get('https://pubmed.ncbi.nlm.nih.'
                                               'gov/' + pmid,
                                               headers=self.headers)\
                                as response:
                            soup = BeautifulSoup(await response.read(),
                                                 'lxml')
                        d_soup = soup.find('span', {'class': 'doi'})
                        entry['doi'] = d_soup.find('a').text.strip()
            else:
                self.path = Path('files', doi)
                async with aiofiles.open('files/database.json', 'r') as f:
                    db = json.loads(await f.read())
                    entry = db['doi'].get(doi)
                    if entry is not None:
                        return entry
                    entry = {'doi': doi}
                    if pmid is None:
                        # Fetch the PMID from pubmed by searching for the DOI
                        async with session.get('https://pubmed.ncbi.nlm.nih.'
                                               'gov/?term=' + doi,
                                               headers=self.headers) as\
                                response:
                            soup = BeautifulSoup(await response.read(),
                                                 'lxml')
                        entry['pmid'] = soup.find('strong',
                                                  {'class': 'current-id'}).text
                    else:
                        entry['pmid'] = pmid
            if 'doi' in entry:
                self.doi = entry['doi']
                if 'pmid' in entry:
                    self.pmid = entry['pmid']
                else:
                    self.pmid = None
                self.path = Path('files', self.doi)
            elif 'pmid' in entry:
                self.doi = None
                self.pmid = entry['pmid']
                self.path = Path('files', 'pmid', self.pmid)
            else:
                raise ArticleError("Could not find article on Pubmed")
            if not self.path.exists():
                self.path.mkdir(parents=True)
                entry['local'] = False
            manifest_path = self.path.joinpath('manifest.json')
            if manifest_path.exists():
                async with aiofiles.open(str(manifest_path),
                                         'r', encoding='utf-8') as m:
                    manifest = json.loads(await m.read())
            else:
                manifest = {}
            self.manifest = manifest
            self.files = {}
            if 'files' in manifest:
                for f in manifest['files']:
                    self.files[f] = ArticleFile(self.path,
                                                manifest=manifest['files'][f])
            if self.doi is not None:
                headers = {**self.headers,
                           'Accept': 'application/vnd.crossref.unixsd+xml'}
                url = 'http://dx.doi.org/' + entry['doi']
                async with session.get(url, headers=headers) as response:
                    self.update_metadata(await response.read())
            elif self.pmid is not None:
                async with session.get('https://pubmed.ncbi.nlm.nih.gov/'
                                       + pmid,
                                       headers=self.headers) as response:
                    soup = BeautifulSoup(await response.read(), 'lxml')
                    cite = soup.find('span', {'class': 'cit'}).text
                    date = cite[:cite.find(';')]
                    date = datetime.strptime(date, '%Y %b %d')
                    a_list = soup.find('div', {'class': 'authors-list'})
                    authors = a_list.find_all('a', {'class': 'full-name'})
                    a_list = []
                    for a in authors:
                        a_list.append(a.text)
                    self.manifest['title'] = soup.find('h1',
                                                       {'class':
                                                        'heading-title'}).text
                    self.manifest['journal'] = \
                        soup.find('button',
                                  {'id': 'full-view-journal-trigger'}).title
                    self.manifest['date'] = date.isoformat()
                    self.manifest['authors'] = a_list
                    self.manifest['metadate'] = datetime.now().isoformat()
            entry['title'] = self.manifest['title']
            entry['authors'] = self.manifest['authors']
            entry['date'] = self.manifest['date']
            await self.update_manifest()
            await self.update_meta_db(entry)
            return entry

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

    async def update_manifest(self):
        manifest_path = self.path.joinpath('manifest.json')
        async with aiofiles.open(str(manifest_path), 'w',
                                 encoding='utf-8') as m:
            await m.write(json.dumps(self.manifest))

    async def update_meta_db(self, entry):
        async with aiofiles.open('files/database.json', 'r') as f:
            db = json.loads(await f.read())
        if 'doi' in entry:
            db_entry = db['doi'].get(entry['doi'])
            db_entry = self.update_dbentry(db_entry, entry)
            db['doi'][entry['doi']] = db_entry
        if 'pmid' in entry:
            db_entry = db['pmid'].get(entry['pmid'])
            db_entry = self.update_dbentry(db_entry, entry)
            db['pmid'][entry['pmid']] = db_entry
        if 'title' in entry:
            db_entry = db['title'].get(entry['title'])
            db_entry = self.update_dbentry(db_entry, entry)
            db['title'][entry['title']] = db_entry
        async with aiofiles.open('files/database.json', 'w') as f:
            await f.write(json.dumps(db))

    def update_dbentry(self, db, ref):
        if db is None:
            return ref
        if ref is None:
            return db
        for k1, v1 in db.items():
            if k1 in ref and ref[k1] is not None:
                if k1 == 'local':
                    if not v1 and k1 in ref:
                        db[k1] = ref[k1]
                    continue
                if v1 is None:
                    db[k1] = ref[k1]
                    continue
                if isinstance(v1, str):
                    if v1 == ref[k1]:
                        continue
                    else:
                        db[k1] = [v1].append(ref[k1])
                elif isinstance(v1, list):
                    # Either author list of list of variants
                    if isinstance(ref[k1], str):
                        # Must not be an author list
                        if ref[k1] in v1:
                            continue
                        else:
                            db[k1].append(ref[k1])
                    elif isinstance(ref[k1], list):
                        # Must be an author list
                        match = False
                        nested = False
                        for i, e1 in enumerate(v1):
                            # If these are strings, its not a nested list
                            if isinstance(e1, str):
                                if e1 != ref[k1][i]:
                                    break
                            elif isinstance(e1, list):
                                # DB is a nested list
                                nested = True
                                for i, e2 in enumerate(e1):
                                    if e2 != ref[k1][i]:
                                        break
                                if i == len(e2) and i == len(ref[k1]):
                                    match = True
                                    break
                            else:
                                if e1 != ref[k1][i]:
                                    break
                        if not nested and i == len(e1) and i == len(ref[k1]):
                            match = True
                        if not match:
                            if nested:
                                db[k1].append(ref[k1])
                            if not nested:
                                db[k1] = [v1].append(ref[k1])
                    else:
                        if ref[k1] in v1:
                            continue
                        else:
                            db[k1].append(ref[k1])
                else:
                    if v1 == ref[k1]:
                        continue
                    else:
                        db[k1] = [v1].append(ref[k1])
            else:
                ref[k1] = v1
        for k2, v2 in ref.items():
            if k2 not in db:
                db[k2] = v2
        return db

    async def save(self):
        async with aiofiles.open(str(self.path.joinpath('content.json')),
                                 'w') as f:
            await f.write(json.dumps(self.content))
        async with aiofiles.open(str(self.path.joinpath('references.json')),
                                 'w') as f:
            await f.write(json.dumps(self.references))

    async def add_file(self, name, source, data, identity=None,
                       overwrite=False, date=None, content_type=None,
                       content_length=None, number=0, title=None, caption='',
                       low_res=False):
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
        if name in self.files and not overwrite:
            if new_file != self.files[name]:
                raise FileExistsError
        entry = {'name': name,
                 'title': title,
                 'caption': caption}
        if low_res:
            entry['lr'] = entry.pop('name')

        def do_pdf(what):
            if self.manifest.get(what) is not None:
                raise FileExistsError
            self.manifest[what] = entry

        def do_files(what):
            if self.manifest.get(what) is None:
                self.manifest[what] = []
            for f in self.manifest[what]:
                if f['title'] == entry['title']:
                    if low_res and 'lr' not in f:
                        f['lr'] = entry['lr']
                        return
                    elif not low_res and 'name' not in f:
                        f['name'] = entry['name']
                        return
                    else:
                        raise FileExistsError
            self.manifest[what].append(entry)

        def do_order(what):
            if self.manifest.get(what) is None:
                self.manifest[what] = []
            if number == 0:
                raise FileTypeError
            if number > len(self.manifest[what]):
                for i in range(number - len(self.manifest[what])):
                    self.manifest[what].append(None)
            if self.manifest[what][number - 1] is None or overwrite:
                self.manifest[what][number - 1] = entry
            elif (low_res and
                  self.manifest[what][number - 1].get('lr') is None):
                self.manifest[what][number - 1]['lr'] = entry['lr']
            elif (not low_res and
                  self.manifest[what][number - 1].get('name') is None):
                self.manifest[what][number - 1]['name'] = entry['name']
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
        await new_file.write()
        await self.update_manifest()

    def add_url(self, url):
        if self.url is None:
            self.url = []
        if url not in self.url:
            self.url.append(url)

    def meta_date(self):
        return self.manifest.get('metadate')

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
