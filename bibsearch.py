#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool for downloading, maintaining, and search a BibTeX database.
"""

import argparse
# import gzip
import logging
import os
import re
import sys
# import tarfile
import urllib.request
import sqlite3
import stop_words
import textwrap
from tqdm import tqdm
import yaml
# from collections import Counter, namedtuple
# from itertools import zip_longest
# from typing import List, Iterable, Tuple

# import math
# import unicodedata

#import pybtex.database

import biblib.biblib.bib as biblib  # TODO: ugly imports
import biblib.biblib.algo as bibutils

VERSION = '0.1.0'

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

def fulltext_to_single_entry(fulltext):
    parser = biblib.Parser()
    entry, = parser.parse(fulltext).get_entries().values()
    return entry

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
                custom_key,\
                author,\
                title,\
                event,\
                year,\
                fulltext\
                )')

    def __len__(self):
        self.cursor.execute('SELECT COUNT(*) FROM bib')
        return int(self.cursor.fetchone()[0])

    def search(self, query):
        self.cursor.execute("SELECT fulltext, event, key FROM bib \
                            WHERE bib MATCH '{key custom_key author title year event}: ' || ?",
                            [" ".join(query)])
        return self.cursor

    def search_key(self, key):
        self.cursor.execute("SELECT fulltext FROM bib WHERE key=? OR custom_key=?",
                            [key, key])
        return self.cursor

    def save(self):
        self.connection.commit()

    def add(self, event, entry: biblib.Entry):
        """ Returns if the entry was added or if it was a duplicate"""
        self.cursor.execute('SELECT 1 FROM bib WHERE key=? LIMIT 1', (entry.key,))
        if not self.cursor.fetchone():
            original_key = entry.key
            try:
                custom_key = generate_custom_key(entry)
                entry.key = custom_key
            except:
                custom_key = None
            try:
                utf_author = bibutils.tex_to_unicode(entry.get("author"))
                utf_title = bibutils.tex_to_unicode(entry.get("title"))
            except:
                utf_author = entry.get("author")
                utf_title = entry.get("title")
            self.cursor.execute('INSERT INTO bib VALUES (?,?,?,?,?,?,?)',
                                (original_key,
                                 custom_key,
                                 utf_author,
                                 utf_title,
                                 event,
                                 entry.get("year"),
                                 entry.to_bib())
                                )
            return True
        else:
            return False

    def update_custom_key(self, original_key, new_custom_key):
        self.cursor.execute('SELECT key, fulltext FROM bib WHERE key=? OR custom_key=? LIMIT 1',
                            [new_custom_key, new_custom_key])
        match = self.cursor.fetchone()
        if match:
            logging.error("Entry with key %s already exists", new_custom_key)
            print(match[1], file=sys.stderr)
            print("[Original key: %s]" % match[0], file=sys.stderr)
            sys.exit(1)
        self.cursor.execute("SELECT fulltext FROM bib WHERE key=? LIMIT 1", (original_key,))
        entry = fulltext_to_single_entry(self.cursor.fetchone())
        entry.key = new_custom_key
        self.cursor.execute("UPDATE bib SET custom_key=?, fulltext=? WHERE key=?",
                            [new_custom_key, entry.to_bib(), original_key])
        self.save()

    def __iter__(self):
        self.cursor.execute("SELECT fulltext FROM bib")
        for e in self.cursor:
            yield e[0]

custom_key_skip_chars = str.maketrans("", "", " `~!@#$%^&*()+=[]{}|\\'\":;,<.>/?")
custom_key_skip_words = set(stop_words.get_stop_words("en"))
def generate_custom_key(entry: biblib.Entry):
    # TODO: fault tolerance against missing fields!
    year = int(entry["year"])
    author_surname = bibutils.parse_names(entry["author"])[0]\
        .pretty(template="{last}")\
        .lower()\
        .translate(custom_key_skip_chars)

    filtered_title = [w for w in [t.lower() for t in entry["title"].split()] if w not in custom_key_skip_words]
    if filtered_title:
        title_word = filtered_title[0]
    else:
        title_word = entry["title"][0]
    title_word = title_word.translate(custom_key_skip_chars)

    return "{surname}{year:02}_{title}".format(
        surname=author_surname,
        year=year%1000,
        title=title_word)


def _find(args):
    db = BibDB()
    if not args.bibtex:
        textwrapper = textwrap.TextWrapper(subsequent_indent="  ")
    for (fulltext, event, original_key) in db.search(args.terms):
        entry = fulltext_to_single_entry(fulltext)
        if args.original_key:
            entry.key = original_key
            fulltext = entry.to_bib()
        if args.bibtex:
            print(fulltext + "\n")
        else:
            author = [a.pretty() for a in bibutils.parse_names(entry["author"])]
            author = ", ".join(author[:-2] + [" and ".join(author[-2:])])
            try:
                utf_author = bibutils.tex_to_unicode(entry.get("author"))
                utf_title = bibutils.tex_to_unicode(entry.get("title"))
            except:
                utf_author = entry.get("author")
                utf_title = entry.get("title")
            lines = textwrapper.wrap('[{key}] {author} "{title}", {event}{year}'.format(
                            key=entry.key,
                            author=utf_author,
                            title=utf_title,
                            event = event.upper() + " " if event else "",
                            year=entry["year"]))
            print("\n".join(lines) + "\n")

def _add_file(event, fname, db, per_file_progress_bar):
    source = download_file(fname) if fname.startswith('http') else open(fname)

    new_entries = biblib.Parser().parse(source, log_fp=sys.stderr).get_entries()
    added = 0
    skipped = 0
    if per_file_progress_bar:
        iterable = tqdm(new_entries.values(), ncols=80, bar_format="{l_bar}{bar}| [Elapsed: {elapsed} ETA: {remaining}]")
    else:
        iterable = new_entries.values()
    for entry in iterable:
        if db.add(event, entry):
            added += 1
        else:
            skipped += 1

    return added, skipped

def get_fnames_from_bibset(raw_fname, override_event):
    fields = raw_fname[len(BIBSETPREFIX):].strip().split('/')
    currentSet = yaml.load(open("acl.yml"))
    bib_spec = raw_fname[len(BIBSETPREFIX):].strip()
    event=None
    if bib_spec:
        fields = bib_spec.split('/')
        event = fields[0]
        for f in fields:
            try:
                currentSet = currentSet[f]
            except:
                logging.error("Invalid branch '%s' in bib specification '%s'",
                              f, raw_fname)
                sys.exit(1)
    def rec_extract_bib(dict_or_list, event):
        result = []
        if isinstance(dict_or_list, list):
            result = [(event, fname) for fname in dict_or_list]
        else:
            for (k, v) in dict_or_list.items():
                if not event: # We are at the first level, extract event
                    result += rec_extract_bib(v, k)
                else:
                    result += rec_extract_bib(v, event)
        return result
    return rec_extract_bib(currentSet, event if not override_event else override_event)


def _add(args):
    db = BibDB()

    raw_fname = args.file
    event_fnames = [(args.event, raw_fname)] if not raw_fname.startswith(BIBSETPREFIX) \
                         else get_fnames_from_bibset(raw_fname, args.event)
    added = 0
    skipped = 0
    if len(event_fnames) > 1:
        iterable = tqdm(event_fnames, ncols=80, bar_format="{l_bar}{bar}| [Elapsed: {elapsed} ETA: {remaining}]")
        per_file_progress_bar = False
    else:
        iterable = event_fnames
        per_file_progress_bar = True
    for event, f in iterable:
        if not per_file_progress_bar:
            log_msg = "Adding entries from %s" % f
            if event:
                log_msg += " (%s)" % event.upper()
            tqdm.write(log_msg)

        f_added, f_skipped = _add_file(event, f, db, per_file_progress_bar)
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

def _tex(args):
    citation_re = re.compile(r'\\citation{(.*)}')
    bibdata_re = re.compile(r'\\bibdata{(.*)}')
    db = BibDB()
    aux_fname = args.file
    if not aux_fname.endswith(".aux"):
        if aux_fname.endswith(".tex"):
            aux_fname = aux_fname[:-4] + ".aux"
        else:
            aux_fname = aux_fname + ".aux"
    bibfile = None
    entries = []
    for l in open(aux_fname):
        match = citation_re.match(l)
        if match:
            key = match.group(1)
            bib_entry = db.search_key(key).fetchone()
            if bib_entry:
                entries.append(bib_entry[0])
            else:
                logging.warning("Entry '%s' not found", key)
        elif args.write_bibfile or args.overwrite_bibfile:
            match = bibdata_re.match(l)
            if match:
                bibfile = match.group(1)
    if bibfile:
        bibfile = os.path.join(os.path.dirname(aux_fname), bibfile+".bib")
        if os.path.exists(bibfile):
            if args.overwrite_bibfile:
                logging.info("Overwriting bib file %s.", bibfile)
            else:
                logging.error("Refusing to overwrite bib file %s. Use '-B' to force.", bibfile)
                sys.exit(1)
        else:
            logging.info("Writing bib file %s.", bibfile)
        fp_out = open(bibfile, "w")
    else:
        fp_out = sys.stdout
    for e in entries:
        print(e + "\n", file=fp_out)

def _set_custom_key(args):
    db = BibDB()
    n_entries = 0
    for (_, _, original_key) in db.search(args.terms):
        n_entries += 1
        if n_entries > 1:
            break
    if n_entries == 0:
        logging.error("Search returned no results. Aborting.")
        sys.exit(1)
    elif n_entries > 1:
        logging.error("Search returned several entries. Aborting.")
        sys.exit(1)
    logging.info("Updating custom key of %s to %s", original_key, args.new_key)
    db.update_custom_key(original_key, args.new_key)

def main():
    parser = argparse.ArgumentParser(description='bibsearch: Download, manage, and search a BibTeX database.')
    parser.add_argument('--version', '-V', action='version', version='%(prog)s {}'.format(VERSION))
    parser.set_defaults(func=lambda _ : parser.print_help())
    subparsers = parser.add_subparsers()

    parser_add = subparsers.add_parser('add', help='Add a BibTeX file')
    parser_add.add_argument('file', type=str, default=None, help='BibTeX file to add')
    parser_add.add_argument("-e", "--event", help="Event for entries")
    parser_add.set_defaults(func=_add)

    parser_dump = subparsers.add_parser('print', help='Print the BibTeX database')
    parser_dump.add_argument('--summary', action='store_true', help='Just print a summary')
    parser_dump.set_defaults(func=_print)

    parser_find = subparsers.add_parser('find', help='Search the database', aliases=['search'])
    parser_find.add_argument('-b', '--bibtex', help='Print entries in bibtex format', action='store_true')
    parser_find.add_argument('-o', "--original-key", help='Print the original key of the entries', action='store_true')
    parser_find.add_argument('terms', nargs='+', help="One or more search terms which are ANDed together")
    parser_find.set_defaults(func=_find)

    parser_tex = subparsers.add_parser('tex', help='Create .bib file for a latex article')
    parser_tex.add_argument('file', help='Article file name or .aux file')
    parser_tex.add_argument('-b', '--write-bibfile', help='Autodetect and write bibfile', action='store_true')
    parser_tex.add_argument('-B', '--overwrite-bibfile', help='Autodetect and write bibfile', action='store_true')
    parser_tex.set_defaults(func=_tex)

    parser_key = subparsers.add_parser('key', help='Change key of entry')
    parser_key.add_argument('-k', '--new-key', help='New key')
    parser_key.add_argument('terms', nargs='+', help='One or more search terms which uniquely identify an entry')
    parser_key.set_defaults(func=_set_custom_key)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
