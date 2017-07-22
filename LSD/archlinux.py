#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import hashlib
import time
from Namcap import package as namcap
import rethinkdb as r
import requests

from .table import Table
from .gpg import GPG

class ArchLinux(Table):
    """Manages 'archlinux' database. Inserts and updated packages."""

    attributes = ['name',
                'base',
                'depends',
                'desc',
                'licenses',
                'url',
                'version',
                'backup',
                'groups',
                'install',
                'optdepends',
                'conflicts',
                'replaces',
                'provides',
                'options',
                'arch',
                'makedepends',
                'validgpgkeys',
                'md5sums',
                'sha1sums',
                'sha256sums',
                'sha384sums',
                'sha512sums',
                'whirlpoolsums', #TODO test
                'source',
                # TODO fix array and split into 2 arrays
                # Manually added:
                #'sha512',
                #'sha256',
                #'repository',
                # Security analysis:
                # 'sec_gpg',
                # 'sec_sig',
                # 'sec_sig_avail',
                # 'sec_https',
                # 'sec_https_avail',
                # 'sec_hash',
                # 'security',
                # 'timestamp'
                ]

    def __init__(self, conn, db, sources, force=False, clean=False):
        super(ArchLinux, self).__init__(conn, db, 'archlinux', 'name', self.attributes, 'sha512')
        self.start()
        self.force = force
        self.sigurlcache = {}
        self.sources = sources
        self.clean = clean

    # TODO inherit from utilprint class
    def verboseprint(self, *args):
        # TODO if
        print(*args)

    def debugprint(self, *args):
        # TODO if
        #print(*args)
        pass

    def error(self, *args):
        print('Error:', *args)
        sys.exit(1)

    def warning(self, *args):
        print('Warning:', *args)


    def parse_pkgbuild(self, pkgbuildpath, pkgname, pkg_repo):
        # Calculate sha256 and sha512 of PKGBUILD at the same time to speed it up
        hash_sha512 = hashlib.sha512()
        hash_sha256 = hashlib.sha256()
        with open(pkgbuildpath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha512.update(chunk)
                hash_sha256.update(chunk)
        sha512 = hash_sha512.hexdigest()
        sha256 = hash_sha256.hexdigest()

        # Check if package was already parsed with the given PKGBUILD
        count = r.db(self.db).table(self.table).get_all(sha512, index='sha512').count().run()
        if count > 0 and not self.force:
            self.verboseprint('Skipping', pkgname)
            return

        # Parse PKGBUILD information and expand data and packages information
        pkginfo = namcap.load_from_pkgbuild(pkgbuildpath)
        if pkginfo is None:
            # TODO stop on error?
            self.warning('Error:', pkgbuildpath ,'is not a valid PKGBUILD') # TODO fix print
            return

        # Parse every (split) package
        packages = []
        for pkg in (pkginfo.subpackages if pkginfo.is_split else [pkginfo]):
            # Add package base information if available
            if "base" in pkginfo:
                pkg['base'] = pkginfo['base']

            # Add package data
            if pkg['name'] not in pkg_repo:
                self.warning('Unknown/outdated repository for package', pkg['name'], 'in PKGBUILD', pkgname)
                continue

            # Verify that gpg key length
            if 'validgpgkeys' in pkg:
                for fingerprint in pkg['validgpgkeys']:
                    if len(fingerprint) != 40:
                        pkg['validgpgkeys'].remove(fingerprint)
                        self.warning('Invalid fingerprint length', fingerprint, pkgname)

            package = {
                'sha512': sha512,
                'sha256': sha256,
                'repository': '[' + pkg_repo[pkg['name']] + ']',
            }
            for attribute in self.attributes:
                if attribute in pkg:
                    package[attribute] = pkg[attribute]
                else:
                    package[attribute] = None
            packages += [package]

        # Skip empty packages (happens if package is not available in any repository)
        if not packages:
            return

        # Insert new packages into database
        ret = r.db(self.db).table(self.table).insert(packages, conflict='replace').run() # TODO self.conn?

        # Print insert status
        if ret['inserted']:
            self.verboseprint('Inserted', pkgname)
        elif ret['replaced']:
            self.verboseprint('Replaced', pkgname)
        elif ret['unchanged']:
            self.verboseprint('Unchanged', pkgname)
        else:
            print(ret)
            sys.exit('Error: unknown database information')

    def parse(self, path):
        # Read repositories from packages from local pkglist
        with open(os.path.join(path, 'archlinux/db/pkglist.txt'), "r") as pkglist:
            lines = pkglist.read().splitlines()

        # Parse the file
        pkg_repo = {}
        for line in lines:
            out = line.split(' ')
            pkg_repo[out[1]] = out[0]

        # Parse PKGBUILD information into newpkg array
        # TODO print how many packages will get parsed
        # TODO print summary how many were inserted/updated/deleted
        print('Parsing PKGBUILD information')
        repositories = os.path.join(path, self.table + '/git')
        for repo in next(os.walk(repositories))[1]:
            repo_path = os.path.join(repositories, repo)
            if "/." not in repo_path:
                for package in next(os.walk(repo_path))[1]:
                    pkgbuild = repo_path + "/" + package + "/trunk/PKGBUILD"
                    if "/." not in pkgbuild:
                        self.parse_pkgbuild(pkgbuild, package, pkg_repo)

        # TODO print missing PKGBUILDs for packages in repositories
        # TODO find duplicated PKGBUILDs in "packages" and "community" git repository (moved packages)

        # Clean database from removed packages (to AUR)
        if self.clean:
            pkglist = list(r.db(self.db).table(self.table)[self.pk].run(self.conn))
            del_list = []
            for pkg in pkglist:
                if pkg not in pkg_repo:
                    print('Clean:', pkg)
                    del_list += [pkg]

            if del_list:
                # Ask the user to really clean
                selection = input('Continue and clean selected packages? [y/N]')
                if selection.lower() == 'y':
                    # Clean
                    for pkg in del_list:
                        r.db(self.db).table(self.table).get(pkg).delete().run(self.conn)
                else:
                    print('Aborted clean')
            else:
                print('Nothing to clean')

            # Check for missing packages in LSD (unable to analyse with namcap probably)
            for pkg in pkg_repo:
                if pkg not in pkglist:
                    print('Missing package in LSD:', pkg)

    def analyze_gpg(self, validgpgkeys):
        ret = 'NA'
        timestamp = int(time.time())
        # TODO replace words (MID, HIGH) with numbers and rename in analysis later?

        # Check gpg key security
        if validgpgkeys:
            ret = 'EXCELLENT'

            # Rate the worst of all GPG keys
            for fingerprint in validgpgkeys:
                # TODO use GPG class and import missing keys
                gpgkey = r.db(self.db).table('gpg').get(fingerprint).run()
                if gpgkey is None:
                    sys.exit('Error: Fingerprint not in database: ' + fingerprint)

                # Check expire date
                if gpgkey['expires'] != '' and timestamp > int(gpgkey['expires']):
                    self.warning('Key expired:', fingerprint)
                    return 'MID'

                if gpgkey['algo'] in GPG.secure_algos:
                    if int(gpgkey['length']) >= 4096:
                        continue
                    elif int(gpgkey['length']) >= 2048:
                        ret = 'HIGH'
                        continue
                elif gpgkey['algo'] in GPG.secure_ecc_algos:
                    if int(gpgkey['length']) == 256:
                        continue
                    else:
                        sys.exit('Error: Unkown algorithm type: ' + gpgkey['algo'] + ' for fingerprint ' + fingerprint)
                elif gpgkey['algo'] not in GPG.insecure_algos:
                    sys.exit('Error: Unkown algorithm type: ' + gpgkey['algo'] + ' for fingerprint ' + fingerprint)

                # Stop on insecure algorithms
                return 'MID'

            # Return whether the key is HIGH or EXCELLENT
            return ret
        else:
            return 'LOW'

    def analyze_hash(self, pkg):
        # Check hash security
        for hash_algo in ['sha512sums', 'whirlpoolsums', 'sha256sums', 'sha384sums', 'md5sums', 'sha1sums']:
            if pkg[hash_algo]:
                for i, messagedigest in enumerate(pkg[hash_algo]):
                    if messagedigest == 'SKIP':
                        try:
                            url = pkg['source'][i].split('::', 1)[-1]
                        except IndexError:
                            # TODO Some packages are parsed wrong (libreoffice-fresh-i18n)
                            self.warning('Package', pkg['name'], 'has no valid url for hash')
                            return 'NA'
                        filename = os.path.basename(pkg['source'][i].split('::', 1)[0])

                        # Only check for online archives
                        if (url.startswith('https://') or url.startswith('http://') or url.startswith('ftp://')) and not url.endswith(tuple(GPG.signatures)):
                            self.warning('Package', pkg['name'], 'has SKIP message digest for archive file', filename)
                            return 'LOW'

        # Check hash algorithm used
        if pkg['sha512sums'] or pkg['whirlpoolsums']:
            return 'EXCELLENT'
        elif pkg['sha256sums'] or pkg['sha384sums']:
            return 'HIGH'
        elif pkg['md5sums'] or pkg['sha1sums']:
            return 'MID'
        else:
            sys.exit('Error: Unknown hash used')

    def analyze_sig(self, source, filenames, sec_gpg, avail_sigs):
        # Parse sources for existant signatures
        sig_count = 0
        file_count = 0
        for src in source:
            filename = os.path.basename(src.split('::', 1)[0])
            url = src.split('::', 1)[-1]
            extension = os.path.splitext(filename)[1]

            # Skip signatures and exclude local files
            if extension in GPG.signatures:
                if '://' in url:
                    sig_count += 1
                    # TODO verify signature hash algorithm
                continue
            else:
                # TODO what about git archives? signatures will be available with pacman 5.1
                if '://' in url:
                    file_count += 1

            # Check for used signatures
            sig_avail = False
            for sig in GPG.signatures:
                try:
                    index = filenames.index(filename + sig)
                except ValueError:
                    continue

                # Safe new found url + sig pair
                sig_avail = True
                if '://' in url:
                    self.sources.set_sig(url, source[index].split('::', 1)[-1])
                break

            # Lookup possible missing source signature in table
            if sig_avail == False and '://' in url:
                sigurl = self.sources.get_sig(url)
                if sigurl:
                    avail_sigs += [sigurl]

        # Compute security status of signatures
        if sig_count == 0:
            return 'LOW'
        elif sig_count == file_count:
            if sec_gpg == 'EXCELLENT':
                return 'EXCELLENT'
            else:
                return 'HIGH'
        else:
            return 'MID'

    def analyze_https(self, source, upstream_url, avail_https):
        # Check urls for https
        https_count = 0
        for src in source:
            url = src.split('::', 1)[-1]
            if url.startswith('https://') or url.startswith('git+https://') \
                    or url.startswith('svn+https://') or url.startswith('hg+https://') \
                    or url.startswith('bzr+https://'):

                # Check http redirect
                if url.startswith('https://'):
                    https_url = self.sources.get_https(url)
                    if https_url and https_url.startswith('http://'):
                        self.warning('Insecure https -> http redirect', url)
                        continue
                    # If the URL is None, the webserver refuses head downloads or it does not exist
                    # anymore. Keep calm and dont throw errors.
                https_count += 1
            elif url.startswith('http://') or url.startswith('git+http://') \
                    or url.startswith('svn+http://') or url.startswith('git://') \
                    or url.startswith('svn://') or url.startswith('ftp://') \
                    or url.startswith('hg://') or url.startswith('bzr://') \
                    or url.startswith('hg+http://') or url.startswith('bzr+http://') \
                    or url.startswith('git+git://'):
                https_url = self.sources.get_https(url)
                if https_url:
                    avail_https += [https_url]
            elif '://' in url:
                sys.exit('Error: Unknown source protocol: ' + url)
            else:
                # Local file
                https_count += 1

        # Compute security status of https sources
        if https_count == len(source):
            if upstream_url.startswith('https://'):
                return 'EXCELLENT'
            else:
                return 'HIGH'
        elif https_count == 0:
            return 'LOW'
        else:
            return 'MID'

    def analyze_pkg(self, pkg, timestamp):
        pkgname = pkg['name']
        #print(pkg)
        #print('Analyzing package:', pkg['name'])

        # Skip packages with existing timestamp
        if 'timestamp' in pkg and pkg['timestamp'] and not self.force:
            print('Skipping package', pkgname)
            return False

        # TODO more compact
        pkg['sec_gpg'] = 'NA'
        pkg['sec_sig'] = 'NA'
        pkg['sec_sig_avail'] = None
        pkg['sec_https'] = 'NA'
        pkg['sec_https_avail'] = None
        pkg['sec_hash'] = 'NA'
        # TODO git commit length
        pkg['security'] = 'NA'

        # Check if sources are available
        if pkg['source']:
            # Check hash security
            pkg['sec_hash'] = self.analyze_hash(pkg)

            # Create filename array
            filenames = []
            local_count = 0
            for src in pkg['source']:
                filenames += [os.path.basename(src.split('::', 1)[0])]
                if '://' not in src:
                    local_count += 1

            # Skip https and signature check for local only PKGBUILDS
            if local_count < len(pkg['source']):
                # Check gpg key security
                pkg['sec_gpg'] = self.analyze_gpg(pkg['validgpgkeys'])

                # Parse sources for existant signatures
                avail_sigs = []
                pkg['sec_sig'] = self.analyze_sig(pkg['source'], filenames, pkg['sec_gpg'], avail_sigs)
                if avail_sigs:
                    pkg['avail_sigs'] = avail_sigs
                else:
                    pkg['avail_sigs'] = None

                # Check urls for https
                avail_https = []
                pkg['sec_https'] = self.analyze_https(pkg['source'], pkg['url'], avail_https)
                if avail_https:
                    pkg['avail_https'] = avail_https
                else:
                    pkg['avail_https'] = None

                # TODO check if official mirror was used (compare with software database)

        # Calculate overall rating
        if (pkg['sec_gpg'] == 'HIGH' or pkg['sec_gpg'] == 'EXCELLENT') \
                and (pkg['sec_sig'] == 'HIGH' or pkg['sec_sig'] == 'EXCELLENT') \
                and (pkg['sec_hash'] == 'HIGH' or pkg['sec_hash'] == 'EXCELLENT') \
                and (pkg['sec_https'] == 'HIGH' or pkg['sec_https'] == 'EXCELLENT'):
            pkg['security'] = 'EXCELLENT'
        elif (pkg['sec_gpg'] == 'HIGH' or pkg['sec_gpg'] == 'EXCELLENT') \
                and (pkg['sec_sig'] == 'HIGH' or pkg['sec_sig'] == 'EXCELLENT'):
            pkg['security'] = 'HIGH'
        elif pkg['sec_https'] == 'HIGH' or pkg['sec_https'] == 'EXCELLENT':
            pkg['security'] = 'MID'
        elif pkg['sec_hash'] != 'NA':
            pkg['security'] = 'LOW'

        # Print results
        self.debugprint('sec_gpg', pkg['sec_gpg'])
        self.debugprint('sec_sig', pkg['sec_sig'])
        self.debugprint('sec_hash', pkg['sec_hash'])
        self.debugprint('sec_https', pkg['sec_https'])
        self.debugprint('security', pkg['security'])

        # Add timestamp
        pkg['timestamp'] = timestamp
        return True

    def analyze(self, packages=None):
        if packages:
            cursor = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc['name'])).run()
        else:
            cursor = r.db(self.db).table(self.table).run()

        timestamp = int(time.time()) # TODO
        print(timestamp)

        for pkg in cursor:
            new = self.analyze_pkg(pkg, timestamp)
            if not new:
                continue

            # Insert new packages into database
            ret = r.db(self.db).table(self.table).insert(pkg, conflict='update').run(self.conn)

            # Print insert status
            pkgname = pkg['name']
            if ret['inserted']:
                self.verboseprint('Inserted', pkgname)
            elif ret['replaced']:
                self.verboseprint('Updated', pkgname)
            elif ret['unchanged']:
                self.verboseprint('Unchanged', pkgname)
            else:
                print(ret)
                sys.exit('Error: unknown database information')

    def evaluate(self, packages=None):
        data = {}

        # Query security data
        criteria = ['security', 'sec_gpg', 'sec_sig', 'sec_https', 'sec_hash']
        repos = list(r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True)['repository'].distinct().run(self.conn))
        data = {}
        for crit in criteria:
            data[crit] = {}
            ret = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).group(crit).count().run(self.conn)
            data[crit]['Total'] = ret
            for repo in repos:
                ret = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).filter({'repository': repo}).group(crit).count().run(self.conn)
                data[crit][repo] = ret

        # TODO Generate lists for security status of packages

        # Add package count
        data['count'] = {}
        data['count']['Total'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).count().run(self.conn)
        data['count'].update(r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).group('repository').count().run(self.conn))
        data['repositories'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True)['repository'].distinct().run(self.conn)

        # Count available signatures and https
        data['avail_sigs'] = {}
        data['avail_sigs']['Total'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_sigs').count().run(self.conn)
        data['avail_sigs'].update(r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_sigs').group('repository').count().run(self.conn))
        data['avail_https'] = {}
        data['avail_https']['Total'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_https').count().run(self.conn)
        data['avail_https'].update(r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_https').group('repository').count().run(self.conn))

        # Get list of available signatures and https
        data['avail_sigs_list'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_sigs').group('repository').pluck('name', 'avail_sigs').run(self.conn)
        data['avail_https_list'] = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc["name"]) if packages else True).has_fields('avail_https').group('repository').pluck('name', 'avail_https').run(self.conn)

        return data

    def get_gpgkeys(self):
        # Get all GPG keys used in database
        keys = r.db(self.db).table(self.table).has_fields('validgpgkeys').concat_map(lambda x: x['validgpgkeys']).distinct().run()
        return keys

    def get_sources(self):
        # Get all urls (remove name prefix and doubled entries)
        cursor = r.db(self.db).table(self.table).has_fields('source').concat_map(lambda x: x['source'].map(lambda y: y.split('::')[-1])).distinct().run()

        # Filter local files out
        sources = []
        for source in cursor:
            if '://' in source:
                sources += [source]

        return sources

    def get_urls(self):
        pass # TODO upstream urls