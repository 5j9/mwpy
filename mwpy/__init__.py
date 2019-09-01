from aiohttp import ClientSession
from typing import Dict
from warnings import warn


__version__ = '0.1.dev0'


class API:

    def __init__(self, url: str):
        self.url = url
        self.session = ClientSession()

    async def post(self, data: dict) -> dict:
        data.update({
            'format': 'json',
            'formatversion': '2',
            'errorformat': 'plaintext'})
        async with self.session.post(self.url, data=data) as resp:
            json = await resp.json()
            if 'warnings' in json:
                warn(str(json['warnings']))
            if 'errors' in json:
                raise RuntimeError(json['errors'])
            return json

    async def tokens(self, types: str) -> Dict[str, str]:
        return (await self.post({
            'action': 'query',
            'meta': 'tokens',
            'type': types}))['query']['tokens']

    async def login(self, name, password, domain=''):
        await self.post({
            'action': 'login',
            'lgname': name,
            'lgpassword': password,
            'lgdomain': domain,
            'lgtoken': (await self.tokens("login"))["logintoken"]})

    async def close(self):
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
