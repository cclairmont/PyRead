from datetime import datetime
from pathlib import Path
import json
import hashlib
import enum
from bs4 import BeautifulSoup
import ssl
import certifi
import aiofiles
from difflib import SequenceMatcher
from yarl import URL
import asyncio
import re
import urllib
import aiosqlite

sslcontext = ssl.create_default_context(cafile=certifi.where())


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
                    'pdf': FileType.PDF,
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

    DATABASE = 'files/pyread.db'

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
        self.name = entry.get('name')
        self.source = entry.get('source')
        self.date = datetime.fromisoformat(entry.get('date'))
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

    async def fetch(self, session, cookies=None, source=0):
        self.reset()
        async with session.get(self.source[source], cookies=cookies,
                               ssl=sslcontext) as response:
            self.data = await response.read()
            content_disp = response.headers.get('Content-Disposition')
            content_type = response.headers.get('Content-Type')
        if content_disp is not None:
            fname = content_disp.find('filename=')
            if fname != -1:
                self.name = content_disp[fname + 9:]
        else:
            self.name = URL(self.source[source]).name
        self.path = self.dir.joinpath(self.name)
        ext = self.path.suffix[1:]
        inferred_type = KNOWN_EXTENSIONS.get(ext)
        if inferred_type is not None:
            self.ftype = inferred_type
        else:
            if content_type is not None:
                content_type = content_type[content_type.find("/") + 1:
                                            content_type.find(";")]
                self.ftype = KNOWN_EXTENSIONS.get(content_type)
            if self.ftype is None:
                self.ftype = FileType.UNKNOWN


