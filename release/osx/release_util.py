from xml.etree import ElementTree as ET

def qn_tag(n, t):
    return {
        'ce': str(ET.QName('http://catchexception.org/xml-namespaces/ce', t)),
        'sparkle': str(ET.QName('http://www.andymatuschak.org/xml-namespaces/sparkle', t))
    }[n]

def create_channel(m):
    if m['stable']:
        return 'stable'
    else:
        return '{0}/{1}'.format(m['user'], m['branch'])

def create_link(rel_channel, filename):
    return 'https://builds.catchexception.org/obs-studio/{0}/{1}'.format(rel_channel, filename)

def create_version(m):
    if m['stable']:
        return m['tag']['name']
    else:
        return '{0}.{1}'.format(m['tag']['name'], m['jenkins_build'])

def create_feed(rel_channel):
    rss_el = ET.Element('rss')

    title = 'OBS Studio {0} channel'.format(rel_channel)
    link = create_link(rel_channel, "updates.xml")
    description = 'OBS Studio update channel'

    channel_el = ET.SubElement(rss_el, 'channel')
    ET.SubElement(channel_el, 'title').text = title
    ET.SubElement(channel_el, 'link').text = link
    ET.SubElement(channel_el, 'description').text = description
    ET.SubElement(channel_el, 'language').text = 'en'
    return rss_el

def load_or_create_feed(rel_channel):
    link = create_link(rel_channel, "updates.xml")
    import urllib2

    feed = create_feed(rel_channel)
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

def load_or_create_history(rel_channel):
    link = create_link(rel_channel, "history")
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
    base_url = 'https://builds.catchexception.org/obs-studio/{0}'.format(channel)

    title = 'OBS Studio {0} on {1} ({2})'.format(user_version, channel, package_type)

    ET.SubElement(item, 'title').text = title
    ET.SubElement(item, qn_tag('sparkle', 'releaseNotesLink')).text = '{0}/notes.html'.format(base_url)
    ET.SubElement(item, 'pubDate').text = formatdate()
    ET.SubElement(item, qn_tag('ce', 'packageType')).text = package_type

    if m['stable']:
        ET.SubElement(item, qn_tag('ce', 'deployed')).text = 'false'
        version = m['tag']['name']
    else:
        version = m['jenkins_build']

    ET.SubElement(item, 'enclosure', {
        'length': str(os.stat(package_path).st_size),
        'type': 'application/octet-stream',
        'url': '{0}/{1}-{2}.zip'.format(base_url, user_version, package_type),
        qn_tag('ce', 'sha1'): m['sha1'],
        qn_tag('sparkle', 'dsaSignature'): signature,
        qn_tag('sparkle', 'shortVersionString'): user_version,
        qn_tag('sparkle', 'version'): version
    })

def mkdir(dirname):
    import os, errno
    try:
        os.makedirs(dirname)
    except OSError, e:
        if e.errno != errno.EEXIST:
            raise

