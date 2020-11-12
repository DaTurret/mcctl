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
# along with mcctl. If not, see <http:// www.gnu.org/licenses/>.

import gzip
import sys
import os
import shutil
import random
import string
import hashlib
import zipfile as zf
from pathlib import Path
from datetime import datetime
from pwd import getpwnam
from mcctl import service, config, CFGVARS

SERVER_USER = CFGVARS.get('settings', 'server_user')


def get_home_path(user_name: str = SERVER_USER) -> Path:
    """Wrapper to return the home Directory of a user

    Arguments:
        user_name {str} -- The username of which the home directory should be determined.

    Returns:
        Path -- The home directory of the user.
    """

    user_data = getpwnam(user_name)
    return Path(user_data.pw_dir)


def get_instance_path(instance: str = '', bare: bool = False) -> Path:
    """Return the assembled absolute Instance Path

    Keyword Arguments:
        instance {str} -- The name of the Instance.
        bare {bool} -- Allow returning the bare Instance Folder.

    Returns:
        Path: The absolute Path to the Instance
    """

    assert instance or bare, "No valid Instance supplied"
    return get_home_path() / "instances" / instance


def get_child_paths(path: Path) -> list:
    """Wrapper to get all subdirectories and files.

    Arguments:
        path {Path} -- Path to walk

    Returns:
        list -- A list of all paths found.
    """

    return sorted(path.rglob("*"))


def get_jar_list(filter_str: str = ''):
    """Get List of all cached .jar-files

    Lists all cached .jar-Files in the Type-Tag format.

    Keyword Arguments:
        filter_str {str} -- Filter for version, type or version. (default: {''})
    """

    jars = get_relative_paths(get_home_path() / "jars", ".jar", -1)
    for jar in jars:
        if filter_str in str(jar):
            print(str(jar).replace("/", ":").replace(".jar", ''))


def chown(path: Path, user: str, group=None):
    """Change owner of file or of a path recursively.

    Changes the owner of a file or of a path and its subdirectories.
    The gid of the default group of the user is used if [group] is omitted.

    Arguments:
        path {Path} -- The path of which owners should be recursively changed.
        user {str} -- User that should own the path.

    Keyword Arguments:
        group {[type]} -- Group that should own the path. (default: {None})
    """

    if not group:
        group = getpwnam(user).pw_gid
    if path.is_dir():
        file_list = get_child_paths(path)
    else:
        file_list = [path]
    for fle in file_list:
        shutil.chown(fle, user, group)


def get_relative_paths(path: Path, filter_str: str = '', filter_idx: int = 0) -> list:
    """Get relative subdirectories of path.

    Get the subdirectories of a path, without any of the path itself. Files are omitted.
    E.g. if 'path/to/dir' has two subdirectories 'path/to/dir/one' and 'path/to/dir/two', 'one' and 'two' are listed.

    The Filter allows simple tests on a directory in the truncated Path. The directory to test against is specified by filter_idx.
    0 -  the first directory of the path is tested. -1 - the last directory is tested, etc.

    Arguments:
        path {Path} -- The path of which the subdirecories should be returned.

    Keyword Arguments:
        filter_str {str} -- A string that is checked against a specified directory. (default: {''})
        filter_idx {int} -- The index of the directory to test against. (default: {0})

    Returns:
        list -- A list of all relative Paths found.
    """

    path_list = []
    length = len(path.parts)
    for file_path in get_child_paths(path):
        rel_path = Path(*file_path.parts[length:])
        if filter_str in rel_path.parts[filter_idx]:
            path_list.append(rel_path)
    return path_list


def create_dirs(path: Path):
    """Wrapper to create Paths recursively, with mode rwxr-x---.

    Arguments:
        path {Path} -- Path to create, if nonexistent.
    """

    Path.mkdir(path, mode=0o0750, parents=True, exist_ok=True)


def copy(source: Path, dest: Path):
    """Wrapper to copy a file or directory

    If [dest] is a directory and [source] is a file, the filename of [source] is retained.

    Arguments:
        source {Path} -- Source file
        dest {Path} -- Destionation file or directory

    Returns:
        Path -- The Destination Path of the copied file.
    """

    return shutil.copy(source, dest)


def move(source: Path, dest: Path):
    """Wrapper to move a file or directory

    If [dest] is a directory and [source] is a file, the filename of [source] is retained.

    Arguments:
        source {Path} -- Source file
        dest {Path} -- Destionation file or directory

    Returns:
        Path -- The Destination Path of the copied file.
    """

    return shutil.move(source, dest)


