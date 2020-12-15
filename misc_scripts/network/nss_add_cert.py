#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
from os import environ
import subprocess as sp
import sys

__all__ = ('main', )


def main() -> int:
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} HOST [PORT]', file=sys.stderr)
        return 1
    try:
        port = int(sys.argv[2])
    except IndexError:
        port = 443
    except ValueError:
        print('Not a valid port', file=sys.stderr)
        return 1
    p = sp.Popen(('openssl', 's_client', '-connect', f'{sys.argv[1]}:{port}'),
                 text=True,
                 stdout=sp.PIPE,
                 stdin=sp.PIPE)
    stdout, _ = p.communicate()
    in_cert = False
    cert_lines = []
    for line in stdout.split('\n'):
        if '-BEGIN CERTIFICATE-' in line:
            cert_lines.append(line)
            in_cert = True
        elif in_cert:
            cert_lines.append(line)
            if '-END CERTIFICATE-' in line:
                break
    home = environ['HOME']
    p = sp.Popen(('certutil', '-A', '-d', f'sql:{home}/.pki/nssdb', '-t', 'TC',
                  '-n', sys.argv[1]),
                 stdin=sp.PIPE,
                 text=True)
    p.communicate('\n'.join(cert_lines) + '\n')
    return p.returncode


if __name__ == '__main__':
    sys.exit(main())
