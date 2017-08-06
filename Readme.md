# Linux Security Database (LSD)
LSD tracks the security status of software projects for various GNU/Linux distributions. This page contains the source code and installing instructions. **Visit the [GitHub.io page](https://nicohood.github.io/LSD/) for the project details and analysis results.**

This project is a work in progress and it is likely that the code and web pages change.

##### Supported distributions
* ArchLinux

# Installation
## Arch Linux
```bash
sudo pacman -S --needed rethinkdb python-rethinkdb rethinkdb-utils \
    python-progressbar pacman namcap python-gnupg python git bash fakeroot
# AUR packages:
python-plotly
```

## Dependencies
* Python 3
* python-progressbar2 >= 0.31.1
* python-gnupg >= 0.4.1
* python-plotly
* Rethinkdb + Python driver
* Pacman
* Namcap
* bash
* git
* fakeroot

# Usage
In order to get started create the default workdir folder, start a rethinkdb instance and run the lsd_cli tool.
```bash
# Start rethinkdb in another terminal
rethinkdb

# Create workdir and run analysis
mkdir -p workdir
./lsd_cli.sh -u -p -c -a -e

# Rate the packages security of your system
./lsd_cli.sh -e -s $(pacman -Qqe | paste -sd " " -)
```

## Backup
* Create backup: `rethinkdb export`
* Regenerate the whole database or table with primary keys: `./lsd_cli.sh -d lsd/archlinux/etc`
* Import single table: `rethinkdb import -f rethinkdb_export/lsd/gpg.json --table lsd.gpg --force`
