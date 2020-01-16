# Python slack client

## Install
```
pip install https://github.com/quickslack/slack-user-client
```
## Usage
```python
import os
from slack_user_client import SlackClient
username = os.environ.get('SLACK_EMAIL')
password = os.environ.get('SLACK_PASSWORD')
workspace_url = os.environ.get('SLACK_WORKSPACE_URL')
slack = SlackClient(username, password, workspace_url)
slack.login()
messages_data = slack.get_all_messages_from_channel(
    '<CHANNEL_ID>')
for item in messages_data:
    print(item)
```
