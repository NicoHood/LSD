#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import hashlib
import time
from Namcap import package as namcap
import rethinkdb as r
import requests
import logging
import progressbar

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

    def __init__(self, conn, db, sources, force=False, clean=False, logger=None):
        super(ArchLinux, self).__init__(conn, db, 'archlinux', 'name', self.attributes, 'sha512')
        self.start()
        self.force = force
        self.sigurlcache = {}
        self.sources = sources
        self.clean = clean
        self.logger = logger or logging.getLogger(__name__)

    def parse_pkgbuild(self, pkgbuildpath, pkgname, git_repo, pkg_repo):
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
            #self.logger.info('Skipping %s', pkgname)
            return 0

        # Parse PKGBUILD information and expand data and packages information
        pkginfo = namcap.load_from_pkgbuild(pkgbuildpath)
        if pkginfo is None:
            self.logger.error('%s is not a valid PKGBUILD', pkgbuildpath)
            return 0

        # Parse every (split) package
        count = 0
        for pkg in (pkginfo.subpackages if pkginfo.is_split else [pkginfo]):
            # Add package base information if available
            if "base" in pkginfo:
                pkg['base'] = pkginfo['base']

            # Add package data
            if pkg['name'] not in pkg_repo:
                self.logger.error('Unknown/outdated repository for package %s in PKGBUILD %s', pkg['name'], pkgname)
                continue

            # Verify that gpg key length
            if 'validgpgkeys' in pkg:
                for fingerprint in pkg['validgpgkeys']:
                    if len(fingerprint) != 40:
                        pkg['validgpgkeys'].remove(fingerprint)
                        self.logger.error('Invalid fingerprint length %s %s', fingerprint, pkgname)

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
            count = r.db(self.db).table(self.table).get_all(sha512, index='sha512').count().run()

            # TODO fix for other distributions
            if git_repo == 'packages' and pkg_repo[pkg['name']] == 'community':
                self.logger.error('Outdated PKGBUILD found in %s but belongs to %s', git_repo, pkg_repo[pkg['name']])
                continue
            if git_repo == 'community' and pkg_repo[pkg['name']] != 'community':
                self.logger.error('Outdated PKGBUILD found in %s but belongs to %s', git_repo, pkg_repo[pkg['name']])
                continue
            # TODO catch error where a package is in two PKGBUILDs in the same git repo(gconf-sharp, djview)
            # to fix this: Create a list of all parsed pkgnames and list duplicates
            self.insert(package, replace=True)
            count += 1

        if not count:
            self.logger.error('No package found inside %s', pkgbuildpath)
        return count

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
        pkgbuild_list = []
        for repo in next(os.walk(repositories))[1]:
            repo_path = os.path.join(repositories, repo)
            if "/." not in repo_path:
                for package in next(os.walk(repo_path))[1]:
                    pkgbuild = repo_path + "/" + package + "/PKGBUILD"
                    if "/." not in pkgbuild:
                        if not os.path.exists(pkgbuild):
                            pkgbuild = repo_path + "/" + package + "/trunk/PKGBUILD"
                            if not os.path.exists(pkgbuild):
                                self.logger.error('PKGBUILD does not exist: %s', pkgbuild)
                                continue
                        pkgbuild_list += [[pkgbuild, package, repo, pkg_repo]]

        # Parse PKGBUILDs
        count = 0
        with progressbar.ProgressBar(max_value=len(pkgbuild_list)) as bar:
            for i, pkgbuild_param in enumerate(pkgbuild_list):
                bar.update(i)
                count += self.parse_pkgbuild(pkgbuild_param[0], pkgbuild_param[1], pkgbuild_param[2], pkgbuild_param[3])
        print('Inserted/Updated {} packages'.format(count))

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
                    self.logger.warn('Key expired:', fingerprint)
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
                            self.logger.error('Package %s has no valid url for hash', pkg['name'])
                            return 'NA'
                        filename = os.path.basename(pkg['source'][i].split('::', 1)[0])

                        # Only check for online archives
                        if (url.startswith('https://') or url.startswith('http://') or url.startswith('ftp://')) and not url.endswith(tuple(GPG.signatures)):
                            self.logger.error('Package %s has SKIP message digest for archive file %s', pkg['name'], filename)
                            return 'LOW'

        # Check hash algorithm used
        if pkg['sha512sums'] or pkg['whirlpoolsums']:
            return 'EXCELLENT'
        elif pkg['sha256sums'] or pkg['sha384sums']:
            return 'HIGH'
        elif pkg['sha1sums']:
            return 'MID'
        elif pkg['md5sums']:
            return 'LOW'
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
                        self.logger.warn('Insecure https -> http redirect %s', url)
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
        self.logger.debug('sec_gpg', pkg['sec_gpg'])
        self.logger.debug('sec_sig', pkg['sec_sig'])
        self.logger.debug('sec_hash', pkg['sec_hash'])
        self.logger.debug('sec_https', pkg['sec_https'])
        self.logger.debug('security', pkg['security'])

        # Add timestamp
        pkg['timestamp'] = timestamp
        return True

    def analyze(self, packages=None):
        if packages:
            cursor = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc['name'])).run()
            count = r.db(self.db).table(self.table).filter(lambda doc: r.expr(packages).contains(doc['name'])).count().run()
        else:
            cursor = r.db(self.db).table(self.table).run()
            count = r.db(self.db).table(self.table).count().run()

        timestamp = int(time.time()) # TODO

        # Analyze all packages
        with progressbar.ProgressBar(max_value=count) as bar:
            for i, pkg in enumerate(cursor):
                bar.update(i)

                # Insert new packages into database
                if self.analyze_pkg(pkg, timestamp):
                    self.insert(pkg, update=True)

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
