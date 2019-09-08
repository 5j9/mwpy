from typing import Dict as _Dict, AsyncGenerator as _AsyncGenerator
from logging import warning as _warning

from asks import Session as _Session
from trio import sleep as _sleep


__version__ = '0.1.dev0'


class APIError(RuntimeError):
    pass


# noinspection PyShadowingBuiltins
class API:

    def __init__(
        self, url: str, maxlag: int = 5,
        user_agent: str = f'mwpy v{__version__}'
    ) -> None:
        """Initialize API object.

        :param url: the api's url, e.g.
            https://en.wikipedia.org/w/api.php
        :param maxlag: see:
            https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
        :param user_agent: see:
            https://www.mediawiki.org/wiki/API:Etiquette#The_User-Agent_header
        """
        self.url = url
        self.session = _Session(
            connections=1, headers={'User-Agent': user_agent})
        self.maxlag = maxlag
        self.user_agent = user_agent

    async def post(self, data: dict) -> dict:
        """Post a request to MW API and return the json response.

        Add format, formatversion and errorformat, maxlag and utf8.
        Warn about warnings and raise errors as APIError.
        """
        data = {
            **data,
            'format': 'json',
            'formatversion': '2',
            'errorformat': 'plaintext',
            'utf8': '',
            'maxlag': self.maxlag}
        resp = await self.session.post(self.url, data=data)
        json = resp.json()
        if 'warnings' in json:
            _warning(str(json['warnings']))
        if 'errors' in json:
            return await self._handle_api_errors(data, resp, json['errors'])
        return json

    async def _handle_api_errors(self, data, resp, errors):
        for error in errors:
            if error['code'] == 'maxlag':
                retry_after = resp.headers['retry-after']
                _warning(f'maxlag error (retry after {retry_after} seconds)')
                await _sleep(int(retry_after))
                return await(self.post(data))
        raise APIError(errors)

    async def query(self, params: dict) -> _AsyncGenerator[dict, None]:
        """Post an API query and yeild results.

        Handle continuations.

        https://www.mediawiki.org/wiki/API:Query
        """
        if 'rawcontinue' in params:
            raise NotImplementedError(
                'rawcontinue is implemented for query method')
        params = {**params, 'action': 'query'}
        while True:
            json = await self.post(params)
            continue_ = json.get('continue')
            yield json
            if continue_ is None:
                return
            params = {**params, **continue_}

    async def tokens(self, type: str) -> _Dict[str, str]:
        """Query API for tokens. Return the json response.

        https://www.mediawiki.org/wiki/API:Tokens
        """
        return await self.meta_query({'meta': 'tokens', 'type': type})

    async def login(self, name: str, password: str, domain=None) -> None:
        """Login using bot name and bot password.

        Should only be used in combination with Special:BotPasswords;
        use for main-account login is deprecated and may fail without warning.

        https://www.mediawiki.org/wiki/API:Login
        """
        await self.post({
            'action': 'login',
            'lgname': name,
            'lgpassword': password,
            'lgdomain': domain,
            'lgtoken': (await self.tokens("login"))["logintoken"]})

    async def close(self) -> None:
        """Close the current API session."""
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_query(self, params: dict):
        """Post a list query and yield the results.

        https://www.mediawiki.org/wiki/API:Lists
        """
        list_ = params['list']
        async for json in self.query(params):
            assert json['batchcomplete'] is True  # T84977#5471790
            for item in json['query'][list_]:
                yield item

    async def prop_query(self, params: dict):
        """Post a prop query, handle batchcomplete, and yield the results.

        https://www.mediawiki.org/wiki/API:Properties
        """
        prop_name = params['prop']
        batch = {}
        batch_get = batch.get
        batch_clear = batch.clear
        batch_setdefault = batch.setdefault
        async for json in self.query(params):
            if 'batchcomplete' in json:
                if not batch:
                    for props in json['query']['pages'].values():
                        yield props[prop_name]
                else:
                    for page_id, props in json['query']['pages'].items():
                        batch_props = batch_get(page_id)
                        if batch_props is None:
                            yield props[prop_name]
                        else:
                            batch_prop = batch_props[prop_name]
                            batch_prop += props[prop_name]
                            yield batch_prop
                    batch_clear()
            else:
                for page_id, props in json['query']['pages'].items():
                    batch_props = batch_setdefault(page_id, props)
                    if props is not batch_props:
                        batch_props.update(props)

    async def meta_query(self, params: dict):
        """Post a meta query and yield the results.

        Note: siteinfo module requires special handling. Use self.siteinfo()
            instead. There may be other meta queries that also require special
            care. Use self.query() if there is no specific method for that
            meta query.

        https://www.mediawiki.org/wiki/API:Meta
        """
        meta = params['meta']
        if meta == 'siteinfo':
            raise NotImplementedError('use self.siteinfo() instead.')
        if meta == 'filerepoinfo':
            meta = 'repos'
        async for json in self.query(params):
            assert json['batchcomplete'] is True
            return json['query'][meta]

    async def siteinfo(
        self, prop: str = None, filteriw: str = None, showalldb: str = None,
        numberingroup: str = None, inlanguagecode: str = None,
    ) -> dict:
        """https://www.mediawiki.org/wiki/API:Siteinfo"""
        async for json in self.query({
            'meta': 'siteinfo',
            'siprop': prop,
            'sifilteriw': filteriw,
            'sishowalldb': showalldb,
            'sinumberingroup': numberingroup,
            'siinlanguagecode': inlanguagecode,
        }):
            assert 'batchcomplete' in json
            assert 'continue' not in json
            return json['query']

    async def recentchanges(
        self, start: str = None, end: str = None, dir: str = None,
        namespace: str = None, user: str = None, excludeuser: str = None,
        tag: str = None, prop: str = None, show: str = None,
        limit: int = 'max', type: str = None, toponly: bool = None,
        title: str = None
    ):
        """https://www.mediawiki.org/wiki/API:RecentChanges"""
        # Todo: somehow support rcgeneraterevisions
        async for rc in self.list_query({
            'list': 'recentchanges', 'rcstart': start, 'rcend': end,
            'rcdir': dir, 'rcnamespace': namespace, 'rcuser': user,
            'rcexcludeuser': excludeuser, 'rctag': tag, 'rcprop': prop,
            'rcshow': show, 'rclimit': limit, 'rctype': type,
            'rctoponly': toponly, 'rctitle': title,

        }):
            yield rc