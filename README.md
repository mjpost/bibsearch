# bibsearch

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

## Installation

The official source can be found on [GitHub](https://github.com/mjpost/bibsearch).
The easiest way to install it is via the Python package manager:

    pip3 install bibsearch

`bibsearch` works best with SQLite with full-text search support.
This causes no performance degradation to SQLite, but is unfortunately not part of the default installation.
If you are on a Mac and have [brew](https://brew.sh/) installed, you can get this with

    brew reinstall sqlite3 --with-fts5

## Usage

Create your database by importing BibTeX files.
There are lots of shortcuts defined in the form of collections.
For example, there is a collection for the entire [ACL Anthology](http://aclanthology.info/).
To add papers from [NAACL 2017](http://naacl.org/2017), you can type:

    bibsearch add bib://acl/naacl/2017

or to add all of NAACL:

    bibsearch add bib://acl/naacl

Or even the entire anthology:

    bibsearch add bib://acl

Other collections available include ICML and NIPS.
Type `bibsearch add bib://list` for a complete list.

You can also add your own files, either locally or via URL.

    # Import from a URL
    bibsearch add http://aclweb.org/anthology/P/P17/P17-2.bib

    # Add a bibtex file from a local database
    bibsearch add main.bib

Multiple arguments are permitted at once.
Duplicate keys are successfully ignored.

Now, search across all fields to find your entries:

    bibsearch search brown 1993 statistical

(`find` also works)
Get the outputs in BibTeX format:

    bibsearch search brown 1993 statistical -b

If there is only one match, you can also open the corresponding PDF:

    bibsearch open brown 1993 statistical

`open` will work implicitly on the results of the last search, so you could also have typed:

    bibsearch open

Generate the BibTeX file based on citations found in a LaTeX source (requires that `LATEX_FILE.aux` exists):

    bibsearch tex LATEX_FILE

and write it to the bibliography file specified in the LaTeX:

    bibsearch tex LATEX_FILE -B

Print a summary of your database:

    bibsearch print --summary

Search the arXiv:

    bibsearch arxiv vaswani attention is all you need

Add the results of an arXiv search to your database:

    bibsearch arxiv vaswani attention is all you need -a

Get the key to use with `\cite`:

    $ bibsearch search vaswani attention
    [vaswani:2017:attention] Vaswani, Ashish and Shazeer, Noam and Parmar,
      Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N. and
      Kaiser, Lukasz and Polosukhin, Illia "Attention Is All You Need",
      ARXIV 2017


## Incorporate in a LaTeX workflow

Bibsearch is easy to incorporate in your paper writing: it will automatically generate a BibTeX file from your LaTeX paper.
To use this feature, first use bibsearch to find the papers you want to cite and add them to your private database.
Then, use the keys in the database with `\cite` commands in your paper.
Run `pdflatex` once to generate a `.aux` file, and then use `bibsearch` to generate the bibliography file.
You can use the following in your `Makefile`, for example:

    pdflatex PAPER
    bibsearch tex PAPER -B
    bibtex PAPER
    pdflatex PAPER
    pdflatex PAPER

This generates whatever bib file is referenced in PAPER.tex.

