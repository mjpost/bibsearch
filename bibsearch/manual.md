bibsearch(1) -- BibTeX database management tool
===============================================

## SYNOPSIS

`bibsearch` [<global options>] <command> [<command options>]

## DESCRIPTION

Bibsearch is a tool for downloading, searching, and managing BibTeX
entries.  It attempts to make use of the official BibTeX entries for
various collections of proceedings, all without you ever needing to
open a web browser and fumble around on Google Scholar or other tools.
Its key features are:

- Automatic downloading of official citations from predefined collections (`bibsearch add bib://`) or arbitrary URI's (`bibsearch add`)
- Keyword-based search against a private collection of entries (`bibsearch search`)
- Searching and downloading from the arXiv (`bibsearch arxiv`)
- Automatic generation of a BibTeX file from LaTeX source (`bibsearch tex`)
- Keyword-based downloading and opening of PDF files (`bibsearch open`)

## GLOBAL OPTIONS

* `-c`, `--config`:
    Specify the config file used by `bibsearch`. The options accepted in the
    config file are listed in the [CONFIG FILE][] section.

* `-V`, `--version`:
    Show `bibsearch` version.

* `-h`, `--help`:
    Show a short help message.

## COMMANDS

Bibsearch operation is guided by commands. Each command accepts the `-h`,
`--help` option to list additional options.

* `add` <files> or <URLs> or <bibspecs>:
    Adds entries to the BibTeX database. Three types of inputs are supported:
    <files>, <URLs> and <bibspecs>.
    <files> are local files present in the filesystem.
    <URLs> are http addresses. The file will be downloaded and added to the
    database.
    <bibspecs> have the form `bib://<spec>`, e.g. `bib://acl`. These are known
    resources for `bibsearch` which will be updated as new conferences are
    held. The list of know resources can be listed with the special
    `bib://list` specification. For some of these resources, finer grain
    specification is available, e.g. you can specify `bib://acl/emnlp` for only
    adding the EMNLP conference.
    `bibsearch` stores which URLs have already been downloaded, and by default
    does not re-download them again. In this way you can update your database
    efficiently by giving a bibspec resource, `bibsearch` will only download
    the new entries. If you still want to re-download known files, use the `-r`
    flag.

* `search` [<query>]:
    Searches the database. For the syntax of search queries look at the [SEARCH QUERIES][] section. By default the search results are listed in a
    human-readable format. Use the `-b` option to show them in BibTeX format.

* `arxiv` [<query>]:
    TODO

* `open` [<query>]:
    Opens the corresponding paper if the <query> returns only one result.
    Requires the BibTeX entry to specify an <URL> field. See the [SEARCH QUERIES][] section for the syntax of the <query>.

* `download` [<query>]:
    Downloads the papers returned by query to the directory specified in the
    [CONFIG FILE][]. Defaults to a <bibsearch> subdirectory in your system's
    default temporary directory.

* `tex` <file>:
    Generates the BibTeX file corresponding to a .tex file. The information is
    read from the .aux file, i.e. LaTeX needs to have been run at least once.
    By default the BibTeX entries are printed to stdout. With the `-b` option
    the bib file specified in the .tex file is generated, although it will not
    be overwritten if it already exists. Use `-B` if you want to overwrite the
    file.

* `edit` [<query>]:
    Opens an external editor to edit the BibTeX entries returned by the
    <query>. Please do not modify the `original_key` field, as this is used
    internally by `bibsearch` to identify the entries.

* `remove` [<query>]:
    Removes the entries returned by <query>.

* `macros`:
    Lists the macros known by bibsearch that can be used in search queries.

* `man`:
    Shows this man page.

## SEARCH QUERIES

