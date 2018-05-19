#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool for downloading, maintaining, and searching a BibTeX database.

Authors:
- David Vilar <david.vilar@gmail.com>
- Matt Post <post@cs.jhu.edu>
"""

import argparse
import logging
import os
import re
import sys
from typing import List, Tuple
import urllib.request
import pybtex.database as pybtex
import subprocess
import tempfile
import textwrap
from tqdm import tqdm
import yaml

from pkg_resources import resource_filename, resource_exists

from .bibdb import BibDB
from . import bibutils
from .config import Config

VERSION = '0.3.6'

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

def prompt(message: str, *answers_in: List[str], default=0, case_insensitive=True):
    valid_answers = [a.lower() for a in answers_in] if case_insensitive else answers_in
    single_letter_answers = [a[0] for a in valid_answers]
    assert len(valid_answers) == len(set(valid_answers)), "Answers are not unique"
    assert len(single_letter_answers) == len(set(single_letter_answers)), "Single letter answers are not unique"
    answer = input("%s [%s] " % (message, "/".join(answers_in)))
    answer_index = -1
    while answer_index < 0:
        if not answer and default >= 0:
            answer_index = default
        else:
            if case_insensitive:
                answer = answer.lower()
            try:
                answer_index = valid_answers.index(answer)
            except ValueError:
                try:
                    answer_index = single_letter_answers.index(answer)
                except ValueError:
                    answer = input("Please answer one of %s: " % "/".join(answers_in))
    return answers_in[answer_index]




def download_file(url, fname_out=None) -> None:
    """
    Downloads a file to a location.
    """

    import ssl

    #~ logging.info('Downloading {} to {}'.format(url, fname_out if fname_out is not None else 'STR'))

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

def format_search_results(results: List[Tuple[str,str]],
                          bibtex_output=False,
                          use_original_key=False) -> str:
    """
    Formats a set of (Pybtex.Entry, custom_key) pairs for printing to the terminal.
    Output can be either actual BibTeX or a summarized form.

    :param results: A list of pairs of full bibtex entries and their associated keys
    :param bibtex_output: Whether to retun the result as a bibtex entry instead of summarized text.
    :param use_original_key: Whether to use the default key instead of the custom one.
    :return: An amalgamated string including all entries.
    """

    if not bibtex_output:
        textwrapper = textwrap.TextWrapper(subsequent_indent="     ")
    output = ""
    for entryno, (fulltext, original_key) in enumerate(results, 1):
        entry = bibutils.fulltext_to_single_entry(fulltext)
        if use_original_key:
            entry.key = original_key
            fulltext = bibutils.single_entry_to_fulltext(entry)
        if bibtex_output:
            output += fulltext + "\n"
        else:
            utf_author = bibutils.field_to_unicode(entry, "author", "")
            utf_author = [a.pretty() for a in bibutils.parse_names(utf_author)]
            utf_author = ", ".join(utf_author[:-2] + [" and ".join(utf_author[-2:])])

            utf_title = bibutils.field_to_unicode(entry, "title", "")
            utf_venue = bibutils.field_to_unicode(entry, "journal", "")
            if not utf_venue:
                utf_venue = bibutils.field_to_unicode(entry, "booktitle", "")
            lines = textwrapper.wrap('{index}. [{key}] {author} "{title}", {venue}{year}\n{url}'.format(
                            index=entryno,
                            key=entry.key,
                            author=utf_author,
                            title=utf_title,
                            venue=utf_venue + ", ",
                            year=entry.fields["year"],
                            url=entry.fields["url"]))
            output += "\n".join(lines) + "\n\n"
    return output[:-1] # Remove the last empty line

def _get_cache_or_search_result(db: BibDB,
                                search_terms: List[str]) -> Tuple[str, str]:
    """
    If search_terms is empty or a single digit, return that item from
    the cache. Otherwise, return the first item from the search results.
    Item returned is a tuple (bibtex_str, custom_key).
    """
    if len(search_terms) == 0:
        # load the search cache, use first entry
        results = db.load_search_cache()
        if not results:
            logging.error("No documents found in search cache.")
            sys.exit(1)

        entry_index = 0

    elif len(search_terms) == 1 and re.match(r'\d+', search_terms[0]) is not None:
        # load the search cache, use specified entry
        results = db.load_search_cache()
        if not results:
            logging.error("No documents found in search cache.")
            sys.exit(1)

        entry_index = int(search_terms[0]) - 1

    else:
        results = db.search(args.terms)

        if not results:
            logging.error("Search returned no results.")
            sys.exit(1)

    if entry_index >= len(results):
        logging.error("You requested result {}, but only {} documents were found.".format(entry_index, len(results)))
        sys.exit(1)

    return results[entry_index]


def _find(args, config):
    db = BibDB(config)
    print(format_search_results(db.search(args.terms), args.bibtex, args.original_key), end='')

def _open(args, config):
    """
    Opens the PDF associated with the last search query (if no
    arguments were given) or the requested index (if a single numeric
    argument was given) or the results of a search term (all other cases).

    """
    db = BibDB(config)
    bibtex, key = _get_cache_or_search_result(db, args.terms)

    entry = bibutils.fulltext_to_single_entry(bibtex)
    if "url" not in entry.fields:
        logging.error("Entry does not contain an URL field")
    if not os.path.exists(config.download_dir):
        os.makedirs(config.download_dir)
    logging.info('Downloading "%s"', entry.fields["title"])
    temp_fname = download_file(entry.fields["url"], os.path.join(config.download_dir, entry.key + ".pdf"))
    subprocess.run([config.open_command, temp_fname])

def _download(args, config):
    db = BibDB(config)
    results = db.search(args.terms)
    if not results:
        logging.error("No documents returned by query")
        sys.exit(1)
    logging.info("Downloading to %s", config.download_dir)
    if not os.path.exists(config.download_dir):
        os.makedirs(config.download_dir)
    iterable = tqdm(results, ncols=80, bar_format="{l_bar}{bar}| [Elapsed: {elapsed} ETA: {remaining}]")
    for fulltext, _ in iterable:
        entry = bibutils.fulltext_to_single_entry(fulltext)
        tqdm.write('Downloading "%s"' % entry.fields["title"])
        if "url" not in entry.fields:
            logging.error("Entry does not contain an URL field")
        download_file(entry.fields["url"], os.path.join(config.download_dir, entry.key + ".pdf"))

class AddFileError(BibsearchError):
    pass

def _add_file(fname, force_redownload, db, per_file_progress_bar):
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
        if db.add(entry):
            added += 1
        else:
            skipped += 1

    return added, skipped, False

def get_fnames_from_bibset(raw_fname, database_url):
    bib_spec = raw_fname[len(BIBSETPREFIX):].strip()
    spec_fields = bib_spec.split('/')
    resource = spec_fields[0]
    if resource == "list":
        # Special case, list know resources
        textwrapper = textwrap.TextWrapper(subsequent_indent=10*" ")
        known_resources = download_file(database_url + "list.txt")
        for l in known_resources.split("\n"):
            line = l.strip()
            if line:
                name, description = line.split("\t")
                print("\n".join(textwrapper.wrap("%-10s%s" % (name, description))))
        return []
    try:
        currentSet = yaml.load(download_file(database_url + resource + ".yml"))
        #~ currentSet = yaml.load(open("resources/" + resource + ".yml")) # for local testing
    except urllib.error.URLError:
        logging.error("Could not find resource %s", resource)
        sys.exit(1)
    if len(spec_fields) > 1:
        for f in spec_fields[1:]:
            # some keys are integers (years)
            try:
                currentSet = currentSet[f]
            except KeyError:
                logging.error("Invalid branch '%s' in bib specification '%s'",
                              f, raw_fname)
                logging.error("Options at this level are:", ', '.join(currentSet.keys()))
                sys.exit(1)
    def rec_extract_bib(dict_or_list):
        result = []
        if isinstance(dict_or_list, list):
            result = [fname for fname in dict_or_list]
        else:
            for v in dict_or_list.values():
                result += rec_extract_bib(v)
        return result
    return rec_extract_bib(currentSet)


def _arxiv(args, config):
    import feedparser

    db = BibDB(config)

    query = ' AND '.join(['"{}"'.format(x) for x in args.query])
    # move the query field search terms outside the quotes
    query = re.sub(r'"au(thor)?:', 'au:"', query)
    query = re.sub(r'"ti(tle)?:', 'ti:"', query)
    query = 'http://export.arxiv.org/api/query?{}'.format(urllib.parse.urlencode({ 'search_query': query,
                                                                                   'max_results': args.max_results }))
    logging.info('ARXIV QUERY: %s', query)
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
    results = []
    for entry in feed.entries:
        arxiv_id = re.sub(r'v\d+$', '', entry.id.split('/abs/')[-1])

        fields = { 'title': entry.title,
                   'journal': 'Computing Research Repository',
                   'year': str(entry.published[:4]),
                   'abstract': entry.summary,
                   'volume': 'abs/{}'.format(arxiv_id),
                   'archivePrefix': 'arXiv',
                   'eprint': arxiv_id,
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
        bib_entry.key = bibutils.generate_custom_key(bib_entry, config.custom_key_format)

        if args.add:
            db.add(bib_entry)
            results.append((bib_entry, bib_entry.key))
        else:
            results.append((bib_entry, arxiv_id))

        # Save the results to the search cache
        db.save_to_search_cache([(bibutils.single_entry_to_fulltext(bib_entry), key) for bib_entry, key in results])

    print(format_search_results( [(bibutils.single_entry_to_fulltext(bib_entry), arxiv_id)],
                                 bibtex_output=False,
                                 use_original_key=True))

    if args.add:
        db.save()


def _remove(args, config):
    db = BibDB(config)
    search_results = db.search(args.terms)
    if not search_results:
        logging.error("Search returned no results. Aborting.")
        sys.exit(1)
    print("You are about to delete these entries:")
    print("")
    print(format_search_results(search_results))
    confirmation = prompt("Do you want to proced with the deletion?", "yes", "NO",
                          default=1)
    if confirmation == "yes":
        for (_, original_key) in search_results:
            db.remove(original_key)
        db.save()
        print("Removed %d entries." % len(search_results))
    else:
        print("Aborted.")


def _add(args, config):
    db = BibDB(config)

    for raw_fname in args.files:
        fnames = [raw_fname] if not raw_fname.startswith(BIBSETPREFIX) \
                             else get_fnames_from_bibset(raw_fname, config.database_url)
        added = 0
        skipped = 0
        n_files_skipped = 0
        if len(fnames) > 1:
            iterable = tqdm(fnames, ncols=80, bar_format="Adding %s {l_bar}{bar}| [Elapsed: {elapsed} ETA: {remaining}]" % raw_fname)
            per_file_progress_bar = False
        else:
            iterable = fnames
            per_file_progress_bar = True
        error_msgs = []
        for f in iterable:
            try:
                f_added, f_skipped, file_skipped = _add_file(f, args.redownload, db, per_file_progress_bar)
                if args.verbose and not per_file_progress_bar:
                    if not file_skipped:
                        log_msg = "Added %d entries from %s" % (f_added, f)
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

def _print(args, config):
    db = BibDB(config)
    if args.summary:
        print('Database has', len(db), 'entries')
    else:
        for entry in db:
            print(entry.rstrip() + "\n")

def _tex(args, config):
    citation_re = re.compile(r'\\citation{(.*)}')
    bibdata_re = re.compile(r'\\bibdata{(.*)}')
    db = BibDB(config)
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

def find_entry(entries_iter, field, value):
    for e in entries_iter:
        if e.fields.get(field) == value:
            return e
    return None

def compare_entries(old, new):
    added = set()
    deleted = set()
    edited = set()
    if old.key != new.key:
        edited.add("key")
    for old_field, old_value in old.fields.items():
        if not old_field in new.fields:
            deleted.add(old_field)
        else:
            if old_value != new.fields[old_field]:
                edited.add(old_field)
    added = set(new.fields.keys()) - set(old.fields.keys())
    return added, deleted, edited

def _edit(args, config):

    db = BibDB(config)
    bibtex, key = _get_cache_or_search_result(db, args.terms)

    with tempfile.NamedTemporaryFile("w") as temp_file:
        temp_fname = temp_file.name
        with open(temp_fname, "wt") as fp:
            original_entries_text = format_search_results(results=[(bibtex, key)],
                                                          bibtex_output=True,
                                                          use_original_key=False)
            fp.write(original_entries_text)
            original_entries = pybtex.parse_string(original_entries_text,
                                                   bib_format="bibtex").entries.values()
        logging.info('Using value of $EDITOR to choose editor.')
        subprocess.run([config.editor, temp_file.name])

        with open(temp_fname, "rt"):
            new_entries = pybtex.parse_file(temp_fname,
                                               bib_format="bibtex").entries.values()
    deleted_entries = []
    edited_entries = []
    seen_original_keys = set()
    changelog = []
    for new in new_entries:
        original_key = new.fields["original_key"]
        seen_original_keys.add(original_key)
        old = find_entry(original_entries,
                         "original_key",
                         original_key)
        added, deleted, edited = compare_entries(old, new)
        if added or deleted or edited:
            edited_entries.append(new)
            # Report changes
            edited_entries.append(new)
            changelog.append("\nEntry %s" % old.key)
            for field in added:
                changelog.append('\tAdded %s with value "%s"' % (field, new.fields[field]))
            for field in deleted:
                changelog.append("\tDeleted %s" % field)
            for field in edited:
                changelog.append('\tChanged %s to "%s"' %
                      (field,
                       new.key if field=="key" else new.fields[field]))
    for old in original_entries:
        if not old.fields["original_key"] in seen_original_keys:
            deleted_entries.append(old)
    if deleted_entries:
        changelog.append("\nDeleted entries:")
        for e in deleted_entries:
            changelog.append("\t%s" % e.key)

    if not edited_entries and not deleted_entries:
        logging.info("There were no changes in the entries.")
        sys.exit(0)

    print("Summary of changes:")
    print("\n".join(changelog) + "\n")

    confirmation = prompt("Do you want to perform these changes?", "YES", "no")
    if confirmation == "YES":
        for e in edited_entries:
            db.update(e)
        for e in deleted_entries:
            db.remove(e.key)
        db.save()
        print("Updated database.")
    else:
        print("Aborted.")

def _macros(args, config):
    for macro, expansion in config.macros.items():
        print("%s:\t%s" % (macro, expansion))

def _man(args, config):
    if not resource_exists('bibsearch', 'manual.1'):
        logging.error("Can't find manual page")
        sys.exit(1)

    manfile_path = resource_filename('bibsearch', 'manual.1')
    subprocess.run(["man", manfile_path])

# From https://stackoverflow.com/questions/13423540/argparse-subparser-hide-metavar-in-command-listing
class SubcommandHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action(self, action):
        #parts = super(argparse.RawDescriptionHelpFormatter, self)._format_action(action)
        parts = super()._format_action(action)
        if action.nargs == argparse.PARSER:
            parts = "\n".join(parts.split("\n")[1:])
        return parts

def main():
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="bibsearch: Download, manage, and search a BibTeX database.\nUse '%(prog)s man' to get complete help.",
                                     formatter_class=SubcommandHelpFormatter)
    parser.add_argument('--version', '-V', action='version', version='%(prog)s {}'.format(VERSION))
    parser.add_argument('-c', '--config_file', help="use this config file",
                        default=os.path.join(os.path.expanduser("~"),
                                             '.bibsearch',
                                             "config")
                        )
    parser.set_defaults(func=lambda *_ : parser.print_help())
    subparsers = parser.add_subparsers(title="commands",
                                       description="Use '%(prog)s <command> -h' to obtain additional help.",
                                       metavar="<command>")

    parser_add = subparsers.add_parser('add', help='Add a BibTeX file')
    parser_add.add_argument('files', type=str, default=None, help='BibTeX files to add', nargs='+')
    parser_add.add_argument("-r", "--redownload", help="Re-download already downloaded files", action="store_true")
    parser_add.add_argument("-v", "--verbose", help="Be verbose about which files are being downloaded", action="store_true")
    parser_add.set_defaults(func=_add)

    parser_arxiv = subparsers.add_parser('arxiv', help='Search the arXiv')
    parser_arxiv.add_argument('query', type=str, nargs='+', default=None, help='Search query')
    parser_arxiv.add_argument("-m", "--max-results", type=int, default=10, help="Maximum number of results to return") 
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

    parser_open = subparsers.add_parser('open', help='Open the article, if search returns only one result and url is available')
    parser_open.add_argument('terms', nargs='*', help="One or more search terms which are ANDed together")
    parser_open.set_defaults(func=_open)

    parser_download = subparsers.add_parser('download', help='download articles')
    parser_download.add_argument('terms', nargs='*', help="One or more search terms which are ANDed together")
    parser_download.set_defaults(func=_download)

    parser_tex = subparsers.add_parser('tex', help='Create .bib file for a latex article')
    parser_tex.add_argument('file', help='Article file name or .aux file')
    parser_tex.add_argument('-b', '--write-bibfile', help='Autodetect and write bibfile', action='store_true')
    parser_tex.add_argument('-B', '--overwrite-bibfile', help='Autodetect and write bibfile', action='store_true')
    parser_tex.set_defaults(func=_tex)

    parser_edit = subparsers.add_parser('edit', help='Edit entries')
    parser_edit.add_argument('terms', nargs='*', help='One or more search terms')
    parser_edit.set_defaults(func=_edit)

    parser_rm = subparsers.add_parser('remove', help='Remove an entry', aliases=['rm'])
    parser_rm.add_argument('terms', nargs='*', help='One or more search terms')
    parser_rm.set_defaults(func=_remove)

    parser_macros = subparsers.add_parser('macros', help='Show defined macros')
    parser_macros.set_defaults(func=_macros)

    parser_man = subparsers.add_parser('man', help='Shows documentation in form of a man page', aliases=['help'])
    parser_man.set_defaults(func=_man)

    args = parser.parse_args()
    config = Config(args.config_file)
    args.func(args, config)

if __name__ == '__main__':
    main()
