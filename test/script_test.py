import unittest
import os
import sys
import boto3
import json
import time
import logging
from scripttest import TestFileEnvironment


class TestIamDockerRun(unittest.TestCase):
    def setUp(self):
        # silence boto debug output to make output more readable
        logging.getLogger('boto').setLevel(logging.ERROR)
        logging.getLogger('botocore').setLevel(logging.ERROR)

        self._policy_name = 'policy-iam-docker-run-test'
        self._role_name   = 'role-iam-docker-run-test'
        self._profile     = os.environ.get('AWS_PROFILE', 'dev')
        self._ssm_path    = '/dev/iam-docker-run-test/'

        self.create_test_aws_resources()


    def tearDown(self):
        pass


#
# Setup/teardown helper functions
#


    def iam_policy_exists(self, policy_arn):
        client = boto3.client('iam')
        try:
            _ = client.get_policy(PolicyArn=policy_arn)
        except client.exceptions.NoSuchEntityException:
            return False
        except Exception as e:
            raise
        return True


    def iam_role_exists(self, role_name):
        client = boto3.client('iam')
        try:
            _ = client.get_role(RoleName=role_name)
        except client.exceptions.NoSuchEntityException:
            return False
        except Exception as e:
            raise
        return True


    def create_test_aws_resources(self):
        aws_account_id    = boto3.client('sts').get_caller_identity()['Account']
        aws_region        = os.environ.get('AWS_REGION', 'us-east-1')

        iam_client = boto3.client('iam')

        policy_arn = "arn:aws:iam::{}:policy/{}".format(aws_account_id, self._policy_name)
        if not self.iam_policy_exists(policy_arn):
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "ssm:GetParameter*",
                        "Resource": "arn:aws:ssm:{}:{}:parameter{}*".format(aws_region, aws_account_id, self._ssm_path)
                    }
                ]
            }
            _ = iam_client.create_policy(
                PolicyName=self._policy_name,
                Path='/',
                PolicyDocument=json.dumps(policy),
                Description='For integration testing of iam-docker-run'
            )
        if not self.iam_role_exists(self._role_name):
            assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": [
                        "arn:aws:iam::{}:root".format(aws_account_id)
                        ]
                    },
                    "Action": "sts:AssumeRole"
                    }
                ]
            }
            _ = iam_client.create_role(
                Path='/',
                RoleName=self._role_name,
                AssumeRolePolicyDocument=json.dumps(assume_role_policy),
                Description='For integration testing of iam-docker-run'
            )
            _ = iam_client.attach_role_policy(
                RoleName=self._role_name,
                PolicyArn=policy_arn
            )

        ssm = boto3.client('ssm')
        ssm.put_parameter(
            Name="{}TEST".format(self._ssm_path),
            Value='Used for integration testing of iam-docker-run',
            Type='String',
            Overwrite=True
        )
        # give AWS some time to implement the IAM changes
        time.sleep(3)



#
# Tests
#

    def test_correctly_assumes_role_with_profile(self):
        awscli_command = "aws ssm get-parameter --name {}TEST --query 'Parameter.Value' --output text".format(self._ssm_path)
        command = [
            'iam-docker-run',
            '--role {}'.format(self._role_name),
            '--profile {}'.format(self._profile),
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"{}\"".format(awscli_command)
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command))
        assert 'Used for integration testing' in result.stdout


    def test_correctly_assumes_profile_without_role(self):
        awscli_command = "aws ssm get-parameter --name {}TEST --query 'Parameter.Value' --output text".format(self._ssm_path)
        command = [
            'iam-docker-run',
            '--profile {}'.format(self._profile),
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"{}\"".format(awscli_command)
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command))
        assert 'Used for integration testing' in result.stdout


    # todo
    # def test_correctly_assumes_role_without_profile(self):
    #     pass

    def test_fails_to_assume_role_without_profile_and_local_env_creds(self):
        awscli_command = "aws ssm get-parameter --name {}TEST --query 'Parameter.Value' --output text".format(self._ssm_path)
        command = [
            'iam-docker-run',
            '--role {}'.format(self._role_name),
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"{}\"".format(awscli_command)
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command), expect_error=True)
        assert not 'Used for integration testing' in result.stdout
        assert 'no AWS credentials found in the environment' in result.stdout


    def test_volume_mounts(self):
        testfile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), './test-input'))
        print("testfile_path: {}".format(testfile_path))
        if not os.path.exists(testfile_path):
            os.mkdir(testfile_path)
        file = open(os.path.join(testfile_path, "testfile.txt"), "w")
        file.write("Test text file")
        file.close()
        command = [
            'iam-docker-run',
            '--role {}'.format(self._role_name),
            '--profile {}'.format(self._profile),
            '-v {}:/app'.format(testfile_path),
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"cat /app/testfile.txt\""
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command))
        assert 'Test text file' in result.stdout


    def test_envvar_arguments(self):
        command = [
            'iam-docker-run',
            '--role {}'.format(self._role_name),
            '--profile {}'.format(self._profile),
            '-e TESTENVARG=MyTestEnvArg',
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"printenv TESTENVARG\""
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command))
        assert 'MyTestEnvArg' in result.stdout


    def test_envvar_arguments_without_role(self):
        command = [
            'iam-docker-run',
            '-e TESTENVARG=MyTestEnvArg',
            '--image mesosphere/aws-cli:latest',
            "--full-entrypoint \"printenv TESTENVARG\""
        ]
        env = TestFileEnvironment('./test-output')
        result = env.run(' '.join(command))
        assert 'MyTestEnvArg' in result.stdout
