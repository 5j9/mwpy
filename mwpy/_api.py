from pprint import pformat
from typing import Dict, AsyncGenerator, Any
from logging import warning, debug

from asks import Session
from trio import sleep

from ._version import __version__


class APIError(RuntimeError):
    pass


# noinspection PyShadowingBuiltins
class API:

    def __init__(
        self, url: str, user_agent: str = None, maxlag: int = 5,
    ) -> None:
        """Initialize API object.

        :param url: the api's url, e.g.
            https://en.wikipedia.org/w/api.php
        :param maxlag: see:
            https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
        :param user_agent: A string to be used as the User-Agent header value.
            If not provided a default value of f'mwpy/v{__version__}'} will be
            used, however that's not enough most of the time. see:
            https://meta.wikimedia.org/wiki/User-Agent_policy and
            https://www.mediawiki.org/wiki/API:Etiquette#The_User-Agent_header
        """
        self.url = url
        self.session = Session(
            connections=1, persist_cookies=True, headers={
               'User-Agent': user_agent or f'mwpy/v{__version__}'})
        self.maxlag = maxlag

    async def post(self, **data: Any) -> dict:
        """Post a request to MW API and return the json response.

        Add format, formatversion and errorformat, maxlag and utf8.
        Warn about warnings and raise errors as APIError.
        """
        debug('post data: %s', data)
        data.update({
            'format': 'json',
            'formatversion': '2',
            'errorformat': 'plaintext',
            'maxlag': self.maxlag})
        resp = await self.session.post(self.url, data=data)
        json = resp.json()
        debug('json response: %s', json)
        if 'warnings' in json:
            warning(pformat(json['warnings']))
        if 'errors' in json:
            return await self._handle_api_errors(data, resp, json['errors'])
        return json

    async def _handle_api_errors(self, data, resp, errors):
        for error in errors:
            if error['code'] == 'maxlag':
                retry_after = resp.headers['retry-after']
                warning(f'maxlag error (retrying after {retry_after} seconds)')
                await sleep(int(retry_after))
                return await(self.post(**data))
        raise APIError(errors)

    async def query(self, **params: Any) -> AsyncGenerator[dict, None]:
        """Post an API query and yeild results.

        Handle continuations.

        https://www.mediawiki.org/wiki/API:Query
        """
        if 'rawcontinue' in params:
            raise NotImplementedError(
                'rawcontinue is not implemented for query method')
        while True:
            json = await self.post(action='query', **params)
            continue_ = json.get('continue')
            yield json
            if continue_ is None:
                return
            params.update(continue_)

    async def tokens(self, type: str) -> Dict[str, str]:
        """Query API for tokens. Return the json response.

        https://www.mediawiki.org/wiki/API:Tokens
        """
        return await self.meta_query('tokens', type=type)

    async def login(self, name: str, password: str, domain=None) -> None:
        """Login using bot name and bot password.

        Should only be used in combination with Special:BotPasswords;
        use for main-account login is deprecated and may fail without warning.

        https://www.mediawiki.org/wiki/API:Login
        """
        json = await self.post(
            action='login',
            lgname=name,
            lgpassword=password,
            lgdomain=domain,
            lgtoken=(await self.tokens('login'))['logintoken'])
        assert json['login']['result'] == 'Success', json['login']['result']
        # todo: store user and pass for relogin and assert username for now on

    async def close(self) -> None:
        """Close the current API session."""
        await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def list_query(self, list: str, **params: Any):
        """Post a list query and yield the results.

        https://www.mediawiki.org/wiki/API:Lists
        """
        async for json in self.query(list=list, **params):
            assert json['batchcomplete'] is True  # T84977#5471790
            for item in json['query'][list]:
                yield item

    async def prop_query(self, prop, **params: Any):
        """Post a prop query, handle batchcomplete, and yield the results.

        https://www.mediawiki.org/wiki/API:Properties
        """
        batch = {}
        batch_get = batch.get
        batch_clear = batch.clear
        batch_setdefault = batch.setdefault
        async for json in self.query(prop=prop, **params):
            pages = json['query']['pages']
            if 'batchcomplete' in json:
                if not batch:
                    for page in pages:
                        yield page
                    continue
                for page in pages:
                    page_id = page['pageid']
                    batch_page = batch_get(page_id)
                    if batch_page is None:
                        yield page
                    batch_page[prop] += page[prop]
                    yield batch_page
                batch_clear()
                continue
            for page in pages:
                page_id = page['pageid']
                batch_page = batch_setdefault(page_id, page)
                if page is not batch_page:
                    batch_page[prop] += page[prop]

    async def langlinks(
        self, limit: int = 'max', prop: str = None, lang: str = None,
        title: str = None, dir: str = None, inlanguagecode: str = None,
        **prop_params
    ):
        async for page_llink in self.prop_query(
            'langlinks', llprop=prop, lllang=lang, lltitle=title, lldir=dir,
            llinlanguagecode=inlanguagecode, lllimit=limit, **prop_params
        ):
            yield page_llink

    async def meta_query(self, meta, **params: Any):
        """Post a meta query and yield the results.

        Note: siteinfo module requires special handling. Use self.siteinfo()
            instead. There may be other meta queries that also require special
            care. Use self.query() if there is no specific method for that
            meta query.

        https://www.mediawiki.org/wiki/API:Meta
        """
        if meta == 'siteinfo':
            raise NotImplementedError('use self.siteinfo() instead.')
        if meta == 'filerepoinfo':
            meta = 'repos'
        async for json in self.query(meta=meta, **params):
            assert json['batchcomplete'] is True
            return json['query'][meta]

    async def siteinfo(
        self, prop: str = None, filteriw: str = None, showalldb: str = None,
        numberingroup: str = None, inlanguagecode: str = None,
    ) -> dict:
        """https://www.mediawiki.org/wiki/API:Siteinfo"""
        async for json in self.query(
            meta='siteinfo',
            siprop=prop,
            sifilteriw=filteriw,
            sishowalldb=showalldb,
            sinumberingroup=numberingroup,
            siinlanguagecode=inlanguagecode,
        ):
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
        async for rc in self.list_query(
            list='recentchanges', rcstart=start, rcend=end, rcdir=dir,
            rcnamespace=namespace, rcuser=user, rcexcludeuser=excludeuser,
            rctag=tag, rcprop=prop, rcshow=show, rclimit=limit, rctype=type,
            rctoponly=toponly, rctitle=title,
        ):
            yield rc