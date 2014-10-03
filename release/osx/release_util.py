from xml.etree import ElementTree as ET

def qn_tag(n, t):
    return {
        'ce': str(ET.QName('http://catchexception.org/xml-namespaces/ce', t)),
        'sparkle': str(ET.QName('http://www.andymatuschak.org/xml-namespaces/sparkle', t))
    }[n]
cd obs
ET.register_namespace('sparkle', 'http://www.andymatuschak.org/xml-namespaces/sparkle')
ET.register_namespace('ce', 'http://catchexception.org/xml-namespaces/ce')

def create_link(rel_author, rel_channel):
    return 'https://builds.catchexception.org/obs-studio/{0}/{1}/updates.xml'.format(rel_author, rel_channel)

def create_version(m):
    return '{0}.{1}'.format(m['tag']['name'], len(m['commits']))

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

        sig = ''.join(p3.communicate()[0].splitlines())

        p1.poll(), p2.poll(), p3.poll()
        if p1.returncode or p2.returncode or p3.returncode:
            raise RuntimeError

        return sig

def load_manifest(manifest_file):
    with open(manifest_file, 'r') as f:
        import cPickle
        return cPickle.load(f)

def populate_item(item, package, signature, m, channel):
    from email.utils import formatdate
    import os

    user_version = create_version(m)
    base_url = 'https://builds.catchexception.org/obs-studio/{0}/{1}'.format(m['user'], channel)

    title = 'OBS Studio {0} {1} by {2}'.format(user_version, channel, m['user'])
    notes_link = '{0}/{1}-notes.html'.format(base_url, user_version)

    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, 'sparkle:releaseNotesLink').text = notes_link
    ET.SubElement(item, 'pubDate').text = formatdate()
    ET.SubElement(item, 'enclosure', {
        'url': '{0}/{1}.zip'.format(base_url, user_version),
        'sparkle:version': m['version'],
        'sparkle:shortVersionString': user_version,
        'length': str(os.stat(package).st_size),
        'type': 'application/octet-stream',
        'sparkle:dsaSignature': signature,
        'ce:sha1': m['sha1']
    })

def mkdir(dirname):
    import os, errno
    try:
        os.makedirs(dirname)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

def create_update(package, signature, manifest_file, channel):
    manifest = load_manifest(args.manifest)
    feed_ele = load_or_create_feed(manifest['user'], channel)
    max_version = 0
    sha1 = None
    for item in feed_ele.findall('channel/item'):
        ET.dump(item)
        en_ele = item.find('enclosure')
        v = int(en_ele.get(qn_tag('sparkle', 'version')))
        if v > max_version:
            max_version = v
            sha1 = en_ele.get(qn_tag('ce', 'sha1'))
        elif v == max_version:
            # if we find the same version, delete as we may be fixing a bad update
            feed_ele.find('channel').remove(item)

    new_item = ET.SubElement(feed_ele.find('channel'), 'item')
    populate_item(new_item, package, signature, manifest, channel)

    from os import path

    deploy_path = path.join('deploy', manifest['user'], channel)
    mkdir(deploy_path)
    with open(path.join(deploy_path, 'updates.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        ET.ElementTree(feed_ele).write(f, encoding='utf-8')

    import shutil
    shutil.copy(package, path.join(deploy_path, '{0}.zip'.format(create_version(manifest))))


import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-m', '--manifest', dest='manifest', default='manifest')
parser.add_argument('-c', '--channel', dest='channel', default='test')
parser.add_argument('-p', '--package', dest='package', default='OBS.zip')
parser.add_argument('-k', '--key', dest='key')
args = parser.parse_args()

sig = sign_package(args.package, args.key)
create_update(args.package, sig, args.manifest, args.channel)
