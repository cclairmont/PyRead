import aiohttp
import asyncio
import aiofiles
from aiohttp import web
from yarl import URL
from pathlib import Path
import ssl
import certifi
from bs4 import BeautifulSoup

sslcontext = ssl.create_default_context(cafile=certifi.where())


class CacheProxy():

    FILE_EXTENSIONS = {'.js': 'text/javascript',
                       '.css': 'text/css',
                       '.html': 'text/html',
                       '.png': 'image/png',
                       '.jpg': 'image/jpeg',
                       '.svg': 'image/svg',
                       '.gif': 'image/gif',
                       '.woff2': 'application/x-font-woff2',
                       '.ico': 'image/x-icon'}

    def __init__(self, no_web=False):
        self.netloc = ''
        self.cookies = ''
        self.no_web = no_web

    async def create_session(self):
        self.session = aiohttp.ClientSession()

    async def request_cache(self, netloc, headers={}, process_remote=None):
        url = URL(netloc)
        path = Path('testing/cache', url.host, url.path[1:] +
                    '/'.join(f'{k}/{v}' for k, v in url.query.items()))
        print(path)
        if path.suffix not in self.FILE_EXTENSIONS:
            print(path.suffix)
            if (Path('tests/cache', url.host, url.path[1:]).suffix not in
                    self.FILE_EXTENSIONS):
                path = path.with_suffix('.html')
            else:
                print(Path('tests/cache', url.host, url.path[1:]).suffix)
                path = path.with_suffix(
                    Path('tests/cache', url.host, url.path[1:]).suffix)
        if path.exists():
            print(f'{netloc}: CACHE HIT')
            async with aiofiles.open(str(path), mode='rb') as f:
                body = await f.read()
        else:
            if self.no_web:
                raise web.HTTPNotFound
            print(f'{netloc}: CACHE MISS')
            path.parent.mkdir(parents=True, exist_ok=True)
            async with self.session.get(url, headers=headers,
                                        cookies=self.cookies,
                                        ssl=sslcontext,
                                        max_redirects=20) as response:
                if process_remote is not None:
                    body = await process_remote(response)
                else:
                    body = await response.content.read()
            async with aiofiles.open(str(path), mode='wb') as f:
                await f.write(body)
        return web.Response(body=body,
                            content_type=self.FILE_EXTENSIONS[path.suffix])

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

    async def proxy_url(self, request):
        url = request.query['url']
        headers = {'User-Agent': request.headers['User-Agent']}
        return await self.request_cache(url, headers=headers)

    async def proxy(self, request):
        headers = {'User-Agent': request.headers['User-Agent']}

        async def process_remote(response):
            body = await response.content.read()
            html = response.content_type.startswith('text/html')
            if html:
                soup = BeautifulSoup(body, 'lxml')
                for a in soup.find_all(['img', 'script', 'link']):
                    try:
                        if a['src'].startswith('http'):
                            a['src'] = ('http://localhost:9999/proxy?url=' +
                                        a['src'])
                    except KeyError:
                        pass
                for a in soup.find_all('a'):
                    try:
                        if a['href'].startswith('http'):
                            a['href'] = ('http://localhost:9999/pyreadproxy?'
                                         'location=' + a['href'])
                    except KeyError:
                        pass
                return str(soup).encode('utf-8')
            else:
                return body
        return await self.request_cache(self.netloc + str(request.rel_url),
                                        headers=headers,
                                        process_remote=process_remote)

    async def handler(self, request):
        path = request.rel_url.path
        if path.startswith('/pyreadproxy'):
            return await self.pyreadproxy(request)
        elif path.startswith('/proxy'):
            return await self.proxy_url(request)
        else:
            return await self.proxy(request)


async def main():
    proxy = CacheProxy(no_web=True)
    await proxy.create_session()
    server = web.Server(proxy.handler)
    runner = web.ServerRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 9999)
    await site.start()

    print("======= Serving on http://127.0.0.1:9999/ ======")

    await asyncio.sleep(100*3600)

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pass
