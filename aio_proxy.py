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

# Workaround to use cookies with illegal keys with aiohttp
http.cookies._is_legal_key = lambda _: True

sslcontext = ssl.create_default_context(cafile=certifi.where())


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
        return self.content[key].value

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

    def __init__(self):
        self.netloc = ''
        self.cookies = ''
        self.cache = PyrCache(self.ARTICLE_CACHE_SIZE)

    async def create_session(self):
        self.session = aiohttp.ClientSession()

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
        data = await request.json()
        doi = data.get('doi')
        type = data.get('type')
        if doi is None or type is None:
            raise web.HTTPBadRequest
        article = self.cache.get('doi')
        if article is None:
            article = Article(self.session, self.cookies)
            article.a_init(doi=doi)
            self.cache[doi] = article

    async def pyreadscrapi(self, request):
        data = await request.json()
        if 'doi' in data or 'pmid' in data or 'title' in data:
            self.article = Article(self.session, self.cookies)
            result = await self.article.a_init(doi=data.get('doi'),
                                               pmid=data.get('pmid'),
                                               title=data.get('title'))
            self.metadata = result
            self.cache[result['doi']] = self.article
            print(self.cache)
            return web.Response(text=json.dumps(result))
        elif 'abstract' in data:
            if hasattr(self.article, 'content'):
                self.article.content.append({'title': 'Abstract',
                                             'content': data['abstract']})
            else:
                self.article.content = [{'title': 'Abstract',
                                         'content': data['abstract']}]
            return web.Response(text=json.dumps({'item': 'abstract',
                                                 'status': 'success'}))
        elif 'figures' in data:
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
                        await self.article.add_file(f[res], identity=identity,
                                                    number=number,
                                                    title=f['title'],
                                                    caption=f.get('legend'),
                                                    low_res=(res == 'lr'))
                    except FileExistsError:
                        pass
            return web.Response(text=json.dumps({'item': 'figures',
                                                 'status': 'success'}))

        elif 'main' in data:
            if hasattr(self.article, 'content'):
                self.article.content = [*self.article.content, *data['main']]
            else:
                self.article.content = data['main']
            await self.article.save()
            return web.Response(text=json.dumps({'item': 'main',
                                                 'status': 'success'}))
        elif 'references' in data:
            await asyncio.gather(*[self.article.add_reference(ref)
                                   for ref in data['references']])
            await self.article.save()
            return web.Response(text=json.dumps({'item': 'references',
                                                 'status': 'success'}))

        elif 'files' in data:
            for file, link in data['files'].items():
                if file == 'pdf':
                    identity = ArticleItem.PDF
                elif file == 'extended':
                    identity = ArticleItem.EXTENDED_PDF
                else:
                    identity = ArticleItem.OTHER
                try:
                    await self.article.add_file(link, identity=identity,
                                                title=file)
                except FileExistsError:
                    pass
            return web.Response(text=json.dumps({'item': 'files',
                                                 'status': 'success'}))
        else:
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
                head_end = body.find(b'</head>')
                if head_end != -1:
                    body = body[:head_end] +\
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

    async def pyreadredirect(self, request):
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
                self.metadata['title'].encode('utf-8') +
                b'</div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-btn">PyRead</div>'
                b'<div class="pyread-msg"></div>'
                b'<div class="pyread-msg"></div>'
                b'<a class="article-link" href="https://dx.doi.org/' +
                self.metadata['doi'].encode('utf-8') +
                b'">Go to Article</a>'
                b'</div>'
                b'</body>'
                b'</html>')
        return web.Response(body=page, content_type='text/html')

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
