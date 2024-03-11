#!/usr/bin/env python3
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
                    help='input json file to use')
parser.add_argument('-o', '--output',
                    help='output file to write the figure to; extension defines format to the'
                         'extend matplotlib supports')
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

scaling = .6
fig = plt.figure(figsize=(16*scaling, 9*scaling))
ax = fig.subplots()

xmin=datetime.fromisoformat('2999-01-01T00:00:00')
xmax=datetime.fromisoformat('1999-01-01T00:00:00')

for room, roomdata in sorted(data['rooms'].items(), key=lambda x: x[1]['counts'][1][-1]):
    if roomdata['name'].startswith('deRSE-test'):
        continue
    if roomdata['name'].startswith('deRSE-alt'):
        continue
    if roomdata['name'].startswith('de-RSE-alt'):
        continue
    times  = [datetime.fromisoformat(s) for s in roomdata['counts'][0]]
    counts = roomdata['counts'][1]
    times.append(times[-1])
    xmin = min(xmin, times[0])
    xmax = max(xmax, times[-1])

    ax.stairs(counts, edges=times, lw=2, label=roomdata['name'])

ax.spines['top'].set_visible(False)
ax.spines['left'].set_visible(False)

ax.set_xlim(xmin=xmin, xmax=xmax)
ax.set_ylim(ymin=0)
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

