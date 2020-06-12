import http.server
import http.cookies
from http import HTTPStatus
import ast
import requests
import pickle
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
import articleparser as ap

class PyRead(http.server.BaseHTTPRequestHandler):
    
    def __init__(self, *args, debug=False, domain='localhost', port=8000,
                 **kwargs):
        self.debug = debug
        self.domain = domain
        self.port = port
        try:
            with open('links.json','r') as l:
                self.url_dict = ast.literal_eval(l.read())
        except FileNotFoundError:
            self.url_dict = {}
        super().__init__(*args, **kwargs)
        
    def inject_script(self, content):
        head_start = content.find(b'<head>') + 6
        content = (content[:head_start] + 
                   b'\n      <script type="text/javascript" src="?pyreadasset=pyreadproxy.js"></script>' + 
                   content[head_start:])
        return content
        
    def scrape(self, data):
        try:
            print(data['url'])
            self.send_response_only(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            doi = ap.scrape(data['url'], data['data'])
            print(doi)
            if doi is None:
                self.wfile.write(b'{"doi": "none"}')
            else:
                self.wfile.write(b''.join([b'{"doi": "',
                                           doi.encode('utf-8'),
                                           b'"}']))
        except KeyError:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
        
    def request_cache(self, session, request_type, url, data=None):
        parsed_url = urllib.parse.urlparse(url)
        netloc = parsed_url.netloc
        path = parsed_url.path
        cache_path = Path.cwd().joinpath('cache', netloc, path[1:])
        if cache_path.suffix == '':
            cache_path = cache_path.with_suffix('.cache')
        if cache_path.exists():
            print('CACHE_HIT')
            with cache_path.open(mode='rb') as f:
                content = f.read()
            return HTTPStatus.OK, content
        else:
            print('CACHE_MISS')
            if request_type == 'GET':
                response = session.get(url)
            elif request_type == 'POST':
                response = session.post(url, data=data)
            if response.status_code == HTTPStatus.OK:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                with cache_path.open(mode='wb') as f:
                    f.write(response.content)
            return HTTPStatus(response.status_code), response.content
            
        
    def proxy_form(self, response):
        soup = BeautifulSoup(response.content, 'lxml')
        for f in soup.find_all('form'):
            action = f.get('action')
            if not action is None:
                print(action)
                if f['action'].startswith('http'):
                    f['action'] = '/?pyreadproxyurl=' + f['action']
        return 
    
    def proxy_links(self, response):
        soup = BeautifulSoup(response.content, 'lxml')
        for f in soup.find_all('a'):
            action = f.get('href')
            if not action is None:
                if f['href'].startswith('http'):
                    f['href'] = '?pyreadproxyurl=' + f['href']
                    #print(f['href'])
                    
        return soup.encode('utf-8')
        
    def proxy(self, request_type, data=None):
        session = requests.Session()
        session.headers = self.headers
        cookie = http.cookies.SimpleCookie(self.headers.get('Cookie'))
        session.cookies.update(cookie)
        try:
            with open('cookies.pik', 'rb') as cfile:
                session.cookies.update(pickle.load(cfile))
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
                name,val = c.split('=',1)
                session.cookies.set(name,val,domain=domain)
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
        status,content = self.request_cache(session, request_type, path, data)
        if main_page:
            content = self.inject_script(content)
        self.send_response_only(status)
        self.end_headers()
        with open('cookies.pik', 'wb') as cfile:
            pickle.dump(session.cookies, cfile)
        self.wfile.write(content)
            
        
    def do_GET(self):
        print(self.path)
        if self.path.startswith('/?pyreadasset='):
            path = Path.cwd().joinpath('assets', self.path[14:])
            if path.exists():
                with path.open(mode='rb') as f:
                    self.send_response_only(HTTPStatus.OK)
                    self.end_headers()
                    self.wfile.write(f.read())
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
        elif self.path.startswith('/pyreadhome'):
            parsed_url = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed_url.query)
            self.send_response_only(HTTPStatus.OK)
            self.end_headers()
            with open('assets/index.html', 'rb') as f:
                self.wfile.write(f.read())
        else:
            self.proxy('GET')
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
        post_data = self.rfile.read(content_length)
        post_data = post_data.decode('utf-8').split('&')
        data = {}
        for elem in post_data:
            try:
                k,v = elem.split('=', 1)
            except ValueError:
                continue
            data[k] = v
        if self.path.startswith('/?pyreadscrape'):
            self.scrape(data)
        else:
            self.proxy('POST', data=data)
        
    def do_HEAD(self):
        self.proxy('GET')
        
if __name__ == '__main__':
    PORT = 8000
    domain = 'localhost'
    
    Handler = PyRead
    
    with http.server.HTTPServer(("", PORT), Handler) as httpd:
        print("serving at port", PORT)
        httpd.serve_forever()