def write_tag_html(f, desc):

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
    # make newest to oldest
    commits = [dict(sha1 = c[:40], desc = c[41:]) for c in manifest['commits']]
    known_commits = set(c['sha1'] for c in commits)
    commit_known = lambda commit: commit['sha1'] in known_commits

    history[manifest['sha1']] = commits

    from distutils.version import LooseVersion
    last_tag = LooseVersion(manifest['tag']['name'])
    versions = [v for v in versions if LooseVersion(v['user_version']) >= last_tag]

    for v in versions:
        v['commit_set'] = set(c['sha1'] for c in history.get(v['sha1'], []))

    # oldest to newest
    if versions:
        v = versions[0]
        v['commits'] = [dict(c) for c in history.get(v['sha1'], [])]
        v['known'] = commit_known(v)
        for c in v['commits']:
            c['known'] = commit_known(c)
            c['removed'] = False

    for p, v in zip(versions, versions[1:]):
        v['commits'] = list()
        v['known'] = commit_known(v)

        removed = p['commit_set'] - v['commit_set']
        added   = v['commit_set'] - p['commit_set']

        for c in history.get(v['sha1'], []):
            if c['sha1'] in added:
                v['commits'].append(dict(c))
                v['commits'][-1]['removed'] = False

        for c in history.get(p['sha1'], [])[::-1]:
            if c['sha1'] in removed:
                v['commits'].append(dict(c))
                v['commits'][-1]['removed'] = True

        for c in v['commits']:
            c['known'] = commit_known(c)

    have_displayable_commits = False
    for v in versions:
        if v['commits']:
            have_displayable_commits = True
            break

    f.write('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Release notes for version {0}</title>
                <meta charset="utf-8">
                <script>
                    var versions = ["{1}"];
                    function toggle(version)
                    {{
                        var changes = document.getElementById("changes" + version);
                        if (changes != null)
                            changes.style.display = changes.style.display == "none" ? "block" : "none";
                        var link    = document.getElementById("toggle"  + version);
                        if (link != null)
                            link.innerHTML = link.innerHTML == "[-]" ? "[+]" : "[-]";
                        return false;
                    }}

                    function toggle_lower(version)
                    {{
                        if (versions.indexOf(version) == -1)
                            return;

                        var version_found = false;
                        var captions = document.getElementsByTagName("h3");
                        for (var i = 0; i < captions.length; i++) {{
                            var parts = captions[i].id.split("caption");
                            if (!parts || parts.length != 2)
                                continue;

                            var rebased = captions[i].className.search(/rebased/) != -1;
                            var current_version = parts[1] == version;

                            if (version_found) {{
                                captions[i].className += " old";
                                toggle(parts[1]);
                            }}

                            if (current_version)
                                version_found = true;
                        }}
                    }}
                </script>
                <style>
                    html
                    {{
                        font-family: sans-serif;
                    }}
                    h3 a
                    {{
                        font-family: monospace;
                    }}
                    h3.old
                    {{
                        color: gray;
                    }}
                    .removed
                    {{
                        text-decoration: line-through;
                    }}
                </style>
            </head>
            <body>
            '''.format(manifest['tag']['name'], '", "'.join(str(v['internal_version']) for v in versions)))
    if have_displayable_commits:
        for v in versions[::-1]:
            removed_class = ' class="removed"'
            extra_style = removed_class if not v['known'] else ""
            expand_link = ' <a id="toggle{0}" href="#caption{0}" onclick="return toggle(\'{0}\')">[-]</a>'.format(v['internal_version']) if v['commits'] else ""
            caption = '<h3 id="caption{0}"{2}>Release notes for version {1}{3}</h3>'
            caption = caption.format(v['internal_version'], v['user_version'], extra_style, expand_link)
            f.write(caption)
            if len(v['commits']):
                url = 'https://github.com/{0}/obs-studio/commit/{1}'
                change_fmt = '<li><a href="{0}"{2}>(view)</a> {1}</li>'
                f.write('<ul id="changes{0}">'.format(v['internal_version']))
                for c in v['commits']:
                    extra_style = removed_class if not c['known'] else ""
                    text = ("<span{0}>{1}</span>" if c['removed'] else "{1}").format(removed_class, c['desc'])
                    url_formatted = url.format(manifest['user'], c['sha1'])
                    f.write(change_fmt.format(url_formatted, text, extra_style))
                f.write('</ul>')
    f.write('<h2>Release notes for version {0}</h2>'.format(manifest['tag']['name']))
    write_tag_html(f, manifest['tag']['description'])
    f.write('''
                <script>
                    parts = window.location.href.toString().split("#");
                    if (parts.length == 2 && parts[1].search(/^\d+$/) == 0)
                        toggle_lower(parts[1]);
                </script>
            </body>
            </html>
            ''')

def dump_xml(file, element):
    with open(file, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        ET.ElementTree(element).write(f, encoding='utf-8', method='xml')

def create_update(package, key, manifest_file):
    manifest = load_manifest(manifest_file)

    channel = create_channel(manifest)

    feed_ele = load_or_create_feed(channel)
    history  = load_or_create_history(channel)

    from distutils.version import LooseVersion

    if manifest['stable']:
        my_version = LooseVersion(manifest['tag']['name'])
    else:
        my_version = LooseVersion(manifest['jenkins_build'])

    versions = []

    seen_versions = set()

    for item in feed_ele.findall('channel/item'):
        en_ele = item.find('enclosure')
        internal_version = LooseVersion(en_ele.get(qn_tag('sparkle', 'version')))
        user_version = en_ele.get(qn_tag('sparkle', 'shortVersionString'))
        sha1 = en_ele.get(qn_tag('ce', 'sha1'))

        if internal_version == my_version:
            # shouldn't happen, delete
            feed_ele.find('channel').remove(item)
            continue

        if str(internal_version) in seen_versions:
            continue
        seen_versions.add(str(internal_version))

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

    deploy_path = path.join('deploy', channel)
    mkdir(deploy_path)

    feed_ele = ET.fromstring(ET.tostring(feed_ele, encoding='utf-8', method='xml'))

    dump_xml(path.join(deploy_path, 'updates.xml'), feed_ele)

    with open(path.join(deploy_path, 'notes.html'), 'w') as f:
        f.write(notes.getvalue())

    with open(path.join(deploy_path, 'history'), 'w') as f:
        import cPickle
        cPickle.dump(history, f)

    import shutil
    shutil.copy('{0}-mpkg.zip'.format(package), path.join(deploy_path, '{0}-mpkg.zip'.format(create_version(manifest))))
    shutil.copy('{0}-app.zip'.format(package), path.join(deploy_path, '{0}-app.zip'.format(create_version(manifest))))


if __name__ == "__main__":
    ET.register_namespace('sparkle', 'http://www.andymatuschak.org/xml-namespaces/sparkle')
    ET.register_namespace('ce', 'http://catchexception.org/xml-namespaces/ce')

    import argparse
    parser = argparse.ArgumentParser(description='obs-studio release util')
    parser.add_argument('-m', '--manifest', dest='manifest', default='manifest')
    parser.add_argument('-p', '--package', dest='package', default='OBS')
    parser.add_argument('-k', '--key', dest='key')
    args = parser.parse_args()

    create_update(args.package, args.key, args.manifest)
