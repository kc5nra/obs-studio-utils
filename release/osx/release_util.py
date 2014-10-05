from xml.etree import ElementTree as ET

def CDATA(text=None):
    element = ET.Element('![CDATA[')
    element.text = text
    return element

ET._original_serialize_xml = ET._serialize_xml

def _serialize_xml(write, elem, encoding, qnames, namespaces):
    if elem.tag == '![CDATA[':
        write("\n<%s%s]]>\n" % (
                elem.tag, elem.text))
        return
    return ET._original_serialize_xml(
        write, elem, encoding, qnames, namespaces)
ET._serialize_xml = ET._serialize['xml'] = _serialize_xml

def qn_tag(n, t):
    return {
        'ce': str(ET.QName('http://catchexception.org/xml-namespaces/ce', t)),
        'sparkle': str(ET.QName('http://www.andymatuschak.org/xml-namespaces/sparkle', t))
    }[n]

ET.register_namespace('sparkle', 'http://www.andymatuschak.org/xml-namespaces/sparkle')
ET.register_namespace('ce', 'http://catchexception.org/xml-namespaces/ce')

def create_link(rel_author, rel_channel):
    return 'https://builds.catchexception.org/obs-studio/{0}/{1}/updates.xml'.format(rel_author, rel_channel)

def create_version(m):
    return '{0}.{1}.{2}'.format(m['tag']['name'], len(m['commits']), m['jenkins_build'])

def create_feed(rel_author, rel_channel):
    rss_el = ET.Element('rss')

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

    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, qn_tag('sparkle', 'releaseNotesLink')).text = '{0}/notes.html'.format(base_url)
    ET.SubElement(item, 'pubDate').text = formatdate()

    ET.SubElement(item, 'enclosure', {
        'length': str(os.stat(package).st_size),
        'type': 'application/octet-stream',
        'url': '{0}/{1}.zip'.format(base_url, user_version),
        qn_tag('ce', 'sha1'): m['sha1'],
        qn_tag('sparkle', 'dsaSignature'): signature,
        qn_tag('sparkle', 'shortVersionString'): user_version,
        qn_tag('sparkle', 'version'): '{0}.{1}'.format(m['version'], m['jenkins_build'])
    })

def mkdir(dirname):
    import os, errno
    try:
        os.makedirs(dirname)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

def write_tag_html(f, name, desc):

    ul = False
    for l in desc:
        if not len(l):
            continue
        if l.startswith('*'):
            ul = True
            if not ul:
                f.write('<ul>')

            import re
            f.write('<li>{0}</li>'.format(re.sub(r'^(\s*)?[*](\s*)?', '', l)))
        else:
            ul = False
            if ul:
                f.write('</ul>')
            f.write('<p>{0}</p>'.format(l))
    if ul:
        f.write('</ul>')

def write_notes_html(f, manifest, versions):
    # make oldest to newest
    commits = manifest['commits'][::-1]

    # oldest to newest
    prev_ver = 0
    for i, v in enumerate(versions):
        v['commits'] = []
        found = False
        for c in commits[prev_ver:]:
            sha1 = c[:40]
            desc = c[41:]
            if v['sha1'] == sha1:
                prev_ver = i
                found = True

            v['commits'].append({
                'sha1': sha1,
                'desc': desc
            })

            if found:
                break

    f.write('<div id="0">')
    f.write('<h3>Release notes for version {0}</h3>'.format(manifest['tag']['name']))
    f.write('<p>')
    write_tag_html(f, manifest['tag']['name'], manifest['tag']['description'])
    f.write('</p>')
    f.write('</div>')
    for v in versions:
        f.write('<div id="{0}">'.format(v['internal_version']))
        f.write('<h3>Release notes for version {0}</h3>'.format(v['user_version']))
        f.write('<p>')
        if len(v['commits']):
            url = 'https://github.com/{0}/obs-studio/commit/{1}'
            change_fmt = '<li><a href="{0}">(view)</a> {1}</li>'
            f.write('<ul>')
            for c in v['commits']:
                f.write(change_fmt.format(url.format(manifest['user'], c['sha1']), c['desc']))
            f.write('</ul>')
        f.write('</p>')
        f.write('</div>')



def create_update(package, signature, manifest_file):
    manifest = load_manifest(args.manifest)

    channel = manifest['branch']

    feed_ele = load_or_create_feed(manifest['user'], channel)

    from distutils.version import StrictVersion

    my_version = StrictVersion('{0}.{1}'.format(manifest['version'], manifest['jenkins_build']))

    versions = []

    for item in feed_ele.findall('channel/item'):
        en_ele = item.find('enclosure')
        internal_version = StrictVersion(en_ele.get(qn_tag('sparkle', 'version')))
        user_version = en_ele.get(qn_tag('sparkle', 'shortVersionString'))
        sha1 = en_ele.get(qn_tag('ce', 'sha1'))

        if internal_version == my_version:
            # shouldn't happen, delete
            feed_ele.find('channel').remove(item)
            continue

        versions.append({
            'internal_version': internal_version,
            'user_version': user_version,
            'sha1': sha1
        })

    import StringIO
    notes = StringIO.StringIO()

    write_notes_html(notes, manifest, versions)

    new_item = ET.SubElement(feed_ele.find('channel'), 'item')
    populate_item(new_item, package, signature, manifest, channel)

    from os import path

    deploy_path = path.join('deploy', manifest['user'], channel)
    mkdir(deploy_path)

    feed_ele = ET.fromstring(ET.tostring(feed_ele, encoding='utf-8', method='xml'))

    with open(path.join(deploy_path, 'updates.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        ET.ElementTree(feed_ele).write(f, encoding='utf-8', method='xml')

    with open(path.join(deploy_path, 'notes.html'), 'w') as f:
        f.write(notes.getvalue())

    import shutil
    shutil.copy(package, path.join(deploy_path, '{0}.zip'.format(create_version(manifest))))


import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-m', '--manifest', dest='manifest', default='manifest')
parser.add_argument('-p', '--package', dest='package', default='OBS.zip')
parser.add_argument('-k', '--key', dest='key')
args = parser.parse_args()

sig = sign_package(args.package, args.key)
create_update(args.package, sig, args.manifest)
