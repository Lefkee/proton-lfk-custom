#!/bin/bash
#
# Legacy standalone version of the video playback patching that now lives in
# protonprep-valve-staging.sh. Nothing in the build invokes this file; keep it
# in sync manually if it is still useful for local experiments.

# Fail fast: never let a half-patched tree reach the compiler.
set -euo pipefail

# shellcheck source=lib.sh
source "$(dirname "$0")/lib.sh"

### (2) WINE PATCHING ###

    enter_clean_dir wine

    git revert --no-commit e813ca5771658b00875924ab88d525322e50d39f

    echo "WINE: -WINEOPENXR- copy files into wine"
    mkdir -p dlls/wineopenxr
    cp -R ../wineopenxr/* dlls/wineopenxr/

### (2-5) WINE HOTFIX/BACKPORT SECTION ###

    # Separate OpenXR steam reliance
    # https://github.com/GloriousEggroll/proton-ge-custom/issues/214
    echo "WINE: -PENDING- add OpenXR patches"
    apply_patch "../patches/wine-hotfixes/pending/0001-decouple-wineopenxr-from-steamvr-and-integrate-it-in.patch"

    echo "WINE: -HOTFIX- Implement GE-Proton ffmpeg + winedmo only video playback rework patches"
    apply_all_in_dir "../patches/ge-video-rework/"


    echo "WINE: RUN AUTOCONF TOOLS/MAKE_REQUESTS"
    autoreconf -f
    ./tools/make_requests

    leave_dir



### END PROTON-GE ADDITIONAL CUSTOM PATCHES ###
### END WINE PATCHING ###
