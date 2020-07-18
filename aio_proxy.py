__version__ = '0.2'

import asyncio
from aiohttp import web
import aiohttp
import aiofiles
from yarl import URL
import ssl
import certifi
import http
from aio_articleparser import Article, ArticleItem
import json
from pathlib import Path
from collections.abc import MutableMapping
import arsenic_hacks as arsenic
import time

# Workaround to use cookies with illegal keys with aiohttp
http.cookies._is_legal_key = lambda _: True

sslcontext = ssl.create_default_context(cafile=certifi.where())

CAPABILITIES = {
    'sciencedirect': 'sciencedirect.js'
}


class PyrCache(MutableMapping):

    def __init__(self, max_size, *args, **kwargs):
        content = {}.update(*args, **kwargs)
        self._max_size = max_size
        self._counter = 0
        if content is None:
            self.content = {}
        else:
            for k, v in content.items():
                self.content[k] = {'counter': self._counter, 'value': v}
                self.counter += 1

    def __getitem__(self, key):
        self._counter += 1
        self.content[key]['counter'] = self._counter
        return self.content[key]['value']

    def __setitem__(self, key, value):
        self._counter += 1
        if key not in self.content:
            self.content[key] = {}
        self.content[key]['counter'] = self._counter
        self.content[key]['value'] = value
        if len(self.content) > self._max_size:
            min_counter = -1
            to_delete = ''
            for k, v in self.content.items():
                if min_counter == -1 or v['counter'] < min_counter:
                    min_counter = v['counter']
                    to_delete = k
            del(self.content[to_delete])

    def __delitem__(self, key):
        del(self.content[key])

    def __iter__(self):
        return iter({k: v['value'] for k, v in self.content.items()})

    def __len__(self):
        return len(self.content)

    def __str__(self):
        return (f'<CACHE MAX_SIZE={self._max_size} ' +
                str({k: v['value'] for k, v in self.content.items()}) + '>')

    def __repr__(self):
        return str(self)


