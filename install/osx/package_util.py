def cmd(cmd):
    import subprocess
    import shlex
    return subprocess.check_output(shlex.split(cmd)).rstrip('\r\n')

def gen_html(github_user, latest_tag):

    rev = cmd('git rev-parse {0}'.format(latest_tag))
    anno = cmd('git cat-file -p {0}'.format(rev))
    url = 'https://github.com/{0}/obs-studio/commit/%H'.format(github_user)

    with open('readme.html', 'w') as f:
        f.write("<html><body>")
        log_cmd = """git log {0}...HEAD --pretty=format:'<li>&bull; <a href="{1}">(view)</a> %s</li>'"""
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

    cmd('textutil -convert rtf readme.html -output readme.rtf')
    cmd("""sed -i '' 's/Times-Roman/Verdana/g' readme.rtf""")

def prepare_pkg(project, package_id, latest_tag, jenkins_build):
    tag_diff_cnt = cmd('git rev-list {0}..HEAD | wc -l'.format(latest_tag))
    new_version = '{0}.{1}.{2}'.format(latest_tag, tag_diff_cnt, jenkins_build)
    cmd('packagesutil --file "{0}" set package-1 identifier {0}'.format(project, package_id))
    cmd('packagesutil --file "{0}" set package-1 version {0}'.format(project, new_version))


import argparse
parser = argparse.ArgumentParser(description='obs-studio readme gen')
parser.add_argument('-u', '--user', dest='user', default='jp9000')
parser.add_argument('-p', '--package-id', dest='package_id', default='org.obsproject.pkg.obs-studio')
parser.add_argument('-f', '--project-file', dest='project', default='OBS.pkgproj')
parser.add_argument('-j', '--jenkins-build', dest='jenkins_build', default='0')
args = parser.parse_args()

latest_tag = cmd('git describe --tags --abbrev=0')
gen_html(args.user, latest_tag)
prepare_pkg(args.project, args.package_id, latest_tag, args.jenkins_build)