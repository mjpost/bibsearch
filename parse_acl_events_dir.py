#!/usr/bin/env python

import argparse
from collections import defaultdict
import glob
import logging
import re
import sys
import os.path
import yaml


base_url = "https://aclanthology.coli.uni-saarland.de"
bib_volume_re = re.compile('href="(/volumes/[^"]*\.bib)"')
fname_re = re.compile('(.+)-([0-9]+)')

def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("events", help="events directory of ACL anthology")
    args = arg_parser.parse_args()

    #~ datasets = defaultdict(lambda: defaultdict(list))
    datasets = {}
    for f in glob.glob(os.path.join(args.events, "*")):
        fname_match = fname_re.match(os.path.basename(f))
        if not fname_match:
            logging.warning("Unknonw fname type: %s", f)
            continue
        event = fname_match.group(1)
        if event not in datasets:
            datasets[event] = {}
        year = fname_match.group(2)
        datasets[event][year] = []
        for l in open(f):
            bib_match = bib_volume_re.search(l)
            if bib_match:
                datasets[event][year].append(base_url + bib_match.group(1))
    print(yaml.dump(datasets))


if __name__ == "__main__":
    main()

