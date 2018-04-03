# bibsearch

Are you annoyed to have to fire up a web browser to search for bibtex entries?
Do you hate browsing through pages of Google Scholar output to find the correct bibtex citation for that paper?
(Not the arxiv version, not the crummy scraped version on ACM or Citeseer, but the proper one from the ACL Anthology?)
`bibsearch` is the tool for you.

## Prerequisites

Version 0.1.0 requires sqlite with full-text search support.
On a Mac, you can get this with

    brew reinstall sqlite3 --with-fts5

Install bibsearch with

    pip3 install bibsearch

## Usage

Create your database by importing bibtex files.
There are lots of shortcuts, e.g., to add [ACL 2017](http://acl2017.org)

    bibsearch add bib://acl/17

or to add all of ACL:

    bibsearch add bib://acl

or add everything in the database (the entire ACL anthology).
(This takes about 20 minutes).

    bibsearch add bib://

You can also add your own files, either locally or via URL.

    bibsearch add http://aclweb.org/anthology/P/P17/P17-2.bib

Now, search across all fields to find your entries:

    bibsearch search AMR

Print a summary of your database:

    bibsearch print --summary
