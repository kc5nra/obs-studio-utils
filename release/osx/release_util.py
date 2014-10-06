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

def create_link(rel_author, rel_channel, filename):
    return 'https://builds.catchexception.org/obs-studio/{0}/{1}/{2}'.format(rel_author, rel_channel, filename)

def create_version(m):
    return '{0}.{1}'.format(m['tag']['name'], m['jenkins_build'])

def create_feed(rel_author, rel_channel):
    rss_el = ET.Element('rss')

    title = 'OBS Studio {0} channel by {1}'.format(rel_channel, rel_author)
    link = create_link(rel_author, rel_channel, "updates.xml")
    description = 'OBS Studio update channel'

    channel_el = ET.SubElement(rss_el, 'channel')
    ET.SubElement(channel_el, 'title').text = title
    ET.SubElement(channel_el, 'link').text = link
    ET.SubElement(channel_el, 'description').text = description
    ET.SubElement(channel_el, 'language').text = 'en'
    return rss_el

def load_or_create_feed(rel_author, rel_channel):
    link = create_link(rel_author, rel_channel, "updates.xml")
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

def load_or_create_history(rel_author, rel_channel):
    link = create_link(rel_author, rel_channel, "history")
    import urllib2, cPickle

    try:
        resp = urllib2.urlopen(link)
        return cPickle.loads(resp.read())
    except urllib2.HTTPError, e:
        if e.code != 404:
            raise
        return dict()

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

def populate_item(item, package, key, m, channel, package_type):
    from email.utils import formatdate
    import os

    package_path = '{0}-{1}.zip'.format(package, package_type)
    signature = sign_package(package_path, key)

    user_version = create_version(m)
    base_url = 'https://builds.catchexception.org/obs-studio/{0}/{1}'.format(m['user'], channel)

    title = 'OBS Studio {0} {1} by {2} ({3})'.format(user_version, channel, m['user'], package_type)

    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, qn_tag('sparkle', 'releaseNotesLink')).text = '{0}/notes.html'.format(base_url)
    ET.SubElement(item, 'pubDate').text = formatdate()
    ET.SubElement(item, qn_tag('ce', 'packageType')).text = package_type

    ET.SubElement(item, 'enclosure', {
        'length': str(os.stat(package_path).st_size),
        'type': 'application/octet-stream',
        'url': '{0}/{1}-{2}.zip'.format(base_url, user_version, package_type),
        qn_tag('ce', 'sha1'): m['sha1'],
        qn_tag('sparkle', 'dsaSignature'): signature,
        qn_tag('sparkle', 'shortVersionString'): user_version,
        qn_tag('sparkle', 'version'): '{0}'.format(m['jenkins_build'])
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

def write_notes_html(f, manifest, versions, history):
    # make oldest to newest
    commits = [dict(sha1 = c[:40], desc = c[41:]) for c in manifest['commits'][::-1]]
    known_commits = set(c['sha1'] for c in commits)

    history[manifest['sha1']] = commits

    assigned_commits = set()

    # oldest to newest
    seen_sha1 = set()
    for v in versions:
        v['commits'] = []
        v['removed_from_history'] = v['sha1'] not in known_commits
        if v['sha1'] in seen_sha1:
            continue
        seen_sha1.add(v['sha1'])
        if v['removed_from_history'] and not v['sha1'] in history:
            continue
        for commit in history[v['sha1']]:
            if commit['sha1'] in assigned_commits:
                continue

            known = commit['sha1'] in known_commits
            v['commits'].append(dict(commit))
            v['commits'][-1]['known'] = known
            if known:
                assigned_commits.add(commit['sha1'])

    f.write('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Release notes for version {0}</title>
                <meta charset="utf-8">
                <script>
                    function toggle(version)
                    {{
                        changes = document.getElementById("changes" + version);
                        if (changes != null)
                            changes.style.display = changes.style.display == "none" ? "block" : "none";
                        return false;
                    }}
                </script>
            </head>
            <body>
            '''.format(manifest['tag']['name']))
    f.write('<h2>Release notes for version {0}</h2>'.format(manifest['tag']['name']))
    write_tag_html(f, manifest['tag']['name'], manifest['tag']['description'])
    for v in versions:
        strike_through = ' style="text-decoration:line-through"'
        extra_style = strike_through if v['removed_from_history'] else ""
        caption = '<h3 id="caption{0}"{2}><a href="#caption{0}" onclick="return toggle(\'{0}\')"> Release notes for version {1}</a></h3>'
        caption = caption.format(v['internal_version'], v['user_version'], extra_style)
        f.write(caption)
        if len(v['commits']):
            url = 'https://github.com/{0}/obs-studio/commit/{1}'
            change_fmt = '<li{2}><a href="{0}">(view)</a> {1}</li>'
            f.write('<ul id="changes{0}">'.format(v['internal_version']))
            for c in v['commits']:
                extra_style = strike_through if not c['known'] else ""
                f.write(change_fmt.format(url.format(manifest['user'], c['sha1']), c['desc'], extra_style))
            f.write('</ul>')
    f.write('''
            </body>
            </html>
            ''')



def create_update(package, key, manifest_file):
    manifest = load_manifest(manifest_file)

    channel = manifest['branch']

    feed_ele = load_or_create_feed(manifest['user'], channel)
    history  = load_or_create_history(manifest['user'], channel)

    from distutils.version import LooseVersion

    my_version = LooseVersion('{0}'.format(manifest['jenkins_build']))

    versions = []

    for item in feed_ele.findall('channel/item'):
        en_ele = item.find('enclosure')
        internal_version = LooseVersion(en_ele.get(qn_tag('sparkle', 'version')))
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

    versions.append(dict(
        internal_version = my_version,
        user_version     = create_version(manifest),
        sha1             = manifest['sha1']
    ))

    import StringIO
    notes = StringIO.StringIO()

    write_notes_html(notes, manifest, versions, history)


    new_item = ET.SubElement(feed_ele.find('channel'), 'item')
    populate_item(new_item, package, key, manifest, channel, 'mpkg')

    new_item = ET.SubElement(feed_ele.find('channel'), 'item')
    populate_item(new_item, package, key, manifest, channel, 'app')

    from os import path

    deploy_path = path.join('deploy', manifest['user'], channel)
    mkdir(deploy_path)

    feed_ele = ET.fromstring(ET.tostring(feed_ele, encoding='utf-8', method='xml'))

    with open(path.join(deploy_path, 'updates.xml'), 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        ET.ElementTree(feed_ele).write(f, encoding='utf-8', method='xml')

    with open(path.join(deploy_path, 'notes.html'), 'w') as f:
        f.write(notes.getvalue())

    with open(path.join(deploy_path, 'history'), 'w') as f:
        import cPickle
        cPickle.dump(history, f)

    import shutil
    shutil.copy('{0}-mpkg.zip'.format(package), path.join(deploy_path, '{0}-mpkg.zip'.format(create_version(manifest))))
    shutil.copy('{0}-app.zip'.format(package), path.join(deploy_path, '{0}-app.zip'.format(create_version(manifest))))


import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-m', '--manifest', dest='manifest', default='manifest')
parser.add_argument('-p', '--package', dest='package', default='OBS')
parser.add_argument('-k', '--key', dest='key')
args = parser.parse_args()

create_update(args.package, args.key, args.manifest)
