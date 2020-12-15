import sys

__all__ = ('main', )


def main() -> int:
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <exe file> <icon> <icon index>',
              file=sys.stderr)
        return 1
    try:
        ico_index = int(sys.argv[3])
    except IndexError:
        ico_index = 0
    except ValueError:
        print(f'Invalid ICO index: {sys.argv[3]}', file=sys.stderr)
        return 1
    try:
        with open('Autorun.inf'):
            print('Not overwriting existing Autorun.inf', file=sys.stderr)
    except FileNotFoundError:
        pass
    with open('Autorun.inf', 'w+') as f:
        f.write('\r\n'.join(('[Autorun]', f'open={sys.argv[1]}',
                             f'icon={sys.argv[2]},{ico_index}')))
        f.write('\r\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
