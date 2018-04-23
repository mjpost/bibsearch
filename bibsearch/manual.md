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

TODO

## CONFIG FILE

TODO
