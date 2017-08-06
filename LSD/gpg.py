#!/usr/bin/env python3

from __future__ import print_function
import os
import sys
import rethinkdb as r
import gnupg
from .table import Table

class GPG(Table):
    attributes = ['fingerprint',
                'type',
                'trust',
                'length',
                'algo',
                'keyid',
                'date',
                'expires',
                'ownertrust',
                'sig',
                'uids',
                'sigs',
                'subkeys',
                ]

    # RFC4880 9.1. Public-Key Algorithms
    # [Noteworthy changes in version 2.1.0-beta834 (2014-09-18)]
    # https://gnupg.org/download/release_notes.html
    # gpg: Switched to algorithm number 22 for EdDSA.
    gpgAlgorithmIDs = {
        '1': 'RSA',
        '2': 'RSA Encrypt-Only',
        '3': 'RSA Sign-Only',
        '17': 'DSA',
        '18': 'Elliptic Curve',
        '19': 'ECDSA',
        '21': 'DH',
        '22': 'EdDSA',
        }

    # TODO ECC
    secure_algos = ['1', '2', '3']
    secure_ecc_algos = ['22']
    insecure_algos = ['17']
    signatures = ['.sig', '.sign', '.asc']

    def __init__(self, conn, db, keyserver, gnupghome=None, force=False):
        super(GPG, self).__init__(conn, db, 'gpg', 'fingerprint', self.attributes)
        self.start()
        self.keyserver = keyserver
        self.force = force
        self.gpg = gnupg.GPG(gnupghome=gnupghome)

    def verboseprint(self, *args):
        # TODO if
        print(*args)

    def recv_keys(self, new_keys):
        # Only import new GPG keys
        public_keys = self.gpg.list_keys()
        for key in public_keys:
            if key['fingerprint'] in new_keys:
                new_keys.remove(key['fingerprint'])

        # Import keys from keyserver
        print('Importing', len(new_keys), 'GPG keys.')
        for i, key in enumerate(new_keys, start=1):
            # Download key from keyserver if not existant
            # TODO sometimes thread errors appear here
            # https://github.com/vsajip/python-gnupg/commit/a03cbd06543200377153983172237e6e476423e4#commitcomment-22398676
            # TODO try 2nd keyserver on error
            self.verboseprint('Importing', str(i) + '/' + str(len(new_keys)), key)
            import_result = self.gpg.recv_keys(self.keyserver, key)

            # Check if import was sucessful
            if import_result.count != 1:
                print('Error importing key', key)
                # TODO exit here?

    def sync_keys(self):
        """Update rethinkdb gpg table with local GPG keys."""
        # TODO --force update keyring data from keyserver information (takes very long)
        public_keys = self.gpg.list_keys()

        fingerprints = r.db(self.db).table(self.table).pluck(self.pk).map(lambda x: x[self.pk]).distinct().run(self.conn)
        print('Attempting to update', len(public_keys), 'GPG keys in rethinkdb.')
        for key in public_keys:
            # Skip existing keys
            if key['fingerprint'] in fingerprints and not self.force:
                print('Skipping', key['fingerprint'])
                continue

            # Strip only required information
            stripped_key = {}
            for attribute in self.attributes:
                if attribute in key:
                    stripped_key[attribute] = key[attribute]
                else:
                    stripped_key[attribute] = None

            # Insert/update key
            ret = r.db(self.db).table(self.table).insert(stripped_key, conflict='replace').run()

            # Print insert status
            if ret['inserted']:
                self.verboseprint('Inserted', stripped_key[self.pk])
            elif ret['replaced']:
                self.verboseprint('Replaced', stripped_key[self.pk])
            elif ret['unchanged']:
                self.verboseprint('Unchanged', stripped_key[self.pk])
            else:
                sys.exit('Error: unknown database information')

    def evaluate(self, keys=None):
        ret = r.db(self.db).table(self.table).filter(lambda doc: r.expr(keys).contains(doc['fingerprint']) if keys else True).group('algo', 'length').count().ungroup().order_by('group').run(self.conn)
        count = r.db(self.db).table(self.table).filter(lambda doc: r.expr(keys).contains(doc['fingerprint']) if keys else True).count().run(self.conn)

        # Collect data. Summarize all algorithms with < 2%
        algorithms = []
        counts = []
        limit = int(count * 1 / 100)
        other = 0
        other_algos = []
        for row in ret:
            # Convert id into human readable string (RSA 4096)
            rowcount = row['reduction']
            algo = self.gpgAlgorithmIDs[row['group'][0]] + ' ' + row['group'][1]
            if rowcount < limit:
                other += rowcount
                other_algos += ['{} ({})'.format(algo, rowcount)]
            else:
                algorithms += [algo]
                counts += [rowcount]
        if other:
            algorithms += ['Other']
            counts += [other]

        # TODO find expired keys
        return {'algorithms': algorithms, 'counts': counts, 'other_algos': other_algos}
