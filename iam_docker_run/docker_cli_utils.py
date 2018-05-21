import os
import uuid
from . import shell_utils


class ContainerNameTempFileError(Exception):
    pass


class DockerCliUtilError(Exception):
    pass


def get_docker_inspect_exit_code(container_name):
    """Retrieve the exit code of the main process inside the docker container (rather
    than the exit code of Docker itself), given the container name."""
    inspect_command = "docker inspect {} --format='{{{{.State.ExitCode}}}}'".format(
        container_name)
    returncode, output = shell_utils.exec_command(inspect_command)
    if not returncode == 0:
        raise DockerCliUtilError("Error from docker (docker exit code {}) inspect trying to get container exit code, output: {}".format(returncode, output))

    try:
        container_exit_code = int(output.replace("'", ""))
    except Exception:
        raise DockerCliUtilError("Error parsing exit code from docker inspect, raw output: {}".format(output))

    # pass along the exit code from the container
    return container_exit_code


def remove_docker_container(container_name):
    """Remove the Docker container given its name."""
    remove_command = "docker rm {}".format(container_name)
    exit_code = os.system(remove_command)
    if not exit_code == 0:
        raise DockerCliUtilError("Error removing named container! Run 'docker container prune' to cleanup manually.")


def random_container_name():
    """Generate a unique name for the container."""
    return uuid.uuid4().hex


def write_container_name_temp_file(container_name, path_prefix):
    """If the container name is needed for anything downstream such as the code
    debugging inside the container feature of VSCode, we'll need to make the
    container name discoverable by writing it to a file in a pre-determined location."""
    last_part_cwd = os.path.basename(os.path.normpath(os.getcwd()))
    temp_filename = os.path.join(os.sep, path_prefix, last_part_cwd, '_container_name.txt')
    temp_filename_path = os.path.dirname(temp_filename)
    try:
        if temp_filename_path:
            shell_utils.mkdir_p(temp_filename_path)
        with open(temp_filename, "w") as f:
            f.write(container_name)
    except Exception:
        raise ContainerNameTempFileError
    return temp_filename
