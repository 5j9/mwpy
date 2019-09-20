from dataclasses import dataclass
from pprint import pformat
from unittest import main, IsolatedAsyncioTestCase
from unittest.mock import patch

from mwpy import API, LoginError, APIError


api = API('https://www.mediawiki.org/w/api.php')


async def fake_sleep(_):
    return


@dataclass
class FakeResp:
    headers: dict
    _json: dict

    def json(self):
        return self._json


def patch_awaitable(obj, attr, return_values):
    def closure(return_value):
        async def fake_post():
            return return_value
        return fake_post()
    fake_posts = []
    fake_posts_append = fake_posts.append
    for return_value in return_values:
        fake_posts_append(closure(return_value))
    return patch.object(obj, attr, side_effect=fake_posts)


def api_post_patch(*return_values: dict):
    return patch_awaitable(api, 'post', return_values)


def session_post_patch(*return_values: dict):
    iterator = iter(return_values)
    return patch_awaitable(api.session, 'post', (
        FakeResp(headers, json) for headers, json in zip(iterator, iterator)))


# noinspection PyProtectedMember
class APITest(IsolatedAsyncioTestCase):

    # noinspection PyPep8Naming
    @staticmethod
    def setUp():
        api.clear_cache()

    @api_post_patch(
        {'batchcomplete': True, 'query': {'tokens': {'logintoken': 'T'}}},
        {'login': {'result': 'Success', 'lguserid': 1, 'lgusername': 'U'}})
    async def test_login(self, post_mock):
        ae = self.assertEqual
        await api.login(lgname='U', lgpassword='P')
        for call, expected_kwargs in zip(post_mock.mock_calls, (
            {'action': 'query', 'meta': 'tokens', 'type': 'login'},
            {'action': 'login', 'lgname': 'U', 'lgpassword': 'P', 'lgtoken': 'T'})
        ):
            ae(call.kwargs, expected_kwargs)

    @api_post_patch(
        {'batchcomplete': True, 'query': {'tokens': {'logintoken': 'T1'}}},
        {'login': {'result': 'WrongToken'}},
        {'batchcomplete': True, 'query': {'tokens': {'logintoken': 'T2'}}},
        {'login': {'result': 'Success', 'lguserid': 1, 'lgusername': 'U'}})
    async def test_bad_login_token(self, post_mock):
        ae = self.assertEqual
        await api.login(lgname='U', lgpassword='P')
        for call, expected_kwargs in zip(post_mock.mock_calls, (
            {'action': 'query', 'meta': 'tokens', 'type': 'login'},
            {'action': 'login', 'lgtoken': 'T1', 'lgname': 'U', 'lgpassword': 'P'},
            {'action': 'query', 'meta': 'tokens', 'type': 'login'},
            {'action': 'login', 'lgtoken': 'T2', 'lgname': 'U', 'lgpassword': 'P'},)
        ):
            ae(call.kwargs, expected_kwargs)

    @api_post_patch({'login': {'result': 'U', 'lguserid': 1, 'lgusername': 'U'}})
    async def test_unknown_login_result(self, post_mock):
        api.login_token = 'T'
        try:
            await api.login(lgname='U', lgpassword='P')
        except LoginError:
            pass
        else:
            raise AssertionError('LoginError was not raised')
        self.assertEqual(len(post_mock.mock_calls), 1)

    @api_post_patch(
        {'batchcomplete': True, 'continue': {'rccontinue': '20190908072938|4484663', 'continue': '-||'}, 'query': {'recentchanges': [{'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'}]}},
        {'batchcomplete': True, 'query': {'recentchanges': [{'type': 'categorize', 'timestamp': '2019-09-08T07:29:38Z'}]}})
    async def test_recentchanges(self, post_mock):
        ae = self.assertEqual
        ae(
            [rc async for rc in api.recentchanges(rclimit=1, rcprop='timestamp')],
            [
                {'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'},
                {'type': 'categorize', 'timestamp': '2019-09-08T07:29:38Z'}])
        post1_call_data = {'list': 'recentchanges', 'rcprop': 'timestamp', 'rclimit': 1, 'action': 'query'}
        post2_call_data = {**post1_call_data, 'rccontinue': '20190908072938|4484663', 'continue': '-||'}
        for call, kwargs in zip(post_mock.mock_calls, (post1_call_data, post2_call_data)):
            ae(call.kwargs, kwargs)

    @patch('mwpy._api.sleep', fake_sleep)
    @patch('mwpy._api.warning')
    @session_post_patch(
        {'retry-after': '5'},
        {'errors': [{'code': 'maxlag', 'text': 'Waiting for 10.64.16.7: 0.80593395233154 seconds lagged.', 'data': {'host': '10.64.16.7', 'lag': 0.805933952331543, 'type': 'db'}, 'module': 'main'}], 'docref': 'See https://www.mediawiki.org/w/api.php for API usage. Subscribe to the mediawiki-api-announce mailing list at &lt;https://lists.wikimedia.org/mailman/listinfo/mediawiki-api-announce&gt; for notice of API deprecations and breaking changes.', 'servedby': 'mw1225'},
        {}, {'batchcomplete': True, 'query': {'tokens': {'watchtoken': '+\\'}}})
    async def test_maxlag(self, post_mock, warning_mock):
        ae = self.assertEqual
        tokens = await api.tokens('watch')
        ae(tokens, {'watchtoken': '+\\'})
        post_data = {'meta': 'tokens', 'type': 'watch', 'action': 'query', 'format': 'json', 'formatversion': '2', 'errorformat': 'plaintext', 'maxlag': 5}
        ae(
            [c.kwargs['data'] for c in post_mock.mock_calls],
            [post_data, post_data])
        warning_mock.assert_called_with('maxlag error (retrying after 5 seconds)')

    @api_post_patch({'batchcomplete': True, 'query': {'protocols': ['http://', 'https://']}})
    async def test_siteinfo(self, post_mock):
        ae = self.assertEqual
        si = await api.siteinfo(siprop='protocols')
        ae(si, {'protocols': ['http://', 'https://']})
        calls = post_mock.mock_calls
        ae(len(calls), 1)
        ae(calls[0].kwargs, {'action': 'query', 'meta': 'siteinfo', 'siprop': 'protocols'})

    @api_post_patch(
        {'continue': {'llcontinue': '15580374|bg', 'continue': '||'}, 'query': {'pages': [{'pageid': 15580374, 'ns': 0, 'title': 'Main Page', 'langlinks': [{'lang': 'ar', 'title': ''}]}]}},
        {'batchcomplete': True, 'query': {'pages': [{'pageid': 15580374, 'ns': 0, 'title': 'Main Page', 'langlinks': [{'lang': 'zh', 'title': ''}]}]}})
    async def test_langlinks(self, post_mock):
        ae = self.assertEqual
        titles_langlinks = [page_ll async for page_ll in api.langlinks(
            titles='Main Page', lllimit=1)]
        ae(len(titles_langlinks), 1)
        for call, kwargs in zip(post_mock.mock_calls, (
            {'action': 'query', 'prop': 'langlinks', 'lllimit': 1, 'titles': 'Main Page'},
            {'action': 'query', 'prop': 'langlinks', 'lllimit': 1, 'titles': 'Main Page', 'llcontinue': '15580374|bg', 'continue': '||'}
        )):
            ae(call.kwargs, kwargs)
        ae(titles_langlinks[0], {'pageid': 15580374, 'ns': 0, 'title': 'Main Page', 'langlinks': [{'lang': 'ar', 'title': ''}, {'lang': 'zh', 'title': ''}]})

    @api_post_patch({'batchcomplete': True, 'query': {'pages': [{'pageid': 1182793, 'ns': 0, 'title': 'Main Page'}]}, 'limits': {'langlinks': 500}})
    async def test_lang_links_title_not_exists(self, post_mock):
        ae = self.assertEqual
        titles_langlinks = [page_ll async for page_ll in api.langlinks(
            titles='Main Page')]
        ae(len(titles_langlinks), 1)
        ae(post_mock.mock_calls[0].kwargs, {'action': 'query', 'prop': 'langlinks', 'lllimit': 'max', 'titles': 'Main Page'})
        ae(titles_langlinks[0], {'pageid': 1182793, 'ns': 0, 'title': 'Main Page'})

    @api_post_patch({'batchcomplete': True, 'query': {'userinfo': {'id': 0, 'name': '1.1.1.1', 'anon': True}}})
    async def test_userinfo(self, post_mock):
        ae = self.assertEqual
        ae(await api.userinfo(), {'id': 0, 'name': '1.1.1.1', 'anon': True})
        ae(post_mock.mock_calls[0].kwargs, {'action': 'query', 'meta': 'userinfo'})

    @api_post_patch({'batchcomplete': True, 'query': {'repos': [{'displayname': 'Commons'}, {'displayname': 'Wikipedia'}]}})
    async def test_filerepoinfo(self, post_mock):
        ae = self.assertEqual
        ae(await api.filerepoinfo(friprop='displayname'), [{'displayname': 'Commons'}, {'displayname': 'Wikipedia'}])
        ae(post_mock.mock_calls[0].kwargs, {'action': 'query', 'meta': 'filerepoinfo', 'friprop': 'displayname'})

    @staticmethod
    async def test_context_manager():
        a = API('')
        with patch.object(a.session, 'close') as close_mock:
            async with a:
                pass
        close_mock.assert_called_once_with()

    @session_post_patch(
        {}, {'batchcomplete': True, 'query': {'tokens': {'patroltoken': '+\\'}}},
        {}, {'errors': [{'code': 'permissiondenied', 'text': 'T', 'module': 'patrol'}], 'docref': 'D', 'servedby': 'mw1233'})
    async def test_patrol_not_logged_in(self, post_mock):
        try:
            await api.patrol(revid=27040231)
        except APIError:
            pass
        else:
            raise AssertionError('APIError was not raised')
        post_mock.assert_called_with(
            'https://www.mediawiki.org/w/api.php',
            data={'revid': 27040231, 'action': 'patrol', 'token': '+\\', 'format': 'json', 'formatversion': '2', 'errorformat': 'plaintext', 'maxlag': 5})

    @api_post_patch({'patrol': {'rcid': 1, 'ns': 4, 'title': 'T'}})
    async def test_patrol(self, post_mock):
        api.patrol_token = '+'
        await api.patrol(revid=1)
        post_mock.assert_called_with(action='patrol', token='+', revid=1)

    @session_post_patch({}, {'errors': [{'code': 'badtoken', 'text': 'Invalid CSRF token.', 'module': 'patrol'}], 'docref': 'D', 'servedby': 'mw1279'})
    async def test_bad_patrol_token(self, _):
        api.patrol_token = '+'
        try:
            await api.patrol(revid=1)
        except APIError:
            pass
        else:
            raise AssertionError('APIError was not raised')
        with patch.object(api, 'tokens', return_value={'patroltoken': 'N'}) as tokens_mock:
            self.assertEqual(await api.patrol_token, 'N')
        tokens_mock.assert_called_once_with('patrol')

    @staticmethod
    async def test_rawcontinue():
        try:
            async for _ in api.query(rawcontinue=''):
                pass
        except NotImplementedError:
            pass
        else:
            raise AssertionError('rawcontinue did not raise in query')

    @patch('mwpy._api.warning')
    async def test_warnings(self, warning_mock):
        warnings = [{'code': 'unrecognizedparams', 'text': 'Unrecognized parameter: unknown_param.', 'module': 'main'}]
        with session_post_patch(
            {}, {'warnings': warnings, 'batchcomplete': True}
        ):
            await api.post()
        warning_mock.assert_called_once_with(pformat(warnings))

    @api_post_patch({})
    async def test_logout(self, post_mock):
        api.csrf_token = 'T'
        await api.logout()
        post_mock.assert_called_once()
        self.assertIsNone(api._csrf_token)

    @api_post_patch({'batchcomplete': True, 'query': {'tokens': {'csrftoken': '+\\'}}})
    async def test_csrf_token(self, post_mock):
        self.assertEqual(await api.csrf_token, '+\\')
        post_mock.assert_called_once()


if __name__ == '__main__':
    main()
