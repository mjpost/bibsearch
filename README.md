# bibsearch

The process of searching for BibTeX entries is cumbersome and annoying.
Authors are inconsistent in providing them, and they are optional on the arXiv.
Google Scholar is useful, but yielding BibTeX entries requires drilling down into entries.
What's worse, for some research fields (such as citations from the [ACL Anthology](http://aclanthology.info/)), the correct citations are not the first search result.
And anyway, why should you have to open a web browser to do something that is inherently text-based?
Ideally one should have to do these tasks only once per paper, but the reality is that management of a database introduces another set of problems.

If this problem statement strikes a chord, `bibsearch` is the tool for you.
It provides the following services:

- Automatic downloading of citations from their official repositories
- Keyword-based search agianst entire entries
- Automatic generation of a BibTeX file from LaTeX source

## Installation

Install bibsearch with

    pip3 install bibsearch

`bibsearch` requires SQLite with full-text search support.
This causes no performance degradation to SQLite, but is unfortunately not part of the default installation.
If you are on a Mac and have [brew](https://brew.sh/) installed, you can get this with

    brew reinstall sqlite3 --with-fts5

## Usage

Create your database by importing BibTeX files.
There are lots of shortcuts, e.g., to add [ACL 2017](http://acl2017.org), type:

    bibsearch add bib://acl/17

or to add all of ACL:

    bibsearch add bib://acl

or add the entire [ACL Anthology](http://aclanthology.info/) (this takes about 20 minutes):

    bibsearch add bib://

You can also add your own files, either locally or via URL.

    # Import from a URL
    bibsearch add http://aclweb.org/anthology/P/P17/P17-2.bib

    # Add a bibtex file from a local database
    bibsearch add main.bib

(Duplicate keys are successfully ignored).
Now, search across all fields to find your entries:

    bibsearch search AMR

(`find` also works)
Get the outputs in BibTeX format:

    bibsearch search AMR -b

Generate the BibTeX file based on citations found in a LaTeX source (requires the .aux file):

    bibsearch tex LATEX_FILE

Print a summary of your database:

    bibsearch print --summary

## Incorporate in a LaTeX workflow

Use this:

    pdflatex PAPER
    bibsearch tex PAPER -B
    bibtex PAPER
    pdflatex PAPER
    pdflatex PAPER

This generates whatever bib file is references in PAPER.tex.
You don't ever need to manually manage it again!