class Article:

    HEADERS = {'User-Agent':
               'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:77.0) '
               'Gecko/20100101 Firefox/77.0'}

    DB_LOCATION = 'files/pyread.db'

    DB_COLS = {'doi': 'varchar(255)',
               'pmid': 'int',
               'title': 'text',
               'authors': 'text',
               'journal': 'varchar(255)',
               'date': 'char(19)',
               'local': 'char'}

    def __init__(self, session, cookies):
        self._ainit_done = False
        self._ainit_start = False
        self.session = session
        self.cookies = cookies

    async def a_init(self, doi=None, pmid=None, title=None):
        if self._ainit_done:
            await self.check_local()
            self.entry['local'] = self.manifest['local']
            return self.entry
        if self._ainit_start:
            await asyncio.sleep(1)
            return await self.a_init(doi, pmid, title)
        self._ainit_start = True
        entry = await self.fetch_metadata(doi, pmid, title)
        if entry['doi'] is not None:
            self.path = Path('files', doi)
        elif entry['pmid'] is not None:
            self.path = Path('files/pmid', pmid)
        else:
            raise ArticleError('Could not identify article')
        if not self.path.exists():
            self.path.mkdir(parents=True)
        manifest_path = self.path.joinpath('manifest.json')
        if manifest_path.exists():
            async with aiofiles.open(str(manifest_path),
                                     'r', encoding='utf-8') as m:
                self.manifest = json.loads(await m.read())
        else:
            self.manifest = {}
        self.files = {}
        if 'files' in self.manifest:
            for k, v in self.manifest['files'].items():
                self.files[k] = ArticleFile(self.path, manifest=v)
        else:
            self.manifest['files'] = {}
        await asyncio.gather(self.check_local(), self.update_manifest())
        entry['local'] = self.manifest['local']
        self.entry = entry
        self._ainit_done = True
        return entry

    async def _fetch_from_pubmed(self, doi=None, pmid=None, title=None):
        result = {'doi': None, 'pmid': None, 'title': None, 'authors': None,
                  'journal': None, 'date': None}
        if pmid is None:
            url = URL('https://pubmed.ncbi.nlm.nih.gov/')
            if doi is not None:
                query = doi
            elif title is not None:
                query = title
            else:
                return result
            encoded_query = 'term=' + urllib.parse.quote(f'"{query}"')
            url._val = urllib.parse.SplitResult(url._val.scheme,
                                                url._val.netloc,
                                                url._val.path,
                                                encoded_query,
                                                url._val.fragment)
        else:
            url = URL('https://pubmed.ncbi.nlm.nih.gov/' + pmid)
        retry = True
        while retry:
            async with self.session.get(url, ssl=sslcontext) as response:
                if response.status == 200:
                    retry = False
                    soup = BeautifulSoup(await response.read(), 'lxml')
                else:
                    print(response.status)
        d_soup = soup.find('span', {'class': 'doi'})
        if d_soup is None:
            if title is None:
                return result
            # This means there was more than one search result,
            # so we compare the titles of all of the search results
            # to our title and pick the closest one that is more
            # than 90% similar
            d_soup = soup.find_all('a', {'class': 'labs-docsum-title'})
            max_score = 0
            max_link = ''
            for d in d_soup:
                try:
                    score = SequenceMatcher(None, title,
                                            d.text.strip()).ratio()
                except AttributeError:
                    return result
                if score > max_score:
                    max_score = score
                    max_link = d['href']
            if max_score > 0.9:
                async with self.session.get('https://pubmed.ncbi.nlm.nih.gov' +
                                            max_link,
                                            ssl=sslcontext) as response:
                    soup = BeautifulSoup(await response.read(),
                                         'lxml')
                d_soup = soup.find('span', {'class': 'doi'})
            else:
                return result
        try:
            result['doi'] = d_soup.find('a').text.strip()
        except AttributeError:
            return result
        if doi is not None:
            assert doi.lower() == result['doi'].lower()
        result['pmid'] = soup.find('strong',
                                   {'class': 'current-id'}).text.strip()
        if pmid is not None:
            assert pmid == result['pmid']
        cite = soup.find('span', {'class': 'cit'}).text
        date = cite[:cite.find(';')]
        result['date'] = self._parse_date(date).isoformat()
        a_list = soup.find('div', {'class': 'authors-list'})
        if a_list is not None:
            authors = a_list.find_all('a', {'class': 'full-name'})
        else:
            authors = []
        result['authors'] = []
        for a in authors:
            result['authors'].append(a.text.strip())
        result['title'] = soup.find('h1',
                                    {'class': 'heading-title'}).text.strip()
        result['journal'] = soup.find(
            'button', {'id': 'full-view-journal-trigger'})['title'].strip()
        return result

    async def _fetch_from_crossref(self, doi):
        result = {'title': None, 'authors': None, 'journal': None,
                  'date': None}
        headers = {**self.HEADERS,
                   'Accept': 'application/vnd.crossref.unixsd+xml'}
        url = 'http://dx.doi.org/' + doi
        async with self.session.get(url, headers=headers,
                                    cookies=self.cookies,
                                    ssl=sslcontext) as response:
            s = BeautifulSoup(await response.read(), 'xml')
        try:
            result['title'] = self._sanitize(s.title.text)
            result['journal'] = s.journal_metadata.full_title.text
            for i in s.find_all('crm-item'):
                if i['name'] == 'created':
                    date = datetime.fromisoformat(i.text[:-1])
                    result['date'] = date.isoformat()
            result['authors'] = []
            for a in s.find_all('person_name'):
                if a['contributor_role'] == 'author':
                    name = a.given_name.text + ' ' + a.surname.text
                    result['authors'].append(name)
        except AttributeError:
            pass
        return result

    def _parse_date(self, date):
        months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG',
                  'SEP', 'OCT', 'NOV', 'DEC']
        long_months = ['JANUARY', 'FEBRUARY', 'MARCH', 'APRIL', 'MAY', 'JUNE',
                       'JULY', 'AUGUST', 'SEPTEMBER', 'OCTOBER', 'NOVEMBER',
                       'DECEMBER']
        try:
            return datetime.strptime(date, '%Y %b %d')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%Y %B %d')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%b %Y')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%B %Y')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%Y %b')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%Y %B')
        except ValueError:
            pass
        try:
            return datetime.strptime(date, '%Y')
        except ValueError:
            pass
        datestring = ''
        pstring = ''
        match = re.search(r'(\d+)?(.*)?(\d\d\d\d)', date)
        if match[1] is not None and match[1] != '':
            datestring += match[1]
            pstring += '%d'
        if match[2] is not None and match[2] != '':
            first_match_pos = -1
            month = ''
            for m in months:
                match_pos = datestring.find(m)
                if first_match_pos == -1 or match_pos < first_match_pos:
                    month = m
                    first_match_pos = match_pos
            if month != '':
                datestring += month
                pstring += '%b'
            else:
                first_match_pos = -1
                month = ''
                for m in long_months:
                    match_pos = datestring.find(m)
                    if first_match_pos == -1 or match_pos < first_match_pos:
                        month = m
                        first_match_pos = match_pos
                    if month != '':
                        datestring += month
                        pstring += '%B'
        if match[3] is not None and match[3] != '':
            datestring += match[3]
            pstring += '%Y'
        return datetime.strptime(datestring, pstring)

    def _sanitize(self, s):
        s = re.sub(r'\\n', '', s)
        return ' '.join(s.split())

    async def fetch_metadata(self, doi=None, pmid=None, title=None):
        async with aiosqlite.connect(self.DB_LOCATION) as db_conn:
            async with db_conn.cursor() as db:
                await db.execute('CREATE TABLE IF NOT EXISTS ref_database (' +
                                 ','.join([' '.join([k, v])
                                           for k, v in self.DB_COLS.items()]) +
                                 ')')
        entry, key = await self._from_db({'doi': doi, 'pmid': pmid})
        if entry is not None and entry != {}:
            return entry
        entry = await self._fetch_from_pubmed(doi=doi, pmid=pmid, title=title)
        if entry.get('doi') is None:
            entry['doi'] = doi
        if entry.get('pmid') is None:
            entry['pmid'] = pmid
        if entry.get('title') is None:
            entry['title'] = title
        pubmed_success = False
        for v in entry.values():
            if v is None:
                pubmed_success = False
        if not pubmed_success and entry['doi'] is not None:
            result = await self._fetch_from_crossref(entry['doi'])
            for k, v in entry.items():
                if v is None or v == []:
                    entry[k] = result.get(k)
        await self._add_to_db(entry)
        return entry

    def add_content(self, content, overwrite=True):
        if not hasattr(self, 'content'):
            self.content = []
        for c in content:
            exists = False
            for i, cc in enumerate(self.content):
                if cc['title'] == c['title']:
                    if overwrite:
                        self.content[i] = c
                    exists = True
                    break
            if not exists:
                self.content.append(c)

    async def add_reference(self, ref, num):
        if ref is None:
            entry = None
        else:
            entry = await Article(self.session,
                                  self.cookies).fetch_metadata(
                                                   doi=ref.get('doi'),
                                                   pmid=ref.get('pmid'),
                                                   title=ref.get('title'))
        print(f"REF {num}: {json.dumps(entry).encode('utf-8')}")
        if not hasattr(self, 'references'):
            self.references = []
        if num >= len(self.references):
            for i in range(num - len(self.references) + 1):
                self.references.append(None)
        self.references[num] = entry

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
        self.manifest['title'] = self._sanitize(title)
        self.manifest['journal'] = journal
        self.manifest['date'] = date.isoformat()
        self.manifest['authors'] = authors
        self.manifest['metadate'] = datetime.now().isoformat()

    async def update_manifest(self):
        manifest_path = self.path.joinpath('manifest.json')
        async with aiofiles.open(str(manifest_path), 'w',
                                 encoding='utf-8') as m:
            await m.write(json.dumps(self.manifest))

    async def save(self):
        async with aiofiles.open(str(self.path.joinpath('content.json')),
                                 'w') as f:
            await f.write(json.dumps(self.content))
        if hasattr(self, 'references'):
            async with aiofiles.open(str(self.path.joinpath(
                                             'references.json')), 'w') as f:
                await f.write(json.dumps(self.references))
        await self.check_local()

    async def load(self):
        if self.path.joinpath('content.json').exists():
            async with aiofiles.open(str(self.path.joinpath('content.json')),
                                     'r') as f:
                self.content = json.loads(await f.read())
        if self.path.joinpath('references.json').exists():
            async with aiofiles.open(str(self.path.joinpath(
                                              'references.json')), 'r') as f:
                self.references = json.loads(await f.read())

    async def add_file(self, source, name=None, data=None, identity=None,
                       overwrite=False, date=None, content_type=None,
                       content_length=None, number=0, title=None, caption='',
                       low_res=False):
        if self.files is None:
            self.files = {}
        if date is None:
            date = datetime.now().isoformat()
        new_file = ArticleFile(data=data, path=self.path,
                               manifest={'name': name,
                                         'source': [source],
                                         'date': date,
                                         'content_type': content_type,
                                         'content_length': content_length})
        if data is None:
            await new_file.fetch(self.session, self.cookies)
            data = new_file.data
            name = new_file.name
        if content_length is None:
            content_length = len(data)
        if name in self.files and not overwrite:
            if new_file != self.files[name]:
                raise FileExistsError
        entry = {'name': name,
                 'title': title,
                 'caption': caption}
        if low_res:
            entry['lr'] = entry.pop('name')

        def do_pdf(what):
            if fig_leg.get(what) is not None:
                raise FileExistsError
            fig_leg[what] = entry

        def do_files(what):
            if fig_leg.get(what) is None:
                fig_leg[what] = []
            for f in fig_leg[what]:
                if f['title'] == entry['title']:
                    if low_res and 'lr' not in f:
                        f['lr'] = entry['lr']
                        return
                    elif not low_res and 'name' not in f:
                        f['name'] = entry['name']
                        return
                    else:
                        raise FileExistsError
            fig_leg[what].append(entry)

        def do_order(what):
            if fig_leg.get(what) is None:
                fig_leg[what] = []
            if number == 0:
                raise FileTypeError
            if number > len(fig_leg[what]):
                for i in range(number - len(fig_leg[what])):
                    fig_leg[what].append(None)
            if fig_leg[what][number - 1] is None or overwrite:
                fig_leg[what][number - 1] = entry
            elif (low_res and fig_leg[what][number - 1].get('lr') is None):
                fig_leg[what][number - 1]['lr'] = entry['lr']
            elif (not low_res and fig_leg[what][number - 1].
                    get('name') is None):
                fig_leg[what][number - 1]['name'] = entry['name']
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
        if Path(self.path, 'figures.json').exists():
            with Path(self.path, 'figures.json').open(mode='r') as f:
                fig_leg = json.loads(f.read())
        else:
            fig_leg = {}
        identity_lookup[identity]()
        self.files[name] = new_file
        self.manifest['files'][name] = new_file.to_manifest()
        with Path(self.path, 'figures.json').open(mode='w') as f:
            f.write(json.dumps(fig_leg))
        await asyncio.gather(self.check_local(), new_file.write(),
                             self.update_manifest())

    def add_url(self, url):
        if self.url is None:
            self.url = []
        if url not in self.url:
            self.url.append(url)

    def meta_date(self):
        return self.manifest.get('metadate')

    async def _from_db(self, entry):
        result = None
        async with aiosqlite.connect(self.DB_LOCATION) as db_conn:
            async with db_conn.cursor() as db:
                if entry.get('doi') is not None:
                    await db.execute('SELECT * FROM ref_database '
                                     'WHERE doi=?;', (entry['doi'],))
                    key = 'doi'
                    result = await db.fetchone()
                if result is None and entry.get('pmid') is not None:
                    await db.execute('SELECT * FROM ref_database '
                                     'WHERE pmid=?;', (entry['pmid'],))
                    key = 'pmid'
                    result = await db.fetchone()
                if result is None:
                    key = None
            new_entry = {}
            if result is not None:
                for k, e in zip(self.DB_COLS.keys(), result):
                    if k == 'pmid':
                        if e is not None:
                            e = str(e)
                    elif k == 'local':
                        e = e == 'T'
                    elif k == 'authors':
                        e = json.loads(e)
                    new_entry[k] = e
            return new_entry, key

    async def _add_to_db(self, entry):
        new_entry = {**entry}
        if entry.get('pmid') is not None:
            new_entry['pmid'] = int(entry['pmid'])
        if entry.get('local') is True:
            new_entry['local'] = 'T'
        else:
            new_entry['local'] = 'F'
        if entry.get('authors') is not None:
            new_entry['authors'] = json.dumps(entry['authors'])
        async with aiosqlite.connect(self.DB_LOCATION) as db_conn:
            async with db_conn.cursor() as db:
                await db.execute('INSERT INTO ref_database VALUES (' +
                                 ','.join(["?"]*len(self.DB_COLS)) + ')',
                                 tuple(new_entry.get(k) for k in
                                       self.DB_COLS.keys()))
            await db_conn.commit()

    async def _update_db(self, entry, key='doi'):
        new_entry = {**entry}
        if entry.get('pmid') is not None:
            new_entry['pmid'] = int(entry['pmid'])
        if entry.get('local') is True:
            new_entry['local'] = 'T'
        else:
            new_entry['local'] = 'F'
        if entry.get('authors') is not None:
            new_entry['authors'] = json.dumps(entry['authors'])
        async with aiosqlite.connect(self.DB_LOCATION) as db_conn:
            async with db_conn.cursor() as db:
                await db.execute('UPDATE ref_database SET ' +
                                 ','.join([k + ' = ?' for k in
                                           self.DB_COLS.keys()]) +
                                 f'WHERE {key}=?',
                                 tuple(new_entry.get(k) for k
                                       in self.DB_COLS.keys()) + (entry[key],))

    async def update_meta_db(self, entry, overwrite=False):
        result, key = await self._from_db(entry)
        if not overwrite:
            for k, v in result.items():
                if entry.get(k) is not None:
                    if k != 'local':
                        assert(entry[k] == v)

        if key is None:
            await self._add_to_db(entry)
        else:
            await self._update_db(entry, key=key)

    async def check_local(self):
        result = await self.verify_integrity()
        is_local = True
        for v in result.values():
            is_local = is_local and v
        self.manifest['local'] = is_local
        await asyncio.gather(self.update_meta_db(
                                 {'title': self.manifest.get('title'),
                                  'doi': self.manifest.get('doi'),
                                  'pmid': self.manifest.get('pmid'),
                                  'local': is_local}),
                             self.update_manifest())

    async def verify_integrity(self):
        result = {'abstract': False,
                  'content': False,
                  'figures': False,
                  'references': False}
        await self.load()
        if hasattr(self, 'content'):
            for item in self.content:
                if item['title'] == 'Abstract':
                    identity = 'abstract'
                else:
                    identity = 'content'
                if (item['content'] is not None and len(item['content']) > 0):
                    result[identity] = True
        if Path(self.path, 'figures.json').exists():
            result['figures'] = True
            async with aiofiles.open(str(Path(self.path, 'figures.json')),
                                     'r') as f:
                figures = json.loads(await f.read())
                for k, v in figures.items():
                    if isinstance(v, list):
                        for f in v:
                            for res in ['name', 'lr']:
                                if res in f:
                                    result['figures'] = (result['figures'] and
                                                         Path(self.path,
                                                              f[res]).exists())
                    else:
                        result['figures'] = (result['figures'] and
                                             Path(self.path,
                                                  v['name']).exists())
        if Path(self.path, 'references.json').exists():
            async with aiofiles.open(str(Path(self.path, 'references.json')),
                                     'r') as f:
                refs = json.loads(await f.read())
                if len(refs) > 0:
                    result['references'] = True
        return result

    async def file_info(self):
        async with aiofiles.open(Path(self.path, 'figures.json'), 'r') as f:
            return json.loads(await f.read())

    async def get_file(self, name):
        file = self.files[name]
        if file.data is None:
            return await file.get_data()
        return file.data
