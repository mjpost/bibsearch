#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool for downloading, maintaining, and searching a BibTeX database.

Authors:
- Matt Post <post@cs.jhu.edu>
- David Vilar <david.vilar@gmail.com>
"""

import argparse
import logging
import os
import re
import sys
import urllib.request
import sqlite3
import stop_words
import subprocess
import textwrap
from tqdm import tqdm
import yaml

import bibutils
from config import Config
import pybtex.database as pybtex

VERSION = '0.2.0'

config = Config()

class BibsearchError(Exception):
    pass

try:
    # SIGPIPE is not available on Windows machines, throwing an exception.
    from signal import SIGPIPE

    # If SIGPIPE is available, change behaviour to default instead of ignore.
    from signal import signal, SIG_DFL
    signal(SIGPIPE, SIG_DFL)

except ImportError:
    logging.warning('Could not import signal.SIGPIPE (this is expected on Windows machines)')

BIBSETPREFIX="bib://"

def download_file(url, fname_out=None) -> None:
    """
    Downloads a file to a location.
    """

    import ssl

    logging.info('Downloading {} to {}'.format(url, fname_out if fname_out is not None else 'STR'))

    try:
        with urllib.request.urlopen(url) as f:
            if not fname_out:
                return f.read().decode("utf-8")
            else:
                fdir = os.path.dirname(fname_out)
                if not os.path.exists(fdir):
                    os.makedirs(fdir)

                with open(fname_out, "wb") as outfile:
                    outfile.write(f.read())
                return fname_out

    except ssl.SSLError:
        print("WHAT!")
        # logging.warning('An SSL error was encountered in downloading the files. If you\'re on a Mac, '
        #                 'you may need to run the "Install Certificates.command" file located in the '
        #                 '"Python 3" folder, often found under /Applications')
        sys.exit(1)

def single_entry_to_fulltext(entry: pybtex.Entry, overwrite_key: str = None) -> str:
    """
    Converts a pybtex.Entry to text.
    """
    effective_key = entry.key if not overwrite_key else overwrite_key
    formatter = pybtex.BibliographyData(entries={effective_key: entry})
    return formatter.to_string(bib_format="bibtex")

def fulltext_to_single_entry(fulltext: str) -> pybtex.Entry:
    """
    Parses a BibTeX entry into a pybtex.Entry
    """
    entry, = pybtex.parse_string(fulltext, bib_format="bibtex").entries.values()
    return entry

class BibDB:
    def __init__(self):
        self.fname = os.path.join(config.bibsearch_dir, "bib.db")
        createDB = False
        if not os.path.exists(self.fname):
            if not os.path.exists(os.path.dirname(self.fname)):
                os.makedirs(os.path.dirname(self.fname))
            createDB = True
        self.connection = sqlite3.connect(self.fname)
        self.cursor = self.connection.cursor()
        if createDB:
            self.cursor.execute("""CREATE TABLE bib (
                key text UNIQUE,
                custom_key text UNIQUE,
                author text,
                title text,
                event text,
                year text,
                fulltext text
                )""")
            self.cursor.execute("""CREATE TABLE downloaded_files (
                file text UNIQUE
                )""")
            try:
                self.cursor.executescript(
                """CREATE VIRTUAL TABLE bibindex USING fts5(
                    key,
                    custom_key,
                    author,
                    title,
                    event,
                    year,
                    fulltext UNINDEXED,
                    content='bib',
                    );
                CREATE TRIGGER bib_ai AFTER INSERT ON bib BEGIN
                   INSERT INTO bibindex
                       (rowid, key, custom_key, author, title, event, year, fulltext)
                       VALUES 
                       (new.rowid, new.key, new.custom_key, new.author, new.title, 
                       new.event, new.year, new.fulltext);
                    END;
                CREATE TRIGGER bib_ad AFTER DELETE ON bib BEGIN
                   INSERT INTO bibindex
                       (bibindex, rowid, custom_key, author, title, event, year, fulltext)
                       VALUES 
                       ('delete', old.rowid, old.key, old.custom_key, old.author, old.title, 
                       old.event, old.year, old.fulltext);
                    END;
                CREATE TRIGGER bibindex_au AFTER UPDATE ON bib BEGIN
                   INSERT INTO bibindex
                       (bibindex, rowid, key, custom_key, author, title, event, year, fulltext)
                       VALUES 
                       ('delete', old.rowid, old.key, old.custom_key, old.author, old.title, 
                       old.event, old.year, old.fulltext);
                   INSERT INTO bibindex
                       (rowid, key, custom_key, author, title, event, year, fulltext)
                       VALUES 
                       (new.rowid, new.key, new.custom_key, new.author, new.title, 
                       new.event, new.year, new.fulltext);
                    END;
                """)
            except sqlite3.OperationalError as e:
                error_msg = str(e)
                if "no such module" in error_msg and "fts5" in error_msg:
                    logging.warning("It seems your sqlite3 installation does not support fts5 indexing.")
                    logging.warning("It is strongly encouraged to activate fts5 (see the README and the FAQ).")
                    input("Press ENTER to continue...")
                else:
                    raise

    def __len__(self):
        self.cursor.execute('SELECT COUNT(*) FROM bib')
        return int(self.cursor.fetchone()[0])

    def search(self, query):
        results = []
        last_results_fname = os.path.join(config.bibsearch_dir, "lastSearch.yml")
        if not query:
            if os.path.exists(last_results_fname):
                results = yaml.load(open(last_results_fname))
        else:
            try:
                self.cursor.execute("SELECT fulltext, event, key FROM bibindex \
                                    WHERE bibindex MATCH ?",
                                    [" ".join(query)])
                results = list(self.cursor)
                with open(last_results_fname, "w") as fp:
                    yaml.dump(results, fp)
            except sqlite3.OperationalError as e:
                error_msg = str(e)
                if "no such table" in error_msg and "bibindex" in error_msg:
                    logging.error("The database was created without fts5 indexing, the 'search' command is not supported.")
                    logging.error("Use command 'where' instead. See the README for more information.")
                    sys.exit(1)
                elif "no such module" in error_msg and "fts5" in error_msg:
                    logging.error("It seems your sqlite3 installation does not support fts5 indexing.")
                    logging.error("Use command 'where' instead. See the README for more information.")
                    sys.exit(1)
                else:
                    raise
        return results

    def where(self, where_args):
        query = [] 
        query_args = []
        if where_args.key:
            query.append("(key LIKE ? OR custom_key LIKE ?)")
            query_args.append(where_args.key)
            query_args.append(where_args.key)
        if where_args.author:
            query.append("(author LIKE ?)")
            query_args.append(where_args.author)
        if where_args.title:
            query.append("(title LIKE ?)")
            query_args.append(where_args.title)
        if where_args.event:
            query.append("(event LIKE ?)")
            query_args.append(where_args.event)
        if where_args.year:
            query.append("(year LIKE ?)")
            query_args.append(where_args.year)

        results = []
        last_results_fname = os.path.join(config.bibsearch_dir, "lastSearch.yml")
        if not query:
            if os.path.exists(last_results_fname):
                results = yaml.load(open(last_results_fname))
        else:
            self.cursor.execute("SELECT fulltext, event, key FROM bib \
                                WHERE %s" % " AND ".join(query),
                                query_args)
            results = list(self.cursor)
            with open(last_results_fname, "w") as fp:
                yaml.dump(results, fp)
        return results

    def search_key(self, key) -> str:
        """
        Searches the database on the specified key or custom key.
        Returns the fulltext entry with the queried key as the entry key.

        :param key: The key to search on (key or custom key)
        :return: The full-text entry.
        """
        self.cursor.execute("SELECT fulltext FROM bib WHERE key=? OR custom_key=?",
                            [key, key])
        entry = single_entry_to_fulltext(fulltext_to_single_entry(self.cursor.fetchone()[0]), overwrite_key=key)
        return entry

    def save(self):
        self.connection.commit()

    def add(self, event, entry: pybtex.Entry):
        """ Returns if the entry was added or if it was a duplicate"""
        original_key = entry.key
        try:
            utf_author = bibutils.tex_to_unicode(entry.fields.get("author"))
            utf_title = bibutils.tex_to_unicode(entry.fields.get("title"))
        except:
            utf_author = entry.fields.get("author")
            utf_title = entry.fields.get("title")
        custom_key_tries = 0
        added = False
        while not added:
            custom_key = None
            if custom_key_tries < 10:
                try:
                    custom_key = generate_custom_key(entry, custom_key_tries)
                except:
                    pass
            else:
                print(custom_key, custom_key_tries)
                logging.warning("Could not generate a unique custom key for entry %s", original_key)
            try:
                self.cursor.execute('INSERT INTO bib(key, custom_key, author, title, event, year, fulltext) VALUES (?,?,?,?,?,?,?)',
                                    (original_key,
                                     custom_key,
                                     utf_author,
                                     utf_title,
                                     event,
                                     str(entry.fields.get("year")),
                                     single_entry_to_fulltext(entry, custom_key)
                                    )
                                   )
                added = True
            except sqlite3.IntegrityError as e:
                error_message = str(e)
                if "UNIQUE" in error_message:
                    if "bib.custom_key" in error_message:
                        # custom_key was already in the DB
                        custom_key_tries += 1
                    elif "bib.key" in error_message:
                        # duplicate entry
                        break
                    else:
                        raise
                else:
                    raise
        return added

    def update_custom_key(self, original_key, new_custom_key):
        self.cursor.execute("SELECT fulltext FROM bib WHERE key=? LIMIT 1", (original_key,))
        entry = fulltext_to_single_entry(self.cursor.fetchone()[0])
        entry.key = new_custom_key
        try:
            self.cursor.execute("UPDATE bib SET custom_key=?, fulltext=? WHERE key=?",
                                [new_custom_key,
                                 single_entry_to_fulltext(entry),
                                 original_key])
            self.save()
        except:
            logging.error("Key %s already exists in the database", new_custom_key)
            sys.exit(1)

    def __iter__(self):
        self.cursor.execute("SELECT fulltext FROM bib")
        for e in self.cursor:
            yield e[0]

    def file_has_been_downloaded(self, file):
        return self.cursor.execute("""SELECT 1 FROM downloaded_files WHERE file = ? LIMIT 1""", [file]).fetchone() is not None

    def register_file_downloaded(self, file):
        try:
            self.cursor.execute("""INSERT INTO downloaded_files(file) VALUES (?)""", [file])
        except sqlite3.IntegrityError:
            # File was already registered. No problem.
            pass

custom_key_skip_chars = str.maketrans("", "", " `~!@#$%^&*()+=[]{}|\\'\":;,<.>/?")
custom_key_skip_words = set(stop_words.get_stop_words("en"))
def generate_custom_key(entry: pybtex.Entry, suffix_level=0):
    # TODO: fault tolerance against missing fields!
    year = int(entry.fields["year"])
    all_authors = bibutils.parse_names(entry.fields["author"])
    author_surname = all_authors[0]\
        .pretty(template="{last}")\
        .lower()\
        .translate(custom_key_skip_chars)
    et_al = "_etAl" if len(all_authors) > 1 else ""

    filtered_title = [w for w in [t.lower() for t in entry.fields["title"].split()] if w not in custom_key_skip_words]
    if filtered_title:
        title_word = filtered_title[0]
    else:
        title_word = entry.fields["title"][0]
    title_word = title_word.translate(custom_key_skip_chars)

    return config.custom_key_format.format(
        surname=author_surname,
        et_al=et_al,
        year=year,
        short_year=year%100,
        suffix='' if suffix_level==0 else chr(ord('a') + suffix_level - 1),
        title=title_word)

def format_search_results(results, bibtex_output, use_original_key):
    if not bibtex_output:
        textwrapper = textwrap.TextWrapper(subsequent_indent="  ")
    for (fulltext, event, original_key) in results:
        entry = fulltext_to_single_entry(fulltext)
        if use_original_key:
            entry.key = original_key
            fulltext = single_entry_to_fulltext(entry)
        if bibtex_output:
            print(fulltext + "\n")
        else:
            author = [a.pretty() for a in bibutils.parse_names(entry.fields["author"])]
            author = ", ".join(author[:-2] + [" and ".join(author[-2:])])
            try:
                utf_author = bibutils.tex_to_unicode(entry.fields.get("author"))
                utf_title = bibutils.tex_to_unicode(entry.fields.get("title"))
            except:
                utf_author = entry.fields.get("author")
                utf_title = entry.fields.get("title")
            lines = textwrapper.wrap('[{key}] {author} "{title}", {event}{year}'.format(
                            key=entry.key,
                            author=utf_author,
                            title=utf_title,
                            event = event.upper() + " " if event else "",
                            year=entry.fields["year"]))
            print("\n".join(lines) + "\n")

def _find(args):
    db = BibDB()
    format_search_results(db.search(args.terms), args.bibtex, args.original_key)

def _where(args):
    db = BibDB()
    format_search_results(db.where(args), args.bibtex, args.original_key)

def _open(args):
    db = BibDB()
    results = db.search(args.terms)
    if not results:
        logging.error("No documents returned by query")
        sys.exit(1)
    elif len(results) > 1:
        logging.error("%d results returned by query. Narrow down to only one results.", len(results))
        sys.exit(1)
    entry = fulltext_to_single_entry(results[0][0])
    logging.info('Downloading "%s"', entry.fields["title"])
    if "url" not in entry.fields:
        logging.error("Entry does not contain an URL field")
    if not os.path.exists(config.tempdir):
        os.makedirs(config.tempdir)
    temp_fname = download_file(entry.fields["url"], os.path.join(config.tempdir, entry.key + ".pdf"))
    subprocess.run([config.opencommand, temp_fname])

class AddFileError(BibsearchError):
    pass

def _add_file(event, fname, force_redownload, db, per_file_progress_bar):
    """
    Return #added, #skipped, file_skipped
    """
    if fname.startswith('http'):
        if not force_redownload and db.file_has_been_downloaded(fname): 
            return 0, 0, True
        try:
            new_entries = pybtex.parse_string(download_file(fname),
                                              bib_format="bibtex").entries
        except urllib.error.URLError as e:
            raise AddFileError("Error downloading '%s' [%s]" % (fname, str(e)))
        except pybtex.PybtexError:
            raise AddFileError("Error parsing file %s" % fname)
        db.register_file_downloaded(fname)
    else:
        new_entries = pybtex.parse_file(fname,
                                        bib_format="bibtex").entries

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

    return added, skipped, False

def get_fnames_from_bibset(raw_fname, override_event):
    bib_spec = raw_fname[len(BIBSETPREFIX):].strip()
    spec_fields = bib_spec.split('/')
    resource = spec_fields[0]
    try:
        currentSet = yaml.load(download_file(config.database_url + resource + ".yml"))
        #~ currentSet = yaml.load(open("resources/" + resource + ".yml")) # for local testing
    except urllib.error.URLError:
        logging.error("Could not find resource %s", resource)
        sys.exit(1)
    # TODO: Ugly logic for detecting events
    prev_level = resource
    prev_level_2 = None
    if len(spec_fields) > 1:
        for f in spec_fields[1:]:
            # some keys are integers (years)
            try:
                currentSet = currentSet[f]
                prev_level_2 =  prev_level
                prev_level = f
            except KeyError:
                logging.error("Invalid branch '%s' in bib specification '%s'",
                              f, raw_fname)
                logging.error("Options at this level are:", ', '.join(currentSet.keys()))
                sys.exit(1)
    def rec_extract_bib(dict_or_list, override_event,
                        prev_level, prev_level_2=None):
        result = []
        if isinstance(dict_or_list, list):
            event = override_event if override_event else prev_level_2
            result = [(event, fname) for fname in dict_or_list]
        else:
            for (k, v) in dict_or_list.items():
                result += rec_extract_bib(v, override_event, k, prev_level)
        return result
    return rec_extract_bib(currentSet,
                           override_event if override_event else None,
                           prev_level, prev_level_2)


def _arxiv(args):
    import feedparser

    db = BibDB()

    query = 'http://export.arxiv.org/api/query?{}'.format(urllib.parse.urlencode({ 'search_query': ' AND '.join(args.query)}))
    response = download_file(query)

    feedparser._FeedParserMixin.namespaces['http://a9.com/-/spec/opensearch/1.1/'] = 'opensearch'
    feedparser._FeedParserMixin.namespaces['http://arxiv.org/schemas/atom'] = 'arxiv'
    feed = feedparser.parse(response)

    # print out feed information
    # print('Feed title: %s' % feed.feed.title)
    # print('Feed last updated: %s' % feed.feed.updated)

    # # print opensearch metadata
    # print('totalResults for this query: %s' % feed.feed.opensearch_totalresults)
    # print('itemsPerPage for this query: %s' % feed.feed.opensearch_itemsperpage)
    # print('startIndex for this query: %s'   % feed.feed.opensearch_startindex)

    # Run through each entry, and print out information
    for entry in feed.entries:

        fields = { 'title': entry.title,
                   'booktitle': '',
                   'year': str(entry.published[:4]),
                   'abstract': entry.summary,
        }

        try:
            fields['comment'] = entry.arxiv_comment
        except AttributeError:
            pass

        # get the links to the pdf
        for link in entry.links:
            try:
                if link.title == 'pdf':
                    fields['url'] = link.href
            except:
                pass

        authors = {'author': [pybtex.Person(author.name) for author in entry.authors]}
        bib_entry = pybtex.Entry('article', persons=authors, fields=fields)
        bib_entry.key = generate_custom_key(bib_entry)

        arxiv_id = re.sub(r'v\d+$', '', entry.id.split('/abs/')[-1])

        format_search_results( [(single_entry_to_fulltext(bib_entry), 'arXiv', arxiv_id)], False, True)

        if args.add:
            db.add('arXiv', bib_entry)

        continue

    if args.add:
        db.save()


def _add(args):
    db = BibDB()

    added = 0
    skipped = 0
    n_files_skipped = 0
    for raw_fname in args.files:
        event_fnames = [(args.event, raw_fname)] if not raw_fname.startswith(BIBSETPREFIX) \
                             else get_fnames_from_bibset(raw_fname, args.event)
        if len(event_fnames) > 1:
            iterable = tqdm(event_fnames, ncols=80, bar_format="Adding %s {l_bar}{bar}| [Elapsed: {elapsed} ETA: {remaining}]" % raw_fname)
            per_file_progress_bar = False
        else:
            iterable = event_fnames
            per_file_progress_bar = True
        error_msgs = []
        for event, f in iterable:
            try:
                f_added, f_skipped, file_skipped = _add_file(event, f, args.redownload, db, per_file_progress_bar)
                if args.verbose and not per_file_progress_bar:
                    if not file_skipped:
                        log_msg = "Added %d entries from %s" % (f_added, f)
                        if event:
                            log_msg += " (%s)" % event.upper()
                        else:
                            log_msg += " (NO EVENT)"
                    else:
                        log_msg = "Skipped %s" % f
                    tqdm.write(log_msg)
            except AddFileError as e:
                f_added = 0
                f_skipped = 0
                file_skipped = False
                error_msgs.append(str(e))
            added += f_added
            skipped += f_skipped
            if file_skipped:
                n_files_skipped += 1

    print('Added', added, 'entries, skipped', skipped, 'duplicates. Skipped', n_files_skipped, 'files')
    if error_msgs:
        print("During operation followint errors occured:")
        for m in error_msgs:
            logging.error(m)
    db.save()

def _print(args):
    db = BibDB()
    if args.summary:
        print('Database has', len(db), 'entries')
    else:
        for entry in db:
            print(entry.rstrip() + "\n")

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
    entries = set()
    for l in open(aux_fname):
        match = citation_re.match(l)
        if match:
            keystr = match.group(1)
            for key in keystr.split(','):
                bib_entry = db.search_key(key)
                if bib_entry:
                    entries.add(bib_entry)
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
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description='bibsearch: Download, manage, and search a BibTeX database.')
    parser.add_argument('--version', '-V', action='version', version='%(prog)s {}'.format(VERSION))
    parser.add_argument('-c', '--config_file', help="use this config file",
                        default=os.path.join(os.path.expanduser("~"),
                                             '.bibsearch',
                                             "bibsearch.config")
                        )
    parser.set_defaults(func=lambda _ : parser.print_help())
    subparsers = parser.add_subparsers()

    parser_add = subparsers.add_parser('add', help='Add a BibTeX file')
    parser_add.add_argument('files', type=str, default=None, help='BibTeX files to add', nargs='+')
    parser_add.add_argument("-e", "--event", help="Event for entries")
    parser_add.add_argument("-r", "--redownload", help="Re-download already downloaded files", action="store_true")
    parser_add.add_argument("-v", "--verbose", help="Be verbose about which files are being downloaded", action="store_true")
    parser_add.set_defaults(func=_add)

    parser_arxiv = subparsers.add_parser('arxiv', help='Search the arXiv')
    parser_arxiv.add_argument('query', type=str, nargs='+', default=None, help='Search query')
    parser_arxiv.add_argument("-a", "--add", action='store_true', help="Add all results to the database (default: just print them to STDOUT)")
    parser_arxiv.set_defaults(func=_arxiv)

    parser_dump = subparsers.add_parser('print', help='Print the BibTeX database')
    parser_dump.add_argument('--summary', action='store_true', help='Just print a summary')
    parser_dump.set_defaults(func=_print)

    parser_find = subparsers.add_parser('find', help='Search the database using fuzzy syntax', aliases=['search'])
    parser_find.add_argument('-b', '--bibtex', help='Print entries in bibtex format', action='store_true')
    parser_find.add_argument('-o', "--original-key", help='Print the original key of the entries', action='store_true')
    parser_find.add_argument('terms', nargs='*', help="One or more search terms which are ANDed together")
    parser_find.set_defaults(func=_find)

    parser_where = subparsers.add_parser('where', help='Search the database using SQL-like syntax')
    parser_where.add_argument('-k', '--key', help="Query for key field")
    parser_where.add_argument('-a', '--author', help="Query for author field")
    parser_where.add_argument('-t', '--title', help="Query for title field")
    parser_where.add_argument('-e', '--event', help="Query for event field")
    parser_where.add_argument('-y', '--year', help="Query for year field")
    parser_where.add_argument('-b', '--bibtex', help='Print entries in bibtex format', action='store_true')
    parser_where.add_argument('-o', "--original-key", help='Print the original key of the entries', action='store_true')
    parser_where.add_argument('terms', nargs='*', help="One or more search terms which are ANDed together")
    parser_where.set_defaults(func=_where)

    parser_open = subparsers.add_parser('open', help='Open the article, if search returns only one result and url is available')
    parser_open.add_argument('terms', nargs='*', help="One or more search terms which are ANDed together")
    parser_open.set_defaults(func=_open)

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
    config.initialize(args.config_file)
    args.func(args)

if __name__ == '__main__':
    main()
