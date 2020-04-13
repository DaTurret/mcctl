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
import subprocess as sp
from pathlib import Path
from mcctl.storage import getHomePath
from mcctl.service import isActive
from mcctl.visuals import compute
from pwd import getpwnam


def attach(instance: str):
    assert isActive(
        instance), "The Server is not running"
    cmd = shlex.split(
        'screen -r mc-{}'.format(instance))
    sp.run(cmd)


def exec(instance: str, command: list, timeout: int = 0.5):
    assert isActive(
        instance), "The Server is not running"

    logPath = getHomePath() / "instances" / instance / "logs/latest.log"

    oldCount = 0
    lineCount = sum(1 for line in open(logPath))

    jarCmd = " ".join(command)
    cmd = shlex.split(
        'screen -p 0 -S mc-{0} -X stuff "{1}^M"'.format(instance, jarCmd))
    sp.run(cmd)

    while lineCount > oldCount:
        time.sleep(timeout)
        with open(logPath) as log:
            for i, line in enumerate(log):
                if i >= lineCount:
                    print(line.rstrip())
        oldCount = lineCount
        lineCount = i + 1


def demote(asUser: str):
    userData = getpwnam(asUser)
    os.setgid(userData.pw_gid)
    os.setuid(userData.pw_uid)


def preStart(jarPath: Path, watchFile=None, killSec: int = 80) -> bool:
    assert isinstance(
        watchFile, Path) or watchFile is None, "WatchFile is not of Type 'Path'"
    cmd = shlex.split(
        '/bin/java -jar {}'.format(jarPath))
    p = sp.Popen(cmd, cwd=jarPath.parent, stdout=sp.PIPE, stderr=sp.PIPE)

    fps = 4
    signaled = False
    success = False
    for i in range(killSec*fps+1):
        print("\r{} Setting up config files...".format(compute(2)), end="")
        time.sleep(1/fps)
        if not signaled and watchFile != None and watchFile.exists():
            p.terminate()
            signaled = True
        elif i == killSec * fps:
            p.kill()
        elif p.poll() != None:
            success = True
            break
    print()
    return success