#!/usr/bin/env bash
#
# Dev aliases for the local PyPI release helper in ./scripts/pypi-release.sh.
#
# Usage:
#   source ./scripts/dev-aliases.sh
#
# Alias guide:
#   tver         Show the current package version from pyproject.toml.
#   tbump-patch  Bump patch version for bugfixes or compatible fixes.
#                Example: 0.1.0 -> 0.1.1
#   tbump-minor  Bump minor version for backward-compatible features.
#                Example: 0.1.0 -> 0.2.0
#   tbump-major  Bump major version for breaking changes.
#                Example: 0.1.0 -> 1.0.0
#   tbuild       Build the distribution artifacts into ./dist.
#   tcheck       Run twine checks against the built artifacts.
#   tupload-test Upload the current ./dist artifacts to TestPyPI.
#   tupload      Upload the current ./dist artifacts to PyPI.
#   trelease     One-command shortcut for:
#                ./scripts/pypi-release.sh release patch pypi
#                This bumps patch, builds, checks, and uploads to PyPI.
#
# Start-to-end example flow:
#   source ./scripts/dev-aliases.sh
#   tver
#   tbump-patch
#   tbuild
#   tcheck
#   tupload-test
#   tupload
#
# Example release sequence with versions:
#   Start at 0.1.0
#   Run tbump-patch  -> 0.1.1
#   Run tbuild       -> create dist artifacts for 0.1.1
#   Run tcheck       -> validate package metadata and files
#   Run tupload-test -> publish 0.1.1 to TestPyPI for verification
#   Run tupload      -> publish 0.1.1 to PyPI
#
# Shortcut alternative:
#   trelease
#   Equivalent to a patch release flow from start to end for PyPI.

alias tver='./scripts/pypi-release.sh version'
alias tbump-patch='./scripts/pypi-release.sh version patch'
alias tbump-minor='./scripts/pypi-release.sh version minor'
alias tbump-major='./scripts/pypi-release.sh version major'
alias tbuild='./scripts/pypi-release.sh build'
alias tcheck='./scripts/pypi-release.sh check'
alias tupload='./scripts/pypi-release.sh upload pypi'
alias tupload-test='./scripts/pypi-release.sh upload testpypi'
alias trelease='./scripts/pypi-release.sh release patch pypi'
