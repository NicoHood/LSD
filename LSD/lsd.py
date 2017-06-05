#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import argparse
import rethinkdb as r

from .table import Table
from .archlinux import ArchLinux
from .gpg import GPG
from .lsa import LSA
from .sources import Sources

# TODO class server (for upstream urls without direct source)
# url domain name between https:// and the next /
# name
# https class
# server software
# server software version

class Software(Table):
    attributes = ['name', # Project name (pk)
                'url', # Upstream website url
                'alt_url', # Alternative upstream url (Github, pypi, git, etc.)
                'download_url', # Link to download page, file or folder
                'sig_url', # Link to signature download page, file or folder
                'hash_url', # Link to hash download page, file or folder
                'https' # HTTPS security grade https://www.ssllabs.com/ssltest/
                'gpg', # Array of valid GPG keys
                'archlinux', # Array of ArchLinux package names (e.g. linux-lts and linux share the same entry)
                'issues', # Array with bugtracker URLs regarding security (request https, signatures etc)
                'cve' # Array of known cve
                'notes', # Additional textfield for notes
                'free', # TODO https://git.hyperbola.info:50100/software/blacklist.git/plain/SYNTAX
                'license', # License array of used licenses
                'version', # Last checked version
                'server', # Server used by download_url https://httpd.apache.org/security/vulnerabilities_24.html https://httpd.apache.org/security/vulnerabilities_22.html https://nginx.org/en/security_advisories.html
                'security', # Security of server, https, gpg signature and key
                'security_overwrite' # Manually overwrite the security setting (please provide notes)
                'editor' # Github name or email
                'timestamp', # Last edit
                ]

    def __init__(self, conn, db, force=False):
        super(Software, self).__init__(conn, db, 'software', 'name', 'archlinux')
        self.start()
        self.force = force

    def parse(self, archlinux=None, base=None, url=None, download_url=None, sig_url=None, https_url=None, gpg=None):
        if not archlinux:
            sys.exit('Error, not implemented yet')

        # For split packages use the base as name
        if base:
            name = base
        else:
            name = archlinux

        # Skip already manually validated entries
        data = r.db(self.db).table(self.table).get(name).run(self.conn)
        if data and data['verified']:
            return
        # Create initital data entry
        elif not data:
            data = { 'name': name, 'verified': False }

        # Update data
        data['url'] = url
        data['download_url'] = download_url
        data['sig_url'] = sig_url
        data['https_url'] = https_url
        data['gpg'] = gpg

        # Append pkgname if not existant
        if 'archlinux' in data and data['archlinux']:
            if archlinux not in data['archlinux']:
                data['archlinux'] += [archlinux]
                print('append', name, base, archlinux)
        else:
            data['archlinux'] = [archlinux]
            print('add')

        self.insert(data, update=True)
        #print(data)

    def analyze(self):

        # Check if package is already inside the database

        # Check if it was validated already
            # Skip it was manually edited to not overwrite important information
            # Update automated information
        pass

    def clean(self):
        pass


class LSD(object):
    # Static data
    db = 'lsd'
    version = '0.1'
    avail_tables = ['archlinux', 'gpg', 'sources', 'software'] # TODO refer to class variables

    def __init__(self, force=None, clean=None, path='.', output='.', gnupghome=None):
        # Default: Parse all tables
        if force == []:
            self.force = self.avail_tables
        elif not force:
            self.force = []
        if clean == []:
            self.clean = self.avail_tables
        elif not clean:
            self.clean = []
        self.path = path
        self.output = output
        self.gnupghome = gnupghome

        # Check workdir and output pathe existance
        if not os.path.isdir(self.path):
            sys.exit('Invalid path ' + path)
        if not os.path.isdir(self.output):
            print('Invalid output path ' + output)
            try:
                ret = input('Create non-existing output path? [Y/n]')
            except KeyboardInterrupt:
                print()
                sys.exit('Aborted by user')
            if ret == 'y' or ret == '':
                os.makedirs(output)
            else:
                sys.exit('Aborted by user')

    def startdb(self, drop=[], keyserver='hkps://pgp.mit.edu'):
        """Connects to rethinkdb and creates non-existing databases and tables.
        Database can be force-dropped via parameter.
        """
        # Connect to database
        try:
            self.conn = r.connect('localhost', 28015).repl()
        except r.errors.ReqlDriverError:
            sys.exit('Error: Connection to rethinkdb failed.')

        # (Re)create database if not existant or drop was requested
        exists = r.db_list().contains(self.db).run()
        if self.db in drop and exists:
            print("Dropping database", self.db)
            r.db_drop(self.db).run()
            exists = False
            drop=[]
        if not exists:
            print("Creating database", self.db)
            r.db_create(self.db).run()

        self.sources = Sources(self.conn, self.db, force=('sources' in self.force))
        self.sources.start(drop=(self.sources.table in drop))
        self.archlinux = ArchLinux(self.conn, self.db, self.sources, force=('archlinux' in self.force), clean=('archlinux' in self.clean))
        self.archlinux.start(drop=(self.archlinux.table in drop))
        self.gpgtable = GPG(self.conn, self.db, keyserver, gnupghome=self.gnupghome, force=('gpg' in self.force))
        self.gpgtable.start(drop=(self.gpgtable.table in drop))

    def parse(self, tables=None):
        # Default: Parse all tables
        if not tables:
            tables = self.avail_tables

        if self.archlinux.table in tables:
            self.archlinux.parse(self.path)

        if self.gpgtable.table in tables:
            # Update GPG keys database
            keys = self.archlinux.get_gpgkeys()
            self.gpgtable.recv_keys(keys)
            self.gpgtable.sync_keys()

        if self.sources.table in tables:
            sources = self.archlinux.get_sources()
            self.sources.parse(sources)

    def analyze(self, tables=None):
        # Default: Parse all tables
        if not tables:
            tables = self.avail_tables

        if self.sources.table in tables:
            self.sources.analyze()

        if self.archlinux.table in tables:
            self.archlinux.analyze()

    def evaluate(self, tables=None, packages=None):
        # Default: Parse all tables
        if not tables:
            tables = self.avail_tables

        data_archlinux = self.archlinux.evaluate(packages)
        data_gpg = self.gpgtable.evaluate()

        lsa = LSA(archlinux=data_archlinux, gpg=data_gpg, output=self.output)
        # TODO before evaluate check if every table entry was analyzed (timestamp set)
        lsa.evaluate()
