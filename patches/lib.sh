#!/bin/bash
# shellcheck shell=bash
#
# Shared helpers for the Proton patch scripts in this directory.
#
# This file is meant to be *sourced*, not executed:
#
#     source "$(dirname "$0")/lib.sh"
#
# It enables `set -euo pipefail` in the calling script so that a failed
# `pushd`, `git reset`, `git clean` or `patch` can never leave a half-patched
# tree behind for the compiler.

set -euo pipefail

# Apply a single patch, reporting exactly which file failed.
apply_patch() {
    local patch_path="${1:?apply_patch: missing patch path}"

    if [[ ! -f "$patch_path" ]]; then
        printf 'error: patch file not found: %s\n' "$patch_path" >&2
        exit 1
    fi

    if ! patch -Np1 < "$patch_path"; then
        printf 'error: failed to apply patch: %s\n' "$patch_path" >&2
        exit 1
    fi
}

# Apply every *.patch in a directory. An empty directory is a warning, not a
# failure: several optional patch sets are allowed to be empty.
apply_all_in_dir() {
    local dir="${1:?apply_all_in_dir: missing directory}"
    local patch
    local -a patches=()

    if [[ ! -d "$dir" ]]; then
        printf 'error: patch directory not found: %s\n' "$dir" >&2
        exit 1
    fi

    shopt -s nullglob
    patches=("$dir"/*.patch)
    shopt -u nullglob

    if [[ ${#patches[@]} -eq 0 ]]; then
        printf 'warning: no *.patch files in %s, skipping\n' "$dir" >&2
        return 0
    fi

    for patch in "${patches[@]}"; do
        apply_patch "$patch"
    done
}

# Like apply_all_in_dir(), but skips one basename (used when a directory
# contains a patch that is applied separately with different options).
apply_all_in_dir_except() {
    local dir="${1:?apply_all_in_dir_except: missing directory}"
    local exclude="${2:?apply_all_in_dir_except: missing exclude name}"
    local patch
    local -a patches=()

    if [[ ! -d "$dir" ]]; then
        printf 'error: patch directory not found: %s\n' "$dir" >&2
        exit 1
    fi

    shopt -s nullglob
    patches=("$dir"/*.patch)
    shopt -u nullglob

    if [[ ${#patches[@]} -eq 0 ]]; then
        printf 'warning: no *.patch files in %s, skipping\n' "$dir" >&2
        return 0
    fi

    for patch in "${patches[@]}"; do
        if [[ "$(basename "$patch")" == "$exclude" ]]; then
            continue
        fi
        apply_patch "$patch"
    done
}

# cd into a submodule without ever leaving the caller in the wrong directory.
enter_dir() {
    local dir="${1:?enter_dir: missing directory}"

    pushd "$dir" >/dev/null || {
        printf 'error: cannot enter directory: %s\n' "$dir" >&2
        exit 1
    }
}

leave_dir() {
    popd >/dev/null || {
        printf 'error: cannot leave directory (popd failed)\n' >&2
        exit 1
    }
}

# Refuse to run destructive git commands unless the current directory is the
# root of its own repository. An uninitialised submodule is just an empty
# directory inside the superproject, so 'git reset --hard' / 'git clean' would
# otherwise run against the parent repository and delete real work.
require_git_repo_root() {
    local here toplevel

    here="$(pwd -P)"

    if ! toplevel="$(git rev-parse --show-toplevel 2>/dev/null)"; then
        printf 'error: %s is not a git repository (submodule not initialized?)\n' "$here" >&2
        exit 1
    fi

    toplevel="$(cd "$toplevel" && pwd -P)"
    if [[ "$toplevel" != "$here" ]]; then
        printf 'error: %s is inside the repository at %s, not its own root;\n' "$here" "$toplevel" >&2
        printf '       refusing git reset/clean (submodule not initialized?)\n' >&2
        exit 1
    fi
}

# The common "start from a pristine submodule" sequence.
enter_clean_dir() {
    local dir="${1:?enter_clean_dir: missing directory}"

    enter_dir "$dir"
    require_git_repo_root

    git reset --hard HEAD || {
        printf 'error: git reset --hard failed in %s\n' "$dir" >&2
        exit 1
    }

    git clean -xdf || {
        printf 'error: git clean -xdf failed in %s\n' "$dir" >&2
        exit 1
    }
}
