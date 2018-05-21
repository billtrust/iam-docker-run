import uuid
import boto3
from botocore.exceptions import ClientError
from .aws_util_exceptions import RoleNotFoundError
from .aws_util_exceptions import AwsUtilError


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


def generate_aws_temp_creds(role_name, profile=None):
    """Generate AWS temporary credentials with the given role and return
    the access key, secret key, and session token in a tuple.  Uses the
    AWS creds in the environment to assume the role, or a specific AWS
    profile name if provided."""
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()

    sts_client = session.client('sts')
    iam_client = session.client('iam')

    try:
        role_arn = iam_client.get_role(RoleName=role_name)['Role']['Arn']
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchEntity':
            method = get_credential_method_description(session)
            raise RoleNotFoundError(method, e)
        else:
            raise AwsUtilError("Error reading role arn for role name {}: {}".format(role_name, e))
    except Exception as e:
        raise AwsUtilError("Error reading role arn for role name {}: {}".format(role_name, e))

    try:
        random_session = uuid.uuid4().hex
        assumed_role_object = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="docker-session-{}".format(random_session),
            DurationSeconds=3600  # 1 hour max
        )
        access_key = assumed_role_object["Credentials"]["AccessKeyId"]
        secret_key = assumed_role_object["Credentials"]["SecretAccessKey"]
        session_token = assumed_role_object["Credentials"]["SessionToken"]
    except Exception as e:
        raise AwsUtilError("Error assuming role {}: {}".format(role_arn, e))

    return access_key, secret_key, session_token, role_arn
