# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import re
import sys
import argparse
import tempfile
from string import Template
from . import aws_iam_utils
from . import docker_cli_utils
from . import shell_utils
from .aws_util_exceptions import RoleNotFoundError
from .docker_cli_utils import DockerCliUtilError


DEFAULT_CUSTOM_ENV_FILE = 'iam-docker-run.env'
VERBOSE_MODE = False


def single_line_string(string):
    # replace all runs of whitespace to a single space
    string = re.sub('\s+', ' ', string)
    # remove newlines
    string = string.replace('\n', '')
    # remove leading/trailing whitespace
    string = string.strip()
    return string


def generate_temp_env_file(
    access_key,
    secret_key,
    session_token,
    region,
    custom_env_file,
    custom_env_args):
    """Write out a file with the environment variables for the AWS credentials which can be passed
    into Docker.  If additional environment variables beyond the AWS creds are desired you can
    also specify a custom_env_file which contains them."""
    envs = []
    if custom_env_file:
        if custom_env_file == DEFAULT_CUSTOM_ENV_FILE:
            if not os.path.isfile(custom_env_file):
                if VERBOSE_MODE:
                    print("{} does not exist".format(custom_env_file))
                # silently ignore when default custom env file is missing
                custom_env_file = None
    if custom_env_file:
        try:
            custom_envs = open(custom_env_file, "r")
            envs = custom_envs.read().splitlines()
            custom_envs.close()
        except Exception as e:
            print("Error processing custom environment variables file {}: {}".format(
                custom_env_file, str(e)))
    if custom_env_args:
        for env_arg in custom_env_args:
            envs.append(env_arg)
    envs.append('AWS_ACCESS_KEY_ID=' + access_key)
    envs.append('AWS_SECRET_ACCESS_KEY=' + secret_key)
    envs.append('AWS_SESSION_TOKEN=' + session_token)
    envs.append('AWS_DEFAULT_REGION=' + region)
    envs.append('AWS_REGION=' + region)
    # ensure stdout flows to docker unbuffered
    envs.append('PYTHONUNBUFFERED=1')

    try:    
        temp_env_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        for item in envs:
            temp_env_file.write('{}\n'.format(item))
        temp_env_file.close()
        print('Temp env file: {}'.format(temp_env_file.name))
    except Exception as e:
        print("Error writing temp env file: {}".format(str(e)))
        raise
    return temp_env_file.name


def build_docker_run_command(args, container_name, env_tmpfile):
    if args.shell:
        shell_cmd = os.environ.get('IAM_DOCKER_RUN_SHELL_COMMAND', '/bin/bash')
        entrypoint = '--entrypoint {}'.format(shell_cmd)
        cmd = ''
    elif args.full_entrypoint:
        entrypoint = '--entrypoint {}'.format(args.full_entrypoint.split(' ')[0])
        cmd = ' '.join(args.full_entrypoint.split(' ')[1:])
    else:
        entrypoint = args.entrypoint or ''
        cmd = args.cmd or ''

    if args.detached:
        runmode = '-d'
    elif args.interactive:
        runmode = '-it'
    else:
        runmode = ''
    if args.shell:
        if runmode:
            print('WARNING: --shell specified, overriding runmode to -it')
        runmode = '-it'

    p = ''
    if args.portmaps:
        for portmap in args.portmaps:
            p += '-p {} '.format(portmap)

    if not os.path.exists(env_tmpfile):
        env_tmpfile = None

    sourcecode_volume_mount = None
    if args.host_source_path and args.container_source_path:
        sourcecode_volume_mount = '-v {}:{}'.format(
            os.path.abspath(args.host_source_path),
            args.container_source_path)
    # http://www.projectatomic.io/blog/2015/06/using-volumes-with-docker-can-cause-problems-with-selinux/
    if args.selinux:
        sourcecode_volume_mount += ':Z'
    dns = "--dns {}".format(args.dns) if args.dns else None
    dns_search = "--dns-search {}".format(args.dns_search) if args.dns_search else None
    docker_volume = '-v /var/run/docker.sock:/var/run/docker.sock'
    additional_volume_mounts = ''
    if args.volumes:
        for volume in args.volumes:
            additional_volume_mounts += "-v {}".format(volume)

    command = Template(single_line_string("""
        docker run
            $runmode
            --name $container_name
            $p
            $env_file
            $sourcecode_volume
            $additional_volumes
            $mount_docker
            $entrypoint
            $dns
            $dns_search
            $image
            $cmd
        """)) \
        .substitute({
            'runmode': runmode,
            'container_name': container_name,
            'p': p,
            'env_file': "--env-file {}".format(env_tmpfile) if env_tmpfile else '',
            'sourcecode_volume': sourcecode_volume_mount if sourcecode_volume_mount else '',
            'additional_volumes': additional_volume_mounts,
            'mount_docker': docker_volume if args.mount_docker else '',
            'entrypoint': entrypoint,
            'dns': dns or '',
            'dns_search': dns_search or '',
            'image': args.image,
            'cmd': cmd
        })
    return command


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True,
                        help='The full name of the docker repo/image')
    parser.add_argument('--role', '--aws-role-name', dest='aws_role_name',
                        help='The AWS IAM role name to assume when running this container')
    parser.add_argument('--custom-env-file', default=DEFAULT_CUSTOM_ENV_FILE,
                        help='Optional file that contains environment variables to map into the container.')
    parser.add_argument('-e', '--envvar', required=False,
                        action="append", dest="envvars",
                        help='Equivalent of docker -e, additive with --custom-env-file')
    parser.add_argument('--profile',
                        help='The AWS creds used on your laptop to generate the STS temp credentials')
    parser.add_argument('--host-source-path', required=False,
                        help='The path (can be relative) to your source code from your laptop to mount into the container.')
    parser.add_argument('--container-source-path', required=False,
                        help='The path (absolute) where your source code will be mounted into the container.')
    parser.add_argument('--selinux', action='store_true', default=False,
                        help='Work around SELinux volume mount issues for source code volume')
    parser.add_argument('-v', '--volume', required=False,
                        action="append", dest="volumes",
                        help='Passthrough to docker -v, additive with default src/app volume mount')
    parser.add_argument('--mount-docker', action='store_true', default=False,
                        help='Mount the docker sock volume to enable DIND')
    parser.add_argument('--no-volume', action='store_true', default=False,
                        help='Deprecated, there is no longer any default volume mount to suppress')
    parser.add_argument('--full-entrypoint',
                        help='The full entrypoint to override, multiple words are okay')
    parser.add_argument('--entrypoint', required=False,
                        help='Passthrough to docker run --entrypoint')
    parser.add_argument('--cmd', required=False,
                        help='Passthrough to docker command')
    parser.add_argument('--dns', required=False,
                        help='Passthrough to docker --dns')
    parser.add_argument('--dns-search', required=False,
                        help='Passthrough to docker --dns-search')
    parser.add_argument('-p', '--portmap', required=False,
                        action="append", dest="portmaps",
                        help='Passthrough to docker -p, e.g. 8080:80')
    parser.add_argument('-d', '--detached', default=False,
                        action='store_true', dest="detached",
                        help='Run Docker in detached mode')
    parser.add_argument('--interactive', action='store_true', default=False,
                        help='Run Docker in interactive terminal mode (-it)')
    parser.add_argument('--shell', action='store_true', default=False)
    parser.add_argument('--region', required=False)
    parser.add_argument('--verbose', action='store_true', default=False)
    return parser


