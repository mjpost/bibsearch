# bibsearch

Are you annoyed to have to fire up a web browser to search for bibtex entries?
Do you hate browsing through pages of Google Scholar output to find the correct bibtex citation for that paper?
(Not the arxiv version, not the crummy scraped version on ACM or Citeseer, but the proper one from the ACL Anthology?)
`bibsearch` is the tool for you.

## Usage

Create your database by importing bibtext files:

    bibsearch add PATH_TO_BIBTEX_FILE

(Someday: give it URLs or predefined names!)

Now, search across all fields to find your entries:

    bibsearch find "first term" "another term"

Print a summary of your database:

    bibsearch print --summary
