import os
import errno
import subprocess


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as e:
        if e.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


def delete_file_silently(env_tempfile):
    try:
        os.remove(env_tempfile)
    except OSError as e:
        if e.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise


def exec_command(command):
    """Shell execute a command and return the exit code as well as the output of that command."""
    stoutdata = sterrdata = ""
    try:
        p = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
        stoutdata, sterrdata = p.communicate()
        stoutdata = stoutdata.decode("utf-8")
    except Exception as e:
        print ("Error: stdout: {} \nstderr: {} \nException:{}".format(
            stoutdata, sterrdata, str(e)))
        return 1, stoutdata
    return p.returncode, stoutdata
