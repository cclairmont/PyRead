from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import title_is
from selenium.webdriver.support.expected_conditions import url_changes
import ast
import selenium_utils as su
from selenium.common.exceptions import TimeoutException

PROXY = {'Harvard': 'javascript:(function(){location.href="http://"+location.hostname+".ezp-prod1.hul.harvard.edu"+location.pathname})();'}
USE_PROXY = 'Harvard'
    
def proxy_auth(driver=None, url=None, time_out=10, headless=True,
               browser='firefox', debug=False, success = None):
    if not driver:
        options = su.driver_options(browser)
        if headless:
            options.headless=True
        driver = su.spawn_driver(browser, options)
        driver.get(url)
    else:
        headless = su.is_headless(driver)
    if not headless:
        time_out = 300
    wait = WebDriverWait(driver, time_out)
    short_wait = WebDriverWait(driver, 5)
    wait.until(su.page_is_ready)
    try:
        with open('cookies.json', 'r') as cookie_file:
            cookies = ast.literal_eval(cookie_file.read())
    except:
        cookies = []
    title = driver.title
    current_url = driver.current_url
    print('Here')
    driver.execute_script(PROXY[USE_PROXY])
    while True:
        try:
            short_wait.until(url_changes(current_url))
        except TimeoutException:
            break
    current_url = driver.current_url
    for c in cookies:
        try:
            driver.add_cookie(c)
            if debug:
                print(f"Added Cookie {c['name']}")
        except:
            if debug:
                print(f"Failed Cookie {c['name']}")
            pass
    driver.get(current_url)
    try:
        if success is None:
            wait.until(title_is(title))
        else:
            wait.until(success)
    except TimeoutException:
        if not headless or not url:
            raise
        else:
            proxy_auth(url=url, headless=False)
    current_url = driver.current_url
    while True:
        try:
            short_wait.until(url_changes, current_url)
        except TimeoutException:
            break
    cookies = driver.get_cookies()
    with open('cookies.json', 'w') as cfile:
        cfile.write(str(cookies))
    return driver.current_url, cookies

if __name__ == '__main__':

    # driver = webdriver.Firefox()
    
    # success = False
    url = 'https://www.sciencedirect.com/science/article/abs/pii/S1097276519307294'
    # driver.get(url)
    # wait = WebDriverWait(driver, 300)
    # wait.until(su.page_is_ready)
    
    # print('Headful')
    # proxy_auth(driver)
    # print('Success')
    
    print('Headless')
    url, cookies = proxy_auth(url=url)
    print('Success')
    print(url, cookies)
    

        



