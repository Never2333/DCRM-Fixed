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

try:
    from MySQLdb.converters import Thing2Literal, conversions

    conversions.setdefault(str, Thing2Literal)
    conversions.setdefault(bytes, Thing2Literal)
except Exception:
    pass
