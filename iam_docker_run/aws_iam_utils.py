import os
import uuid
import boto3
from six.moves import configparser
from botocore.exceptions import ClientError
from .aws_util_exceptions import ProfileParsingError
from .aws_util_exceptions import RoleNotFoundError
from .aws_util_exceptions import AssumeRoleError


def get_aws_account_id(profile=None):
    if profile:
        session = boto3.Session(profile_name=profile)
        client = session.client('sts')
    else:
        client = boto3.client('sts')
    account_id = client.get_caller_identity()['Account']
    return account_id


def get_credential_method_description(session):
    """Provides a helpful message describing the current IAM execution context."""
    profile = ''
    try:
        profile = session.profile_name
    except:
        pass
    try:
        credentials = session.get_credentials()
        return "{} ({}{})".format(
            credentials.method,
            "profile {} -> ".format(profile) if profile != 'default' else '',
            credentials.access_key
        )
    except:
        return 'error describing session credentials'


def get_boto3_session(aws_creds):
    if aws_creds:
        session_token = None
        if 'AWS_SESSION_TOKEN' in aws_creds:
            session_token = aws_creds['AWS_SESSION_TOKEN']
        return boto3.Session(
            aws_access_key_id=aws_creds['AWS_ACCESS_KEY_ID'],
            aws_secret_access_key=aws_creds['AWS_SECRET_ACCESS_KEY'],
            aws_session_token=session_token,
        )
    else:
        return boto3.Session()


def get_aws_profile_credentials(profile_name, verbose=False):
    aws_creds = {}
    # the source_profile may be overridden if a source_profile is indicated in ~/.aws/config
    source_profile = profile_name

    config = configparser.ConfigParser()
    config_file_path = os.path.join(os.path.expanduser("~"),'.aws/config')
    config.read([config_file_path])

    try:
        section = 'profile {}'.format(profile_name)
        if not config.has_section(section):
            msg = "Profile {} not found in {}".format(profile_name, config_file_path)
            raise ProfileParsingError(msg)

        if not config.has_option(section, 'role_arn'):
            if verbose:
                print("Profile {} in ~/.aws/config does not indicate a role_arn".format(profile_name))
        else:
            aws_creds['role_arn'] = config.get(section, 'role_arn')
            print("Profile {} indicates role to assume: {}".format(profile_name, aws_creds['role_arn']))
            if config.has_option(section, 'source_profile'):
                source_profile = config.get(section, 'source_profile')
                print("Found profile {} in ~/.aws/config, indicated source_profile {}".format(
                    profile_name, source_profile
                ))
            else:
                msg = "Profile {} in ~/.aws/config does not indicate a source_profile needed to assume role {}".format(
                    profile_name, aws_creds['role_arn']
                )
                raise ProfileParsingError(msg)
    except configparser.ParsingError:
        print('Error parsing AWS config file')
        raise
    except (configparser.NoSectionError, configparser.NoOptionError):
        print('Error parsing sections or options for AWS profile {} in {}'.format(
            profile_name,
            config_file_path))
        raise

    credentials = configparser.ConfigParser()
    credentials_file_path = os.path.join(os.path.expanduser("~"),'.aws/credentials')
    credentials.read([credentials_file_path])

    try:
        aws_creds['AWS_ACCESS_KEY_ID'] = credentials.get(source_profile, 'aws_access_key_id')
        aws_creds['AWS_SECRET_ACCESS_KEY'] = credentials.get(source_profile, 'aws_secret_access_key')
        try:
            aws_creds['AWS_SESSION_TOKEN'] = credentials.get(source_profile, 'aws_session_token')
        except:
            pass
        if verbose:
            print("Found source profile {} in ~/.aws/credentials, access key: {}".format(
                source_profile, aws_creds['AWS_ACCESS_KEY_ID']
            ))
    except configparser.ParsingError:
        print('Error parsing AWS credentials file')
        raise
    except (configparser.NoSectionError, configparser.NoOptionError):
        print('Unable to find AWS profile named {} in {}'.format(
            profile_name,
            credentials_file_path))
        raise
    return aws_creds


def get_role_arn_from_name(aws_creds, role_name, verbose=False):
    try:
        session = get_boto3_session(aws_creds)
        iam_client = session.client('iam')
        role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
        return role_arn
    except ClientError as e:
        if verbose:
          print(e)
        method = get_credential_method_description(session)
        if e.response['Error']['Code'] == 'NoSuchEntity':
            raise RoleNotFoundError(method, e)
        else:
            raise AssumeRoleError(method, "Error reading role arn for role name {}: {}".format(role_name, e))
    except Exception as e:
        if verbose:
          print(e)
        method = get_credential_method_description(session)            
        raise AssumeRoleError(method, "Error reading role arn for role name {}: {}".format(role_name, e))


def generate_aws_temp_creds(role_arn, aws_creds=None, verbose=False):
    session = get_boto3_session(aws_creds)
    sts_client = session.client('sts')

    aws_creds = {}
    try:
        random_session = uuid.uuid4().hex
        assumed_role_object = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="iamstarter-session-{}".format(random_session),
            DurationSeconds=3600  # 1 hour max
        )
        aws_creds['AWS_ACCESS_KEY_ID'] = assumed_role_object["Credentials"]["AccessKeyId"]
        aws_creds['AWS_SECRET_ACCESS_KEY'] = assumed_role_object["Credentials"]["SecretAccessKey"]
        aws_creds['AWS_SESSION_TOKEN'] = assumed_role_object["Credentials"]["SessionToken"]
    except Exception as e:
        if verbose:
          print(e)
        method = get_credential_method_description(session)
        raise AssumeRoleError(method, "Error assuming role {}: {}".format(role_arn, e))

    return aws_creds
