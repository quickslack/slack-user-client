import os
import re
import json
from datetime import datetime
from requests_html import HTMLSession
__version__ = "0.0.0.0"


def now_timestamp():
    '''
    convenience function to get current datetime unix timestamp
    '''
    return datetime.now().timestamp()


class SlackClient:
    '''
    Slack Client using slack's internal web api
    '''

    def __init__(self, email, password, workspace_url):
        self.session = HTMLSession()
        self.email = email
        self.password = password
        self.workspace_url = workspace_url
        self.version_hash = None
        self.workspace_id = None
        self.api_token = None

    def login(self):
        '''
        Login to slack using initialized credentials
        '''
        email = self.email
        password = self.password
        workspace_url = self.workspace_url

        headers = {
            'content-type': 'application/x-www-form-urlencoded',
        }

        # check the login page for csrf token
        res = self.session.get(workspace_url)
        crumb = res.html.find(
            '#signin_form input[name="crumb"]', first=True).attrs['value']

        login_payload = {
            'signin': 1,
            'redir': '/gantry/client',
            'has_remember': 1,
            'crumb': crumb,
            'email': email,
            'password': password,
            'remember': 'on'
        }

        # login to get auth cookies, version hash and workspace id
        res = self.session.post(
            workspace_url, headers=headers, data=login_payload)
        self.version_hash = res.html.find(
            'html', first=True).attrs['data-version-hash']
        self.workspace_id = res.url.split('/')[-1]
        # use auhtenticated session cookie to get the api token
        url_params = {
            'app': 'client',
            'lc': int(datetime.now().timestamp()),
            'return_to': f'/client/{self.workspace_id}',
            'teams': '',
            'iframe': 1
        }
        res = self.session.get('https://app.slack.com/auth', params=url_params)
        match = re.search(r"JSON\.stringify\((.+?)\);", res.text)
        auth_data = data = json.loads(match.group(1))
        self.api_token = auth_data['teams'][self.workspace_id]['token']

    def get_messages_from_channel(
            self,
            channel_id,
            oldest=None,
            latest=None,
            ignore_replies=True,
            inclusive=False,
            limit=100):
        timestamp = now_timestamp()
        endpoint = f'{self.workspace_url}/api/conversations.history'
        url_params = {
            '_x_id': f'{self.version_hash[:8]}-{timestamp}',
            'x_version_ts': int(timestamp),
            '_x_gantry': 'true',
        }
        form_data = {
            'channel': (None, channel_id),
            'limit': (None, str(limit)),
            'latest': (None, str(timestamp)),
            'token': (None, self.api_token),
            'ignore_replies': (None, 'true' if ignore_replies else 'false'),
            'inclusive': (None, 'true' if inclusive else 'false'),
            'include_pin_count': (None, 'false'),
            'no_user_profile': (None, 'true'),
        }

        if latest:
            form_data['latest'] = (None, str(latest))
        if oldest:
            form_data['oldest'] = (None, (oldest))

        res = self.session.post(endpoint, params=url_params, files=form_data)
        return res.json()

    def get_all_messages_from_channel(self, channel_id, **kwargs):
        messages = []
        # Fetch messages until there's no more of them
        while True:
            message_data = self.get_messages_from_channel(channel_id, **kwargs)
            messages.extend(message_data['messages'])
            kwargs['latest'] = message_data['messages'][-1]['ts']
            if not message_data['has_more']:
                break
        return messages
