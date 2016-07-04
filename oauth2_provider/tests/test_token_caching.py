from __future__ import unicode_literals

import json

import mock
from django.contrib.auth import get_user_model
from django.core.urlresolvers import reverse
from django.test import TestCase, RequestFactory

from .test_utils import TestCaseUtils
from ..models import get_application_model
from ..settings import oauth2_settings

Application = get_application_model()
UserModel = get_user_model()


class CacheTest(TestCaseUtils, TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.test_user = UserModel.objects.create_user("test_user", "test@user.com", "123456")

        self.application = Application(
            name="Test Application",
            user=self.test_user,
            client_type=Application.CLIENT_CONFIDENTIAL,
            client_id="test_client_id",
            authorization_grant_type=Application.GRANT_PASSWORD,
            client_secret="test_client_secret",
            scopes="test_app_scope1 test_app_scope2"
        )
        self.application.save()

        oauth2_settings._SCOPES = ['read', 'write']

    def tearDown(self):
        self.application.delete()
        self.test_user.delete()


class TestTokenCaching(CacheTest):
    def test_caching_tokens(self):
        token_request_data = {
            'username': "test_user",
            'password': "123456",
            'grant_type': 'password'
        }
        auth_headers = self.get_basic_auth_header(self.application.client_id, self.application.client_secret)

        with mock.patch('oauth2_provider.oauth2_validators.oauth2_settings.redis_server') as mock_redis:
            response = self.client.post(reverse('oauth2_provider:token'), data=token_request_data, **auth_headers)

            self.assertTrue(response.status_code, 200)
            content = json.loads(response.content.decode("utf-8"))
            access_token = content['access_token']
            refresh_token = content['refresh_token']
            self.assertIsNotNone(access_token)

            mock_redis.expire.assert_called_once()
            mock_redis.hmset.assert_called_once_with(access_token, mock.ANY)
            # TODO Fix this after adding user id in cache
            #self.assertEquals("test_user" in str(mock_redis.hmset.call_args_list), "Username from Redis doesn't match")
            self.assertEqual(refresh_token in str(mock_redis.hmset.call_args_list), True,
                             "Refresh token from Redis doesn't match")
            self.assertEqual("test_app_scope1" in str(mock_redis.hmset.call_args_list), True,
                             "Test App scope not found")