def main():
    here = os.path.abspath(os.path.dirname(__file__))
    about = {}
    with open(os.path.join(here, 'version.py'), 'r') as f:
        exec(f.read(), about)

    print('IAM-Docker-Run version {}'.format(about['__version__']))

    parser = create_parser()
    args = parser.parse_args()

    if args.verbose:
        global VERBOSE_MODE
        VERBOSE_MODE = True

    region = args.region or \
             os.environ.get('AWS_REGION',
             os.environ.get('AWS_DEFAULT_REGION', 'us-east-1'))

    if args.no_volume:
        print("WARNING: --no-volume is deprecated, there is no longer any default volume mount")

    env_tmpfile = ''
    if args.aws_role_name:
        try:
            access_key, secret_key, session_token, role_arn = \
                aws_iam_utils.generate_aws_temp_creds(args.aws_role_name, args.profile)
            if VERBOSE_MODE:
                print("Role arn: {}".format(role_arn))
            print("Generated temporary AWS credentials: {}".format(access_key))
        except RoleNotFoundError as e:
            if VERBOSE_MODE:
                print(str(e))
            try:
                account_id = aws_iam_utils.get_aws_account_id(args.profile)
            except Exception as e:
                if VERBOSE_MODE:
                    print("Error retrieving AWS Account ID: {}".format(str(e)))
                account_id = 'error'
            print("IAM role '{}' not found in account id {}, credential method: {}".format(
                args.aws_role_name,
                account_id,
                e.credential_method
            ))
            sys.exit(1)

        env_tmpfile = generate_temp_env_file(
            access_key,
            secret_key,
            session_token,
            region,
            args.custom_env_file,
            args.envvars
            )
 
    container_name = docker_cli_utils.random_container_name()
    if os.environ.get('IAM_DOCKER_RUN_DISABLE_CONTAINER_NAME_TEMPFILE', None):
        print('Container name temp file writing is disabled')
    else:
        try:
            path_prefix = os.environ.get(
                'IAM_DOCKER_RUN_CONTAINER_NAME_PATH_PREFIX', 'temp')
            container_name_file = \
                docker_cli_utils.write_container_name_temp_file(container_name, path_prefix)
            print("Container name file: {}".format(container_name_file))
        except docker_cli_utils.ContainerNameTempFileError as e:
            if VERBOSE_MODE:
                print("Error writing container name temporary file")

    docker_run_command = build_docker_run_command(
        args,
        container_name,
        env_tmpfile if env_tmpfile else args.custom_env_file)

    print(docker_run_command)
    os.system(docker_run_command)

    exit_code = None
    if not args.detached:
        try:
            exit_code = docker_cli_utils.get_docker_inspect_exit_code(container_name)
            print("Container exited with code {}".format(exit_code))
        except DockerCliUtilError as e:
            print(e)
            sys.exit(1)
        print("Removing container: {}".format(container_name))
        docker_cli_utils.remove_docker_container(container_name)

    if env_tmpfile:
        shell_utils.delete_file_silently(env_tmpfile)
    
    sys.exit(exit_code if exit_code else 0)
