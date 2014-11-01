from release_util import qn_tag, create_link, dump_xml
from xml.etree import ElementTree as ET

def load_feed(rel_channel):
    link = create_link(rel_channel, "updates.xml")
    import urllib2
    return ET.fromstring(urllib2.urlopen(link).read())


ET.register_namespace('sparkle', 'http://www.andymatuschak.org/xml-namespaces/sparkle')
ET.register_namespace('ce', 'http://catchexception.org/xml-namespaces/ce')

import argparse
parser = argparse.ArgumentParser(description='obs-studio release util')
parser.add_argument('-c', '--channel', dest='channel', default='stable')
parser.add_argument('-v', '--version', dest='version')
parser.add_argument('-a', '--action', dest='action')
parser.add_argument('-V', '--value', dest='action_value')

args = parser.parse_args()

feed = load_feed(args.channel)
items = feed.findall('''.//item/enclosure[@{0}='{1}']..'''.format(qn_tag('sparkle', 'version'), args.version))

if args.action == 'activate':
    for item in items:
        item.find(qn_tag('ce', 'deployed')).text = str(args.action_value)
elif args.action == 'delta':
    for item in items:
        el = item.find(qn_tag('ce', 'deltaCandidate'))
        if el is None:
            el = ET.SubElement(item, qn_tag('ce', 'deltaCandidate'))
        el.text = args.action_value

dump_xml('updates.xml', feed)