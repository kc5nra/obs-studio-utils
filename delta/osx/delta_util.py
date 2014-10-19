from xml.etree import ElementTree as ET
from collections import namedtuple, defaultdict
from distutils.version import LooseVersion

# make LooseVersion usable as dict key by implementing __hash__, don't call parse on LooseVersion keys!
LooseVersion.__hash__ = lambda self: hash(str(self))

BASE_URL = "https://builds.catchexception.org/obs-studio/"

def qn_tag(n, t):
    return {
        'ce': str(ET.QName('http://catchexception.org/xml-namespaces/ce', t)),
        'sparkle': str(ET.QName('http://www.andymatuschak.org/xml-namespaces/sparkle', t))
    }[n]

def get_feed_path(url, base_dir):
    return url.replace(BASE_URL, base_dir)

def load_feed(filename):
    return ET.parse(filename)

def sign_delta(filename, key):
    from shlex import split as shplit
    from subprocess import PIPE

    with open(filename, 'r') as f:
        import subprocess
        p1 = subprocess.Popen(shplit('openssl dgst -sha1 -binary'), stdin=f, stdout=PIPE)
        p2 = subprocess.Popen(shplit('openssl dgst -dss1 -sign "{0}"'.format(key)), stdin=p1.stdout, stdout=PIPE)
        p3 = subprocess.Popen(shplit('openssl enc -base64'), stdin=p2.stdout, stdout=PIPE)

        sig = ''.join(p3.communicate()[0].splitlines())

        p1.poll(), p2.poll(), p3.poll()
        if p1.returncode or p2.returncode or p3.returncode:
            raise RuntimeError

        return sig

