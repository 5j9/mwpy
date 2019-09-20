from collections import namedtuple
from unittest import main, IsolatedAsyncioTestCase
from unittest.mock import patch

from mwpy import API


api = API('https://www.mediawiki.org/w/api.php')


async def fake_sleep(_):
    return

FakeResp = namedtuple('FakeResp', ('json', 'headers'))


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


def api_post_patch(*return_values):
    return patch_awaitable(api, 'post', return_values)


def session_post_patch(*return_values):
    return patch_awaitable(api.session, 'post', return_values)


class APITest(IsolatedAsyncioTestCase):

    @api_post_patch(
        {'batchcomplete': True, 'query': {'tokens': {'logintoken': 'LOGIN_TOKEN'}}},
        {'login': {'result': 'Success', 'lguserid': 1, 'lgusername': 'U'}})
    async def test_login(self, post_mock):
        await api.login('U', 'P')
        self.assertEqual([c.kwargs for c in post_mock.mock_calls], [
            {'action': 'query', 'meta': 'tokens', 'type': 'login'},
            {'action': 'login', 'lgname': 'U', 'lgpassword': 'P', 'lgdomain': None, 'lgtoken': 'LOGIN_TOKEN'}])

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
        FakeResp(
            lambda: {
                'errors': [{
                    'code': 'maxlag',
                    'text': 'Waiting for 10.64.16.7: 0.80593395233154 seconds lagged.',
                    'data': {
                        'host': '10.64.16.7', 'lag': 0.805933952331543,
                        'type': 'db'}, 'module': 'main'}],
                'docref': 'See https://www.mediawiki.org/w/api.php for API usage. Subscribe to the mediawiki-api-announce mailing list at &lt;https://lists.wikimedia.org/mailman/listinfo/mediawiki-api-announce&gt; for notice of API deprecations and breaking changes.',
                'servedby': 'mw1225'},
            {'retry-after': '5'}),
        FakeResp(lambda: {'batchcomplete': True, 'query': {'tokens': {'watchtoken': '+\\'}}}, {}))
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


if __name__ == '__main__':
    main()
