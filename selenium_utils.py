from selenium import webdriver
from selenium.webdriver.firefox.options import Options as firefox_options
import requests


def page_is_ready(driver):
    return driver.execute_script('return document.readyState') == 'complete'


def url_changed(current_url):
    return lambda d: d.current_url != current_url


def driver_options(browser):
    if browser == 'firefox':
        return firefox_options()
    else:
        raise NotImplementedError


def is_headless(driver):
    browser = driver.capabilities['browserName']
    if browser == 'firefox':
        return driver.capabilities['moz:headless']
    else:
        raise NotImplementedError


def spawn_driver(browser, options=None):
    if browser == 'firefox':
        driver = webdriver.Firefox(options=options)
    else:
        raise NotImplementedError
    return driver


def make_cookiejar(driver=None, cookies=None):
    if not cookies:
        cookies = driver.get_cookies()
    cookiejar = requests.cookies.RequestsCookieJar()
    for c in cookies:
        if 'httpOnly' in c:
            c['rest'] = {'HttpOnly': c.pop('httpOnly')}
        if 'expiry' in c:
            c['expires'] = c.pop('expiry')
        cookiejar.set_cookie(requests.cookies.create_cookie(**c))
    return cookiejar