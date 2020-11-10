#!/bin/env python3

# mcctl: A Minecraft Server Management Utility written in Python
# Copyright (C) 2020 Matthias Cotting

# This file is part of mcctl.

# mcctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# mcctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with mcctl. If not, see <http://www.gnu.org/licenses/>.

import shlex
import time
import os
import sys
import subprocess as sproc
from pathlib import Path
from pwd import getpwnam
from mcctl import CFGVARS, storage, service
from mcctl.visuals import compute


def attach(instance: str):
    """Attach to the console of a server.

    Launches screen to reattach to the screen session of the server.

    Arguments:
        instance {str} -- The name of the instance.
    """

    assert service.is_active(instance), "The Server is not running"
    cmd = shlex.split('screen -r mc-{}'.format(instance))
    proc = sproc.Popen(cmd)
    proc.wait()


def shell(instance: str, shell_path: Path):
    """Create a shell process in the server directory.

    Launches a shell from the config file.

    Arguments:
        shell_path {Path} -- The Path to the Unix shell binary.
        cwd {str} -- The name of the instance or a subfolder in the Instance.
    """

    if instance:
        sh_cwd = storage.get_instance_path(instance)
        assert sh_cwd.exists(), "Instance or subfolder not found: {}".format(sh_cwd)
    else:
        sh_cwd = storage.get_home_path()

    cmd = shlex.split(shell_path)
    proc = sproc.Popen(cmd, cwd=sh_cwd)
    proc.wait()


def mc_exec(instance: str, command: list, pollrate: float = 0.2, max_retries: int = 25, max_flush_retries: int = 10):
    """Execute a command on the console of a server.

    Uses the 'stuff' command of screen to pass the minecraft command to the server.
    Return Values are read from 'latest.log' shortly after the command is executed.
    The logfile is read every <timeout> seconds. If nothing is appended to the Log after the set amount of <retries>,
    the function exits. If there were already some lines received, the function tries <flush_retries> times before exiting.
    Like this, the function will more likely give an output, and will exit faster if an output was already returned.

    Arguments:
        instance {str} -- The name of the instance.
        command {list} -- A list of the individual parts of the command executed on the server console.

    Keyword Arguments:
        pollrate {float} -- The polling interval between log reads/checks. (default: {0.2})
        max_retries {int} -- The amount of retries when no lines have been pushed to console. (default: {25})
        max_flush_retries {int} -- The amount of retries when some lines have been pushed to console. (default: {10})
    """

    assert service.is_active(instance), "The Server is not running"

    log_path = storage.get_instance_path(instance) / "logs/latest.log"

    file_hnd = open(log_path)
    old_count = sum(1 for line in file_hnd) - 1

    jar_cmd = " ".join(command)
    cmd = shlex.split(
        'screen -p 0 -S mc-{0} -X stuff "^U{1}^M"'.format(instance, jar_cmd))
    proc = sproc.Popen(cmd, preexec_fn=demote()) # nopep8 pylint: disable=subprocess-popen-preexec-fn
    proc.wait()

    i = 0
    while i < max_retries:
        i += 1
        time.sleep(pollrate)
        file_hnd.seek(0)
        for j, line in enumerate(file_hnd):
            if j > old_count:
                i = max_retries - max_flush_retries
                print(line.rstrip())
                old_count += 1
    file_hnd.close()


def get_ids(user: str) -> tuple:
    """Wrapper for getpwnam() that only returns UID and GID.

    Arguments:
        user {str} -- User of which passwd information should be retrieved.

    Returns:
        tuple -- A Tuple containing th UID and GID of the user.
    """
    user_data = getpwnam(user)
    return (user_data.pw_uid, user_data.pw_gid)


def run_as(uid: int, gid: int) -> tuple:
    """Changes the user of the current python Script

    Set the EGID and EUID of the running Python script to the permissions of <as_user>.

    Arguments:
        as_user {str} -- The User of which the UID and GID is used.

    Retruns:
        old_ids {tuple}  -- A tuple of the UID and GID that were set before the change.
    """
    old_ids = (os.geteuid(), os.getegid())

    os.setegid(gid)
    os.seteuid(uid)

    return old_ids


def demote():
    """A Function containing instructions to demote a subprocess.

    Returns:
        NoneType -- Returns a function executed by Popen() before running the external command.
    """
    user_name = CFGVARS.get('settings', 'server_user')
    user = getpwnam(user_name)

    def set_ids():

        if (os.getuid, os.getgid) != (user.pw_uid, user.pw_gid):
            # Set EGID and EUID so that GID and UID can be set correctly.
            os.setegid(0)
            os.seteuid(0)

            os.setgid(user.pw_gid)
            os.setuid(user.pw_uid)

    return set_ids


def pre_start(jar_path: Path, watch_file=None, kill_sec: int = 80) -> bool:
    """Prepares the server and lets it create configuration files and such.

    Starts the server and waits for it to exit or for [watchFile] to be created.
    If the file exists, the server is sent SIGTERM to shut it down again.

    Arguments:
        jar_path {Path} -- Path to the jar-file of the server.

    Keyword Arguments:
        watch_file {Path} -- A file to be awaited for creation. Ignored if set to None. (default: {None})
        kill_sec {int} -- Time to wait before killing the server. (default: {80})

    Returns:
        bool -- True: The server stopped as expected. False: The server had to be killed.
    """

    cmd = shlex.split('/bin/java -jar {}'.format(jar_path))
    proc = sproc.Popen(cmd, cwd=jar_path.parent, stdout=sproc.PIPE,  # nopep8 pylint: disable=subprocess-popen-preexec-fn
                       stderr=sproc.PIPE, preexec_fn=demote())

    fps = 4
    signaled = False
    success = False
    for i in range(kill_sec*fps+1):
        print("\r{} Setting up config files...".format(compute(2)), end="")
        time.sleep(1/fps)
        if not signaled and watch_file is not None and watch_file.exists():
            proc.terminate()
            signaled = True
        elif i == kill_sec * fps:
            proc.kill()
        elif proc.poll() is not None:
            success = True
            break
    print()
    return success


def edit(file_path: Path, editor: str):
    """Attach to the console of a server.

    Launches screen to reattach to the screen session of the server.

    Arguments:
        file_path {Path} -- The file to be edited in the Editor.
    """

    cmd = shlex.split("{0} '{1}'".format(editor, file_path))
    proc = sproc.Popen(cmd, preexec_fn=demote()) # nopep8 pylint: disable=subprocess-popen-preexec-fn
    proc.wait()


def elevate(user="root"):
    """Replaces the current Process with a new one as a different User. Requires sudo.

    Args:
        user (str, optional): The User that will be switched to. Defaults to "root".
    """

    desired_uid = getpwnam(user).pw_uid
    if os.getuid() == desired_uid:
        return

    package = sys.modules.get('__main__', {}).__package__
    if package is None:
        args = sys.argv
    else:
        args = [sys.executable, "-m", package] + sys.argv[1:]

    userargs = ["-u", user] if user != 'root' else []
    sudoargs = ["sudo"] + userargs + args
    os.execvp(sudoargs[0], sudoargs)
