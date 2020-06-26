__version__ = '0.2'

import asyncio
from aiohttp import web
import aiohttp
import aiofiles
from yarl import URL
import ssl
import certifi
import http
from aio_articleparser import Article
import json

# Workaround to use cookies with illegal keys with aiohttp
http.cookies._is_legal_key = lambda _: True

sslcontext = ssl.create_default_context(cafile=certifi.where())


class AIOProxy:

    def __init__(self):
        self.netloc = ''
        self.cookies = ''

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

    async def pyreadscrapi(self, request):
        data = await request.json()
        if 'doi' in data or 'pmid' in data or 'title' in data:
            self.article = Article()
            result = await self.article.fetch_metadata(doi=data.get('doi'),
                                                       pmid=data.get('pmid'),
                                                       title=data.get('title'))
            return web.Response(text=json.dumps(result))

    async def proxy(self, request):
        headers = {'User-Agent': request.headers['User-Agent']}
        async with self.session.get(self.netloc + str(request.rel_url),
                                    headers=headers,
                                    cookies=self.cookies,
                                    ssl=sslcontext,
                                    max_redirects=20) as response:
            body = await response.content.read()
            head_start = body.find(b'<head>') + 6
            body = body[:head_start] +\
                b'<script type="text/javascript"'\
                b' src="/pyreadasset?file=pyreadscrape.js"></script>' +\
                body[head_start:]
            return web.Response(body=body,
                                status=response.status,
                                content_type=response.content_type,
                                charset=response.charset)

    async def pyreadasset(self, request):
        query = request.rel_url.query
        if 'file' not in query:
            raise web.HTTPBadRequest
        else:
            try:
                async with aiofiles.open('assets/' + query['file'], 'r') as f:
                    body = await f.read()
                    return web.Response(body=body, status=200)
            except FileNotFoundError:
                raise web.HTTPNotFound

    async def handler(self, request):
        path = request.rel_url.path
        if path.startswith('/pyreadproxy'):
            return await self.pyreadproxy(request)
        elif path.startswith('/pyreadscrapi'):
            return await self.pyreadscrapi(request)
        elif path.startswith('/pyreadasset'):
            return await self.pyreadasset(request)
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
