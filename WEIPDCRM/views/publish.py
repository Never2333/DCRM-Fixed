# coding=utf-8

"""
DCRM - Darwin Cydia Repository Manager
Copyright (C) 2017  WU Zheng <i.82@me.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import unicode_literals

import os
from urllib.parse import quote_plus

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound, HttpResponseBadRequest
from django.shortcuts import redirect
from django.utils.http import http_date
from django.views.static import serve

from WEIPDCRM.models.package import Package
from WEIPDCRM.models.version import Version
from preferences import preferences


APT_INDEX_RESOURCES = {
    "InRelease",
    "Release",
    "Release.gpg",
    "Packages",
    "Packages.gz",
    "Packages.bz2",
    "Packages.xz",
}
BASIC_RESOURCES = APT_INDEX_RESOURCES | {"CydiaIcon.png"}
APT_CONTENT_TYPES = {
    "InRelease": "text/plain; charset=utf-8",
    "Release": "text/plain; charset=utf-8",
    "Release.gpg": "application/pgp-signature",
    "Packages": "text/plain; charset=utf-8",
    "Packages.gz": "application/gzip",
    "Packages.bz2": "application/x-bzip2",
    "Packages.xz": "application/x-xz",
    "CydiaIcon.png": "image/png",
}


def _resource_url(*parts):
    """
    Join URL fragments without letting os.path normalize URL schemes or emit
    doubled slashes. ``resources_alias`` may be a path (/resources/) or an
    absolute CDN URL (https://cdn.example/resources/).
    """
    url = "/".join(str(part).strip("/") for part in parts if str(part).strip("/"))
    first = str(parts[0]) if parts else ""
    if first.startswith(("http://", "https://")):
        scheme, rest = url.split(":/", 1)
        return scheme + "://" + rest.lstrip("/")
    if first.startswith("/"):
        return "/" + url
    return url


def _set_file_validators(response, file_path):
    stat = os.stat(file_path)
    response["Last-Modified"] = http_date(stat.st_mtime)
    response["ETag"] = '"%x-%x"' % (stat.st_mtime_ns, stat.st_size)
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _set_repository_index_headers(response, resource_name, file_path=None):
    response["Content-Type"] = APT_CONTENT_TYPES.get(resource_name, "application/octet-stream")
    response["Cache-Control"] = "public, no-cache, max-age=0, s-maxage=0, must-revalidate, proxy-revalidate, no-transform"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["Vary"] = "Accept-Encoding"
    response["X-Accel-Expires"] = "0"
    response["Cloudflare-CDN-Cache-Control"] = "no-cache, max-age=0"
    response["CDN-Cache-Control"] = "no-cache, max-age=0"
    if file_path is not None:
        _set_file_validators(response, file_path)
    return response


def _set_package_file_headers(response, pkg, file_path):
    response["Content-Type"] = "application/vnd.debian.binary-package"
    response["Content-Transfer-Encoding"] = "binary"
    response["Cache-Control"] = "public, max-age=31536000, immutable, no-transform"
    response["Content-Disposition"] = "attachment; filename=\"" + quote_plus(pkg.base_filename()) + "\""
    response["Accept-Ranges"] = "bytes"
    response["X-Accel-Buffering"] = "no"
    response["Cloudflare-CDN-Cache-Control"] = "public, max-age=31536000, immutable"
    response["CDN-Cache-Control"] = "public, max-age=31536000, immutable"
    _set_file_validators(response, file_path)
    return response


def package_file_fetch(request, package_name=None, package_id='latest'):
    pkg = None
    if package_id == 'latest':
        if package_name is None:
            return HttpResponseNotFound()
        pkg = Package.objects.get(c_package=package_name).get_latest_version()
    else:
        package_id = int(package_id)
        if package_id <= 0:
            return HttpResponseNotFound()
        pkg = Version.objects.get(id=package_id)
    if pkg is None:
        return HttpResponseNotFound()
    else:
        if package_name is not None and pkg.c_package != package_name:
            return HttpResponseNotFound()
    file_path = os.path.join(settings.MEDIA_ROOT, pkg.storage.name)
    if not os.path.exists(file_path):
        return HttpResponseNotFound()
    pref = preferences.Setting
    if pref.download_cydia_only:
        if 'HTTP_X_UNIQUE_ID' not in request.META:
            return HttpResponseBadRequest()
    request_path = pkg.storage.name
    request_url = pkg.get_external_storage_link()
    if pref.redirect_resources == 1 and pref.redirect_prefix:
        request_url = _resource_url(pref.redirect_prefix, request_url)
    pkg.download_times = pkg.download_times + 1
    pkg.save()
    if pref.redirect_resources == 1:
        # Download URLs are versioned/hashed by database storage paths; temporary
        # redirects avoid clients pinning a stale CDN hostname forever.
        response = redirect(request_url, permanent=False)
    elif pref.redirect_resources == 2:
        # Redirect to WEB server
        response = HttpResponse()
        if pref.web_server == 0:
            response['X-Accel-Redirect'] = request_url
        elif pref.web_server == 1:
            # You may set Send File Path to settings.MEDIA_ROOT
            response['X-Sendfile'] = request_path
        elif pref.web_server == 2:
            pass
    else:
        # Return FileResponse By Reading Static File
        response = serve(
            request,
            path=request_path,
            document_root=settings.MEDIA_ROOT,
        )
    return _set_package_file_headers(response, pkg, file_path)


def basic_resource_fetch(request, resource_name):
    if resource_name == "CydiaIcon":
        resource_name = "CydiaIcon.png"
    if resource_name not in BASIC_RESOURCES:
        return HttpResponseNotFound()
    pref = preferences.Setting
    if pref.active_release is None:
        return HttpResponseNotFound()
    else:
        release_id = str(pref.active_release.id)
    release_root_path = os.path.join(settings.MEDIA_ROOT, "releases", release_id)
    request_path = os.path.join(release_root_path, resource_name)
    if not os.path.exists(request_path):
        return HttpResponseNotFound()
    if pref.download_cydia_only:
        if 'HTTP_X_UNIQUE_ID' not in request.META:
            return HttpResponseBadRequest()  # X-UNIQUE-ID
    release_root_url = _resource_url(pref.resources_alias, "releases", release_id)
    request_url = _resource_url(release_root_url, resource_name)
    if pref.redirect_resources == 1:
        # Never make APT indexes a permanent redirect: Cydia/Sileo/Zebra and CDN
        # edges must revalidate Release/Packages immediately after each rebuild.
        response = redirect(request_url, permanent=False)
    elif pref.redirect_resources == 2:
        # Redirect to WEB server
        response = HttpResponse()
        if pref.web_server == 0:
            response['X-Accel-Redirect'] = request_url
        elif pref.web_server == 1:
            response['X-Sendfile'] = request_path
        elif pref.web_server == 2:
            # TODO: Tomcat Support
            pass
        response['Content-Disposition'] = "attachment; filename=\"" + quote_plus(resource_name) + "\""
    elif pref.redirect_resources == 0:
        # Return FileResponse By Reading Static File
        request_path = os.path.join("releases", release_id, resource_name)
        response = serve(request, path=request_path, document_root=settings.MEDIA_ROOT)
    else:
        response = HttpResponseNotFound()
    return _set_repository_index_headers(response, resource_name, os.path.join(release_root_path, resource_name))
