# coding=utf-8
"""
Exposes a simple HTTP API to search a users Gists via a regular expression.

Github provides the Gist service as a pastebin analog for sharing code and
other develpment artifacts.  See http://gist.github.com for details.  This
module implements a Flask server exposing two endpoints: a simple ping
endpoint to verify the server is up and responding and a search endpoint
providing a search across all public Gists for a given Github account.
"""
import re
import requests
from flask import Flask, jsonify, request

# *The* app object
app = Flask(__name__)


@app.route("/ping")
def ping():
    """Provide a static response to a simple GET request."""
    return "pong"

def get_gist(id):
    """Provides gist metadata for a gist id.

    This abstracts the /gists/GIST_ID endpoint from the Github API.
    See https://docs.github.com/en/rest/gists/gists#get-a-gist for
    more information.

    Args:
        id (string): the id of the target gist

    Returns:
        The dict parsed from the json response from the Github API.  See
        the above URL for details of the expected structure.
    """
    gist_url = 'https://api.github.com/gists/{id}'.format(id=id)
    response = requests.get(gist_url)


    # in case invalid id was sent return empty dict & add log message
    # or you can send error notification, email or whatever
    if response.status_code in [403, 404]:
        app.logger.error('Failed to get gist(%s) data', id)
        return False
    try:
        response_data = response.json()
        response_keys = response_data.keys()
        if 'documentation_url' in response_keys and 'message' in response_keys:
            app.logger.error(
                'Failed to get gist(%s) data, response from server is: %s',
                id,
                response.content
            )
            return False
        return response_data
    except:
        # in case of invalid json response return empty dict and add log message,
        # or you can send error notification, email or whatever
        app.logger.error('Failed to parse get gist(%s) request json response: %s', id, response.content)
        return False

def gists_for_user(username='', page=1, per_page=1, url=False, data=[]):
    """Provides the list of gist metadata for a given user.

    This abstracts the /users/:username/gist endpoint from the Github API.
    See https://developer.github.com/v3/gists/#list-a-users-gists for
    more information.

    Args:
        username (string): the user to query gists for

    Returns:
        The dict parsed from the json response from the Github API.  See
        the above URL for details of the expected structure.
    """
    gists_url = 'https://api.github.com/users/{username}/gists?page={page}&per_page={per_page}'.format(
        username=username,
        page=page,
        per_page=per_page
    )
    if url:
        gists_url = url
    response = requests.get(gists_url)
    # BONUS: What failures could happen? => validation errors from api + username name not found
    # BONUS: Paging? How does this work for users with tons of gists? ===> done above

    # in case invalid username was sent return empty list & add log message
    # or you can send error notification, email or whatever
    if response.status_code == 422:
        app.logger.error('Failed to get %s gists ', username)
        return []
    try:
        response_data = response.json();
        if not isinstance(response_data, list):
            # in case of invalid username response return dict
            # add log message or you can send error notification, email or whatever
            app.logger.error(
                'Failed to get username(%s) gists, response from server is: %s',
                username,
                response.content
            )
            return []
        data += response_data
        if 'next' in response.links.keys():
            return gists_for_user(url=response.links['next']['url'], data=data)
        return data
    except:
        # in case of invalid json response return empty list and add log message,
        # or you can send error notification, email or whatever
        app.logger.error('Failed to get username(%s) gists, response from server is: %s', username, response.content)
        return []

def get_gist_files_content(gist_data):
    """Provides content of gist files.
    Args:
        gist_data (dict): gist full meta data

    Returns:
        string contains all files contents joined by newline
    """
    content = ''
    files = gist_data.get('files')
    if files:
        files_data = files.values()
        for item in files_data:
            content += item.get('content') + "\n"
    return content

@app.route("/api/v1/search", methods=['POST'])
def search():
    """Provides matches for a single pattern across a single users gists.

    Pulls down a list of all gists for a given user and then searches
    each gist for a given regular expression.

    Returns:
        A Flask Response object of type application/json.  The result
        object contains the list of matches along with a 'status' key
        indicating any failure conditions.
    """
    post_data = request.get_json()
    # BONUS: Validate the arguments?
    if ['username', 'pattern'] != list(post_data.keys()):
        raise ValueError("Keys does not match with post_data keys")

    username = post_data.get('username', '')
    pattern = post_data.get('pattern', '')

    if username == '' or pattern == '':
        raise ValueError("Pattern & Username values should not be empty!")

    result = {}
    gists = gists_for_user(username)

    # BONUS: Handle invalid users? => done above

    matches = []

    for gist in gists:
        # REQUIRED: Fetch each gist and check for the pattern
        gist_data = get_gist(gist.get('id'))
        if gist_data:
            pattern_re = re.compile(pattern)
            if pattern_re.match(get_gist_files_content(gist_data)):
                matches.append('https://gist.github.com/%s/%s' % (username, gist.get('id')))

        # BONUS: What about huge gists? ===> done above to get all gists using pagination but this needs cache on request level
        # BONUS: Can we cache results in a datastore/db?
        # caching can be done in two levels, request level and matches result level
        #  - request level, could be done by using url as indentifier
        #  - matches result level can be done by using username & pattern as indentifier
        #  - there is ready to use package for flask caching and in there u can use any cache backend i.e redis

    result['status'] = 'success'
    result['username'] = username
    result['pattern'] = pattern
    result['matches'] = list(set(matches))

    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9876)
