#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import rethinkdb as r
import hashlib
import requests
import logging
import progressbar

from .table import Table
from .gpg import GPG

class Sources(Table):
    attributes = ['sha256', # ID as PK, because the length is limited
                'url',# URL to source or signature
                'sig_url', # Signature url of the url (only a single entry is possible)
                'https_url', # Https url of the http source. If https and None then its a bad redirect to http!
                'hash_url', # Array of available upstream urls TODO use?
                'sig_hash', # Hash type of the gpg signature TODO how to parse with gpg modul?
                'mirror', # True or False when a potential mirror is used (url returns different sources)
                'timestamp',
                ]

    def __init__(self, conn, db, force=False, logger=None):
        super(Sources, self).__init__(conn, db, 'sources', 'sha256', self.attributes, 'url')
        self.force = force
        self.logger = logger or logging.getLogger(__name__)
        self.start()

    def parse(self, sources):
        # Add all new sources
        available_sources = list(r.db(self.db).table(self.table)['url'].run())
        for src in sources:
            # Skip parsed sources
            # TODO improve outside loop
            if src in available_sources:
                self.logger.info('Skipping %s', src)
                continue

            # Insert new packages into database
            sha256 = hashlib.sha256(src.encode('utf-8')).hexdigest()
            data = {'sha256': sha256, 'url': src}
            self.insert(data, name=src)

    def check_url(self, url):
        try:
            ret = requests.head(url, allow_redirects=True, timeout=10)
        except requests.exceptions.SSLError:
            self.logger.debug('SSL error %s', url)
            return None
        except requests.exceptions.ConnectionError:
            self.logger.debug('Connection error %s', url)
            return None
        except requests.exceptions.ReadTimeout:
            self.logger.debug('Read timeout %s', url)
            return None
        except requests.exceptions.InvalidSchema:
            self.logger.debug('Redirect to ftp or other unsupported protocol %s', url)
            return None

        # Evaluate http status code
        if ret.status_code == 200:
            self.logger.debug('200 OK %s', ret.url)
            return ret.url
        else:
            self.logger.debug('Http status code: %s %s', ret.status_code, url)
            return None

    def analyze_sig(self, url):
        # Filter out SVC and local sources
        # TODO and not url.startswith('ftp://')
        if not url.startswith('http://') and not url.startswith('https://'):
            return None

        # Filter out signatures themselves
        if url.endswith(tuple(GPG.signatures)):
            return None

        # Try to get any available signature
        # TODO skip urls like https://cgit.kde.org/akonadi.git/patch/?id=2dc7fbf5.sig
        for sig in GPG.signatures:
            sigurl = url + sig
            # Try https first, then normal http
            if url.startswith('http://'):
                new_url = self.check_url(sigurl.replace('http://', 'https://', 1))
                if new_url:
                    return new_url
            new_url = self.check_url(sigurl)
            if new_url:
                return new_url
        return None

    def analyze_https(self, url):
        # Filter out SVC, ftp and local sources
        new_url = None
        if url.startswith('http://'):
            new_url = self.check_url(url.replace('http://', 'https://', 1))
        elif url.startswith('https://'):
            new_url = self.check_url(url)

        # check https -> http redirect
        if new_url and new_url.startswith('http://'):
            self.logger.warn('Bad https -> http redirect: %s', new_url)
        # None as return either means no https is available or the webserver refuses to download
        # the head of the request. This happens for github:
        # https://github.com/rpm-software-management/rpmlint/issues/71
        return new_url

    def analyze(self):
        # Get sources to analyse
        if self.force:
            sources = r.db(self.db).table(self.table).run()
            count = r.db(self.db).table(self.table).count().run()
        else:
            # Exclude already parsed entries
            sources = r.db(self.db).table(self.table).filter(~r.row.has_fields('timestamp')).run()
            count = r.db(self.db).table(self.table).filter(~r.row.has_fields('timestamp')).count().run()

        # Check if new sources exist
        if count == 0:
            self.logger.info('All sources already analyzed. Force with -f.')
            return

        # Analyse all selected sources
        with progressbar.ProgressBar(max_value=count) as bar:
            for i, src in enumerate(sources):
                bar.update(i)

                # Analyze
                url = src['url']
                src['sig_url'] = self.analyze_sig(url)
                src['https_url'] = self.analyze_https(url)

                # Query twice to check for mirror downloads with changing sources
                src['mirror'] = False
                if src['https_url']:
                    mirror_url = self.analyze_https(url)
                    if mirror_url == src['https_url']:
                        src['mirror'] = True

                src['timestamp'] = r.now()

                # Insert new packages into database
                self.insert(src, update=True, name=url)

    def set_sig(self, url, sig):
        """Add new known signature for url
        Sample: through the PKGBUILD source renaming we can determine if a file has a signature.
        However this signature can be on a different server path.
        On Github some users use the (insecure) Github downloads and sign them locally.
        The uploaded signature is available under a different path.
        With this function we also add this "hidden" information within the script.
        """

        # Insert new packages into database
        sha256 = hashlib.sha256(url.encode('utf-8')).hexdigest()
        src = r.db(self.db).table(self.table).get(sha256).run(self.conn)
        if not src:
            sys.exit('Error: Url not in source database. Run with "-p TODO -t sources" first. ' + url) # TODO text/params
        if src['sig_url'] == sig:
            return
        src['sig_url'] = sig
        self.insert(src, update=True, name=url)

    def get_sig(self, url):
        # Get signature from url
        sha256 = hashlib.sha256(url.encode('utf-8')).hexdigest()
        ret = r.db(self.db).table(self.table).get(sha256).run(self.conn)
        if not ret:
            sys.exit('Error: Url not in source database. Run with "-p TODO -t sources" first. ' + url) # TODO text/params
        if ret['sig_url']:
            return ret['sig_url']
        else:
            return None

    def get_https(self, url):
        # Get signature from url
        sha256 = hashlib.sha256(url.encode('utf-8')).hexdigest()
        ret = r.db(self.db).table(self.table).get(sha256).run(self.conn)
        if not ret:
            sys.exit('Error: Url not in source database. Run with "-p TODO -t sources" first. ' + url) # TODO text/params
        if ret['https_url']:
            return ret['https_url']
        else:
            return None

    def clean(self):
        pass
