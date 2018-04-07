#!/usr/bin/env python

import os.path
import re
import sys
import urllib.request
import yaml

def download_file(url, fname_out=None) -> None:
    """
    Downloads a file to a location.
    """

    import ssl

    try:
        with urllib.request.urlopen(url) as f:
            if not fname_out:
                return f.read().decode("utf-8")
            else:
                fdir = os.path.dirname(fname_out)
                if not os.path.exists(fdir):
                    os.makedirs(fdir)

                with open(fname_out, "wb") as outfile:
                    outfile.write(f.read())
                return fname_out

    except ssl.SSLError:
        print("WHAT!")
        sys.exit(1)

def main():
    volume_re = re.compile("""<a href="([^"]*)"><b>(Volume .*)</b></a>""")
    volumes = {}
    base_url = """http://proceedings.mlr.press/"""
    for l in download_file("http://proceedings.mlr.press/").split("\n"):
        match = volume_re.search(l)
        if match:
            volumes[match.group(2)] = [base_url + match.group(1) + "/bibliography.bib"]
    print(yaml.dump(volumes))

if __name__ == "__main__":
    main()
