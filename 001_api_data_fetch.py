import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Section 1: Project Setup and Configuration

    Load necessary libraries, the list of pages to pull revision data for, and the project's configuration from 'project.json.' This ensures that all subsequent steps in the project have access to its root path and settings
    """)
    return


@app.cell
def _():
    import marimo as mo
    from pathlib import Path
    import json
    import polars as pl
    from pprint import pprint
    from datetime import datetime

    # Find the project's root directory.
    # This allows this file to be run from the 'notebooks' subfolder without breaking file paths.
    ROOT = Path.cwd()
    if ROOT.name == 'notebooks':
        ROOT = ROOT.parent

    # Load the main configuration file.
    # This file contains all the key parameters for the project, such as
    # the starting category, API settings, and language.
    CONF_PATH = ROOT / "conf" / "project.json"
    CONF = json.load(open(CONF_PATH))

    # Load in the list of pages to pull data from with API
    PAGES_PATH = ROOT / "data" / "seed_pages.csv"
    page_list_df = pl.read_csv(PAGES_PATH)
    return CONF, ROOT, mo, page_list_df, pl


@app.cell
def _(mo):
    mo.md(r"""
    # Section 2: API Request Handling
    Uses a direct 'requests.get' for each call. This ensures that every API request is completely independent and stateless, which is more robust against rare, state-related network issues that can occur during very long-running jobs.
    """)
    return


@app.cell
def _(CONF):
    import time
    import requests
    import parquet_tools

    # Define the API URL
    url = "https://en.wikipedia.org/w/api.php"

    # Use settings from our configuration file
    SLEEP = CONF["api_sleep"]
    MAXLAG = CONF["api_maxlag"]
    # Establish a user agent so Wikimedia doesn't block request
    USER_AGENT = 'ControversyAndProtection/1.0 (noneill256@protonmail.com)'
    # Define headers that will be sent with every request
    HEADERS = {"User-Agent": USER_AGENT}

    session = requests.Session()
    session.headers.update(HEADERS)
    return HEADERS, MAXLAG, SLEEP, requests, session, time, url


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## Revision Data
    Define the function used to access revision data via the MediaWiki API.
    """)
    return


