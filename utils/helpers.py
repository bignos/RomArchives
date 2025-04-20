# -*- coding: utf-8 -*-

# -[ Imports ]-

import json

# -[ Constants ]-

DEBUG = True

# -[ Private ]-

# -[ Public ]-


def debug(string: str):
    """
    Prints a debug message.
    """
    if DEBUG:
        print(f'[DEBUG] {string}')


def terminal_display(var: any):
    """
    Displays a variable in the terminal.
    """
    print(json.dumps(var, indent=4))


def load_json(path: str):
    """
    Loads a json file.
    """
    with open(path, 'r') as f:
        return json.load(f)
