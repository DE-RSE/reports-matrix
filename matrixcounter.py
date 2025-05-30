#!/usr/bin/env python3
""" Keep track of matrix room user counts over time

Help is available with the "--help" option.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.
This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = "Frank Löffler"
__contact__ = "frank.loeffler@uni-jena.de"
__copyright__ = "Copyright 2024, Frank Löffler; 2024 Friedrich-Schiller-Universität Jena"
__date__ = "2024-02-22"
__email__ = "frank.loeffler@uni-jena.de"
__license__ = "AGPLv3"
__maintainer__ = "frank.loeffler@uni-jena.de"
__status__ = "Development"
__version__ = "0.0.1"

import sys, os
import argparse
import json
from pprint import pprint
from datetime import datetime

import requests

# skeleton for data scructure for internal state
status_empty = {
    'matrix_access_tokens': {},
    'rooms': {},
    }
# global state, to be saved between invocations
status = None

config = {}
def log(msg):
    if config['verbose']:
        print(msg)

def parse_commandline():
    config = {}
    parser = argparse.ArgumentParser(
        description="Collect user count statistics of rooms a given matrix user has joined.",
        epilog='Example usage (replace the echo with the respective command for your '
               "password manager):\n"
               'echo matrix_passwd  | ./matrixcounter.py '
               '--matrixhost synapse.mymatrix.nowhere '
               '--matrixuser matrixuser '
               '--matrixpass - '
               "\n",
        add_help=False)
    req = parser.add_argument_group('required arguments')
    opt = parser.add_argument_group('optional arguments')
    opt.add_argument("-h", "--help", action="help", help="show this help message and exit")
    req.add_argument('--matrixhost', metavar='host', required=True,
                     help='hostname of the matrix server (not including https://)')
    req.add_argument('--matrixuser', metavar='user', required=True,
                     help='user name for the matrix server')
    req.add_argument('--matrixpass', metavar='password', required=True,
                     help='password for the user on matrix, read from stdin if == "-". ')
    opt.add_argument('--statusfile', metavar='filename', required=False, default='.matrixcounter.status',
                     help='filename to use to save state, e.g., to be able to use a '
                          'longer-living matrix access token, as well as past user counts. '
                          'NEVER share this file, as it does contain the matrix access token. '
                          'See --counterfile for a shareable file. '
                          'This file can be shared between invocations of this script with '
                          'different matrix options (e.g. different matrix users that may '
                          'share joined rooms). '
                          'If this file does not exist or cannot be (properly) read, '
                          'it will be created/overwritten. Default: .matrixcounter.status')
    opt.add_argument('--counterfile', metavar='filename', required=False, default='matrixcounter.json',
                     help='filename to use to save counter data. Note that this will contain '
                          'all room data also contained in --statusfile (but no authentication '
                          'data), i.e., will contain data of all rooms of a possibly shared '
                          '--statusfile. If you do not want this, use separate --statusfile.'
                          'If this file does not exist or cannot be (properly) read, '
                          'it will be created/overwritten. Default: matrixcounter.json')
    opt.add_argument('--matrix-always-logout', action='store_true',
                     help='logout of a possibly opened matrix session at the end of operations. '
                          'This also invalidates the access token, so a new login will be '
                          'necessary in the future. This is not intended for regular usage, '
                          'but to close sessions from within the script if it is known that '
                          'the access token will not be used in the future.')
    opt.add_argument('--verbose', action='store_true',
                     help='Be verbose. By default nothing will be printed if everything works '
                          'as planned.')
    args = vars(parser.parse_args())
    config['matrix_host']     = args['matrixhost']
    config['matrix_user']     = args['matrixuser']
    config['statusfile_name'] = args['statusfile']
    config['counterfile_name'] = args['counterfile']
    config['matrix_always_logout'] = args['matrix_always_logout']
    config['verbose']         = args['verbose']
    if args['matrixpass'] == '-':
        config['matrix_pass'] = sys.stdin.readline().rstrip('\n')
    else:
        config['matrix_pass'] = args['matrixpass']
    return config

def load_status(statusfile_name):
    """Load status from file and do some sanity checks.

    Use the template in case of any error or inconsistancy."""
    status = None
    try:
        statusfile = open(statusfile_name, 'r')
        status = json.load(statusfile)
        close(statusfile_name)
    except Exception as e:
        pass
    if type(status) != dict:
        status = status_empty
    for req_key in status_empty.keys():
        if req_key not in status:
            status = status_empty
    if type(status['matrix_access_tokens']) != dict:
        status['matrix_access_tokens'] = status_empty['matrix_access_tokens']
    matrix_access_token_id = f'{matrix_user}@{matrix_host}'
    if (not matrix_access_token_id in status['matrix_access_tokens'] or
        type(status['matrix_access_tokens'][matrix_access_token_id]) != str):
        status['matrix_access_tokens'][matrix_access_token_id] = None
    return status, matrix_access_token_id

# parse the command line options
config = parse_commandline()
# use returned dict to setup local variables
locals().update(config)

# load status information from last invocation from file
status, matrix_access_token_id = load_status(statusfile_name)

class Matrix:
    """Simple class to encapsulate a set-up Matrix configuration."""
    access_token = None

    def __init__(self, host, user, password, token=None):
        """Initilize the class and login.

        This requires host, user and password. Optionally, a pre-existing access-token
        can be passed in and will be used instead of user and password. However, the
        latter two are still required, as it will fall back to them in case the token
        does not work (to obtain a new token)."""
        self.host = host
        self.s = requests.Session()
        if token != None:
            # Check if the passed token works. Any API call that requires authentication
            # and should always work is fine here. We here request the list of joined
            # rooms, but do not use that information later.
            r = self.s.get(f'https://{self.host}/_matrix/client/v3/joined_rooms?access_token={token}')
            if r.status_code != 200:
                token = None
                log(f'matrix: existing token invalid, about to obtain a new one')
            self.access_token = token
        # If no token was passed or the one that was did not work: request a new one
        if token == None:
            pdata = {
              'type'    : 'm.login.password',
              'user'    : user,
              'password': password,
              }
            r = self.s.post(f'https://{self.host}/_matrix/client/v3/login', json=pdata)
            if r.status_code != 200:
                print(f"Could not login to Matrix: {r.text}.")
                sys.exit(1)
            token = json.loads(r.text)['access_token']
            self.access_token = token
            log(f"matrix: just logged in")
        else:
            log(f"matrix: already logged in")

    def logout(self):
        """For completeness, as we usually do not call this: logout of Matrix.

        The reason we by default do not call this is that this invalidates the access token
        and always obtaining a new one can run into rate limits."""
        if self.access_token == None:
            print("No token known: cannot logout.")
            sys.exit(1)
        r = self.s.post(f'https://{self.host}/_matrix/client/v3/logout?access_token={self.access_token}')
        if r.status_code != 200:
            print("Could not logout.")
            # Do not fail here, as we effectively achieved what we wanted.
        log("matrix: logged out")

matrix = None
def login_matrix():
    global matrix
    """Login to matrix if not already done"""
    if matrix is None or matrix.access_token is None:
        matrix = Matrix(matrix_host, matrix_user, matrix_pass,
                        status['matrix_access_tokens'][matrix_access_token_id])
        status['matrix_access_tokens'][matrix_access_token_id] = matrix.access_token
    return matrix

matrix = login_matrix()

def add_data(dates, values, date, value):
    """append 'date' to 'dates' and 'value' to 'values' or only update last 'dates'

    We mostly do not want to record when nothing changed. Thus, this function updates
    the time of the last entry in 'dates' with 'value' if 'value' is the same as 'values[-1]',
    but append a new time if we also have a new value. This effectively creates singles or
    pairs of times with the same value, but not more than pairs.
    For most purposes we could also remove the second of the values in a pair, as we know
    that the next entry will record the new value and the "next" time, but then plotting the 
    result would need to use implicit knowledge on the intervals this script is run, and I
    would rather not do that to keep things simple and consistent.
    """
    if len(dates) != len(values):
        print('internal error')
        sys.exit(1)
    # if nothing changed, only update the last-seen time
    if len(dates) > 1 and value == values[-1] and value == values[-2]:
        dates[-1] = date
    # else, add a new data point
    else:
        dates.append(date)
        values.append(value)

# get list of joined rooms and then get info for each
s = requests.Session()
r = s.get(f'https://{matrix_host}/_matrix/client/v3/joined_rooms?access_token={matrix.access_token}')
if r.status_code != 200:
    print("Could not get list of joined rooms")
    sys.exit(1)

room_info = {}
unique_users = set()
isodate = datetime.now().replace(microsecond=0).isoformat()
for room_id in json.loads(r.text)['joined_rooms']:
    r = s.get(f'https://{matrix_host}/_matrix/client/v3/rooms/{room_id}/joined_members?access_token={matrix.access_token}')
    if r.status_code != 200:
        print('Could not get list of users of room {room_id}')
    else:
        users = set(json.loads(r.text)['joined'].keys())
        room_info[room_id] = {'users': users}
        if not room_id in status['rooms']:
            r = s.get(f'https://{matrix_host}/_matrix/client/v3/rooms/{room_id}/state/m.room.name?access_token={matrix.access_token}')
            # rooms are allowed have no name, but all we want to monitor do
            if r.status_code != 200:
                continue
            room_name = json.loads(r.text)['name']
            status['rooms'][room_id] = {'name': room_name, 'counts': [[], []]}
        add_data(status['rooms'][room_id]['counts'][0],
                 status['rooms'][room_id]['counts'][1],
                 isodate, len(users)-1) # subtract 1 to exclude this user (supposedly a bot)
        unique_users |= users
if not 'total' in status['rooms']:
    status['rooms']['total'] = {'name': 'Total', 'counts': [[], []]}
add_data(status['rooms']['total']['counts'][0],
         status['rooms']['total']['counts'][1],
         isodate, len(unique_users)-1)

if config['matrix_always_logout']:
    if matrix is None or matrix.access_token is not None:
        matrix = login_matrix()
    matrix.logout()
    del status['matrix_access_tokens'][matrix_access_token_id]

# save current state. Since this also contains the access token, make sure to create the
# file with safe access permissions.
try:
    file_desc = os.open(path=statusfile_name,
                        flags=os.O_WRONLY|os.O_CREAT|os.O_TRUNC, mode=0o600)
    statusfile = open(file_desc, 'w')
    json.dump(status, statusfile)
    statusfile.close()
except Exception as e:
    print(e)
    pass

# save counters. This is the same file format as the state, but only contains the counters
# and especially no authorization information
with open(counterfile_name, 'w') as counterfile:
    json.dump({'rooms': status['rooms']}, counterfile, indent=0, separators=(',',':'))
    counterfile.close()

