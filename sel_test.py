from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from selenium.webdriver.support.expected_conditions import title_is
from selenium.webdriver.support.expected_conditions import url_changes
import ast

PROXY = {'Harvard': 'javascript:(function(){location.href="http://"+location.hostname+".ezp-prod1.hul.harvard.edu"+location.pathname})();'}
USE_PROXY = 'Harvard'

def is_headless(driver):
    browser = driver.capabilities['browserName']
    if browser == 'firefox':
        return driver.capabilities['moz:headless']
    else:
        raise NotImplementedError
        
def spawn_driver(browser, options):
    if browser == 'firefox':
        driver = webdriver.Firefox(options=options)
    else:
        raise(NotImplementedError)
    return driver
    
def proxy_auth(driver=None, url=None, time_out=10, headless=True,
               browser='firefox'):
    if not driver:
        options = Options()
        if headless:
            options.headless=True
        driver = spawn_driver(browser, options)
        driver.get(url)
    else:
        headless = is_headless(driver)
    if not headless:
        time_out = 300
    wait = WebDriverWait(driver, time_out)
    wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
    try:
        with open('cookies.json', 'r') as cookie_file:
            cookies = ast.literal_eval(cookie_file.read())
    except:
        cookies = []
    title = driver.title
    current_url = driver.current_url
    driver.execute_script(PROXY[USE_PROXY])
    wait.until(url_changes(current_url))
    current_url = driver.current_url
    for c in cookies:
        try:
            driver.add_cookie(c)
        except:
            pass
    driver.get(current_url)
    try:
        wait.until(title_is(title))
    except:
        if not headless or not url:
            raise
        else:
            proxy_auth(url=url, headless=False)
    wait.until(lambda d: d.execute_script('return document.readyState') == 'complete')
    cookies = driver.get_cookies()
    with open('cookies.json', 'w') as cfile:
        cfile.write(str(cookies))
    return cookies

if __name__ == '__main__':

    driver = webdriver.Firefox()
    
    success = False
    
    driver.get('https://www.sciencedirect.com/science/article/abs/pii/S1097276519307294')
    wait = WebDriverWait(driver, 300)
    label = wait.until(presence_of_element_located((By.CLASS_NAME, 'pdf-download-label')))
    
    if label.text == 'Get Access':
        cookies = proxy_auth(driver)
    
    print('cookies')
    

        



