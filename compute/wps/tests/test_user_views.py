import random

from django import test

from . import helpers
from wps import models

class UserViewsTestCase(test.TestCase):
    fixtures = ['users.json', 'processes.json', 'files.json']

    def test_user_stats_process_missing_authentication(self):
        response = self.client.get('/auth/user/stats/', {'type': 'process'})

        helpers.check_failed(self, response)
        
    def test_user_stats_process(self):
        user = models.User.objects.first()

        self.client.login(username=user.username, password=user.username)

        response = self.client.get('/auth/user/stats/', {'stat': 'process'})

        data = helpers.check_success(self, response)

        self.assertIn('processes', data['data'])
        self.assertEqual(len(data['data']['processes']), 6)

    def test_user_stats_files_missing_authentication(self):
        response = self.client.get('/auth/user/stats/')

        helpers.check_failed(self, response)

    def test_user_stats_files(self):
        user = models.User.objects.first()

        self.client.login(username=user.username, password=user.username)

        response = self.client.get('/auth/user/stats/')

        data = helpers.check_success(self, response)

        self.assertIn('files', data['data'])
        self.assertEqual(len(data['data']['files']), 133)

    def test_user_details_missing_authentication(self):
        response = self.client.get('/auth/user/')

        helpers.check_failed(self, response)

    def test_user_details(self):
        user = models.User.objects.first()

        self.client.login(username=user.username, password=user.username)

        response = self.client.get('/auth/user/')

        data = helpers.check_success(self, response)['data']

        expected = ('username', 'openid', 'admin', 'local_init', 'api_key', 'type', 'email')

        for exp in expected:
            self.assertIn(exp, data)

    def test_update_missing_authentication(self):
        response = self.client.post('/auth/update/')

        helpers.check_failed(self, response)

    def test_update_invalid(self):
        user = models.User.objects.first()

        self.client.login(username=user.username, password=user.username)

        params = {
            'email': 'notavalidemail',
            'openid': 'http://test',
            'password': 'test2'
        }

        response = self.client.post('/auth/update/', params)

        data = helpers.check_failed(self, response)

    def test_update(self):
        user = models.User.objects.first()

        self.client.login(username=user.username, password=user.username)

        params = {
            'email': 'imdifferent@hello.com',
        }

        response = self.client.post('/auth/update/', params)

        data = helpers.check_success(self, response)['data']

        expected = ('username', 'openid', 'admin', 'local_init', 'api_key', 'type', 'email')

        for exp in expected:
            self.assertIn(exp, data)

            if exp in params:
                self.assertEqual(params[exp], data[exp])

    def test_regenerate_missing_authentication(self):
        response = self.client.get('/auth/user/regenerate/')

        helpers.check_failed(self, response)

    def test_regenerate(self):
        user = models.User.objects.first()

        user.auth.api_key = 'some api key'

        user.auth.save()

        self.client.login(username=user.username, password=user.username)

        response = self.client.get('/auth/user/regenerate/')

        helpers.check_success(self, response)
