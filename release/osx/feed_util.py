import os

def get_sub(dir):
    return [name for name in os.listdir(dir) if os.path.isdir(os.path.join(dir, name))]

import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-d', '--directory', dest='dir', default='.')
parser.add_argument('-u', '--base-url', dest='base_url', default='https://builds.catchexception.org/obs-studio')
args = parser.parse_args()


users = get_sub(args.dir)
root = {}
for u in users:
    channels = get_sub(os.path.join(args.dir, u))
    root[u] = {}
    for c in channels:
        root[u][c] = {
            'name': '''{0}'s {1} channel'''.format(u, c),
            'feed': '{0}/{1}/{2}/updates.xml'.format(args.base_url, u, c)
        }

import json
with open(os.path.join(args.dir, 'feeds.json'), 'w') as f:
    json.dump(root, f, sort_keys=True, indent=4, separators=(',', ': '))

