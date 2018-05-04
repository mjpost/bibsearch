#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tool for downloading, maintaining, and searching a BibTeX database.

Authors:
- Matt Post <post@cs.jhu.edu>
- David Vilar <david.vilar@gmail.com>
"""

import argparse
import click
import logging
import os
import re
import sys
from typing import List
import urllib.request
import pybtex.database as pybtex
import subprocess
import tempfile
import textwrap
from tqdm import tqdm
import yaml

from .bibdb import BibDB
from . import bibutils
from .config import Config

VERSION = '0.2.0'

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

def format_search_results(results,
                          bibtex_output=False,
                          use_original_key=False) -> str:
    if not bibtex_output:
        textwrapper = textwrap.TextWrapper(subsequent_indent="  ")
    output = ""
    for (fulltext, original_key) in results:
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
            lines = textwrapper.wrap('[{key}] {author} "{title}", {venue}{year}'.format(
                            key=entry.key,
                            author=utf_author,
                            title=utf_title,
                            venue=utf_venue + ", ",
                            year=entry.fields["year"]))
            output += "\n".join(lines) + "\n\n"
    return output[:-1] # Remove the last empty line

# CLI definition ###############################################################
@click.group(context_settings={"help_option_names": ['-h', '--help']})
@click.option('-c', '--config-file', help="use this config file", 
              metavar="CONFIG",
              default=os.path.join(os.path.expanduser("~"),
                                   '.bibsearch',
                                   "config")
              )
@click.version_option(version=VERSION)
@click.pass_context
def cli(ctx, config_file):
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] %(message)s")
    # Needed when going through setuptools
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["config"] = Config(config_file)

@cli.command(help="Search the database")
@click.option("-b", "--bibtex", help="Print entries in bibtex format", is_flag=True)
@click.option("-o", "--original-key", help="Print the original key of the entries", is_flag=True)
@click.argument("terms", nargs=-1)
@click.pass_context
def search(ctx, bibtex, original_key, terms):
    db = BibDB(ctx.obj["config"])
    print(format_search_results(db.search(terms), bibtex, original_key), end='')

@cli.command(name="open",
             short_help="Download and open paper",
             help="Download and open the paper returned by search, if only one result is returned and the entry contains an 'url' field")
@click.argument("terms", nargs=-1)
@click.pass_context
def open_bib_url(ctx, terms):
    config = ctx.obj["config"]
    db = BibDB(config)
    results = db.search(terms)
    if not results:
        logging.error("No documents returned by query")
        sys.exit(1)
    elif len(results) > 1:
        logging.error("%d results returned by query. Narrow down to only one results.", len(results))
        sys.exit(1)
    entry = bibutils.fulltext_to_single_entry(results[0][0])
    logging.info('Downloading "%s"', entry.fields["title"])
    if "url" not in entry.fields:
        logging.error("Entry does not contain an URL field")
    if not os.path.exists(config.download_dir):
        os.makedirs(config.download_dir)
    temp_fname = download_file(entry.fields["url"], os.path.join(config.download_dir, entry.key + ".pdf"))
    subprocess.run([config.open_command, temp_fname])

@cli.command(short_help="Download papers",
             help="Download papers returned by search, if the entries contain an 'url' field")
@click.argument("terms", nargs=-1)
@click.pass_context
def download(ctx, terms):
    config = ctx.obj["config"]
    db = BibDB(config)
    results = db.search(terms)
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


@cli.command(help="Search the arXiv")
@click.option("-a", "--add", is_flag=True,
              help="Add all results to the database (default: just print them to STDOUT)")
@click.argument("terms", nargs=-1)
@click.pass_context
def arxiv(ctx, add, terms):
    import feedparser

    config = ctx.obj["config"]
    db = BibDB(config)

    query = 'http://export.arxiv.org/api/query?{}'.format(urllib.parse.urlencode({ 'search_query': ' AND '.join(terms)}))
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
    results_to_save = []
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

        print(format_search_results( [(bibutils.single_entry_to_fulltext(bib_entry), arxiv_id)],
                                     bibtex_output=False,
                                     use_original_key=True))

        if add:
            db.add(bib_entry)
            results_to_save.append((bibutils.single_entry_to_fulltext(bib_entry), bib_entry.key))
        else:
            results_to_save.append((bibutils.single_entry_to_fulltext(bib_entry), arxiv_id))

        db.save_to_search_cache(results_to_save)

    if add:
        db.save()


@cli.command(help="Remove an entry")
@click.argument("terms", nargs=-1)
@click.pass_context
def remove(ctx, terms):
    db = BibDB(ctx.obj["config"])
    search_results = db.search(terms)
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

@cli.command(help="Add BibTeX files")
@click.option("-r", "--redownload", help="Re-download already downloaded files", is_flag=True)
@click.option("-v", "--verbose", help="Be verbose about which files are being downloaded", is_flag="True")
@click.argument("files", nargs=-1)
@click.pass_context
def add(ctx, redownload, verbose, files):
    config = ctx.obj["config"]
    db = BibDB(config)

    for raw_fname in files:
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
                f_added, f_skipped, file_skipped = _add_file(f, redownload, db, per_file_progress_bar)
                if verbose and not per_file_progress_bar:
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

@cli.command(name="print", help="Print the BibTeX database")
@click.option("--summary", help="Just print a summary", is_flag=True)
@click.pass_context
def print_db(ctx, summary):
    db = BibDB(ctx.obj["config"])
    if summary:
        print('Database has', len(db), 'entries')
    else:
        for entry in db:
            print(entry.rstrip() + "\n")

@cli.command(help="Create .bib file for a latex article")
@click.option('-b', '--write-bibfile', help='Autodetect and write bibfile', is_flag=True)
@click.option('-B', '--overwrite-bibfile', help='Autodetect and write bibfile', is_flag=True)
@click.argument('file')
@click.pass_context
def tex(ctx, file, write_bibfile, overwrite_bibfile):
    citation_re = re.compile(r'\\citation{(.*)}')
    bibdata_re = re.compile(r'\\bibdata{(.*)}')
    db = BibDB(ctx.obj["config"])
    aux_fname = file
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
        elif write_bibfile or overwrite_bibfile:
            match = bibdata_re.match(l)
            if match:
                bibfile = match.group(1)
    if bibfile:
        bibfile = os.path.join(os.path.dirname(aux_fname), bibfile+".bib")
        if os.path.exists(bibfile):
            if overwrite_bibfile:
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

@cli.command(help="Edit entries")
@click.argument("terms", nargs=-1)
@click.pass_context
def edit(ctx, terms):
    config = ctx.obj["config"]
    db = BibDB(config)
    
    search_results = db.search(terms)
    if not search_results:
        logging.error("Search returned no results. Aborting.")
        sys.exit(1)

    with tempfile.NamedTemporaryFile("w") as temp_file:
        temp_fname = temp_file.name
        with open(temp_fname, "wt") as fp:
            original_entries_text = format_search_results(search_results,
                                                          bibtex_output=True,
                                                          use_original_key=False)
            fp.write(original_entries_text)
            original_entries = pybtex.parse_string(original_entries_text,
                                                   bib_format="bibtex").entries.values()
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
        logging.warning("There were not changes in the entries.")
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

@cli.command(help="Show defined macros")
@click.pass_context
def macros(ctx):
    config = ctx.obj["config"]
    for macro, expansion in config.macros.items():
        print("%s:\t%s" % (macro, expansion))

@cli.command(help="Shows the documentation")
def man():
    subprocess.run(["man", 
                    os.path.join(os.path.dirname(__file__), "manual.1")])
