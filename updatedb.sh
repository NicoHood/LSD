#!/bin/bash

if ! type -P fakeroot >/dev/null; then
    echo 'Cannot find the fakeroot binary.'
    exit 1
fi

if ! type -P pacman >/dev/null; then
    echo 'Cannot find the pacman binary.'
    exit 1
fi

# TODO check if git is installed

function error_exit
{
    local parent_lineno="$1"
    local message="${2:-}"
    local code="${3:-1}"
    if [[ -n "${message}" ]] ; then
        echo "Error on or near line ${parent_lineno}: ${message}; exiting with status ${code}"
    else
        echo "Error on or near line ${parent_lineno}; exiting with status ${code}"
    fi
    exit "${code}"
}

set -o errtrace
set -e
trap 'error_exit ${LINENO}' ERR

if (( $# > 1 )); then
        echo "Usage: ${0} [workdir]"
        echo
        echo 'Note: Export the "WORKDIR" variable to change the path of the temporary database.'
        echo 'Default workdir: Path of the script location'
        exit 1
fi

if (( $# == 1 )); then
    WORKDIR="${1}"
fi

SCRIPTDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ -z "${WORKDIR}" ]]; then
    # TODO just use current dir instead of script dir?
    WORKDIR="${SCRIPTDIR}"
fi

function init_archlinux {
    for repo in git://projects.archlinux.org/svntogit/{packages,community}.git
    do
        git clone ${repo} --depth=1
    done
}

function init_hyperbola {
    for repo in https://git.hyperbola.info:50100/packages/{core,extra,multilib,community}.git
    do
        # TODO --depth=1 impossible
        git clone ${repo}
    done
}

distributions=('archlinux' 'hyperbola')
for DISTRIBUTION in "${distributions[@]}"
do
    # Important! cd into dirctory because the config file uses mirrors relative to the execution path
    mkdir -p "${WORKDIR}/${DISTRIBUTION}/db"
    mkdir -p "${WORKDIR}/${DISTRIBUTION}/git"
    pushd "${WORKDIR}/${DISTRIBUTION}/db" &>/dev/null

    # Delete db.lock on cleanup
    trap 'rm -f db.lck' INT TERM EXIT

    echo "Synchronizing ${DISTRIBUTION} database"
    cp "${SCRIPTDIR}/config/${DISTRIBUTION}/mirrorlist" .
    fakeroot -- pacman -Syy --config "${SCRIPTDIR}/config/${DISTRIBUTION}/"pacman.conf --logfile /dev/null
    echo "Writing pkglist.new.txt"
    pacman --config "${SCRIPTDIR}/config/${DISTRIBUTION}/"pacman.conf --logfile /dev/null -Sl 2> /dev/null | awk '{print $1 " " $2}' >pkglist.new.txt

    popd &>/dev/null
    pushd "${WORKDIR}/${DISTRIBUTION}/git" &>/dev/null

    # Init Git if not available
    if [[ "$(find . -maxdepth 1 -mindepth 1 -type d | wc -l)" == "0" ]]; then
        echo "Initializing ${DISTRIBUTION} Git repository"
        init_"${DISTRIBUTION}"
    fi

    # Update all git repositories
    while IFS= read -d $'\0' -r directory ; do
        pushd ${directory} &>/dev/null
        echo "Updating git: $(basename ${directory})"
        git pull
        popd &>/dev/null
    done < <(find . -maxdepth 1 -mindepth 1 -type d -print0)

    popd &>/dev/null
done

# Only copy new pkglists if git pull succeded
echo "Saving new pkglists"
for DISTRIBUTION in "${distributions[@]}"
do
    echo "Saving pkglist.txt for ${DISTRIBUTION}"
    mv "${WORKDIR}/${DISTRIBUTION}/db/pkglist.new.txt" "${WORKDIR}/${DISTRIBUTION}/db/pkglist.txt"
done

echo "DB Updated without errors."
