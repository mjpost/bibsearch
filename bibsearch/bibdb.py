import functools
import logging
import os.path
import pybtex.database as pybtex
import sqlite3
import sys
import yaml

from typing import Tuple

from . import bibutils

class BibDB:
    def __init__(self, config):
        self.config = config
        self.fname = os.path.join(self.config.bibsearch_dir, "bib.db")

        self.column_names_no_key = ["author", "title", "venue", "year"]

        createDB = False
        if not os.path.exists(self.fname):
            if not os.path.exists(os.path.dirname(self.fname)):
                os.makedirs(os.path.dirname(self.fname))
            createDB = True
        self.connection = sqlite3.connect(self.fname)
        self.cursor = self.connection.cursor()
        if createDB:
            self._create_db()
        # Find out if we have FTS
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bibindex'")
        self.has_fts = bool(self.cursor.fetchone())

    def _create_db(self):
        self.cursor.execute("""CREATE TABLE bib (
            key text UNIQUE,
            custom_key text UNIQUE,
            author text,
            title text,
            venue text,
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
                venue,
                year,
                fulltext UNINDEXED,
                content='bib',
                );
            CREATE TRIGGER bib_ai AFTER INSERT ON bib BEGIN
               INSERT INTO bibindex
                   (rowid, key, custom_key, author, title, venue, year, fulltext)
                   VALUES 
                   (new.rowid, new.key, new.custom_key, new.author, new.title, 
                   new.venue, new.year, new.fulltext);
                END;
            CREATE TRIGGER bib_ad AFTER DELETE ON bib BEGIN
               INSERT INTO bibindex
                   (bibindex, rowid, key, custom_key, author, title, venue, year, fulltext)
                   VALUES 
                   ('delete', old.rowid, old.key, old.custom_key, old.author, old.title, 
                   old.venue, old.year, old.fulltext);
                END;
            CREATE TRIGGER bibindex_au AFTER UPDATE ON bib BEGIN
               INSERT INTO bibindex
                   (bibindex, rowid, key, custom_key, author, title, venue, year, fulltext)
                   VALUES 
                   ('delete', old.rowid, old.key, old.custom_key, old.author, old.title, 
                   old.venue, old.year, old.fulltext);
               INSERT INTO bibindex
                   (rowid, key, custom_key, author, title, venue, year, fulltext)
                   VALUES 
                   (new.rowid, new.key, new.custom_key, new.author, new.title, 
                   new.venue, new.year, new.fulltext);
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

    def save_to_search_cache(self, search: Tuple[str,str,str]) -> None:
        """
        Saves the result of a search, which is represented as a tuple: (full bibtex, collection, key).
        This can then be used by subcommands that support implicit arguments, like 'open'.
        """
        last_results_fname = os.path.join(self.config.bibsearch_dir, "lastSearch.yml")
        with open(last_results_fname, "w") as fp:
            yaml.dump(search, fp)

    def load_search_cache(self) -> Tuple[str,str,str]:
        """
        Returns the result of a cached search.
        """
        last_results_fname = os.path.join(self.config.bibsearch_dir, "lastSearch.yml")
        if os.path.exists(last_results_fname):
            return yaml.load(open(last_results_fname))

    def _format_query_fts(self, query_terms):
        processed_query_terms = []
        for t in query_terms:
            current_term = t
            if t in self.config.macros:
                current_term = self.config.macros[t]
                # TODO: for now we trust macros blindly
            else:
                if not (current_term.startswith("author:") or
                        current_term.startswith("key:") or
                        current_term.startswith("title:") or
                        current_term.startswith("venue:") or
                        current_term.startswith("year")):
                    # Protect the whole sequence
                    if current_term[0] != '"' and current_term[-1] != '"':
                        current_term = '"%s"' % current_term
                else:
                    specifier, query = current_term.split(":", 1)
                    quoted_query = query if (query[0] == '"' and query[-1] == '"') \
                                         else '"%s"' % query
                    if specifier == "key":
                        current_term = '(key:%s OR custom_key:%s)' % (quoted_query, quoted_query)
                    else:
                        current_term = '%s:%s' % (specifier, quoted_query)
            processed_query_terms.append(current_term)
        return " AND ".join(processed_query_terms)

    def _format_query_no_fts(self, input_terms):
        query_terms = []
        query_values = []
        for t in input_terms:
            if not functools.reduce(lambda x, y: x or y,
                                    [t.startswith(c + ":")
                                     for c in self.column_names_no_key + ["key"]]):
                current_terms = []
                for c in self.column_names_no_key + ["key", "custom_key"]:
                    current_terms.append('(%s LIKE ?)' % c)
                    query_values.append('%%%s%%' % t)
                query_terms.append("(%s)" % " OR ".join(current_terms))
            else:
                specifier, query = t.split(":", 1)
                wildquery = '%%%s%%' % query
                if specifier == "key":
                    query_terms.append('((key LIKE ?) OR (custom_key LIKE ?))')
                    query_values.append(wildquery)
                    query_values.append(wildquery)
                else:
                    query_terms.append('(%s LIKE ?)' % specifier)
                    query_values.append(wildquery)
        return " AND ".join(query_terms), query_values

    def search(self, query: str):
        """
        Performs a search against the private database.

        :param query: The search query.
        :return: A list of search results.
        """
        if self.has_fts:
            self.cursor.execute("SELECT fulltext, key FROM bibindex \
                                WHERE bibindex MATCH ?",
                                [self._format_query_fts(query)])
        else:
            where_clause, query_values = self._format_query_no_fts(query)
            self.cursor.execute("SELECT fulltext, key FROM bib \
                                    WHERE %s" % where_clause,
                                query_values)
        results = list(self.cursor)

        self.save_to_search_cache(results)

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
        entry = self.cursor.fetchone()
        if entry is not None:
            entry = bibutils.single_entry_to_fulltext(bibutils.fulltext_to_single_entry(entry[0]), overwrite_key=key)
        return entry

    def save(self):
        self.connection.commit()

    def remove(self, key: str):
        """Removes the entry"""

        self.cursor.execute('DELETE FROM bib WHERE key=? or custom_key=?', [key, key])

    def add(self, entry: pybtex.Entry):
        """ Returns if the entry was added or if it was a duplicate"""

        # TODO: make this a better sanity checking and perhaps report errors
        if not entry.key:
            return False
        if not entry.fields.get("author"):
            entry.fields["author"] = "UNKNOWN"

        original_key = entry.key
        entry.fields["original_key"] = original_key
        utf_author = bibutils.field_to_unicode(entry, "author")
        utf_title = bibutils.field_to_unicode(entry, "title")
        utf_venue = bibutils.field_to_unicode(entry, "journal")
        if not utf_venue:
            utf_venue = bibutils.field_to_unicode(entry, "booktitle")
        custom_key_tries = 0
        added = False
        while not added:
            custom_key = None
            if custom_key_tries < 27:
                try:
                    custom_key = bibutils.generate_custom_key(entry, self.config.custom_key_format, custom_key_tries)
                except Exception as e:
                    pass
            else:
                logging.warning("Could not generate a unique custom key for entry %s", original_key)
                custom_key = original_key
            try:
                self.cursor.execute('INSERT INTO bib(key, custom_key, author, title, venue, year, fulltext) VALUES (?,?,?,?,?,?,?)',
                                    (original_key,
                                     custom_key,
                                     utf_author,
                                     utf_title,
                                     utf_venue,
                                     str(entry.fields.get("year")),
                                     bibutils.single_entry_to_fulltext(entry, custom_key)
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
        entry = bibutils.fulltext_to_single_entry(self.cursor.fetchone()[0])
        entry.key = new_custom_key
        try:
            self.cursor.execute("UPDATE bib SET custom_key=?, fulltext=? WHERE key=?",
                                [new_custom_key,
                                 bibutils.single_entry_to_fulltext(entry),
                                 original_key])
            self.save()
        except:
            logging.error("Key %s already exists in the database", new_custom_key)
            sys.exit(1)

    def update(self, entry: pybtex.Entry):
        """ Returns if the entry was added or if it was a duplicate"""

        # TODO: make this a better sanity checking and perhaps report errors
        if not entry.key:
            return False

        original_key = entry.fields["original_key"]
        utf_author = bibutils.field_to_unicode(entry, "author")
        utf_title = bibutils.field_to_unicode(entry, "title")
        utf_venue = bibutils.field_to_unicode(entry, "journal")
        if not utf_venue:
            utf_venue = bibutils.field_to_unicode(entry, "booktitle")
        try:
            self.cursor.execute('UPDATE bib SET custom_key=?, author=?, title=?, venue=?, year=?, fulltext=? WHERE key=?',
                                (entry.key,
                                 utf_author,
                                 utf_title,
                                 utf_venue,
                                 str(entry.fields.get("year")),
                                 bibutils.single_entry_to_fulltext(entry),
                                 original_key
                                )
                               )
        except sqlite3.IntegrityError as e:
            error_message = str(e)
            if "UNIQUE" in error_message:
                if "bib.custom_key" in error_message:
                    logging.error("Key %s already exists in the database")
                else:
                    raise
            else:
                raise

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
