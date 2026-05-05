"""Runtime shims for legacy Django dependencies on modern Python.

DCRM still targets Django 1.11 and a few unmaintained ecosystem packages.
Python 3.10+ moved several collection ABCs and removed the ``codeset``
argument from ``gettext.translation``; importing this module automatically at
interpreter startup keeps those dependencies importable without patching
site-packages.
"""

import collections
import collections.abc
import gettext
import inspect
import sys
import types

for _name in (
    "Callable",
    "Container",
    "Iterable",
    "Iterator",
    "Mapping",
    "MutableMapping",
    "Sequence",
    "MutableSequence",
    "Set",
    "MutableSet",
):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))

if "codeset" not in inspect.signature(gettext.translation).parameters:
    _translation = gettext.translation

    def translation(domain, localedir=None, languages=None, class_=None, fallback=False, codeset=None):
        return _translation(
            domain,
            localedir=localedir,
            languages=languages,
            class_=class_,
            fallback=fallback,
        )

    gettext.translation = translation

if not hasattr(gettext.NullTranslations, "set_output_charset"):
    def set_output_charset(self, charset):
        self._output_charset = charset

    gettext.NullTranslations.set_output_charset = set_output_charset
    gettext.GNUTranslations.set_output_charset = set_output_charset

try:
    from MySQLdb.converters import Thing2Literal, conversions

    conversions.setdefault(str, Thing2Literal)
    conversions.setdefault(bytes, Thing2Literal)
except Exception:
    pass


def _install_six_moves_compat(root_module_name):
    """
    Python 3.12 no longer supports the old ``find_module``-only import hooks
    used by Django 1.11's vendored six module. Pre-register the moved modules
    that Django imports so ``django.utils.six.moves.*`` keeps working.
    """
    try:
        import _thread
        import builtins
        import html.entities
        import html.parser
        import http.client
        import http.cookies
        import importlib
        import pickle
        import socketserver
        import urllib.error
        import urllib.parse
        import urllib.request
        import urllib.response
        import urllib.robotparser

        root_module = importlib.import_module(root_module_name)
    except Exception:
        return

    moves_name = root_module_name + ".moves"
    moves_module = types.ModuleType(moves_name)
    moves_module.__path__ = []
    moves_module._thread = _thread
    moves_module.builtins = builtins
    moves_module.cPickle = pickle
    moves_module.html_entities = html.entities
    moves_module.html_parser = html.parser
    moves_module.http_client = http.client
    moves_module.http_cookies = http.cookies
    moves_module.input = input
    moves_module.map = map
    moves_module.range = range
    moves_module.reload_module = importlib.reload
    moves_module.socketserver = socketserver
    moves_module.zip = zip

    urllib_module = types.ModuleType(moves_name + ".urllib")
    urllib_module.__path__ = []
    urllib_module.error = urllib.error
    urllib_module.parse = urllib.parse
    urllib_module.request = urllib.request
    urllib_module.response = urllib.response
    urllib_module.robotparser = urllib.robotparser
    moves_module.urllib = urllib_module

    module_map = {
        moves_name: moves_module,
        moves_name + ".builtins": builtins,
        moves_name + ".html_entities": html.entities,
        moves_name + ".html_parser": html.parser,
        moves_name + ".http_client": http.client,
        moves_name + ".http_cookies": http.cookies,
        moves_name + ".socketserver": socketserver,
        moves_name + ".urllib": urllib_module,
        moves_name + ".urllib.error": urllib.error,
        moves_name + ".urllib.parse": urllib.parse,
        moves_name + ".urllib.request": urllib.request,
        moves_name + ".urllib.response": urllib.response,
        moves_name + ".urllib.robotparser": urllib.robotparser,
        moves_name + ".urllib_error": urllib.error,
        moves_name + ".urllib_parse": urllib.parse,
        moves_name + ".urllib_request": urllib.request,
        moves_name + ".urllib_response": urllib.response,
        moves_name + ".urllib_robotparser": urllib.robotparser,
    }
    for name, module in module_map.items():
        sys.modules.setdefault(name, module)
    root_module.moves = moves_module


_install_six_moves_compat("six")
_install_six_moves_compat("django.utils.six")
