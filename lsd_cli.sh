#!/bin/bash

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARSE_PKGBUILD_PATH="${SCRIPTDIR}" ./lsd_cli.py "$@"
