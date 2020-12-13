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


import os
import sys
import gzip
import shutil
import random
import string
import hashlib
import zipfile as zf
from typing import List
from pathlib import Path
from datetime import datetime
from grp import getgrgid
from pwd import getpwnam
from mcctl import service, config, visuals, CFGVARS

SERVER_USER = CFGVARS.get('system', 'server_user')


def get_home_path(user_name: str = SERVER_USER) -> Path:
    """Return the home directory of a user.

    Arguments:
        user_name (str): The username of which the home directory should be determined.

    Returns:
        Path: The home directory of the user.
    """
    user_data = getpwnam(user_name)
    return Path(user_data.pw_dir)


def get_instance_path(instance: str = '', bare: bool = False) -> Path:
    """Return the assembled absolute Instance Path.

    Keyword Arguments:
        instance (str): The name of the Instance.
        bare (bool): Allow returning the bare Instance Folder.

    Returns:
        Path: The absolute Path to the Instance
    """
    if not instance and not bare:
        raise ValueError("No valid Instance supplied")
    return get_home_path() / "instances" / instance


def get_jar_path(type_id: str = '', bare: bool = False) -> Path:
    """Return the assembled asolute Path of a cached .jar-File.

    Args:
        type_id (str, optional): The type_id of the .jar-File. Defaults to ''.
        bare (bool, optional): Allow returning the bare Jar Cache Folder. Defaults to False.

    Returns:
        Path: The Path to the .jar-File supplied.
    """
    if ':' not in type_id and not bare:
        raise ValueError("No valid Type-ID supplied")
    bare_path = get_home_path() / "jars"
    return bare_path if bare else bare_path / f"{type_id.replace(':', '/')}.jar"


def get_child_paths(path: Path) -> list:
    """Get all subdirectories and files of a Path.

    Arguments:
        path (Path): Path to walk.

    Returns:
        list: A list of all paths found.
    """
    return sorted(path.rglob("*"))


def list_plugins(filter_str: str = '') -> None:
    """List all Servers which have plugins installed.

    Args:
        filter_str (str, optional): [description]. Defaults to ''.
    """
    base_path = get_instance_path(bare=True)
    instance_paths = base_path.iterdir()

    template = "{:16}: {:^18} {}"
    print(template.format("Instance", "Plugins supported", "Plugins installed"))

    for instance_path in instance_paths:
        instance = instance_path.name
        plugin_path = instance_path / "plugins"
        if plugin_path.is_dir():
            plugins = (x.name for x in plugin_path.iterdir() if x.suffix == ".jar")
        else:
            plugins = None
        resolved = template.format(instance, str(plugins is not None), ", ".join(plugins))
        if filter_str in resolved:
            print(resolved)


def list_jars(filter_str: str = '') -> None:
    """Get a List of all cached .jar-files.

    Lists all cached .jar-Files in the Type-Tag format.

    Keyword Arguments:
        filter_str (str): Filter for version, type or version. (default: {''})
    """
    jars = get_relative_paths(get_home_path() / "jars", ".jar", -1)
    for jar in jars:
        if filter_str in str(jar):
            print(str(jar).replace("/", ":").replace(".jar", ''))


