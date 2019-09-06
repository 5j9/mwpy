from unittest import main, TestCase
from unittest.mock import patch, call

from trio import run

from mwpy import API


async def fake_token_post():
    return {'query': {'tokens': {'logintoken': 'LOGIN_TOKEN'}}, 'batchcomplete': True}


async def fake_login_post():
    return {'query': {'tokens': {'logintoken': 'LOGIN_TOKEN'}}}


async def fake_rc_post1():
    return {'batchcomplete': True, 'continue': {'rccontinue': '20190908072938|4484663', 'continue': '-||'}, 'query': {'recentchanges': [{'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'}]}}


async def fake_rc_post2():
    return {'batchcomplete': True, 'query': {'recentchanges': [{'type': 'categorize', 'timestamp':'2019-09-08T07:29:38Z'}]}}


api = API('https://www.mediawiki.org/w/api.php')


class APITest(TestCase):

    @patch.object(
        api, 'post', side_effect=(fake_token_post(), fake_login_post()))
    async def login_test(self, post_patch):
        await api.login('U', 'P')
        post_patch.assert_has_calls((
            call({'action': 'query', 'meta': 'tokens', 'type': 'login'}),
            call({'action': 'login', 'lgname': 'U', 'lgpassword': 'P', 'lgdomain': None, 'lgtoken': 'LOGIN_TOKEN'})))

    def test_login(self):
        run(self.login_test)

    @patch.object(
        api, 'post', side_effect=(fake_rc_post1(), fake_rc_post2()))
    async def recentchanges_test(self, post_patch):
        self.assertEqual(
            [rc async for rc in api.recentchanges(limit=1, prop='timestamp')],
            [
                {'type': 'log', 'timestamp': '2019-09-08T07:30:00Z'},
                {'type': 'categorize', 'timestamp': '2019-09-08T07:29:38Z'}])
        post1_call_data = {'list': 'recentchanges', 'rcstart': None, 'rcend': None, 'rcdir': None, 'rcnamespace': None, 'rcuser': None, 'rcexcludeuser': None, 'rctag': None, 'rcprop': 'timestamp', 'rcshow': None, 'rclimit': 1, 'rctype': None, 'rctoponly': None, 'rctitle': None, 'action': 'query'}
        post2_call_data = {**post1_call_data, 'rccontinue': '20190908072938|4484663', 'continue': '-||'}
        post_patch.assert_has_calls(
            [call(post1_call_data), call(post2_call_data)])

    def test_recentchanges(self):
        run(self.recentchanges_test)


if __name__ == '__main__':
    main()
