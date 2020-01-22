import re
import json
from datetime import datetime
from requests_html import HTMLSession
from multiprocessing.dummy import Pool
from itertools import chain
import time
import logging
from requests.adapters import HTTPAdapter

__version__ = "0.0.0.4"


def val_to_str(value):
    if value is None:
        return ''
    if type(value) == bool:
        return 'true' if value else 'false'
    return str(value)


def val_to_form_str(value):
    return None, val_to_str(value)


def now_timestamp():
    """
    convenience function to get current datetime unix timestamp
    """
    return datetime.now().timestamp()


class SlackClient:
    """
    Slack Client using slack's internal web api
    """

    def __init__(self, email, password, workspace_url):
        self.session = HTMLSession()
        self.session.mount('https://', HTTPAdapter(max_retries=8))
        self.email = email
        self.password = password
        self.workspace_url = workspace_url
        self.version_hash = None
        self.workspace_id = None
        self.api_token = None
        self.auth_url_params = {}
        self.rate_limit = 0.1
        self.logger = logging.getLogger('slack-user-client')
        self.logger.info("Slack Client Initialized.")

    def login(self):
        """
        Login to slack using initialized credentials
        """
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
        # use authenticated session cookie to get the api token
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
        # Setup base url parameters
        timestamp = now_timestamp()
        self.auth_url_params = {
            '_x_id': f'{self.version_hash[:8]}-{timestamp}',
            'x_version_ts': int(timestamp),
            '_x_gantry': 'true',
        }

    def _auth_session_export(self, path):
        # todo
        pass

    def _auth_session_import(self, path):
        # todo
        pass

    def _api_post(self, api_path, **kwargs):
        kwargs.update({'token': self.api_token})
        form_data = {k: val_to_form_str(kwargs[k]) for k in kwargs.keys()}
        endpoint = f'{self.workspace_url}/api/{api_path}'
        url_params = self.auth_url_params
        res = self.session.post(endpoint, params=url_params, files=form_data)
        time.sleep(self.rate_limit)
        retval = res.json()
        if retval.get('error') == 'ratelimited':
            self.logger.info("Rate limited, sleeping for 15 seconds")
            # use new token
            self.session = HTMLSession()
            self.session.mount('https://', HTTPAdapter(max_retries=8))
            self.login()
            return self._api_post(api_path, **kwargs)
        return retval

    def get_messages_from_channel(
            self, channel, limit=100, latest=9999999999, ignore_replies=True,
            inclusive=False, include_pin_count=False, no_user_profile=False,
            **kwargs):
        return self._api_post('conversations.history',
                              channel=channel,
                              limit=limit,
                              latest=latest,
                              ignore_replies=ignore_replies,
                              inclusive=inclusive,
                              include_pin_count=include_pin_count,
                              no_user_profile=no_user_profile,
                              **kwargs
                              )

    def get_all_messages_from_channel(self, channel_id, **kwargs):
        messages = []
        # Fetch messages until there's no more of them
        while True:
            message_data = self.get_messages_from_channel(channel_id, **kwargs)
            messages.extend(message_data['messages'])
            if not message_data['has_more']:
                break
            kwargs['latest'] = message_data['messages'][-1]['ts']
        return messages

    def channel_search(
            self, query='', page=1, sort='created', sort_dir='desc',
            exclude_my_channels=0, only_my_channel=0,
            browse='standard', channel_type='exclude_archive', **kwargs):

        return self._api_post(
            'search.modules', module='channels', query=query,
            page=page, sort=sort, sort_dir=sort_dir,
            exclude_my_channels=exclude_my_channels,
            only_my_channel=only_my_channel, browse=browse,
            channel_type=channel_type, ** kwargs)

    def get_all_channels(self, threads=8):
        # get first page to obtain info about # of pages
        first_page = self.channel_search()
        channels = first_page['items']

        def get_page_item(page):
            return self.channel_search('', page)['items']

        page_count = first_page['pagination']['page_count']
        # get all remaining channels
        pool = Pool(threads)
        channels.extend(
            chain(*pool.map(get_page_item, range(2, page_count+1))))
        return channels

    def get_replies(self, channel, ts, oldest, inclusive=True, limit=400):
        return self._api_post(
            'conversations.replies', channel=channel, ts=ts, oldest=oldest,
            inclusive=True,
        )

    def get_all_replies(self, channel, ts):
        replies = []
        oldest = ts
        while True:
            res = self.get_replies(channel, ts, oldest)
            replies.extend(res.get('messages') or [])
            if not res.get('has_more'):
                break
            oldest = res['messages'][-1]

        return replies

    def get_boot_data(self):
        return self._api_post(
            'client.boot', only_self_substreams=1, flannel_api_ver=4,
            include_min_version_bump_check=1, version_ts=now_timestamp())
