import sys
import os
import re
from setuptools import setup, find_packages

# 'setup.py publish-test' shortcut
if sys.argv[-1] == 'publish-test':
    os.system('rm -r dist/*')
    os.system('python setup.py sdist')
    os.system('twine upload -r pypitest dist/*')
    sys.exit()
# 'setup.py publish' shortcut
if sys.argv[-1] == 'publish':
    os.system('rm -r dist/*')
    os.system('python setup.py sdist')
    os.system('twine upload dist/*')
    sys.exit()

# read the version number from source
version = re.search(
    "^__version__\s*=\s*'(.*)'",
    open('iam_docker_run/iam_docker_run.py').read(),
    re.M
    ).group(1)

# Get the long description from the relevant file
try:
    # in addition to pip install pypandoc, might have to: apt install -y pandoc
    import pypandoc
    long_description = pypandoc.convert('README.md', 'rst')
except (IOError, ImportError) as e:
    print("Error converting READMD.md to rst:", str(e))
    long_description = open('README.md').read()

setup(name='iam-docker-run',
      version=version,
      description='Run Docker containers within the context of an AWS IAM Role, and other development workflow helpers.',
      long_description=long_description,
      keywords=['aws', 'iam', 'iam-role', 'docker'],
      author='Doug Kerwin',
      author_email='dkerwin@billtrust.com',
      url='https://github.com/billtrust/iam-docker-run',
      install_requires=[
        'boto3>=1.7.20, <2.0',
        'botocore>=1.10.20, <2.0'
        ],
      packages=find_packages(),
      entry_points={
        "console_scripts": [
            'iam-docker-run = iam_docker_run.iam_docker_run:main',
            'idr = iam_docker_run.iam_docker_run:main'
        ]
        },
      license='MIT',
      classifiers=[
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        ]
     )
