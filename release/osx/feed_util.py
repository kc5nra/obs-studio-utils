import os

def get_sub(dir):
    return [name for name in os.listdir(dir) if os.path.isdir(os.path.join(dir, name))]

import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-d', '--directory', dest='dir', default='.')
parser.add_argument('-u', '--base-url', dest='base_url', default='https://builds.catchexception.org/obs-studio')
args = parser.parse_args()

r = {}
import fnmatch

for d in get_sub('.'):
    for root, dirs, files in os.walk(d):
      for f in fnmatch.filter(files, 'updates.xml'):
            c = os.path.dirname(os.path.join(root, f))
            r[c] = '{0}/{1}/updates.xml'.format(args.base_url, c)

import json
with open(os.path.join(args.dir, 'feeds.json'), 'w') as f:
    json.dump(r, f, sort_keys=True, indent=4, separators=(',', ': '))