class AIOProxy:

    FILE_EXTENSIONS = {'.js': 'text/javascript',
                       '.css': 'text/css',
                       '.html': 'text/html',
                       '.png': 'image/png',
                       '.jpg': 'image/jpeg'}

    ARTICLE_CACHE_SIZE = 50
    ACTIVE_TIMEOUT = 10

    def __init__(self):
        self.netloc = ''
        self.cookies = ''
        self.cache = PyrCache(self.ARTICLE_CACHE_SIZE)
        self.active_tab = 0

    async def create_session(self):
        self.session = aiohttp.ClientSession()

    async def pyreadhome(self, request):
        async with aiofiles.open('assets/index.html', 'r') as f:
            return web.Response(text=await f.read(),
                                content_type='text/html')

    async def pyreadproxy(self, request):
        query = request.rel_url.query
        if 'location' not in query:
            raise web.HTTPBadRequest
        location = URL(query['location'])
        self.netloc = location.scheme + '://' + location.host
        if 'pyreadcookies' in query:
            qs = request.rel_url.query_string
            cookie_str = qs[qs.find('pyreadcookies=') + 14:]
            self.cookies = {}
            cookies = cookie_str.split('; ')
            for c in cookies:
                k, v = c.split('=', 1)
                self.cookies[k] = v
        raise web.HTTPFound(location.path)

    async def pyreadapi(self, request):
        if request.method == 'POST':
            data = await request.json()
        elif request.method == 'GET':
            data = request.query
        else:
            raise web.HTTPBadRequest
        doi = data.get('doi')
        type = data.get('type')
        if type == 'active':
            return web.Response(text=json.dumps((time.time() -
                                                 self.active_tab) <
                                                self.ACTIVE_TIMEOUT))
        if doi is None or type is None:
            raise web.HTTPBadRequest
        article = self.cache.get(doi)
        if article is None:
            article = Article(self.session, self.cookies)
            self.cache[doi] = article
        entry = await article.a_init(doi=doi)
        if type == 'info':
            status = await article.verify_integrity()
            if not hasattr(article, 'loading'):
                article.loading = False
            return web.Response(text=json.dumps({'loading': article.loading,
                                                 **entry, **status}),
                                content_type='application/json')
        if type == 'fileinfo':
            try:
                return web.Response(text=json.dumps(await article.file_info()),
                                    content_type='application/json')
            except FileNotFoundError:
                raise web.HTTPNotFound
        if type == 'file':
            name = data.get('name')
            if name is None:
                raise web.HTTPBadRequest
            ext = Path(name).suffix
            content_type = self.FILE_EXTENSIONS[ext]
            try:
                body = await article.get_file(name)
            except FileNotFoundError:
                raise web.HTTPNotFound
            return web.Response(body=body,
                                content_type=content_type)
        if type == 'content':
            await article.load()
            if not hasattr(article, 'content'):
                raise web.HTTPNotFound
            return web.Response(text=json.dumps(article.content),
                                content_type='application/json')

        if type == 'references':
            await article.load()
            if not hasattr(article, 'references'):
                raise web.HTTPNotFound
            return web.Response(text=json.dumps(article.references),
                                content_type='application/json')

    async def pyreadscrapi(self, request):
        data = await request.json()
        doi = data.get('doi')
        if doi is None:
            raise web.HTTPBadRequest
        article = self.cache.get(doi)
        if article is None:
            article = Article(self.session, self.cookies)
            self.cache[doi] = article
        entry = await article.a_init(doi=doi)
        if 'info' in data:
            status = await article.verify_integrity()
            if not hasattr(article, 'loading'):
                article.loading = False
            return web.Response(text=json.dumps({'loading': article.loading,
                                                 **entry, **status}),
                                content_type='application/json')
        if 'abstract' in data:
            article.add_content([{'title': 'Abstract',
                                  'content': data['abstract']}])
            await article.save()
            return web.Response(text=json.dumps({'item': 'abstract',
                                                 'status': 'success'}),
                                content_type='application/json')
        if 'figures' in data:
            for f in data['figures']:
                for res in ['lr', 'hr']:
                    if res not in f:
                        continue
                    if (f['title'].startswith('Figure S') or
                        f['title'].encode('utf-8').startswith(
                            b'Figure\xc2\xa0S')):
                        identity = ArticleItem.SUPPLEMENTARY_FIGURE
                        number = int(f['title'][8:f['title'].find('.')])
                    elif f['title'].startswith('Figure'):
                        identity = ArticleItem.FIGURE
                        number = int(f['title'][7:f['title'].find('.')])
                    else:
                        identity = ArticleItem.OTHER
                        number = 0
                    try:
                        await article.add_file(f[res], identity=identity,
                                               number=number, title=f['title'],
                                               caption=f.get('legend'),
                                               low_res=(res == 'lr'))
                    except FileExistsError:
                        pass
            return web.Response(text=json.dumps({'item': 'figures',
                                                 'status': 'success'}),
                                content_type='application/json')

        if 'main' in data:
            article.add_content(data['main'])
            await article.save()
            return web.Response(text=json.dumps({'item': 'main',
                                                 'status': 'success'}),
                                content_type='application/json')
        if 'references' in data:
            await asyncio.gather(*[article.add_reference(ref, num)
                                   for num, ref in
                                   enumerate(data['references'])])
            await article.save()
            return web.Response(text=json.dumps({'item': 'references',
                                                 'status': 'success'}),
                                content_type='application/json')

        if 'files' in data:
            for file, link in data['files'].items():
                if file == 'pdf':
                    identity = ArticleItem.PDF
                elif file == 'extended':
                    identity = ArticleItem.EXTENDED_PDF
                else:
                    identity = ArticleItem.OTHER
                try:
                    await article.add_file(link, identity=identity, title=file)
                except FileExistsError:
                    pass
            return web.Response(text=json.dumps({'item': 'files',
                                                 'status': 'success'}),
                                content_type='application/json')
        raise web.HTTPBadRequest

    async def proxy(self, request):
        headers = {'User-Agent': request.headers['User-Agent']}
        async with self.session.get(self.netloc + str(request.rel_url),
                                    headers=headers,
                                    cookies=self.cookies,
                                    ssl=sslcontext,
                                    max_redirects=20) as response:
            body = await response.content.read()
            if response.content_type == 'text/html':
                scraper = None
                for c in CAPABILITIES:
                    if self.netloc.find(c) != -1:
                        scraper = CAPABILITIES[c].encode('utf-8')
                head_end = body.find(b'</head>')
                if head_end != -1:
                    if scraper is not None:
                        scraper_str = b'<script type="text/javascript"'\
                                      b' src="/pyreadasset?file=scrapers/' +\
                                      scraper + b'"></script>'
                    else:
                        scraper_str = b''
                    body = body[:head_end] + scraper_str +\
                        b'<script type="text/javascript"'\
                        b' src="/pyreadasset?file=pyreadscrape.js"></script>'\
                        + body[head_end:]
            return web.Response(body=body,
                                status=response.status,
                                content_type=response.content_type,
                                charset=response.charset)

    async def pyreadasset(self, request):
        query = request.rel_url.query
        if 'file' not in query:
            raise web.HTTPBadRequest
        else:
            suffix = Path(query['file']).suffix
            content_type = self.FILE_EXTENSIONS.get(suffix)
            try:
                async with aiofiles.open('assets/' + query['file'], 'rb') as f:
                    body = await f.read()
                    return web.Response(body=body, content_type=content_type)
            except FileNotFoundError:
                raise web.HTTPNotFound

    async def pyreadresolve(self, request):
        TIMEOUT = 20
        doi = request.query.get('doi')
        if doi is None:
            raise web.HTTPBadRequest
        service = arsenic.PyrGeckodriver(
            binary='C:\\webdrivers\\geckodriver.exe')
        browser = arsenic.PyrFirefox(**{'moz:firefoxOptions':
                                     {'args': ['-headless']}})
        found = False
        retry_num = 0
        async with arsenic.pyr_get_session(service, browser) as session:
            await session.get('https://dx.doi.org/' + doi)
            while not found and retry_num < TIMEOUT:
                current_url = await session.get_url()
                print(current_url)
                for c in CAPABILITIES:
                    if current_url.find(c) != -1:
                        found = True
                        break
                if found:
                    break
                retry_num += 1
                await asyncio.sleep(0.5)
        if found:
            return web.Response(text=json.dumps({'url': current_url}),
                                content_type='application/json')
        raise web.HTTPNotFound

    async def pyreadredirect(self, request):
        doi = request.query.get('doi')
        if doi is None:
            raise web.HTTPNotFound
        article = self.cache.get(doi)
        if article is None:
            article = Article(self.session, self.cookies)
            self.cache[doi] = article
        entry = await article.a_init(doi=doi)
        page = (b'<!DOCTYPE html>'
                b'<html>'
                b'<head>'
                b'<link rel="stylesheet" '
                b'href="/pyreadasset?file=pyreadredirect.css">'
                b'<script type="text/javascript" '
                b'src="/pyreadasset?file=pyreadredirect.js"></script>'
                b'<meta charset="UTF-8">'
                b'</head>'
                b'<body>'
                b'<div class="view-box">'
                b'<div class="pyread-msg"></div>'
                b'<div class="article-title">' +
                entry['title'].encode('utf-8') +
                b'</div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-btn">PyRead</div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-msg"></div>'
                b'<a class="article-link" href="https://dx.doi.org/' +
                doi.encode('utf-8') +
                b'">Go to Article</a>'
                b'</div>'
                b'</body>'
                b'</html>')
        return web.Response(body=page, content_type='text/html')

    async def pyreadstatus(self, request):
        print(request.query)
        doi = request.query.get('doi')
        loading = request.query.get('loading')
        if doi is None:
            self.active_tab = time.time()
            return web.Response(text='')
        if loading is not None:
            print(loading)
            article = self.cache.get(doi)
            if article is None:
                article = Article(self.session, self.cookies)
                self.cache[doi] = article
            await article.a_init(doi=doi)
            if loading == 'true':
                article.loading = True
            elif loading == 'false':
                article.loading = False
            else:
                raise web.HTTPBadRequest
        else:
            if not hasattr(article, 'loading'):
                article.loading = False
        return web.Response(text=json.dumps({'loading': article.loading}),
                            content_type='application/json')

    async def handler(self, request):
        path = request.rel_url.path
        if path.startswith('/pyreadproxy'):
            return await self.pyreadproxy(request)
        elif path.startswith('/pyreadscrapi'):
            return await self.pyreadscrapi(request)
        elif path.startswith('/pyreadasset'):
            return await self.pyreadasset(request)
        elif path.startswith('/pyreadredirect'):
            return await self.pyreadredirect(request)
        elif path.startswith('/pyreadapi'):
            return await self.pyreadapi(request)
        elif path.startswith('/pyreadhome'):
            return await self.pyreadhome(request)
        elif path.startswith('/pyreadresolve'):
            return await self.pyreadresolve(request)
        elif path.startswith('/pyreadstatus'):
            return await self.pyreadstatus(request)
        else:
            return await self.proxy(request)


async def main():
    proxy = AIOProxy()
    await proxy.create_session()
    server = web.Server(proxy.handler)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    print("======= Serving on http://127.0.0.1:8080/ ======")

    await asyncio.sleep(100*3600)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
