# bibsearch

Are you annoyed to have to fire up a web browser to search for bibtex entries?
Do you hate browsing through pages of Google Scholar output to find the correct bibtex citation for that paper?
(Not the arxiv version, not the crummy scraped version on ACM or Citeseer, but the proper one from the ACL Anthology?)
`bibsearch` is the tool for you.

## Usage

Create your database by importing bibtext files:

    bibsearch add PATH_TO_BIBTEX_FILE

e.g.,

    wget http://aclweb.org/anthology/P/P17/P17-2.bib
    bibsearch add P17-2.bib

(Parsing of `P17-1.bib` is currently broken...)

Someday: give it URLs or predefined names!

Now, search across all fields to find your entries:

    bibsearch find AMR

Print a summary of your database:

    bibsearch print --summary

## TODO

- Doesn't work for people
- Fails parsing http://aclweb.org/anthology/P/P17/P17-1.bib
- preload with entire ACL anthology (and --download-all or something)
- change keys to format

       {first author lastname}{year}{first significant word of title}

  e.g., brown1993mathematical
