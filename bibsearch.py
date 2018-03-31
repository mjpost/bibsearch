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
# from collections import Counter, namedtuple
# from itertools import zip_longest
# from typing import List, Iterable, Tuple

# import math
# import unicodedata

#import pybtex.database

import biblib.biblib.bib as biblib  # TODO: ugly import

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
DATASETS = {
    'cl': {
        '2017': ['https://aclanthology.coli.uni-saarland.de/volumes/computational-linguistics-volume-43-issue-1-april-2017.bib',
                 'https://aclanthology.coli.uni-saarland.de/volumes/computational-linguistics-volume-43-issue-2-june-2017.bib',
                 'https://aclanthology.coli.uni-saarland.de/volumes/computational-linguistics-volume-43-issue-3-september-2017.bib',
                 'https://aclanthology.coli.uni-saarland.de/volumes/computational-linguistics-volume-43-issue-4-december-2017.bib'],
    },
    'tacl': {'https://aclanthology.coli.uni-saarland.de/volumes/transactions-of-the-association-of-computational-linguistics-volume-5-issue-1.bib',
             'https://aclanthology.coli.uni-saarland.de/volumes/transactions-of-the-association-of-computational-linguistics-volume-4-issue-1.bib',
             'https://aclanthology.coli.uni-saarland.de/volumes/transactions-of-the-association-of-computational-linguistics-volume-3-issue-1.bib',
             'https://aclanthology.coli.uni-saarland.de/volumes/transactions-of-the-association-of-computational-linguistics-volume-2-issue-1.bib',
             'https://aclanthology.coli.uni-saarland.de/volumes/transactions-of-the-association-of-computational-linguistics-volume-1-issue-1.bib',
    },
    'acl': {
        '2017': [
            'http://aclweb.org/anthology/P/P17/P17-1.bib',
            'http://aclweb.org/anthology/P/P17/P17-2.bib',
            'http://aclweb.org/anthology/P/P17/P17-3.bib',
            'http://aclweb.org/anthology/P/P17/P17-4.bib',
            'http://aclweb.org/anthology/P/P17/P17-5.bib',
        ],
    },
}


# bibtex_file = open(args.bibtex_file)
# parser = BibTexParser()
# parser.customization = convert_to_unicode
# db = bibtexparser.load(bibtex_file, parser=parser)
# entries = list(filter(lambda x: 'Post, Matt' in x.get('author',''), db.entries))

# entries_map = defaultdict(list)
# for entry in entries:
#     remove = [key for key in entry.keys() if key.startswith('bdsk') or key.startswith('date-')]
#     for key in remove:
#         del entry[key]

#     for key in entry:
#         entry[key] = clean(entry[key])

# for entry in entries:
#     if not 'link' in entry:
#         if 'url' in entry:
#             url = entry['url']
#             if not url.startswith('http://'):
#                 entry.link = 'papers/' + url
#             else:
#                 entry.link = url
#             del entry['url']
#         elif 'file' in entry:
#             entry['link'] = 'papers/' + entry['file']
#             del entry['file']

#     if 'abstract' not in entry or entry['abstract'] == '':
#         print('Error: empty abstract for {}'.format(entry['title']), file=sys.stderr)

#     if entry['ENTRYTYPE'] == 'article':
#         entry['venue'] = entry['journal']
#     elif entry['ENTRYTYPE'] == 'techreport':
#         entry['venue'] = 'Technical Report %s, %s' % (entry['number'], entry['institution'])
#     elif entry['ENTRYTYPE'] == 'phdthesis':
#         entry['venue'] = 'PhD Thesis, %s' % (entry['school'])
#     else:
#         entry['venue'] = entry['booktitle']

#     authors = entry.get('author', '').split(' and ')
#     for i,author in enumerate(authors):
#         if ', ' in author:
#             authors[i] = ' '.join(author.split(', ')[::-1])
#             entry['authors'] = ','.join(authors)

#     entries_map[entry['year']].append(entry)

class BibDB:
    """
    Currently a wrapper around pybtex which I find suboptimal.
    """
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
        raise NotImplementedError

    def search(self, query):
        self.cursor.execute("SELECT fulltext FROM bib \
                            WHERE bib MATCH '{author title year}: ' || ?",
                            [" ".join(query)])
        return self.cursor

    def save(self):
        self.connection.commit()

    def add(self, entry: biblib.Entry):
        # TODO: check for duplicates
        self.cursor.execute('INSERT INTO bib VALUES (?,?,?,?,?)',
                            (entry.key,
                             entry.get("author"),
                             entry.get("title"),
                             entry.get("year"),
                             entry.to_bib())
                            )

    def __iter__(self):
        raise NotImplementedError


def download_file(bibfile) -> None:
    """Downloads the specified bibfile and adds it to the database.

    :param bibfile: the test set to download
    """

    import tempfile, ssl

    db = WrapperAroundCrummyPythonBibtexParsers()
    tmpfile = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.bib')

    try:
        with urllib.request.urlopen(bibfile) as f:
            tmpfile.write(f.read())
            tmpfile.close()

    except ssl.SSLError or urllib.error.URLError:
        print("WHAT!")
        # logging.warning('An SSL error was encountered in downloading the files. If you\'re on a Mac, '
        #                 'you may need to run the "Install Certificates.command" file located in the '
        #                 '"Python 3" folder, often found under /Applications')
        sys.exit(1)

    return tmpfile.name


def _find(args):
    db = BibDB()
    for entry in db.search(args.terms):
        print(entry[0])


def _add(args):
    db = BibDB()

    fname = args.file
    if fname.startswith('http'):
        fname = download_file(fname)

    new_entries = biblib.Parser().parse(open(fname), log_fp=sys.stderr).get_entries()
    added = 0
    skipped = 0
    for entry in new_entries.values():
        try:
            db.add(entry)
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1

    print('Added', added, 'entries, skipped', skipped, 'duplicates')
    db.save()

def _print(args):
    db = WrapperAroundCrummyPythonBibtexParsers()
    if args.summary:
        print('Database has', len(db), 'entries')
    else:
        for entry in db:
            print(entry)


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

    parser_find = subparsers.add_parser('find', help='Search the database')
    parser_find.add_argument('terms', nargs='+', help="One or more search terms which are ANDed together")
    parser_find.set_defaults(func=_find)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
