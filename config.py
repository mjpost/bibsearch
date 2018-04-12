import configparser
import logging
import os.path

class Config():
    defaults = {
        "bibsearch" : {
              "bibsearch_dir": os.path.join(os.path.expanduser("~"), '.bibsearch')
            , "open_command": "open"  # TODO: Customize by OS
            , "temp_dir": "/tmp/bibsearch"
            , "database_url": "https://github.com/mjpost/bibsearch/raw/master/resources/"
            , "custom_key_format": "{surname}{short_year:02}{suffix}_{title}"
        }
        , "macros" : {
              '@acl': 'booktitle:"Annual Meeting of the Association for Computational Linguistics"'
            , '@emnlp': 'booktitle:"Conference on Empirical Methods in Natural Language Processing"'
            , '@wmt': '(booktitle:"Workshop on Statistical Machine Translation" OR booktitle:"Conference on Machine Translation")'
            , '@naacl': 'booktitle:"Conference of the North American Chapter of the Association for Computational Linguistics"'
        }
    }

    def __init__(self):
        pass

    def initialize(self, fname):
        config = configparser.ConfigParser()
        config.read_dict(self.__class__.defaults)
        config.read(fname)
        for k, v in config["bibsearch"].items():
            if k in self.__class__.defaults["bibsearch"]:
                self.__setattr__(k, v)
            else:
                logging.warning("Unknown config option '%s'", k)

        self.macros = config["macros"]
        
