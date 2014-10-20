def cmd(cmd):
    import subprocess
    import shlex
    return subprocess.check_output(shlex.split(cmd)).rstrip('\r\n')

def get_template(file):
    with open(file, 'r') as f:
        import string
        return string.Template(f.read())

def get_tag_info(tag):
    rev = cmd('git -C obs-studio rev-parse {0}'.format(tag))
    anno = cmd('git -C obs-studio cat-file -p {0}'.format(rev))
    tag_info = []
    for i, v in enumerate(anno.splitlines()):
        if i <= 4:
            continue
        tag_info.append(v.lstrip())

    return tag_info

def create_ppa(tag, jenkins_build):
    cmd('git clone https://github.com/jp9000/obs-studio.git')
    cmd('git -C obs-studio checkout {0}'.format(tag))
    cmd('git -C obs-studio submodule update --init --recursive')

    archive = 'obs-studio_{0}'.format(tag)
    cmd('git -C obs-studio archive --format tar.gz --output "../{0}.orig.tar.gz" --prefix {0}/ {1}'.format(archive, tag))
    cmd('tar xvzf {0}.orig.tar.gz'.format(archive))

    import os
    debian_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'debian')
    args = {
        'tag': tag,
        'jenkins_build': jenkins_build,
        'changelog': '  '+'\n  '.join(get_tag_info(tag)),
        'date': cmd('date -R')
    }
    control_template = get_template(os.path.join(debian_dir, 'changelog'))

    import shutil
    shutil.copytree(debian_dir, '{0}/debian'.format(archive))

    with open('{0}/debian/changelog'.format(archive), 'w') as f:
        f.write(control_template.substitute(args))

if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description='obs-studio ubuntu ppa util')
    parser.add_argument('-j', '--jenkins-build', dest='jenkins_build')
    parser.add_argument('-t', '--tag', dest='tag')

    args = parser.parse_args()

    create_ppa(args.tag, args.jenkins_build)