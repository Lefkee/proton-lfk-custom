"""Parsing of Proton prefix version strings.

Prefix versions are written to ``<prefix>/version`` and compared against
``CURRENT_PREFIX_VERSION`` to decide whether the prefix needs migrating.

Two naming schemes exist in the wild:

* Valve Proton: ``6.3-3``, ``9.0-4`` (``<wine major>.<wine minor>-<prefix>``)
* GE-Proton:    ``GE-Proton10-9`` (``GE-Proton<wine base>-<ge build>``)

``str.split('-')`` cannot parse the GE form because it has two dashes, which
is why prefix migrations silently stopped working after the GE naming change.
"""

import re

_GE_RE = re.compile(r'^GE-Proton(\d+)(?:-(\d+))?$')
_VALVE_RE = re.compile(r'^(\d+)\.(\d+)(?:-(\d+))?$')


def parse_prefix_version(version):
    """Parse *version* into ``(proton_ver, major, minor, prefix_ver)``.

    ``proton_ver`` is the historical string used by migration checks
    (``"3.7"``), ``major``/``minor`` are integers used for ordering, and
    ``prefix_ver`` stays a string because callers compare it with ``int()``.

    For GE names only the Wine base is a comparable version: the GE build
    number is not a Wine minor version and must not make a prefix look newer
    (``GE-Proton11-12`` is not newer than ``GE-Proton11-11``). It therefore
    maps to ``prefix_ver`` only and ``minor`` stays ``0``.

    Returns ``None`` when the string is not recognised.
    """
    if not version:
        return None

    version = version.strip()

    match = _GE_RE.match(version)
    if match is not None:
        major = int(match.group(1))
        prefix_ver = match.group(2) or "0"
        return (f"GE-Proton{major}", major, 0, prefix_ver)

    match = _VALVE_RE.match(version)
    if match is not None:
        proton_ver = f"{match.group(1)}.{match.group(2)}"
        prefix_ver = match.group(3) or "0"
        return (proton_ver, int(match.group(1)), int(match.group(2)), prefix_ver)

    return None


def is_newer_prefix(old_parsed, new_parsed):
    """Return whether the prefix in *old_parsed* is newer than *new_parsed*.

    Only the comparable ``(major, minor)`` components are considered, so a
    higher GE build number alone never triggers the "Removing newer prefix"
    cleanup. Returns ``None`` if either side could not be parsed.
    """
    if old_parsed is None or new_parsed is None:
        return None

    _, old_major, old_minor, _ = old_parsed
    _, new_major, new_minor, _ = new_parsed

    return new_major < old_major or (new_major == old_major and new_minor < old_minor)
