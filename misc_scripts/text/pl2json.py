import json
import plistlib
import sys

__all__ = ('main', )


def main() -> int:
    with open(sys.argv[1], 'rb') as f:
        data = plistlib.load(f)
        try:
            print(json.dumps(data, allow_nan=False, sort_keys=True, indent=2))
        except TypeError:
            print(
                plistlib.dumps(data,
                               fmt=plistlib.PlistFormat.FMT_XML).decode())
    return 0


if __name__ == '__main__':
    sys.exit(main())
