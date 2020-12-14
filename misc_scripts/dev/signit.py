import subprocess as sp
import sys

__all__ = ('main', )


def main() -> int:
    if len(sys.argv) < 2:
        print(f'Usage: {sys.argv[0]} app [IDENTITY]', file=sys.stderr)
        return 1
    try:
        identity = sys.argv[2]
    except IndexError:
        identity = [
            x for x in sp.run(('security', 'find-identity', '-v', '-s',
                               'Mac Developer'),
                              text=True,
                              check=True,
                              stdout=sp.PIPE).stdout.split('\n') if '1)' in x
        ][0].split('"')[1]
    try:
        sp.run(('codesign', '-s', identity, '-fv', sys.argv[1]), check=True)
    except sp.CalledProcessError:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
