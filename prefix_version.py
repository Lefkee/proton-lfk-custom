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

    For GE names the Wine base maps to ``major`` and the GE build number maps
    to ``minor``. Returns ``None`` when the string is not recognised.
    """
    if not version:
        return None

    version = version.strip()

    match = _GE_RE.match(version)
    if match is not None:
        major = int(match.group(1))
        prefix_ver = match.group(2) or "0"
        return (f"GE-Proton{major}", major, int(prefix_ver), prefix_ver)

    match = _VALVE_RE.match(version)
    if match is not None:
        proton_ver = f"{match.group(1)}.{match.group(2)}"
        prefix_ver = match.group(3) or "0"
        return (proton_ver, int(match.group(1)), int(match.group(2)), prefix_ver)

    return None