@app.cell
def _(HEADERS, MAXLAG, requests, session, time, url):
    def mediawiki_get_revisions(params):
        """
        Makes stateless GET requests to the MediWiki API to pull revision history data.
        """

        p = params.copy()
        # the Update function is for modifying dicts / sets
        p.update({'formatversion': 2, 'maxlag': MAXLAG})

        try:
            rev_response = session.get(url, params=p, headers=HEADERS, timeout=60)
            #print(rev_response.url) ##########
            rev_response.raise_for_status()
            # Convert results to JSON
            rev_js = rev_response.json()

            # If there's an error in the results
            if 'error' in rev_js and rev_js['error'].get('code') == 'maxlag':
                wait_time = int(rev_js['error'].get('lag', 5))
                print(f'Server lag detected. Waiting {wait_time} seconds and will skip this batch.')
                time.sleep(wait_time)
                return None # Skip this batch and let the main loop continue

            return rev_js

        except requests.exceptions.RequestException as ex:
            print(f'An API request failed: {ex}')
            return None
        except requests.exceptions.JSONDecodeError:
            print(f'Failed to decode JSON. Status: {rev_response.status_code}, Text: {rev_response.text[:100]}')
            return None

    print('First stateless API helper function is ready.')
    return (mediawiki_get_revisions,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    Run the function to pull revision data. To curb the amount of data pulled, we'll only look at revisions from 2012 and later.
    """)
    return


@app.cell
def _():
    """test_params = {
                'action': 'query',
                'format': 'json',
                'pageids': 48410011, #####################
                'prop': 'info|revisions',
                'rvprop': 'ids|timestamp|user|size',
                'rvdir': 'newer',
                'rvstart': '2012-01-01T00:00:00Z', # Start with the year 2012
                'rvlimit': '10'
                }

    test_result = mediawiki_get_revisions(test_params)
    test_page = test_result['query']['pages'][0]

    print(test_result)"""
    return


@app.cell
def _(SLEEP, mediawiki_get_revisions, page_list_df, pl, time):
    rev_result_dict = []

    for page_id in page_list_df['pageid']:

        print(f'Making API call for page ID {page_id}...')
        rev_continuation_token = None

        # Keep the previous (older) revision's size so we can calculate
        # the size delta even when revisions span multiple API calls.
        previous_size = None

        # Collect all revisions for each title
        # This will likely take multiple API calls for each title.
        while True: 
            rev_params = {
                'action': 'query',
                'format': 'json',
                'pageids': page_id,
                'prop': 'info|revisions',
                'rvprop': 'ids|timestamp|user|size',
                'rvdir': 'newer',
                'rvstart': '2012-01-01T00:00:00Z', # Start with the year 2012
                'rvlimit': 'max'
                }

            # If a continuation token was pulled from the last API call
            if rev_continuation_token:
                rev_params['rvcontinue'] = rev_continuation_token

            # Make the API call, returns a JSON of results
            rev_result = mediawiki_get_revisions(rev_params)


            # Stop if the request failed or returned empty
            if not rev_result or 'query' not in rev_result:
                break


            # Pull the data points we want out of the results
            if 'query' in rev_result:
                page = rev_result['query']['pages'][0]
                if 'revisions' not in page:
                    print(f'NO REVISIONS RETURNED FOR: {page.get("title")}')
                    print(page)
                rev_title = page['title']
                rev_id_list = []
                rev_timestamp_list = []
                rev_user_list = []
                size_delta_list = []
                size_list = []

                # Loop through all of the lists of revisions, and store their data
                # Use 'get' to prevent errors if a page is missing revisions
                revisions = page.get('revisions', [])
                for revision in revisions:
                    rev_id_list.append(revision['revid'])
                    rev_timestamp_list.append(revision['timestamp'])
                    if 'userhidden' in revision: # Account for when there is no 'user' value because they're hidden
                        rev_user_list.append('USER_HIDDEN')
                    else:
                        rev_user_list.append(revision['user'])

                    # Calculate size delta
                    current_size = revision.get('size')
                    size_list.append(current_size)
                    if current_size is not None and previous_size is not None:
                        size_delta = current_size - previous_size
                    else:
                    # No older revision available to compare against
                        size_delta = None
                    size_delta_list.append(size_delta)

                    # Because revisions are newest -> oldest, this revision
                    # becomes the "previous" (older) revision for the next one.
                    previous_size = current_size


            # Add data to a dictionary
                rev_result_dict.append({
                    'title': rev_title,
                    'revision_ids': rev_id_list,
                    'users': rev_user_list,
                    'timestamps': rev_timestamp_list,
                    'sizes': size_list,
                    'size_deltas': size_delta_list
                    })


            rev_continuation_token = rev_result.get('continue', {}).get('rvcontinue')
            # Get continuation token for this page and get more revisions

            if not rev_continuation_token:
                break # No more revisions, so we're done with this page


            time.sleep(SLEEP) # Be polite and pause between requests


    # Convert data into dataframe
    rev_results_df_raw = pl.DataFrame(rev_result_dict)
    print('API data pull is complete.')
    return (rev_results_df_raw,)


@app.cell
def _(mo, rev_results_df_raw):
    mo.ui.table(rev_results_df_raw)
    return


@app.cell
def _(mo):
    mo.md(r"""
    ## Protection Data
    Define the function used to access protection history data via the MediaWiki API.
    """)
    return


@app.cell
def _(HEADERS, MAXLAG, requests, session, time, url):
    def mediawiki_get_protections(params):
        """
        Makes stateless GET requests to the MediWiki API to pull protections history data.
        """

        p = params.copy()
        # the Update function is for modifying dicts / sets
        p.update({'formatversion': 2, 'maxlag': MAXLAG})

        try:
            prot_response = session.get(url, params=p, headers=HEADERS, timeout=60)
            prot_response.raise_for_status()
            # Convert results to JSON
            prot_js = prot_response.json()

            # If there's an error in the results
            if 'error' in prot_js and prot_js['error'].get('code') == 'maxlag':
                wait_time = int(prot_js['error'].get('lag', 5))
                print(f'Server lag detected. Waiting {wait_time} seconds and will skip this batch.')
                time.sleep(wait_time)
                return None # Skip this batch and let the main loop continue

            return prot_js

        except requests.exceptions.RequestException as ex:
            print(f'An API request failed: {ex}')
            return None
        except requests.exceptions.JSONDecodeError:
            print(f'Failed to decode JSON. Status: {prot_response.status_code}, Text: {prot_response.text[:100]}')
            return None

    print('Second stateless API helper function is ready.')
    return (mediawiki_get_protections,)


@app.cell
def _(mo):
    mo.md(r"""
    Run the function to pull protection data.
    """)
    return


@app.cell
def _(SLEEP, mediawiki_get_protections, page_list_df, pl, time):
    # Create a dictionary of all log events
    protection_result_dict = {'title': [], 'log_id': [], 'action': [], 'timestamp': [], 'comment': [], 'users': [],
                'edit_level': [], 'edit_expiry': [],
                'move_level': [], 'move_expiry': [],
                'upload_level': [], 'upload_expiry': [], 
                'create_level': [], 'create_expiry': []}


    for title in page_list_df['title']: 

        print(f'Making API call for {title}...')
        le_continuation_token = None

        # Collect all log event history for each title, filtered only to protection events.
        # This may take multiple API calls for each title.
        while True: 
            prot_params = {
                'action': 'query',
                'format': 'json',
                'letitle': title,
                'list': 'logevents',
                'letype': 'protect',
                'leprop': 'ids|title|type|user|timestamp|comment|details',
                'rvstart': '2012-01-01T00:00:00Z', # Start with the year 2012
                'lelimit': 'max'
                }

            # If a continuation token was pulled from the last API call
            if le_continuation_token:
                prot_params['lecontinue'] = le_continuation_token

            # Make the API call, returns a JSON of results
            prot_result = mediawiki_get_protections(prot_params)


            # Stop if the request failed or returned empty
            if not prot_result or 'query' not in prot_result:
                break


            # Pull the data points we want out of the results
            if 'query' in prot_result:
                # A log event can have multiple different protection changes made at once.
                # Iterate through all the protection changes (stored in 'details') made in this one log event, 
                # and store their data based on what type of change it is.
                # We should also account for when log events don't have detailed data, either because
                # the event took place a long time ago, or because it's an 'unprotect' action.
                for logevent in prot_result['query']['logevents']:

                    edit_level = 'n/a'
                    edit_expiry = 'n/a'
                    move_level = 'n/a'
                    move_expiry = 'n/a'
                    upload_level = 'n/a'
                    upload_expiry = 'n/a'
                    create_level = 'n/a'
                    create_expiry = 'n/a' # Default values for if 'details' doesn't have this info    
                    title_value = title

                    # Pull basic log event info
                    protection_result_dict['title'].append(title_value)
                    protection_result_dict['log_id'].append(logevent['logid'])
                    protection_result_dict['timestamp'].append(logevent['timestamp'])
                    protection_result_dict['action'].append(logevent['action'])
                    # Add the user's comment, accounting for when there isn't one
                    if 'commenthidden' in logevent:
                        protection_result_dict['comment'].append('COMMENT_HIDDEN')
                    else:
                        protection_result_dict['comment'].append(logevent['comment'])
                    # Add users, accounting for when they're hidden
                    if 'userhidden' in logevent:
                        protection_result_dict['users'].append('USER_HIDDEN')
                    else:
                        protection_result_dict['users'].append(logevent['user'])


                    # If there is detailed log event data, we can pull more information
                    if logevent.get('params', {}).get('details', []):

                        details = logevent.get('params', {}).get('details', [])
                        for detail in details:
                            if detail['type'] == 'edit':
                                edit_level = detail['level']
                                edit_expiry = detail['expiry']
                            if detail['type'] == 'move':
                                move_level = detail['level']
                                move_expiry = detail['expiry']
                            if detail['type'] == 'upload':
                                upload_level = detail['level']
                                upload_expiry = detail['expiry']
                            if detail['type'] == 'create':
                                create_level = detail['level']
                                create_expiry = detail['expiry']
                    protection_result_dict['edit_level'].append(edit_level)
                    protection_result_dict['edit_expiry'].append(edit_expiry)
                    protection_result_dict['move_level'].append(move_level)
                    protection_result_dict['move_expiry'].append(move_expiry)
                    protection_result_dict['upload_level'].append(upload_level)
                    protection_result_dict['upload_expiry'].append(upload_expiry)
                    protection_result_dict['create_level'].append(create_level)
                    protection_result_dict['create_expiry'].append(create_expiry)



            le_continuation_token = prot_result.get('continue', {}).get('lecontinue')
            # Get continuation token for this page and get more log events

            if not le_continuation_token:
                break # No more revisions, so we're done with this page


            time.sleep(SLEEP) # Be polite and pause between requests


    # Convert data into dataframe
    protect_results_df_raw = pl.DataFrame(protection_result_dict)
    print('API data pull is complete.')
    return (protect_results_df_raw,)


@app.cell
def _(mo):
    mo.md(r"""
    # Section 3: Export Data
    """)
    return


@app.cell
def _(mo):
    mo.md(r"""
    Export datasets as Parquet files.
    """)
    return


@app.cell
def _(ROOT, rev_results_df_raw):
    # Export revision data into Parquet file.
    EXP_PATH_REV = ROOT / "data" / "raw" / "revision_results_df_raw.parquet"
    rev_results_df_raw.write_parquet(EXP_PATH_REV)
    return


@app.cell
def _(ROOT, protect_results_df_raw):
    # Export protection data into CSV file
    EXP_PATH_PROT = ROOT / "data" / "raw" / "protection_results_df_raw.csv"
    protect_results_df_raw.write_csv(EXP_PATH_PROT)
    return


if __name__ == "__main__":
    app.run()
