bibsearch(1) -- BibTeX database management tool
===============================================

## SYNOPSIS

`bibsearch` [<global options>] <command> [<command options>]

## DESCRIPTION

The process of searching for BibTeX entries is cumbersome and annoying. Authors
are inconsistent in providing them, and they are optional on the arXiv. Google
Scholar is useful, but yielding BibTeX entries requires drilling down into
entries. What's worse, for some research fields (such as citations from the ACL
Anthology), the correct citations are not the first search result. And anyway,
why should you have to open a web browser to do something that is inherently
text-based? Ideally one should have to do these tasks only once per paper, but
the reality is that management of a database introduces another set of
problems.

If this problem statement strikes a chord, `bibsearch` is the tool for you. It
provides the following services:

* Keyword-based search against a private collection of entries (`bibsearch
  search`)
* Automatic downloading of citations from predefined collections (`bibsearch
  add bib://`) or arbitrary URI's (`bibsearch add`)
* Searching and downloading from the arXiv (`bibsearch arxiv`)
* Automatic generation of a project BibTeX file from LaTeX source (`bibsearch
  tex`)
* Keyword-based downloading and opening of PDF files (`bibsearch open`)

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
    Searches the database. For the syntax of search queries look at the [SEARCH
    QUERIES][] section. By default the search results are listed in a
    human-readable format. Use the `-b` option to show them in BibTeX format.

* `arxiv` [<query>]:
    TODO

* `open` [<query>]:
    Opens the corresponding paper if the <query> returns only one result.
    Requires the BibTeX entry to specify an <URL> field. See the [SEARCH
    QUERIES][] section for the syntax of the <query>.

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

## CONFIG FILE

TODO
