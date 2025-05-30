#!/usr/bin/env python3
""" Plot user counts for different matrix channels

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
__date__ = "2024-03-05"
__email__ = "frank.loeffler@uni-jena.de"
__license__ = "AGPLv3"
__maintainer__ = "frank.loeffler@uni-jena.de"
__status__ = "Development"
__version__ = "0.0.2"

import sys, os
from pprint import pprint
import argparse
import json
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import matplotlib.dates as mdates

parser = argparse.ArgumentParser(description="")
parser.add_argument('file',
                    help='input json file to use. The output of the matrixcounter.py script '
                         'is the intended input.')
parser.add_argument('-o', '--output',
                    help='output file to write the figure to; extension defines format to the'
                         'extend matplotlib supports; default: counter_matrix.pdf')
args = vars(parser.parse_args())

try:
    fd = open(args['file'])
except:
    print(f'cannot open {args["file"]}')
    sys.exit(1)
try:
    data = json.loads(fd.read())
except:
    print(f'cannot read data in {args["file"]}')
    sys.exit(1)

scaling = .8
fig = plt.figure(figsize=(16*scaling, 9*scaling))
ax = fig.subplots()

xmin=datetime.fromisoformat('2999-01-01T00:00:00')
xmax=datetime.fromisoformat('1999-01-01T00:00:00')

# go through all rooms and sort by current (last) user count
for room, roomdata in sorted(data['rooms'].items(), key=lambda x: list(x[1]['counts'].values())[-1]):
    # exclude a few rooms; TODO: already do not include those numbers in the collected data
    if roomdata['name'].startswith('deRSE-test'):
        continue
    if roomdata['name'].startswith('deRSE-enc-test'):
        continue
    if roomdata['name'].startswith('deRSE-alt'):
        continue
    if roomdata['name'].startswith('de-RSE-alt'):
        continue
    # convert data to the right types for plotting
    times  = [datetime.fromisoformat(s) for s in list(roomdata['counts'].keys())]
    counts = list(roomdata['counts'].values())
    # add one more "fake" datapoint, as stairs() requires len(edges) = len(data)+1
    times.append(times[-1])
    # get global extrema as limits later
    xmin = min(xmin, times[0])
    xmax = max(xmax, times[-1])
    # the actual plot line
    ax.stairs(counts, edges=times, lw=1, label=roomdata['name'])

# limit to the observed time range and ensure ymin to be 0
ax.set_xlim(xmin=xmin, xmax=xmax)
ax.set_ylim(ymin=0)

# some plot cosmetics
ax.spines['top'].set_visible(False)
ax.spines['left'].set_visible(False)
ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
for label in ax.get_xticklabels(which='major'):
    label.set(rotation=20, horizontalalignment='right')
ax.yaxis.tick_right()
ax.yaxis.set_major_locator(MaxNLocator(integer=True))

handles, labels = ax.get_legend_handles_labels()
ax.legend(reversed(handles), reversed(labels),
          loc='center left', bbox_to_anchor=(1.1, 0.5), frameon=False)

plt.tight_layout()
outfilename = 'counter_matrix.pdf'
if args['output']:
    outfilename = args['output']
plt.savefig(outfilename)

