# bibsearch

The process of searching for BibTeX entries is cumbersome and annoying.
Authors are inconsistent in providing them, and they are optional on [the arXiv](http://arxiv.org/).
Google Scholar is useful, but yielding BibTeX entries requires drilling down into entries.
What's worse, for some research fields (such as citations from the [ACL Anthology](http://aclanthology.info/)), the correct citations are not the first search result.
And anyway, why should you have to open a web browser to do something that is inherently text-based?
Ideally one should have to do these tasks only once per paper, but the reality is that management of a database introduces another set of problems.

If this problem statement strikes a chord, `bibsearch` is the tool for you.
It provides the following services:

- Keyword-based search against a private collection of entries (`bibsearch search`)
- Automatic downloading of citations from predefined collections (`bibsearch add bib://`) or arbitrary URI's (`bibsearch add`)
- Searching and downloading from the arXiv (`bibsearch arxiv`)
- Automatic generation of a project BibTeX file from LaTeX source (`bibsearch tex`)
- Keyword-based downloading and opening of PDF files (`bibsearch open`)

Stick to the command line where life is best!

## Installation

Install bibsearch with

    pip3 install bibsearch

`bibsearch` requires SQLite with full-text search support.
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

    bibsearch search brown 1993 statistical

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

Add the results to your database:

    bibsearch arxiv vaswani attention is all you need -a

Open the PDF:

    bibsearch open

Get the key to use with `\cite`:

    $ bibsearch search vaswani attention
    [vaswani:2017:attention] Vaswani, Ashish and Shazeer, Noam and Parmar,
      Niki and Uszkoreit, Jakob and Jones, Llion and Gomez, Aidan N. and
      Kaiser, Lukasz and Polosukhin, Illia "Attention Is All You Need",
      ARXIV 2017


## Incorporate in a LaTeX workflow

If you use the following in a Makefile, you can use bibsearch to find paper keys, and avoid creating the bibliography file entirely.
`bibsearch` will generate it for you!

    pdflatex PAPER
    bibsearch tex PAPER -B
    bibtex PAPER
    pdflatex PAPER
    pdflatex PAPER

This generates whatever bib file is referenced in PAPER.tex.

