import configparser
import logging
import os
import os.path
import platform
import tempfile

class Config():
    defaults = {
        "bibsearch" : {
              "bibsearch_dir": os.path.join(os.path.expanduser("~"), '.bibsearch')
            , "download_dir": os.path.join(tempfile.gettempdir(), "bibsearch")
            , "open_command": "xdg-open" if platform.system() == "Linux" else "open"
            , "database_url": "https://github.com/mjpost/bibsearch/raw/master/resources/"
            , "custom_key_format": "{surname}{year}{suffix}:{title}"
            , "editor": os.environ.get("EDITOR", "nano")
        }
        , "macros" : {
              '@acl': 'venue:"Annual Meeting of the Association for Computational Linguistics"'
            , '@emnlp': 'venue:"Conference on Empirical Methods in Natural Language Processing"'
            , '@wmt': '(venue:"Workshop on Statistical Machine Translation" OR venue:"Conference on Machine Translation")'
            , '@naacl': 'venue:"Conference of the North American Chapter of the Association for Computational Linguistics"'
            , '@cl': 'venue:"Computational Linguistics"'  # Probably useless because the terms comes up in several conferences as well
            , '@arxiv': 'venue:"Computing Research Repository"'
            , '@corr': 'venue:"Computing Research Repository"'
        }
    }

    def __init__(self, fname):
        config = configparser.ConfigParser()
        config.read_dict(self.__class__.defaults)
        config.read(fname)
        for k, v in config["bibsearch"].items():
            if k in self.__class__.defaults["bibsearch"]:
                self.__setattr__(k, v)
            else:
                logging.warning("Unknown config option '%s'", k)

        self.macros = config["macros"]
