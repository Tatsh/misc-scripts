import re
import subprocess as sp
import sys


def main() -> int:
    command = 'open'
    try:
        sp.run(('bash', '-c', f'command -v {command}'),
               stdout=sp.PIPE,
               stderr=sp.PIPE,
               check=True)
    except sp.CalledProcessError:
        command = 'xdg-open'
    try:
        lines = sp.run(('git', 'remote'),
                       stdout=sp.PIPE,
                       text=True,
                       check=True).stdout.strip().split('\n')
    except sp.CalledProcessError:
        return 1
    try:
        orig = sp.run(('git', 'remote', 'get-url', lines[0]),
                      stdout=sp.PIPE,
                      check=True,
                      text=True).stdout.strip()
    except sp.CalledProcessError:
        return 1
    if orig:
        url = re.sub(
            r'\.git', '',
            re.sub(r'\.(com|org)\:', r'.\1/', re.sub(r'^git@', 'https://',
                                                     orig)))
        try:
            sp.run((command, url), check=True)
        except sp.CalledProcessError:
            return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
