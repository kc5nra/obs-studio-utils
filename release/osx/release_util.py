from xml.etree import ElementTree as ET

def create_feed(rel_author, rel_channel):
    rss_el = ET.Element('rss', {
        'xmlns:sparkle': 'http://www.andymatuschak.org/xml-namespaces/sparkle',
        'version': '2.0'
    })

    title = 'OBS Studio {0} channel by {1}'.format(rel_channel, rel_author)
    link = 'https://builds.catchexception.org/obs-studio/{0}/{1}/updates.xml'.format(rel_author, rel_channel)
    description = 'OBS Studio update channel'

    channel_el = ET.SubElement(rss_el, 'channel')
    ET.SubElement(channel_el, 'title').text = title
    ET.SubElement(channel_el, 'link').text = link
    ET.SubElement(channel_el, 'description').text = description
    ET.SubElement(channel_el, 'language').text = 'en'

    return rss_el, channel_el