def export(instance: str, zip_path=None, compress: bool = False, world_only: bool = False) -> Path:
    """Export a minecraft server instance to a Zip-File.

    Export a minecraft server instance to a Zip-File for archiving or similar.
    Optionally, the File can also be compressed and all config Files can be excluded.

    Arguments:
        instance {str} -- The name of the Instance to be exported.

    Keyword Arguments:
        zip_path {Path} -- The path of the Zip-File that is generated. (default: {None})
        compress {bool} -- True: Compress the Zip-File using ZIP_DEFLATE. False: Use ZIP_STORE (default: {False})
        world_only {bool} -- Only export the World data without configuration files. (default: {False})

    Returns:
        Path -- The Path where the Zip-File was saved to.
    """

    if not zip_path:
        zip_path = Path("{0}_{1}.zip".format(
            instance, datetime.now().strftime("%y-%m-%d-%H.%M.%S")))

    server_path = get_instance_path(instance)

    world = ""
    if world_only:
        server_cfg = config.get_properties(server_path / "server.properties")
        world = server_cfg.get("level-name")

    file_list = get_relative_paths(server_path, world)
    total_size = sum([(server_path / x).stat().st_size for x in file_list])
    compress_mode = zf.ZIP_DEFLATED if compress else zf.ZIP_STORED
    with zf.ZipFile(zip_path, "w", compression=compress_mode, allowZip64=True) as zip_file:
        written = 0
        for file_path in file_list:
            full_path = server_path / file_path
            written += full_path.stat().st_size
            sys.stdout.write("\r[%3.0d%%] Writing: %s...\033[K" % (
                written * 100 / total_size, file_path))
            zip_file.write(full_path, file_path)
    print()
    chown(zip_path, os.getlogin())
    print("Archive saved in '{}'".format(zip_path))
    return zip_path


def remove(instance: str, confirm: bool = True):
    """Remove an instance from disk.

    Arguments:
        instance {str} -- The name of the Instance to be deleted.

    Keyword Arguments:
        confirm {bool} -- Ask the user if they are sure to delete the instance. (default: {True})
    """

    del_path = get_instance_path(instance)
    if not del_path.exists():
        raise FileNotFoundError("Instance Path not found: {}".format(del_path))
    if (service.is_enabled(instance) or service.is_active(instance)):
        raise OSError("The server is still running and/or persistent")
    if confirm:
        ans = input(
            "Are you absolutely sure you want to remove the Instance '{}'? [y/n]: ".format(instance))
        while ans.lower() not in ("y", "n"):
            ans = input("Please answer [y]es or [n]o: ")
    else:
        ans = "y"
    if ans == "y":
        shutil.rmtree(del_path)


def remove_jar(type_id: str):
    """Remove an .jar-File from disk.

    Arguments:
        type_id {str} -- The type_id of the .jar-File to be deleted.
    """

    base_path = get_home_path() / "jars"
    del_all = type_id == "all"

    if not del_all:
        del_path = base_path / "{}.jar".format(type_id.replace(":", "/"))
        msg = "Are you absolutely sure you want to remove the Server Jar '{}'? [y/n]: ".format(
            type_id)
    else:
        del_path = base_path
        msg = "Are you sure you want to remove ALL cached Server Jars? [y/n]: "

    if not del_path.exists():
        raise FileNotFoundError(
            "Type-ID not found in cache: {}".format(del_path))
    ans = input(msg)
    while ans.lower() not in ("y", "n"):
        ans = input("Please answer [y]es or [n]o: ")
    if ans == "y":
        if not del_all:
            del_path.unlink()
        else:
            shutil.rmtree(del_path)


def inspect(instance: str, limit: int = 0):
    """Get the last lines of the Log.

    Arguments:
        instance {str} -- The name of the instance to be inspected.

    Keyword Arguments:
        limit {int} -- The amount of lines to output. 0 returns all lines. (default: {0})
    """

    if limit < 0:
        raise OverflowError("Line Limit is lower than minimum of 0")
    log_path = get_instance_path(instance) / "logs"
    logs = get_child_paths(log_path)

    lines = []
    for log in reversed(logs):
        try:
            if log.name.endswith(".gz"):
                log_file = gzip.open(log, "rt")
            else:
                log_file = open(log)
            lines = log_file.readlines() + lines
        finally:
            log_file.close()
        if len(lines) >= limit and limit != 0:
            break

    lines_out = lines[-limit:]
    print(''.join(lines_out), end='')


def tmpcopy(file_path: Path) -> Path:
    """[summary]

    Args:
        file_path (Path): The file which will be copied to a temporary location.

    Returns:
        Path: The Path where the temporary file is saved.
    """
    tmpid = ''.join(random.choice(string.ascii_letters) for _ in range(16))
    tmp_path = file_path.parent / Path("{0}.{1}".format(file_path.name, tmpid))
    shutil.copy(file_path, tmp_path)
    return tmp_path


def get_file_hash(file_path: Path) -> str:
    """Generate the Hash of a File.

    Args:
        file_path (Path): The Path of the File to be hashed.

    Returns:
        str: The Hash as a String.
    """
    hash_sha1 = hashlib.sha1()
    with open(file_path, "rb") as fhnd:
        for chunk in iter(lambda: fhnd.read(4096), b""):
            hash_sha1.update(chunk)
    return hash_sha1.hexdigest()
