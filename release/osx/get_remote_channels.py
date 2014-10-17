def cmd(cmd):
    import subprocess
    import shlex
    return subprocess.check_output(shlex.split(cmd)).rstrip('\r\n')

def get_remote_channels(user, url):
    heads_raw = cmd('git ls-remote --heads {0}'.format(url))

    import re
    return ['{0}/{1}'.format(user, x) for x in re.findall(r'[a-f, 0-9]{40}\s+?refs/heads/(.*)', heads_raw)]

if __name__ == "__main__":
    print get_remote_channels('palana', 'https://github.com/palana/obs-studio.git')

