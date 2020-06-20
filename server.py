__version__ = '0.1'

import http.server
import http.cookies
from http import HTTPStatus
import ast
import requests
import pickle
import json
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
import pyread


class PyRead(http.server.BaseHTTPRequestHandler):

    server_version = "PyRead/" + __version__

    def __init__(self, *args, debug=False, domain='localhost', port=8000,
                 **kwargs):
        self.debug = debug
        self.domain = domain
        self.port = port
        self.session = requests.Session()
        try:
            with open('links.json', 'r') as f:
                self.url_dict = ast.literal_eval(f.read())
        except FileNotFoundError:
            self.url_dict = {}
        super().__init__(*args, **kwargs)

    def fetch(self, url, headers={}, cache=True):
        try:
            with open('cookies.pik', 'rb') as cfile:
                self.session.cookies.update(pickle.load(cfile))
        except FileNotFoundError:
            pass
        self.session.headers = headers
        if not url.startswith('http'):
            with open('proxy_url.txt', 'r') as u:
                url = u.read() + url
        status, content, name = self.request_cache('GET', url, cache)
        return status, content, name

    def inject_content(self, elem_type, content):
        message = {'elem_type': elem_type,
                   'content': content}
        with open('message.json', 'w') as f:
            f.write(json.dumps(message))

    def update_status(self, status):
        # Status should be a list of dicts: [{'caption': str,
        #                                     'messages': [str,...],
        #                                     'status': 'not started' |
        #                                               'working' |
        #                                               'success' |
        #                                               'fail'},...}]
        with open('status.json', 'w') as s:
            s.write(json.dumps(status))

    def inject_script(self, content):
        head_start = content.find(b'<head>') + 6
        content = b''.join([content[:head_start],
                            b'\n      <script type="text/javascript" src="/',
                            b'pyreadasset=pyreadproxy.js"></script>',
                            content[head_start:]])
        return content

    def scrape(self, data):
        doi = pyread.scrape(data, self.inject_content, self.fetch,
                            self.update_status)
        self.send_response(HTTPStatus.OK)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        if doi is None:
            self.wfile.write(b'{"doi": "none"}')
        else:
            self.wfile.write(b''.join([b'{"doi": "',
                                       doi.encode('utf-8'),
                                       b'"}']))

    def request_cache(self, request_type, url, cache=True, data=None):
        parsed_url = urllib.parse.urlparse(url)
        netloc = parsed_url.netloc
        path = parsed_url.path
        cache_path = Path.cwd().joinpath('cache', netloc, path[1:])
        fname = cache_path.name.split('&')[-1].split('=')[-1]
        cache_path = cache_path.with_name(fname)
        for parent in cache_path.parents:
            if parent.is_file():
                parent.rename(parent.with_suffix('.cache'))
                break
        if cache_path.is_dir():
            cache_path = cache_path.with_suffix('.cache')
        alias_path = cache_path.with_name('.alias')
        if alias_path.exists():
            with alias_path.open(mode='r') as a:
                alias = json.loads(a.read())
        else:
            alias = {}
        if url in alias:
            cache_path = cache_path.with_name(alias[url])
        if cache and cache_path.exists():
            with cache_path.open(mode='rb') as f:
                content = f.read()
            return HTTPStatus.OK, content, cache_path.name
        else:
            if request_type == 'GET':
                response = self.session.get(url, timeout=10)
            elif request_type == 'POST':
                response = self.session.post(url, data=data, timeout=10)
            content_disp = response.headers.get('Content-Disposition')
            if content_disp is not None:
                fname = content_disp.find('filename=')
                if fname != -1:
                    fname = content_disp[fname + 9:]
                    alias[url] = fname
                    cache_path = cache_path.with_name(fname)
            if cache and response.status_code == HTTPStatus.OK:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with alias_path.open(mode='w') as a:
                    a.write(json.dumps(alias))
                with cache_path.open(mode='wb') as f:
                    f.write(response.content)
            return (HTTPStatus(response.status_code), response.content,
                    cache_path.name)

    def proxy_form(self, response):
        soup = BeautifulSoup(response.content, 'lxml')
        for f in soup.find_all('form'):
            action = f.get('action')
            if action is not None:
                if f['action'].startswith('http'):
                    f['action'] = '/?pyreadproxyurl=' + f['action']
        return

    def proxy_links(self, response):
        soup = BeautifulSoup(response.content, 'lxml')
        for f in soup.find_all('a'):
            action = f.get('href')
            if action is not None:
                if f['href'].startswith('http'):
                    f['href'] = '?pyreadproxyurl=' + f['href']
                    # print(f['href'])

        return soup.encode('utf-8')

    def proxy(self, request_type, data=None):
        self.session.headers = self.headers
        cookie = http.cookies.SimpleCookie(self.headers.get('Cookie'))
        self.session.cookies.update(cookie)
        try:
            with open('cookies.pik', 'rb') as cfile:
                self.session.cookies.update(pickle.load(cfile))
        except FileNotFoundError:
            pass
        if self.path.startswith('/?pyreadproxyurl='):
            main_page = True
            cookies = self.path.find('&pyreadcookies=')
            url = self.path[17:cookies]
            parsed_url = urllib.parse.urlparse(url)
            base_url = parsed_url.scheme + '://' + parsed_url.netloc
            cookies = urllib.parse.unquote(self.path[cookies+15:]).split('; ')
            domain = '.' + '.'.join(parsed_url.netloc.split('.')[-2:])
            for c in cookies:
                name, val = c.split('=', 1)
                self.session.cookies.set(name, val, domain=domain)
            with open('proxy_url.txt', 'w') as u:
                u.write(base_url)
            path = url
        else:
            main_page = False
            with open('proxy_url.txt', 'r') as u:
                base_url = u.read()
            if not self.path.startswith('/http'):
                path = base_url + self.path
            else:
                path = self.path
        status, content, name = self.request_cache(request_type, path, data)
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        if main_page:
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            content = self.inject_script(content)
        self.end_headers()
        with open('cookies.pik', 'wb') as cfile:
            pickle.dump(self.session.cookies, cfile)
        self.wfile.write(content)

    def do_GET(self):
        if self.path.startswith('/pyreadasset='):
            path = Path.cwd().joinpath('assets', self.path[13:])
            if path.exists():
                with path.open(mode='rb') as f:
                    self.send_response(HTTPStatus.OK)
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
        elif self.path.startswith('/pyreadapi'):
            query = self.path[11:]
            queries = query.split('&')
            data = {}
            for q in queries:
                [key, val] = q.split('=', 1)
                data[key] = val
            self.api(data)
        elif self.path.startswith('/pyreadhome'):
            self.send_response(HTTPStatus.OK)
            self.end_headers()
            with open('assets/index.html', 'rb') as f:
                self.wfile.write(f.read())
        elif self.path.startswith('/pyreadinfo'):
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/json')
            with open('message.json', 'rb+') as f:
                message = f.read()
                f.truncate(0)
            if len(message) == 0:
                message = b'{}'
            self.send_header('Content-Length', len(message))
            self.end_headers()
            self.wfile.write(message)
        elif self.path.startswith('/pyreadstatus'):
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/json')
            with open('status.json', 'rb') as f:
                status = f.read()
            if len(status) == 0:
                status = b'{}'
            self.send_header('Content-Length', len(status))
            self.end_headers()
            self.wfile.write(status)

        else:
            self.proxy('GET')

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        if self.path.startswith('/pyreadscrape'):
            self.scrape(post_data)
            return
        data = {}
        post_data = urllib.parse.unquote(post_data.decode('utf-8'))
        for elem in post_data.split('&'):
            try:
                k, v = elem.split('=', 1)
            except ValueError:
                continue
            data[k] = v
        if self.path.startswith('/pyreadapi'):
            self.api(data)
        else:
            self.proxy('POST', data=data)

    def api(self, data):
        try:
            doi = data['doi']
            request_type = data['type']
            name = data.get('name')
        except KeyError:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return
        doi_path = Path.cwd().joinpath('files', doi)
        if not doi_path.exists():
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            return
        else:
            content_type = 'application/json'
            manifest_path = doi_path.joinpath('manifest.json')
            with manifest_path.open() as m_file:
                manifest = json.loads(m_file.read())
            if request_type == 'info':
                content = json.dumps(manifest).encode('utf-8')
            elif request_type == 'file':
                content_type = ''
                file_path = doi_path.joinpath(name)
                if file_path.exists():
                    with file_path.open(mode='rb') as f:
                        content = f.read()
                else:
                    self.send_response(HTTPStatus.NOT_FOUND)
                    self.end_headers()
                    return
            elif request_type == 'content':
                content_path = doi_path.joinpath('content.json')
                if content_path.exists():
                    with content_path.open(mode='rb') as f:
                        content = f.read()
                else:
                    self.send_response(HTTPStatus.NOT_FOUND)
                    self.end_headers
                    return
            elif request_type == 'references':
                ref_path = doi_path.joinpath('references.json')
                if ref_path.exists():
                    with ref_path.open(mode='rb') as f:
                        content = f.read()
                else:
                    self.send_response(HTTPStatus.NOT_FOUND)
                    self.end_headers
                    return
            else:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()
                return
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
            return


if __name__ == '__main__':
    PORT = 8000
    domain = 'localhost'

    Handler = PyRead

    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        httpd.serve_forever()