def dump_xml(file, element):
    with open(file, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>')
        ET.ElementTree(element).write(f, encoding='utf-8', method='xml')

DeltaInfo = namedtuple("DeltaInfo", """version
                                       user_version
                                       deltas_needed
                                       deltas
                                       delta_elements
                                       base_url""")

def create_delta_infos(feed_ele):
    delta_infos = dict()

    for item in feed_ele.findall('channel/item'):
        en_ele = item.find('enclosure')
        internal_version = LooseVersion(en_ele.get(qn_tag('sparkle', 'version')))
        user_version = LooseVersion(en_ele.get(qn_tag('sparkle', 'shortVersionString')))

        if internal_version not in delta_infos:
            base_url = en_ele.get('url').rsplit("/", 1)[0] + "/"
            info = DeltaInfo(internal_version, user_version, set(), set(), list(), base_url)
            delta_infos[user_version] = info

        delta_elem = item.find('{http://www.andymatuschak.org/xml-namespaces/sparkle}deltas')
        if delta_elem is None:
            delta_elem = ET.SubElement(item, 'sparkle:deltas')
        if delta_elem is not None:
            delta_infos[user_version].delta_elements.append(delta_elem)

            for delta in delta_elem.findall('enclosure'):
                info.deltas.add(LooseVersion(delta.get(qn_tag('sparkle', 'deltaFrom'))))

    return delta_infos

def compute_required_deltas(delta_infos):
    required_for_version = defaultdict(set)
    previous_versions    = set()
    versions             = sorted(delta_infos.keys())

    for version in versions:
        delta_info = delta_infos[version]
        delta_info.deltas_needed.update(previous_versions - delta_info.deltas)
        previous_versions.add(version)

        for prev in delta_info.deltas_needed:
            required_for_version[prev].add(version)

        """if delta_info.deltas_needed:
            print "Required deltas for {0}: {1}".format(version, delta_info.deltas_needed)"""

    return {k: v for k, v in delta_infos.iteritems() if v.deltas_needed}, required_for_version

def compute_processing_order(delta_infos, required_for_version):
    version_required_deltas = lambda version: delta_infos[version].deltas_needed if version in delta_infos else []
    delta_operations = lambda version: len(required_for_version[version]) + len(version_required_deltas(version))
    processing_order = sorted(delta_infos, key=delta_operations)
    #print [(v, delta_operations(v)) for v in processing_order]
    return processing_order

def build_delta(source, target, diff, binary_delta):
    from subprocess import call
    call([binary_delta, "create", source, target, diff])

def create_temp_app(zipfile):
    from subprocess import call
    from tempfile import mkdtemp
    from os import path
    directory = mkdtemp()
    call(["unzip", "-q", "-d", directory, zipfile])
    return directory, path.join(directory, "OBS.app")

def create_deltas(feed_path, base_dir, key, binary_delta):
    from os import path
    feed_ele    = load_feed(feed_path)
    delta_infos = create_delta_infos(feed_ele)

    required_deltas, required_for_version = compute_required_deltas(delta_infos)

    processing_order = compute_processing_order(required_deltas, required_for_version)

    zip_pattern   = path.join(path.dirname(feed_path), "{0}-app.zip")
    delta_pattern = path.join(path.dirname(feed_path), "{0}-{1}.delta")

    unzipped_versions = dict()
    def unzip(version):
        if version not in unzipped_versions:
            unzipped_versions[version] = create_temp_app(zip_pattern.format(delta_infos[version].user_version))
        return unzipped_versions[version][1]

    try:
        import os
        for version in processing_order:
            info = delta_infos[version]
            for from_ in info.deltas_needed:
                print "Creating delta:", from_, "->", version
                delta_filename = delta_pattern.format(from_, version)
                build_delta(unzip(from_), unzip(version), delta_filename, binary_delta)
                signature = sign_delta(delta_filename, key)
                for elem in info.delta_elements:
                    ET.SubElement(elem, 'enclosure', {
                        'length': str(os.stat(delta_filename).st_size),
                        'type': 'application/octet-stream',
                        'url': '{0}/{1}'.format(info.base_url, delta_filename),
                        qn_tag('sparkle', 'dsaSignature'): signature,
                        qn_tag('sparkle', 'shortVersionString'): str(info.user_version),
                        qn_tag('sparkle', 'version'): str(version),
                        qn_tag('sparkle', 'deltaFrom'): str(from_),
                    })

    finally:
        import shutil
        for paths in unzipped_versions.values():
            shutil.rmtree(paths[0])

    feed_ele = ET.fromstring(ET.tostring(feed_ele.getroot(), encoding='utf-8', method='xml'))

    dump_xml(feed_path, feed_ele)

    """import shutil
    shutil.copy('{0}-mpkg.zip'.format(package), path.join(deploy_path, '{0}-mpkg.zip'.format(create_version(manifest))))
    shutil.copy('{0}-app.zip'.format(package), path.join(deploy_path, '{0}-app.zip'.format(create_version(manifest))))"""

def create_deltas_for_feeds(feeds_json, base_dir, delta_tool, key):
    import json
    with open(feeds_json) as f:
        feeds = json.load(f)

    for name, channel in feeds.iteritems():
        feed_path = get_feed_path(channel['url'], base_dir)
        print "Processing %s:"%name, channel['url'], "->", feed_path
        create_deltas(feed_path, base_dir, key, delta_tool)

if __name__ == "__main__":
    ET.register_namespace('sparkle', 'http://www.andymatuschak.org/xml-namespaces/sparkle')
    ET.register_namespace('ce', 'http://catchexception.org/xml-namespaces/ce')

    import argparse
    parser = argparse.ArgumentParser(description='obs-studio delta util')
    parser.add_argument('-k', '--key', dest='key')
    parser.add_argument('-d', '--delta-tool', dest='delta_tool')
    parser.add_argument('-f', '--feeds-json', dest='feeds')
    parser.add_argument('-b', '--feed-base-dir', dest='base_dir')
    args = parser.parse_args()

    create_deltas_for_feeds(args.feeds, args.base_dir, args.delta_tool, args.key)
