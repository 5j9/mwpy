from inspect import iscoroutinefunction
from pprint import pformat
from typing import Dict, AsyncGenerator, Any
from logging import warning, debug, info

from asks import Session
from asks.response_objects import Response
from trio import sleep

from ._version import __version__


class APIError(RuntimeError):
    pass


class LoginError(RuntimeError):
    pass


# noinspection PyShadowingBuiltins,PyAttributeOutsideInit
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
            return await self._handle_api_errors(data, resp, json)
        return json

    async def _handle_api_errors(self, data: dict, resp: Response, json: dict):
        errors = json['errors']
        for error in errors:
            handler = getattr(self, f'_handle_{error["code"]}_error', None)
            if handler is not None:
                if iscoroutinefunction(handler):
                    handler_result = await handler(resp, data, error)
                else:
                    handler_result = handler(resp, data, error)
                if handler_result is not None:
                    return handler_result
        raise APIError(errors)

    async def _handle_maxlag_error(
        self, resp: Response, data: dict, _
    ) -> dict:
        retry_after = resp.headers['retry-after']
        warning(f'maxlag error (retrying after {retry_after} seconds)')
        await sleep(int(retry_after))
        return await(self.post(**data))

    async def _handle_badtoken_error(self, _: Response, __: dict, error: dict):
        if error['module'] == 'patrol':
            info('invalidating patrol token cache')
            del self.patrol_token

    @property
    async def csrf_token(self):
        token = getattr(self, '_csrf_token', None)
        if token is None:
            token = self._csrf_token = (
                await self.tokens('csrf'))['csrftoken']
        return token

    @csrf_token.setter
    def csrf_token(self, value):
        self._csrf_token = value

    @csrf_token.deleter
    def csrf_token(self):
        self._csrf_token = None

    async def logout(self):
        """https://www.mediawiki.org/wiki/API:Logout"""
        await self.post(action='logout', token=await self.csrf_token)
        self.clear_cache()

    async def query(self, **params: Any) -> AsyncGenerator[dict, None]:
        """Post an API query and yield results.

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

    @property
    async def login_token(self):
        """Fetch login token and cache the result.

        Use deleter to invalidate cache.
        """
        token = getattr(self, '_login_token', None)
        if token is None:
            token = self._login_token = (
                await self.tokens('login'))['logintoken']
        return token

    @login_token.setter
    def login_token(self, value):
        self._login_token = value

    @login_token.deleter
    def login_token(self):
        self._login_token = None

    async def login(self, lgname: str, lgpassword: str, **kwargs: Any) -> None:
        """https://www.mediawiki.org/wiki/API:Login

        `lgtoken` will be added automatically.
        """
        json = await self.post(
            action='login',
            lgname=lgname,
            lgpassword=lgpassword,
            lgtoken=await self.login_token,
            **kwargs)
        result = json['login']['result']
        if result == 'Success':
            self.clear_cache()
            return
        if result == 'WrongToken':
            # token is outdated?
            info(result)
            del self._login_token
            return await self.login(lgname, lgpassword, **kwargs)
        raise LoginError(result)
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

    async def prop_query(self, prop: str, **params: Any):
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

    async def langlinks(self, lllimit: int = 'max', **kwargs: Any):
        async for page_llink in self.prop_query(
            'langlinks', lllimit=lllimit, **kwargs
        ):
            yield page_llink

    async def meta_query(self, meta, **kwargs: Any):
        """Post a meta query and return the result .

        Note: Some meta queries require special handling. Use `self.query()`
            directly if this method cannot handle it properly and there is no
            other specific method for it.

        https://www.mediawiki.org/wiki/API:Meta
        """
        if meta == 'siteinfo':
            async for json in self.query(meta='siteinfo', **kwargs):
                assert 'batchcomplete' in json
                assert 'continue' not in json
                return json['query']
        async for json in self.query(meta=meta, **kwargs):
            if meta == 'filerepoinfo':
                meta = 'repos'
            assert json['batchcomplete'] is True
            return json['query'][meta]

    async def userinfo(self, **kwargs):
        """https://www.mediawiki.org/wiki/API:Userinfo"""
        return await self.meta_query('userinfo', **kwargs)

    async def siteinfo(self, **kwargs: Any) -> dict:
        """https://www.mediawiki.org/wiki/API:Siteinfo"""
        return await self.meta_query('siteinfo', **kwargs)

    async def recentchanges(self, rclimit: int = 'max', **kwargs: Any):
        """https://www.mediawiki.org/wiki/API:RecentChanges"""
        # Todo: somehow support rcgeneraterevisions
        async for rc in self.list_query(
            list='recentchanges', rclimit=rclimit, **kwargs
        ):
            yield rc

    async def filerepoinfo(self, **kwargs: Any):
        """https://www.mediawiki.org/wiki/API:Filerepoinfo"""
        return await self.meta_query('filerepoinfo', **kwargs)

    @property
    async def patrol_token(self):
        """Fetch patrol token and cache the result.

        Use deleter to invalidate cache.
        """
        token = getattr(self, '_patrol_token', None)
        if token is None:
            token = self._patrol_token = (
                await self.tokens('patrol'))['patroltoken']
        return token

    @patrol_token.setter
    def patrol_token(self, value):
        self._patrol_token = value

    @patrol_token.deleter
    def patrol_token(self):
        self._patrol_token = None

    async def patrol(self, **kwargs: Any) -> None:
        """https://www.mediawiki.org/wiki/API:Patrol

        `token` will be added automatically.
        """
        await self.post(
            action='patrol', token=await self.patrol_token, **kwargs)

    def clear_cache(self):
        """Clear cached values."""
        del self.login_token, self.patrol_token, self.csrf_token
