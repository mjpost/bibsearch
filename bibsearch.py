#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool for downloading, maintaining, and search a BibTeX database.
"""

import argparse
# import gzip
import logging
import os
# import re
import sys
# import tarfile
import urllib.request
import sqlite3
import textwrap
import yaml
# from collections import Counter, namedtuple
# from itertools import zip_longest
# from typing import List, Iterable, Tuple

# import math
# import unicodedata

#import pybtex.database

import biblib.biblib.bib as biblib  # TODO: ugly imports
import biblib.biblib.algo as bibutils

VERSION = '0.0.2'

try:
    # SIGPIPE is not available on Windows machines, throwing an exception.
    from signal import SIGPIPE

    # If SIGPIPE is available, change behaviour to default instead of ignore.
    from signal import signal, SIG_DFL
    signal(SIGPIPE, SIG_DFL)

except ImportError:
    logging.warning('Could not import signal.SIGPIPE (this is expected on Windows machines)')

# Where to store downloaded test sets.
# Define the environment variable $SACREBLEU, or use the default of ~/.sacrebleu.
#
# Querying for a HOME environment variable can result in None (e.g., on Windows)
# in which case the os.path.join() throws a TypeError. Using expanduser() is
# a safe way to get the user's home folder.
BIBSEARCHDIR = os.path.join(os.path.expanduser("~"), '.bibsearch')
DBFILE = os.path.join(BIBSEARCHDIR, 'bib.db')


# This defines data locations.
# At the top level are test sets.
# Beneath each test set, we define the location to download the test data.
# The other keys are each language pair contained in the tarball, and the respective locations of the source and reference data within each.
# Many of these are *.sgm files, which are processed to produced plain text that can be used by this script.
# The canonical location of unpacked, processed data is $SACREBLEU/$TEST/$SOURCE-$TARGET.{$SOURCE,$TARGET}
# TODO: Probably a good idea to move it outside of the main .py
BIBSETPREFIX="bib://"

def download_file(bibfile) -> None:
    """Downloads the specified bibfile and adds it to the database.

    :param bibfile: the test set to download
    """

    import ssl

    try:
        with urllib.request.urlopen(bibfile) as f:
            return f.read().decode("utf-8")
    except ssl.SSLError or urllib.error.URLError:
        print("WHAT!")
        # logging.warning('An SSL error was encountered in downloading the files. If you\'re on a Mac, '
        #                 'you may need to run the "Install Certificates.command" file located in the '
        #                 '"Python 3" folder, often found under /Applications')
        sys.exit(1)
    except:
        logging.warning("Error dowloading '%s'", bibfile)
        return ""


class BibDB:
    def __init__(self, fname=DBFILE):
        self.fname = fname
        createDB = False
        if not os.path.exists(self.fname):
            if not os.path.exists(os.path.dirname(self.fname)):
                os.makedirs(os.path.dirname(self.fname))
            createDB = True
        self.connection = sqlite3.connect(self.fname)
        self.cursor = self.connection.cursor()
        if createDB:
            self.cursor.execute('CREATE VIRTUAL TABLE bib USING fts5(\
                key,\
                author,\
                title,\
                year,\
                fulltext\
                )')

    def __len__(self):
        self.cursor.execute('SELECT COUNT(*) FROM bib')
        return int(self.cursor.fetchone()[0])

    def search(self, query):
        self.cursor.execute("SELECT fulltext FROM bib \
                            WHERE bib MATCH '{author title year}: ' || ?",
                            [" ".join(query)])
        return self.cursor

    def save(self):
        self.connection.commit()

    def add(self, entry: biblib.Entry):
        """ Returns if the entry was added or if it was a duplicate"""
        self.cursor.execute('SELECT 1 FROM bib WHERE key=? LIMIT 1', (entry.key,))
        if not self.cursor.fetchone():
            self.cursor.execute('INSERT INTO bib VALUES (?,?,?,?,?)',
                                (entry.key,
                                 entry.get("author"),
                                 entry.get("title"),
                                 entry.get("year"),
                                 entry.to_bib())
                                )
            return True
        else:
            return False

    def __iter__(self):
        self.cursor.execute("SELECT fulltext FROM bib")
        for e in self.cursor:
            yield e[0]

def _find(args):
    db = BibDB()
    if not args.bibtex:
        textwrapper = textwrap.TextWrapper(subsequent_indent="  ")
    for entry in db.search(args.terms):
        if args.bibtex:
            print(entry[0] + "\n")
        else:
            parser = biblib.Parser()
            for e in parser.parse(entry[0]).get_entries().values():
                author = [a.pretty() for a in bibutils.parse_names(e["author"])]
                author = ", ".join(author[:-2] + [" and ".join(author[-2:])])
                lines = textwrapper.wrap('{key}: {author} "{title}", {year}'.format(
                                key=e.key,
                                author=author,
                                title=e["title"],
                                year=e["year"]))
                print("\n".join(lines) + "\n")

def _add_file(fname, db):
    logging.info("Adding entries from %s", fname)
    source = download_file(fname) if fname.startswith('http') else open(fname)

    new_entries = biblib.Parser().parse(source, log_fp=sys.stderr).get_entries()
    added = 0
    skipped = 0
    for entry in new_entries.values():
        if db.add(entry):
            added += 1
        else:
            skipped += 1

    return added, skipped

def get_fnames_from_bibset(raw_fname):
    fields = raw_fname[len(BIBSETPREFIX):].strip().split('/')
    currentSet = yaml.load(open("acl.yml"))
    bib_spec = raw_fname[len(BIBSETPREFIX):].strip()
    if bib_spec:
        fields = bib_spec.split('/')
        for f in fields:
            try:
                currentSet = currentSet[f]
            except:
                logging.error("Invalid branch '%s' in bib specification '%s'",
                              f, raw_fname)
                sys.exit(1)
    def rec_extract_bib(dict_or_list):
        result = []
        if isinstance(dict_or_list, list):
            result = dict_or_list
        else:
            for v in dict_or_list.values():
                result += rec_extract_bib(v)
        return result
    return rec_extract_bib(currentSet)


def _add(args):
    db = BibDB()

    raw_fname = args.file
    fnames = [raw_fname] if not raw_fname.startswith(BIBSETPREFIX) \
                         else get_fnames_from_bibset(raw_fname)
    added = 0
    skipped = 0
    for f in fnames:
        f_added, f_skipped = _add_file(f, db)
        added += f_added
        skipped += f_skipped

    print('Added', added, 'entries, skipped', skipped, 'duplicates')
    db.save()

def _print(args):
    db = BibDB()
    if args.summary:
        print('Database has', len(db), 'entries')
    else:
        for entry in db:
            print(entry + "\n")


def main():
    parser = argparse.ArgumentParser(description='bibsearch: Download, manage, and search a BibTeX database.')
    parser.add_argument('--version', '-V', action='version', version='%(prog)s {}'.format(VERSION))
    subparsers = parser.add_subparsers()

    parser_add = subparsers.add_parser('add', help='Add a BibTeX file')
    parser_add.add_argument('file', type=str, default=None, help='BibTeX file to add')
    parser_add.set_defaults(func=_add)

    parser_dump = subparsers.add_parser('print', help='Print the BibTeX database')
    parser_dump.add_argument('--summary', action='store_true', help='Just print a summary')
    parser_dump.set_defaults(func=_print)

    parser_find = subparsers.add_parser('find', help='Search the database', aliases=['search'])
    parser_find.add_argument('-b', '--bibtex', help='Print entries in bibtex format', action='store_true')
    parser_find.add_argument('terms', nargs='+', help="One or more search terms which are ANDed together")
    parser_find.set_defaults(func=_find)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