def chown(path: Path, user: str, group: str = None) -> None:
    """Change owner of file or of a path recursively.

    Changes the owner of a file or of a path and its subdirectories.
    The gid of the default group of the user is used if [group] is omitted.

    Arguments:
        path (Path): The path of which owners should be recursively changed.
        user (str): User that should own the path.

    Keyword Arguments:
        group (str): Group that should own the path. (default: {None})
    """
    if not group:
        gid = getpwnam(user).pw_gid
        group = getgrgid(gid).gr_name
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
        path (Path): The path of which the subdirecories should be returned.

    Keyword Arguments:
        filter_str (str): A string that is checked against a specified directory. (default: {''})
        filter_idx (int): The index of the directory to test against. (default: {0})

    Returns:
        list: A list of all relative Paths found.
    """
    path_list = []
    length = len(path.parts)
    for file_path in get_child_paths(path):
        rel_path = Path(*file_path.parts[length:])
        if filter_str in rel_path.parts[filter_idx]:
            path_list.append(rel_path)
    return path_list


def create_dirs(path: Path) -> None:
    """Create Paths recursively, with mode rwxr-x---.

    Arguments:
        path (Path): Path to create, if nonexistent.
    """
    Path.mkdir(path, mode=0o0750, parents=True, exist_ok=True)


def remove_all(path: Path) -> None:
    """Remove a path and its children, or a single file.

    Arguments:
        path (Path): Path to delete.
    """
    shutil.rmtree(path)


def copy(source: Path, dest: Path) -> Path:
    """Copy a file or directory.

    If [dest] is a directory and [source] is a file, the filename of [source] is retained.

    Arguments:
        source (Path): Source file or directory.
        dest (Path): Destionation file or directory.

    Returns:
        Path: The Destination Path of the copied file.
    """
    return shutil.copy(source, dest)


def move(source: Path, dest: Path) -> Path:
    """Move a file or directory.

    If [dest] is a directory and [source] is a file, the filename of [source] is retained.

    Arguments:
        source (Path): Source file or directory.
        dest (Path): Destionation file or directory.

    Returns:
        Path: The Destination Path of the copied file.
    """
    return shutil.move(source, dest)


def export(instance: str, zip_path: Path = None, compress: bool = False, world_only: bool = False) -> Path:
    """Export a minecraft server instance to a Zip-File.

    Export a minecraft server instance to a Zip-File for archiving or similar.
    Optionally, the File can also be compressed and all config Files can be excluded.

    Arguments:
        instance (str): The name of the Instance to be exported.

    Keyword Arguments:
        zip_path (Path): The path of the Zip-File that is generated. (default: {None})
        compress (bool): True: Compress the Zip-File using ZIP_DEFLATE. False: Use ZIP_STORE (default: {False})
        world_only (bool): Only export the World data without configuration files. (default: {False})

    Returns:
        Path: The Path where the Zip-File was saved to.
    """
    if not zip_path:
        zip_path = Path(
            f"{instance}_{datetime.now().strftime('%y-%m-%d-%H.%M.%S')}.zip")

    server_path = get_instance_path(instance)

    world = ""
    if world_only:
        server_cfg = config.get_properties(server_path / "server.properties")
        world = server_cfg.get("level-name")

    file_list = get_relative_paths(server_path, world)
    total_size = sum((server_path / x).stat().st_size for x in file_list)
    compress_mode = zf.ZIP_DEFLATED if compress else zf.ZIP_STORED
    with zf.ZipFile(zip_path, "w", compression=compress_mode, allowZip64=True) as zip_file:
        written = 0
        for file_path in file_list:
            full_path = server_path / file_path
            written += full_path.stat().st_size
            sys.stdout.write(
                f"\r[{(written * 100 / total_size):3.0f}%] Writing: {file_path}...\033[K")
            zip_file.write(full_path, file_path)
    print()

    try:
        login_name = os.getlogin()
    except FileNotFoundError:
        login_name = None
        print("WARN: Unable to retrieve Login Name.")
    if login_name:
        chown(zip_path, login_name)

    print(f"Archive saved in '{zip_path}'")
    return zip_path


def remove(instance: str, force: bool = False) -> None:
    """Remove an instance from disk.

    Arguments:
        instance (str): The name of the Instance to be deleted.

    Keyword Arguments:
        force (bool): Delete the Instance without a prompt. (default: {False})
    """
    del_path = get_instance_path(instance)
    if not del_path.exists():
        raise FileNotFoundError(f"Instance Path not found: {del_path}.")
    if (service.is_enabled(instance) or service.is_active(service.get_unit(instance))):
        raise OSError("The server is still running and/or persistent.")

    msg = f"Are you absolutely sure you want to remove the Instance '{instance}'? [y/n]: "
    ans = "y" if force else input(msg).lower()
    while ans not in ("y", "n"):
        ans = input("Please answer [y]es or [n]o: ")
    if ans == "y":
        remove_all(del_path)


def remove_jar(source: str, force: bool = False) -> None:
    """Remove an .jar-File from disk.

    Arguments:
        type_id (str): The type_id of the .jar-File to be deleted.
    Keyword Arguments:
        force (bool): Delete the Jar File without a prompt. (default: {False})
    """
    del_all = source == "all"
    if not del_all:
        del_path = get_jar_path(source)
        msg = f"Are you absolutely sure you want to remove the Server Jar '{source}'? [y/n]: "
    else:
        del_path = get_jar_path(bare=True)
        msg = "Are you sure you want to remove ALL cached Server Jars? [y/n]: "

    if not del_path.exists():
        raise FileNotFoundError(f"Type-ID not found in cache: {del_path}.")
    ans = "y" if force else input(msg).lower()
    while ans not in ("y", "n"):
        ans = input("Please answer [y]es or [n]o: ")
    if ans == "y":
        if not del_all:
            del_path.unlink()
        else:
            remove_all(del_path)


def inspect(instance: str, limit: int = 0) -> None:
    """Get the last lines of the Log.

    Arguments:
        instance (str): The name of the instance to be inspected.

    Keyword Arguments:
        limit (int): The amount of lines to output. 0 returns all lines. (default: {0})
    """
    if limit < 0:
        raise OverflowError("Line Limit is lower than minimum of 0.")
    log_path = get_instance_path(instance) / "logs"
    logs = get_child_paths(log_path)

    lines: List[str] = []
    for log in reversed(logs):
        opener = gzip.open if log.name.endswith(".gz") else open
        with opener(log, "rt") as log_file:
            lines = log_file.readlines() + lines
        if len(lines) >= limit and limit != 0:
            break

    lines_out = lines[-limit:]
    print(''.join(lines_out), end='')


def tmpcopy(file_path: Path) -> Path:
    """Create a temporary copy of a file. Create original File if it does not exist.

    Args:
        file_path (Path): The file which will be copied to a temporary location.

    Returns:
        Path: The Path where the temporary file is saved.
    """
    tmpid = ''.join(random.choice(string.ascii_letters) for _ in range(16))
    tmp_path = file_path.parent / Path(f"{file_path.name}.{tmpid}")
    if not file_path.exists():
        file_path.touch()
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


def install_bare_plugin(plugin_path: Path, plugin_dest: Path) -> str:
    """Install a .jar file as a Plugin on a Server.

    Args:
        plugin_path (Path): The source path of the plugin.
        plugin_dest (Path): The destination path of the plugin.

    Returns:
        str: The file name of the installed plugin
    """
    dst_file = plugin_dest / plugin_path.name
    copy(plugin_path, dst_file)
    dst_file.chmod(0o750)
    return plugin_path.name


def install_compressed_plugin(plugin_path: Path, plugin_dest: Path) -> list:
    """Install a user selection of .jar files from a compresed file as a Plugin on a Server.

    Args:
        plugin_path (Path): The source path of the archive containing plugin(s).
        plugin_dest (Path): The destination path of the plugin(s).

    Raises:
        FileNotFoundError: If no Plugins are found in the Archive.

    Returns:
        list: File names of installed plugins.
    """
    installed = []
    with zf.ZipFile(plugin_path) as zip_file:
        selection = []
        for zinfo in zip_file.infolist():
            if not zinfo.is_dir() and zinfo.endswith(".zip"):
                selection.append(zinfo)
        if len(selection) < 1:
            raise FileNotFoundError("No Plugin(s) found in Archive.")
        else:
            if len(selection) > 1:
                print(f"Multiple Plugins found in '{plugin_path}':")
                final_selection = visuals.list_selector(
                    selection, display=lambda x: Path(x.filename).name)
            else:
                final_selection = selection
            for zinfo in final_selection:
                jar_name = Path(zinfo.filename).name
                dst = plugin_dest / jar_name
                with zip_file.open(zinfo) as zjar, open(dst, 'wb') as dst_file:
                    shutil.copyfileobj(zjar, dst_file)
                dst.chmod(0o750)
                installed.append(jar_name)
    return installed


def mc_import(instance: str, zip_path: Path, world_only: bool = False) -> None:
    """Import a minecraft server instance from a Zip-File.

    Import a minecraft server instance from a Zip-File.
    Also, the world files can be extracted separately.

    Arguments:
        zip_path (Path): The path of the Zip-File to import from. (default: {None})
        instance (str): The name of the Instance to be imported.

    Keyword Arguments:
        world_only (bool): Only import the World data without configuration files. (default: {False})
    """
    instance_path = get_instance_path(instance)
    if instance_path.exists() != world_only:
        if world_only:
            raise FileNotFoundError(f"Instance Path not found: {instance_path}.")
        raise FileExistsError("Instance already exists.")

    if not instance_path.exists():
        create_dirs(instance_path)
    filter_str = ""
    with zf.ZipFile(zip_path) as zip_file:
        if world_only:
            with zip_file.open("server.properties") as prop, tmpf.NamedTemporaryFile() as tmp_file:
                shutil.copyfileobj(prop, tmp_file)
                filter_str = config.get_properties(tmp_file.name).get("level-name", "world")
        file_list = (x for x in zip_file.infolist() if x.name.startswith(filter_str))
        t_size = sum(x.file_size for x in file_list)
        written = 0
        for zpath in file_list:
            safe_zpath = zpath.filename.replace("../", "")
            dst_path = instance_path / safe_zpath
            with zip_file.open(zpath) as zfile, open(dst_path, 'wb') as dst_file:
                written += zpath.file_size
                print(f"\r[{(written * 100 / t_size):3.0f}%] Writing: {safe_zpath}...\033[K", end='')
                shutil.copyfileobj(zfile, dst_file)
    print()
