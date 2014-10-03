from xml.etree import ElementTree as ET

def create_link(rel_author, rel_channel):
    return 'https://builds.catchexception.org/obs-studio/{0}/{1}/updates.xml'.format(rel_author, rel_channel)

def create_feed(rel_author, rel_channel):
    rss_el = ET.Element('rss', {
        'xmlns:sparkle': 'http://www.andymatuschak.org/xml-namespaces/sparkle',
        'xmlns:ce': 'http://catchexception.org/xml-namespaces/ce',
        'version': '2.0'
    })

    title = 'OBS Studio {0} channel by {1}'.format(rel_channel, rel_author)
    link = create_link(rel_author, rel_channel)
    description = 'OBS Studio update channel'

    channel_el = ET.SubElement(rss_el, 'channel')
    ET.SubElement(channel_el, 'title').text = title
    ET.SubElement(channel_el, 'link').text = link
    ET.SubElement(channel_el, 'description').text = description
    ET.SubElement(channel_el, 'language').text = 'en'
    return rss_el

def load_or_create_feed(rel_author, rel_channel):
    link = create_link(rel_author, rel_channel)
    import urllib2

    feed = create_feed(rel_author, rel_channel)
    try:
        resp = urllib2.urlopen(link)
        feed = ET.fromstring(resp.read())
    except urllib2.HTTPError, e:
        if e.code != 404:
            raise
        return feed
    except:
        raise

    return feed

def sign_package(package, key):
    from shlex import split as shplit
    from subprocess import PIPE

    with open(package, 'r') as f:
        import subprocess
        p1 = subprocess.Popen(shplit('openssl dgst -sha1 -binary'), stdin=f, stdout=PIPE)
        p2 = subprocess.Popen(shplit('openssl dgst -dss1 -sign "{0}"'.format(key)), stdin=p1.stdout, stdout=PIPE)
        p3 = subprocess.Popen(shplit('openssl enc -base64'), stdin=p2.stdout, stdout=PIPE)

        p1.poll(), p2.poll(), p3.poll()

        if p1.returncode or p2.returncode or p3.returncode:
            raise RuntimeError

        return ''.join(p3.communicate()[0].splitlines())

def load_manifest(manifest_file):
    with open(manifest_file, 'r') as f:
        import cPickle
        return cPickle.load(f)

def populate_item(item, package, signature, m, channel):
    from email.utils import formatdate
    import os

    user_version = '{0}.{1}'.format(m['tag']['name'], len(m['commits']))
    base_url = 'https://builds.catchexception.org/obs-studio/{0}/{1}'.format(m['user'], channel)

    title = 'OBS Studio {0} {1} by {2}'.format(user_version, channel, m['user'])
    notes_link = '{0}/{1}-notes.html'.format(base_url, user_version)

    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'sparkle:releaseNotesLink').text = notes_link
    ET.SubElement(item, 'pubDate').text = formatdate()
    ET.SubElement(item, 'enclosure', {
        'url': '{0}/{1}.zip'.format(base_url, user_version),
        'sparkle:version': m['version'],
        'length': str(os.stat(package).st_size),
        'type': 'application/octet-stream',
        'sparkle:dsaSignature': signature
    })

def create_update(package, signature, manifest_file, channel):
    manifest = load_manifest(args.manifest)
    feed_ele = load_or_create_feed(manifest['user'], channel)
    ET.dump(feed_ele)
    max_version = 0
    sha1 = None
    for item in feed_ele.findall('channel/item'):
        ET.dump(item)
        en_ele = item.find('enclosure')
        v = int(en_ele.get('sparkle:version'))
        if v > max_version:
            max_version = v
            sha1 = en_ele.get('ce:sha1')
        elif v == max_version:
            # if we find the same version, delete as we may be fixing a bad update
            feed_ele.find('channel').remove(item)

    new_item = ET.SubElement(feed_ele.find('channel'), 'item')
    populate_item(new_item, package, signature, manifest, channel)
    ET.dump(feed_ele)

import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-m', '--manifest', dest='manifest', default='manifest')
parser.add_argument('-c', '--channel', dest='channel', default='test')
parser.add_argument('-p', '--package', dest='package', default='OBS.zip')
parser.add_argument('-k', '--key', dest='key')
args = parser.parse_args()

sig = sign_package(args.package, args.key)
create_update(args.package, sig, args.manifest, args.channel)