If available, queries will be processed by sqlite's full text search system
(FTS, see https://www.sqlite.org/fts5.html). This means that in general you just type the
terms you want to look for, as you would do in an online search engine. E.g. for
searching for papers by David Vilar published in 2015, you can just type

    bibsearch search david vilar 2015

or if you are looking for the seminal paper on statistical machine translation

    bibsearch search brown mathematics machine translation

If FTS is not available in your system, `bibsearch` will do its best to
approximate the results. Note however that the search quality will be better for
systems supporting FTS (e.g. not using FTS the first query above will also match
papers for author David Vilares). Have a look at the installation section of the
README file for pointers for enabling FTS on your system.

If you do not specify any query terms, the results of the last search will be
reused. This works across commands, i.e. you can search for the paper you are
interested in through the `search` command and then just open the result simply
typing `bibsearch open`.

Although in most cases it will not be necessary, if you want to narrow down your
search, you can specify the relevant fields for each search term. Known fields
are

* author
* title
* venue
* year
* key

You specify them by prepending the search term with the desired field
specification, separated with a colon ':'. E.g. if you want to look for papers
by [Matt] Post, but not necessarily all papers containing "post-processing" or
similar in the title, you can issue the command

    bibsearch search author:post

Remember to quote the search terms if they include more than one word. But keep
also in mind, that author names are normalized in the form "surname, given name"
in the database, i.e. if you want to search for Matt Post, you would do

    bibsearch search author:"post, matt"

or perhaps more robustly

    bibsearch search author:matt author:post

You can also use pre-defined macros for more convenient queries. `bibsearch`
provides some pre-defined macros for well-known conferences in the area of
computational linguistics (the research area of the authors) which can be listed
with the `macros` command. E.g. if you want to look for papers by Matt Post in
the ACL conference, you may use

    bibsearch search matt post @acl

which internally will get expanded to

    bibsearch search matt post venue:"Annual Meeting of the Association for Computational Linguistics"

You can define your own custom macros in the [CONFIG FILE][].  Macros
pre-defined by `bibsearch` will always start with the '@' symbol.

## CONFIG FILE

By default, `bibsearch` will load $HOME/.bibsearch/config, but an alternative
config file can be specified via the `-c` option. The format of this file is
"similar to what’s found in Microsoft Windows INI files" (or more specifically
what is supported by python's configparser library, see
https://docs.python.org/3/library/configparser.html). An example of the contents
of such a config file could be

    [bibsearch]
    bibsearch_dir = /Users/dvilar/bibsearch_dir
    download_dir = /Users/dvilar/downloaded_papers
    open_command = zathura
    custom_key_format = {surname}{et_al}{short_year}{suffix}_{title}

    [macros]
    mp = matt post
    dv = david vilar

The main section of the config file has the <[bibsearch]> label. Supported
options are

* `bibsearch_dir`:
The directory where different `bibsearch` files (including the database)
will be stored in.

* `download_dir`:
The target directory to download papers to for the `open` and `download`
commands. If not specified, a temporary directory will be used.

* `open_command`:
The command that will be used to open pdf files. This command will be called
with the file name of the pdf file as first and only argument.

* `database_url`:
The URL to query when parsing bibset specifications in the `add` command.

* `custom_key_format`:
The format used for generating custom keys. See [CUSTOM BIBTEX KEYS][]

* `editor`:
The editor used for editing entries in the `edit` command. The command will be
called with a single file path as argument.

The <[macros]> section can be used for defining custom macros for usage in
commands that accept queries. See [SEARCH QUERIES][] for details.

## CUSTOM BIBTEX KEYS

`bibsearch` will generate custom BibTeX keys for the entries. By default it
will use the last name of the first author, the publication year and the first
non-function word of the title, e.g.

    @Article{brown1993:mathematics,
        author = "Brown, Peter E. and Pietra, Stephen A. Della and Pietra, Vincent J. Della and Mercer, Robert L.",
        title = "The Mathematics of Statistical Machine Translation: Parameter Estimation",
        journal = "Computational Linguistics, Volume 19, Number 2, June 1993, Special Issue on Using Large Corpora: II",
        year = "1993",
        url = "http://www.aclweb.org/anthology/J93-2003"
    }

You can customize the format of the keys in the config file, using the
custom_key_format option (see [CONFIG FILE][]). You can specify any string, with
special fields delimited by curly braces which will substituted with information
extracted from the entry, e.g. the default string is
{surname}{year}{suffix}:{title}.

The supported keywords are

* `{surname}`:
Surname of the first author of the paper.

* `{et_al}`:
"_etAl" will be added if there is more than one author.

* `{year}`:
The year of publication.

* `{short_year}`:
The year of publication in short form (i.e. the last two digits).

* `{suffix}`:
An alphabetical suffix to avoid conflicts in key generation (e.g. brown1993 and
brown1993a).

* `{title}`:
The first non-function word of the title.

## BUGS

Currently tildes ('~') are not correctly handled.

## SEE ALSO

bibtex(1)
