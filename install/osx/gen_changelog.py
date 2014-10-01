def cmd(cmd):
    import subprocess
    import shlex
    return subprocess.check_output(shlex.split(cmd)).rstrip('\r\n')

def gen_html(github_user):
    latest_tag = cmd('git describe --tags --abbrev=0')
    rev = cmd('git rev-parse {0}'.format(latest_tag))
    anno = cmd('git cat-file -p {0}'.format(rev))
    url = 'https://github.com/{0}/obs-project/commit/%H'.format(github_user)

    with open('readme.html', 'w') as f:
        f.write("<html><body>")

        log_cmd = 'git log {0}...HEAD --pretty=format:\'<li>&bull; <a href="{1}">(view)</a> %s</li>\''
        log_res = cmd(log_cmd.format(latest_tag, url))
        if len(log_res.splitlines()):
            f.write('<p>Changes since {0}: (Newest to oldest)</p>'.format(latest_tag))
            f.write(log_res)

        ul = False
        f.write('<p>')
        for i, v in enumerate(anno.splitlines()):
            if i <= 4:
                continue

            import re
            l = v.lstrip()
            if not len(l):
                continue
            if l.startswith('*'):
                ul = True
                if not ul:
                    f.write('<ul>')
                f.write('<li>&bull; {0}</li>'.format(re.sub(r'^(\s*)?[*](\s*)?', '', l)))
            else:
                ul = False
                if ul:
                    f.write('</ul>')
                f.write('<p>{0}</p>'.format(l))
        if ul:
            f.write('</ul>')
        f.write('</p></body></html>')

import argparse
parser = argparse.ArgumentParser(description='obs-studio readme gen')
parser.add_argument('-u', '--user', dest='user', default='jp9000')
args = parser.parse_args()

gen_html(args.user)