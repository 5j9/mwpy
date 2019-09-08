from collections import namedtuple
from unittest import main, TestCase
from unittest.mock import patch, call

from trio import run

from mwpy import API


api = API('https://www.mediawiki.org/w/api.php')


async def fake_login_token_post():
    return {'query': {'tokens': {'logintoken': 'LOGIN_TOKEN'}}, 'batchcomplete': True}


async def fake_login_post():
    return {'query': {'tokens': {'logintoken': 'LOGIN_TOKEN'}}}


async def fake_rc_fist_post():
    return {'batchcomplete': True, 'continue': {'rccontinue': '20190908072938|4484663', 'continue': '-||'}, 'query': {'recentchanges': [{'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'}]}}


async def fake_rc_fanal_post():
    return {'batchcomplete': True, 'query': {'recentchanges': [{'type': 'categorize', 'timestamp': '2019-09-08T07:29:38Z'}]}}


async def fake_sleep(_):
    return

FakeResp = namedtuple('FakeResp', ('json', 'headers'))


async def fake_maxlag_tokens_session_post():
    return FakeResp(
        lambda: {'errors': [{'code': 'maxlag', 'text': 'Waiting for 10.64.16.7: 0.80593395233154 seconds lagged.', 'data': {'host': '10.64.16.7', 'lag': 0.805933952331543, 'type': 'db'}, 'module': 'main'}], 'docref': 'See https://www.mediawiki.org/w/api.php for API usage. Subscribe to the mediawiki-api-announce mailing list at &lt;https://lists.wikimedia.org/mailman/listinfo/mediawiki-api-announce&gt; for notice of API deprecations and breaking changes.', 'servedby': 'mw1225'},
        {'retry-after': '5'})


async def fake_watch_token_session_post():
    return FakeResp(lambda: {'batchcomplete': True, 'query': {'tokens': {'watchtoken': '+\\'}}}, {})


def add_async_test_runners(c):
    class_dict = vars(c)
    for attr_name, attr in class_dict.copy().items():
        if attr_name[-5:] == '_test':
            def closure(attr_name):
                def test_case(s):
                    run(getattr(s, attr_name))
                return test_case
            setattr(c, 'test_' + attr_name[:-5], closure(attr_name))
    return c


@add_async_test_runners
class APITest(TestCase):

    @patch.object(
        api, 'post', side_effect=(fake_login_token_post(), fake_login_post()))
    async def login_test(self, post_patch):
        await api.login('U', 'P')
        post_patch.assert_has_calls((
            call(action='query', meta='tokens', type='login'),
            call(action='login', lgname='U', lgpassword='P', lgdomain=None, lgtoken='LOGIN_TOKEN')))

    @patch.object(
        api, 'post', side_effect=(fake_rc_fist_post(), fake_rc_fanal_post()))
    async def recentchanges_test(self, post_patch):
        self.assertEqual(
            [rc async for rc in api.recentchanges(limit=1, prop='timestamp')],
            [
                {'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'},
                {'type': 'categorize', 'timestamp': '2019-09-08T07:29:38Z'}])
        post1_call_data = {'list': 'recentchanges', 'rcstart': None, 'rcend': None, 'rcdir': None, 'rcnamespace': None, 'rcuser': None, 'rcexcludeuser': None, 'rctag': None, 'rcprop': 'timestamp', 'rcshow': None, 'rclimit': 1, 'rctype': None, 'rctoponly': None, 'rctitle': None, 'action': 'query'}
        post2_call_data = {**post1_call_data, 'rccontinue': '20190908072938|4484663', 'continue': '-||'}
        post_patch.assert_has_calls(
            [call(**post1_call_data), call(**post2_call_data)])

    @patch('mwpy._sleep', fake_sleep)
    @patch('mwpy._warning')
    @patch.object(api.session, 'post', side_effect=(
        fake_maxlag_tokens_session_post(),
        fake_maxlag_tokens_session_post(),
        fake_watch_token_session_post()))
    async def maxlag_test(self, post_mock, warning_mock):
        ae = self.assertEqual
        tokens = await api.tokens('watch')
        ae(tokens, {'watchtoken': '+\\'})
        post_data = {'meta': 'tokens', 'type': 'watch', 'action': 'query', 'format': 'json', 'formatversion': '2', 'errorformat': 'plaintext', 'utf8': '', 'maxlag': 5}
        ae(
            [c.kwargs['data'] for c in post_mock.mock_calls],
            [post_data, post_data, post_data])
        warning_mock.assert_called_with('maxlag error (retry after 5 seconds)')


if __name__ == '__main__':
    main()
