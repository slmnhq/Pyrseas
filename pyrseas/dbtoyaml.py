#!/usr/bin/python
# -*- coding: utf-8 -*-
"""dbtoyaml - extract the schema of a PostgreSQL database in YAML format"""

from __future__ import print_function
import os
import sys
import getpass
from argparse import ArgumentParser

import yaml

from pyrseas.database import Database
from pyrseas.cmdargs import parent_parser


def main(host='localhost', port=5432, schema=None):
    """Convert database table specifications to YAML."""
    parser = ArgumentParser(parents=[parent_parser()],
                            description="Extract the schema of a PostgreSQL "
                            "database in YAML format")
    parser.add_argument('-n', '--schema',
                        help="only for named schema (default %(default)s)")
    parser.add_argument('-t', '--table', dest='tablist', action='append',
                     help="only for named tables (default all)")

    parser.set_defaults(host=host, port=port, username=os.getenv("USER"),
                        schema=schema)
    args = parser.parse_args()

    pswd = (args.password and getpass.getpass() or '')
    db = Database(args.dbname, args.username, pswd, args.host, args.port)
    dbmap = db.to_map([args.schema], args.tablist)
    if args.output:
        fd = args.output
        sys.stdout = fd
    print(yaml.dump(dbmap, default_flow_style=False))
    if args.output:
        fd.close()

if __name__ == '__main__':
    main()
