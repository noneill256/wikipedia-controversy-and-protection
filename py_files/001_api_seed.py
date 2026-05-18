# Section 1: Project Setup and Configuration ##################################

# Load necessary libraries and loads the project's configuration from 'project.json'
# This ensures that all subsequent steps in the project have access to its root path and settings

from pathlib import Path
import json

# Find the project's root directory.
# This allows this file to be run from the 'py_files' subfolder without breaking file paths.
ROOT = Path.cwd()
if ROOT.name == 'py_files':
    ROOT = ROOT.parent
    
# Load the main configuration file.
# This file contains all the key parameters for the project, such as
# the starting category, API settings, and language.
CONF_PATH = ROOT / "conf" / "project.json"
CONF = json.load(open(CONF_PATH))


# Section 2: API Session and Request Handling #################################

# Uses a direct 'requests.get' for each call.
# This ensures that every API request is completely independent and stateless,
# which is more robust against rare, state-related network issues that can occur
# during very long-running jobs.

import time
import requests 
import pandas as pd
from tqdm.notebook import tqdm

# Define the API URL
url = "https://en.wikipedia.org/w/api.php"

# Use settings from our configuration file
SLEEP = CONF["api_sleep"]
MAXLAG = CONF["api_maxlag"]
# Establish a user agent so Wikimedia doesn't block request
USER_AGENT = 'ControversyAndProtection/1.0 (noneill256@protonmail.com)'
# Define headers that will be sent with every request
HEADERS = {"User-Agent": USER_AGENT}

def mediawiki_get(params):
    """
    Makes stateless GET requests to the MediWiki API.
    """

    p = params.copy()
    # the Update function is for modifying dicts / sets
    p.update({'format': 'json', 'formatversion': 2, 'maxlag': MAXLAG})
    
    try:
        response = requests.get(url, params=p, headers=HEADERS, timeout=60)
        response.raise_for_status()
        js = response.json()
    
        if 'error' in js and js['error'].get('code') == 'maxlag':
            wait_time = int(js['error'].get('lag', 5))
            print(f'Server lag detected. Waiting {wait_time} seconds and will skip this batch.')
            time.sleep(wait_time)
            return None # Skip this batch and let the main loop continue
        
        return js