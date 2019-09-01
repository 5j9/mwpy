from asyncio import run
from unittest.mock import patch, call
from unittest import main, TestCase
from mwpy import API


async def fake_token_post():
    return {'query': {'tokens': {'logintoken': None}}}


async def fake_login_post():
    return


class APITest(TestCase):

    @staticmethod
    async def login_test():
        async with API('https://www.mediawiki.org/w/api.php') as api:
            with patch.object(
                api, 'post',
                side_effect=(fake_token_post(), fake_login_post()),
            ) as post_patch:
                await api.login('U', 'P')
            post_patch.assert_has_calls((
                call({'action': 'query', 'meta': 'tokens', 'type': 'login'}),
                call({
                    'action': 'login', 'lgname': 'U', 'lgpassword': 'P',
                    'lgdomain': '', 'lgtoken': None})))

    def test_login(self):
        run(self.login_test())


if __name__ == '__main__':
    main()
