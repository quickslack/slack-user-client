from os import path
from setuptools import setup

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='slack-user-client',
    version='0.0.0.5',
    description="Python Slack client using slack's internal web api",
    long_description=long_description,
    long_description_content_type='text/markdown',
    package_dir={'': 'src'},
    py_modules=['slack_user_client'],
    install_requires=[
        'requests-html>=0.10.0',
    ]
)
