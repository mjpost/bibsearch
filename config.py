import configparser
import logging
import os.path

class Config():
    defaults = {
        "bibsearch_dir": os.path.join(os.path.expanduser("~"), '.bibsearch'),
        "open_command": "open",  # TODO: Customize by OS
        "temp_dir": "/tmp/bibsearch",
        "database_url": "https://github.com/mjpost/bibsearch/raw/master/resources/",
        "custom_key_format": "{surname}{short_year:02}{suffix}_{title}"
    }

    def __init__(self):
        pass

    def initialize(self, fname):
        config = configparser.ConfigParser(
            default_section="bibsearch",
            defaults=self.__class__.defaults
        )
        config.read(fname)
        for k, v in config["bibsearch"].items():
            if k in self.__class__.defaults:
                self.__setattr__(k, v)
            else:
                logging.warning("Unknown config option '%s'", k)
