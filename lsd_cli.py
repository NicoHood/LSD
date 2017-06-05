#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import argparse
import hashlib
import time
from LSD.lsd import LSD
import subprocess
import logging
import progressbar

# TODO https://github.com/WoLpH/python-progressbar/issues/129
#progressbar.streams.wrap_stderr()

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("requests").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("gnupg").setLevel(logging.WARNING)

logging.getLogger("LSD.sources").setLevel(logging.INFO)

def main(arguments):
    """Main entry point that parses configs and creates LSD instance."""
    parser = argparse.ArgumentParser(description='LSD')
    parser.add_argument('-v', '--version', action='version', version='LSD ' + LSD.version)
    parser.add_argument('--verbose', action='store_true', help='Verbose print')
    parser.add_argument('--debug', action='store_true', help='Debug print')

    parser.add_argument('-w', '--workdir', default='./workdir', help='Workdir with git repositories and gnupghome')
    parser.add_argument('-o', '--output', help='Output path')
    parser.add_argument('-g', '--gnupghome', help='GNUPGHOME path. Can also be set via environment variable.')

    parser.add_argument('-d', '--drop', choices= [LSD.db] + LSD.avail_tables, nargs='+', default=[], help='Drop the database and start with a fresh instance')
    parser.add_argument('-p', '--parse', choices=LSD.avail_tables, nargs='*', help='Parses specified table, no arg = all')
    parser.add_argument('-a', '--analyze', choices=LSD.avail_tables, nargs='*', help='Analyze packages. No additional package == all packages')
    parser.add_argument('-f', '--force', choices=LSD.avail_tables, nargs='*', help='Force update for selected options')
    parser.add_argument('-e', '--evaluate', choices=LSD.avail_tables, nargs='*', help='') # TODO --rate?
    parser.add_argument('-c', '--clean', choices=LSD.avail_tables, nargs='*', help='Cleanup the specified table from old entries.')
    parser.add_argument('-s', '--special', nargs='+', help='Specify special archlinux packages to analyze.')
    parser.add_argument('-u', '--update', action='store_true', help='Update PKGBUILD git and pkglist.')

    args = parser.parse_args()

    if not args.gnupghome:
        args.gnupghome = os.path.join(args.workdir, 'gnupghome')
    if not args.output:
        args.output = os.path.join(args.workdir, 'output')

    # Set print verbose/debug level
    global verboseprint
    global debugprint
    verboseprint = print if args.verbose else lambda *a, **k: None
    debugprint = print if args.debug else lambda *a, **k: None

    lsd = LSD(force=args.force, clean=args.clean, path=args.workdir, output=args.output, gnupghome=args.gnupghome)

    lsd.startdb(args.drop, keyserver='hkps://hkps.pool.sks-keyservers.net')

    #if args.pkgbuild:
    #    lsd.parse(archlinux=args.pkgbuild)

    if args.update:
        #print(os.path.join(os.path.dirname(os.path.realpath(__file__)), 'updatedb.sh'))
        subprocess.run([os.path.join(os.path.dirname(os.path.realpath(__file__)), 'updatedb.sh'), args.workdir])
        # TODO remove, stdout=subprocess.PIPE).stdout.decode('utf-8').split('\n')

    if args.parse == []:
        lsd.parse() # TODO not so complicated required?
    elif args.parse is not None:
        lsd.parse(tables=args.parse)

    if args.analyze == []:
        lsd.analyze() # TODO not so complicated required?
    elif args.analyze is not None:
        lsd.analyze(tables=args.analyze)

    if args.evaluate == []:
        lsd.evaluate(packages=args.special) # TODO not so complicated required?
    elif args.evaluate is not None:
        lsd.evaluate(tables=args.evaluate)

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
