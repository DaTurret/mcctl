# mcctl: A Minecraft Server Management Utility written in Python
# Copyright (C) 2020 Matthias Cotting

# This file is part of mcctl.

# mcctl is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# mcctl is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY
# without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with mcctl.  If not, see < http: // www.gnu.org/licenses/>.

import sys
import urllib.request as req
import json
from modules import visuals

downloadUrls = {
    "vanilla": "https://launchermeta.mojang.com/mc/game/version_manifest.json",
    "paper": "https://papermc.io/api/v1/paper"
}


def restGet(url):
    header = {'User-Agent': 'curl/7.4'}
    request = req.Request(url=url, headers=header)
    with req.urlopen(request) as response:
        data = response.read()
    return json.loads(data)


def download(url, dest):
    storeData = req.urlretrieve(url, dest, reporthook)
    sys.stderr.write("\n")
    return storeData

def reporthook(blockcount, blocksize, total):
    current = blockcount * blocksize
    if total > 0:
        percent = current * 100 / total
        s = "\r%s %3.0f%% %*dkB / %dkB" % (
            visuals.spinner(int(percent), 0), percent, len(str(total//1024)), current/1024, total/1024)
    else:
        s = "\r%s %dkB / %skB" % (visuals.spinner(blockcount), current/1024, "???")
    sys.stderr.write(s)


def joinUrl(base, *parts):
    path = "/".join(list([x.strip("/") for x in parts]))
    return "{}/{}".format(base.rstrip("/"), path)


def getVanillaDownloadUrl(manifestUrl, versionTag):
    versionManifest = restGet(manifestUrl)
    if versionTag == "latest":
        versionTag = versionManifest["latest"]["release"]
    elif versionTag == "latest-snap":
        versionTag = versionManifest["latest"]["snapshot"]

    for version in versionManifest["versions"]:
        if version["id"] == versionTag:
            downloadUrl = version["url"]
            break
    versionData = restGet(downloadUrl)
    return versionData["downloads"]["server"]["url"]


def getPaperDownloadUrl(baseUrl, versionTag):
    if versionTag == "latest":
        versions = restGet(baseUrl)
        major = versions["versions"][0]
        minor = versionTag
    else:
        major, minor = versionTag.split(":", 1)
    testUrl = joinUrl(baseUrl, major, minor)
    try:
        restGet(testUrl)
    except:
        raise Exception(
            "Unsupported Server Version '{}' for type 'paper'".format(versionTag))
    return joinUrl(testUrl, "download")


def getDownloadUrl(serverTag):
    global downloadUrls
    typeTag, versionTag = serverTag.split(":", 1)
    if typeTag == "paper":
        url = getPaperDownloadUrl(downloadUrls[typeTag], versionTag)
    elif typeTag == "vanilla":
        url = getVanillaDownloadUrl(downloadUrls[typeTag], versionTag)
    else:
        raise Exception("Unsupported Server Type: '{}'".format(typeTag))
    return url