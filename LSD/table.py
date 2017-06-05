#!/usr/bin/env python3

from __future__ import print_function
import sys
import rethinkdb as r
import logging

class Table(object):
    """Manages rethinkdb table creation and contains information about primary key and an index"""
    def __init__(self, conn, db, table, pk, attributes, index=None, logger=None):
        if table == db:
            sys.exit('Invalid table. Same name as DB')
        self.conn = conn
        self.db = db
        self.table = table
        self.pk = pk
        self.index = index
        self.attributes = attributes
        self.logger = logger or logging.getLogger(__name__)

    def prompt(self):
        selection = input('Continue? [y/N]')
        if selection.lower() == 'y':
            return True
        else:
            sys.exit('Aborted by user')

    def start(self, drop=False):
        if drop:
            print('Dropping table', self.table)
            self.prompt()
            r.db(self.db).table_drop(self.table).run()

        if not r.db(self.db).table_list().contains(self.table).run():
            print('Creating table', self.table)
            r.db(self.db).table_create(self.table, primary_key=self.pk).run()

            # Create a secondary index
            if self.index:
                print('Creating index', self.index, 'for table', self.table)
                r.db(self.db).table(self.table).index_create(self.index).run()
                r.db(self.db).table(self.table).index_wait(self.index).run()

    def insert(self, data, update=False, name=None):
        # Fill empty attributes
        # TODO filter not available attributes?
        if not update:
            for attribute in self.attributes:
                if attribute not in data:
                    data[attribute] = None

        # Set conflict options
        conflict='error'
        if update:
            conflict='update'

        # Insert data
        ret = r.db(self.db).table(self.table).insert(data, conflict=conflict).run(self.conn)

        # Use PK as default name
        if not name:
            name = data[self.pk]

        # Print insert status
        if ret['inserted']:
            self.logger.info('Inserted %s', name)
        elif ret['unchanged']:
            self.logger.info('Unchanged %s', name)
        elif ret['replaced']:
            self.logger.info('Updated %s', name)
        else:
            self.logger.critical('Unknown database information')
            sys.exit()
