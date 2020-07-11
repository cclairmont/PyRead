import sys
import json
import jsmin
import pytest
import asyncio
import aiohttp
from difflib import SequenceMatcher
sys.path.insert(1, 'C:\\Users\\Connor\\Python\\Papers')
import aio_articleparser as ap

pytestmark = [pytest.mark.asyncio]

MAX_CONCURRENT = 50

with open('testing/full_list.json') as f:
    links = json.loads(jsmin.jsmin(f.read()))


async def _fetch_doi(session, i):
    retry = True
    while retry:
        if i['url'].find('biorxiv') != -1:
            return
        print(f"{i['doi']}: Fetching...")
        try:
            result = await ap.Article(session, {}).fetch_metadata(doi=i['doi'])
            retry = False
        except aiohttp.client_exceptions.ClientError:
            pass
        except asyncio.exceptions.TimeoutError:
            pass
        print(f"{i['doi']}: Done...")
    if i['pmid'] is not None:
        assert(result['pmid'] == i['pmid'])
    if i['title'] is not None:
        assert(result['title'] is not None and
               (SequenceMatcher(None, result['title'].upper(),
                                i['title'].upper()).ratio() > 0.6 or
                i['title'].upper().find(result['title'].upper()) != -1 or
                result['title'].upper().find(i['title'].upper()) != -1))


async def test_doi():
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(links), MAX_CONCURRENT):
            if i + MAX_CONCURRENT < len(links):
                do_block = links[i:i + MAX_CONCURRENT - 1]
            else:
                do_block = links[i:]
            await asyncio.gather(*[_fetch_doi(session, j) for j in do_block])
