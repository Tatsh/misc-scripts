from base64 import b64decode
import subprocess as sp
import sys

__all__ = ('main', )


def main() -> int:
    try:
        fn = sys.argv[1]
    except IndexError:
        return 1
    fn_lower = fn.lower()
    if '.m4' in fn_lower or fn_lower.endswith('.mp4'):
        sp.run(('MP4Box', '-dump-item', '1:path=/dev/stdout', fn), check=True)
    elif fn_lower.endswith('.mp3'):
        for line in sp.run(('id3ted', '-l', fn),
                           stdout=sp.PIPE,
                           text=True,
                           check=True).stdout.split('\n'):
            if 'TXXX' in line:
                print(b64decode(line.split(':')[2].replace(' ', '')))
                break
    elif fn_lower.endswith('.mkv'):
        for line in sp.run(('mkvextract', fn, 'attachments', '1:/dev/stdout'),
                           stdout=sp.PIPE,
                           text=True,
                           check=True).stdout.split('\n')[1:]:
            sys.stdout.write(line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
