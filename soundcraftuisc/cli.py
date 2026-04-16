#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import sys
import urllib.parse

from contextlib import ExitStack
from functools import reduce
from pathlib import Path
from typing import Any

import yaml


def obj2diff(objfull: Any, objref: Any) -> tuple[bool, Any]:
    '''
    Converts a snapshot object from Soundcraft Ui24R full format to custom diff
    format using objref as reference object.
    The first return value is True if objfull is equal to objref and False
    otherwise. The second return value is the object in the diff format
    '''
    if type(objref) is not dict and type(objref) is not list:
        if objfull == objref:
            return True, None
        else:
            return False, objfull

    objdiff = {}

    if type(objref) is dict:
        keys = objref.keys()
    else:
        keys = range(min(len(objfull), len(objref)))

    for k in keys:
        e, d = obj2diff(objfull[k], objref[k])
        if not e:
            objdiff[k] = d

    if objdiff:
        return False, objdiff
    else:
        return True, {}


def obj2full(objdiff: Any, objref: Any) -> Any:
    '''
    Converts a snapshot object from custom diff format to Soundcraft Ui24R full
    format using objref as reference object.
    The return value is the object in the full format
    '''
    if type(objref) is not dict and type(objref) is not list:
        return objdiff

    if type(objref) is dict:
        objfull = {}
        keys = objref.keys()
    else:
        objfull = [None] * len(objref)  # List with pre-defined size
        keys = range(len(objref))

    for k in keys:
        if k in objdiff.keys():
            objfull[k] = obj2full(objdiff[k], objref[k])
        else:
            objfull[k] = objref[k]

    return objfull


def obj2tree(objdots: dict) -> dict:
    '''
    Converts a snapshot object from Soundcraft Ui24R dotted format to tree
    format
    '''
    objtree = {}

    for key, val in objdots.items():
        # Avoid problems with "vg.*" keys
        if key.startswith('vg.') and len(key) == 4:
            key = 'vg.' + key[3] + '.content'

        path = key.split('.')

        # Create the structure down to key
        target = reduce(lambda d, k: d.setdefault(k, {}), path[:-1], objtree)

        target[path[-1]] = val

    return objtree


def obj2dots(objtree: Any, path: str = '') -> dict[str, Any]:
    '''
    Converts a snapshot object from tree format to Soundcraft Ui24R dotted
    format
    '''
    if path == 'LOCAL':  # The 'LOCAL' root object is preserved as it is
        return {'LOCAL': objtree}

    objdots = {}

    if type(objtree) is dict:
        prefix = '' if path == '' else path + '.'
        for k, v in objtree.items():
            objdots.update(obj2dots(v, prefix + k))
    elif type(objtree) is list:
        prefix = '' if path == '' else path + '.'
        for i, v in enumerate(objtree):
            objdots.update(obj2dots(v, prefix + str(i)))
    else:
        if path.startswith('vg.') and path.endswith('.content') \
                and len(path) == 12:
            path = 'vg.' + path[3]  # Restore "vg.*" keys
        objdots[path] = objtree

    return objdots


def objsort(obj: Any) -> Any:
    '''
    Recursively sorts an object according to special rules. Returns the sorted
    object
    '''
    if type(obj) is dict:
        if len(obj) == 0:
            return obj
        elif next(iter(obj)) == '0':
            # Numerical sorting
            return {k: objsort(v)
                    for k, v in sorted(obj.items(), key=lambda x: int(x[0]))}
        else:
            tmp = dict(sorted(obj.items()))
            result = {}

            if 'name' in tmp:
                # If present, name should be the first attribute
                result['name'] = tmp.pop('name')

            result.update({k: v for k, v in tmp.items()
                           if type(v) is not dict
                           and type(v) is not list})
            result.update({k: objsort(v) for k, v in tmp.items()
                           if type(v) is list})
            result.update({k: objsort(v) for k, v in tmp.items()
                           if type(v) is dict})

            return result
    elif type(obj) is list:
        return [objsort(x) for x in obj]
    else:
        return obj


DEFAULT_INIT_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                 'default-init.yml')


# ---------------------------------------------------------------------------
# uisnapshot serialisation / deserialisation
# ---------------------------------------------------------------------------

def uisnapshot2dots(text: str) -> dict:
    '''
    Parse a .uisnapshot file (plain text key=value format) into a flat dotted
    dict compatible with the Soundcraft Ui24R dots format.
    Comment lines (starting with "#") and the "##MD5:" footer are ignored.
    Values are type-coerced: int first, then float, otherwise kept as str.
    '''
    result = {}
    for line in text.splitlines():
        if line.startswith('#'):
            continue
        if '=' not in line:
            continue
        key, _, raw_val = line.partition('=')
        try:
            result[key] = int(raw_val)
        except ValueError:
            try:
                result[key] = float(raw_val)
            except ValueError:
                result[key] = raw_val
    return result


def _val_to_uisnapshot_str(val: Any) -> str:
    '''Format a single value for uisnapshot key=value output.'''
    if isinstance(val, bool):  # must come before int check (bool is subclass of int)
        return '1' if val else '0'
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    return str(val)


def dots2uisnapshot(obj: dict) -> str:
    '''
    Convert a flat dotted dict to .uisnapshot text.
    LOCAL.* keys are excluded.  No poem header is written.
    An MD5 checksum footer (##MD5: <HEX>) is appended.
    '''
    lines = []
    for key, val in obj.items():
        if key == 'LOCAL' or key.startswith('LOCAL.'):
            continue
        lines.append(f'{key}={_val_to_uisnapshot_str(val)}')
    body = '\n'.join(lines) + '\n'
    md5 = hashlib.md5(body.encode('utf-8')).hexdigest().upper()
    return body + f'##MD5: {md5}\n'


# ---------------------------------------------------------------------------
# .uishow generation helpers
# ---------------------------------------------------------------------------

# Channel letter prefixes that carry safe/mgmask entries in a .uishow file.
# Single-letter prefixes 'i', 's', 'f', 'a', 'l', 'p', 'v' are always
# followed by a numeric index.  'm' (master) is un-indexed.
_UISHOW_CHANNEL_TYPES = frozenset('i s f a l p v'.split())
_UISHOW_N_VG = 6  # number of VG groups in a ui24 show


def _channel_prefixes_from_dots(dots: dict) -> set[str]:
    '''
    Extract unique channel prefixes (e.g. "i.3", "a.0", "m") from a dots dict.
    Only mixer channel types are included (i, s, f, a, l, p, v, m).
    '''
    prefixes: set[str] = set()
    for key in dots:
        if key == 'LOCAL' or key.startswith('LOCAL.'):
            continue
        parts = key.split('.')
        if len(parts) >= 2 and parts[0] in _UISHOW_CHANNEL_TYPES:
            try:
                int(parts[1])
                prefixes.add(f'{parts[0]}.{parts[1]}')
            except ValueError:
                pass
        elif parts[0] == 'm' and len(parts) >= 2:
            prefixes.add('m')
    return prefixes


def _uishow_text(channel_prefixes: set[str]) -> str:
    '''
    Generate default .uishow file content for a show with the given channel
    prefixes.  All safe/mgmask values default to 0.
    '''
    lines: list[str] = []
    # ISO isolation keys (always present, values empty)
    for k in ('iso.gr', 'iso.fx', 'iso.m', 'iso.mtx', 'iso.bus', 'iso.ch'):
        lines.append(f'{k}=')
    # VG group name + value keys
    for n in range(_UISHOW_N_VG):
        lines.append(f'vg.{n}.name=')
        lines.append(f'vg.{n}=[]')
    # Per-channel safe and mgmask, sorted alphabetically
    def _ch_sort_key(p: str) -> tuple:
        parts = p.split('.')
        return (parts[0], int(parts[1]) if len(parts) > 1 else -1)
    for prefix in sorted(channel_prefixes, key=_ch_sort_key):
        lines.append(f'{prefix}.safe=0')
        lines.append(f'{prefix}.mgmask=0')
    body = '\n'.join(lines) + '\n'
    md5 = hashlib.md5(body.encode('utf-8')).hexdigest().upper()
    return body + f'##MD5: {md5}\n'


# ---------------------------------------------------------------------------
# Name encoding / decoding for USB filesystem paths
# ---------------------------------------------------------------------------

# Only percent-encode characters that are hazardous to file paths.
# Spaces are left as-is (matching observed device behavior).
_PATH_SAFE_CHARS = ' '


def _encode_name(name: str) -> str:
    '''Percent-encode a show/snapshot name for use as a filesystem path component.'''
    return urllib.parse.quote(name, safe=_PATH_SAFE_CHARS)


def _decode_name(safe_name: str) -> str:
    '''Decode a percent-encoded filesystem path component to a plain name.'''
    return urllib.parse.unquote(safe_name)


# ---------------------------------------------------------------------------
# Batch tree conversion
# ---------------------------------------------------------------------------

def convert_tree(src_root: str | Path, dst_root: str | Path,
                 direction: str = 'json2snap') -> None:
    '''
    Batch-convert between the offline JSON export folder structure and the USB
    uisnapshot tree that the Soundcraft Ui24R expects.

    json2snap:
        src_root/SHOW_NAME/SNAPSHOT_NAME.json
        → dst_root/Exports/shows/SAFE_SHOW_NAME/SAFE_SNAPSHOT_NAME.uisnapshot
        A .uishow file is generated in each output show folder (skipped if one
        already exists so user customisations are not overwritten).

    snap2json:
        src_root/Exports/shows/SAFE_SHOW_NAME/*.uisnapshot
        → dst_root/SHOW_NAME/SNAPSHOT_NAME.json
    '''
    src_root = Path(src_root)
    dst_root = Path(dst_root)

    if direction == 'json2snap':
        shows_dir = dst_root / 'Exports' / 'shows'
        for show_dir in sorted(src_root.iterdir()):
            if not show_dir.is_dir():
                continue
            safe_show = _encode_name(show_dir.name)
            out_show_dir = shows_dir / safe_show
            seen_channels: set[str] = set()

            for json_file in sorted(show_dir.glob('*.json')):
                snap_name = json_file.stem
                safe_snap = _encode_name(snap_name)
                out_path = out_show_dir / f'{safe_snap}.uisnapshot'

                with open(json_file, 'r', encoding='utf-8') as f:
                    dots = json.load(f)

                seen_channels |= _channel_prefixes_from_dots(dots)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(dots2uisnapshot(dots))

            # Write .uishow only if it does not already exist
            uishow_path = out_show_dir / '.uishow'
            if seen_channels and not uishow_path.exists():
                uishow_path.parent.mkdir(parents=True, exist_ok=True)
                with open(uishow_path, 'w', encoding='utf-8') as f:
                    f.write(_uishow_text(seen_channels))

    elif direction == 'snap2json':
        usb_shows_dir = src_root / 'Exports' / 'shows'
        if not usb_shows_dir.exists():
            raise FileNotFoundError(
                f'USB shows directory not found: {usb_shows_dir}')

        for safe_show_dir in sorted(usb_shows_dir.iterdir()):
            if not safe_show_dir.is_dir():
                continue
            show_name = _decode_name(safe_show_dir.name)
            out_show_dir = dst_root / show_name

            for snap_file in sorted(safe_show_dir.glob('*.uisnapshot')):
                snap_name = _decode_name(snap_file.stem)
                out_path = out_show_dir / f'{snap_name}.json'

                with open(snap_file, 'r', encoding='utf-8') as f:
                    dots = uisnapshot2dots(f.read())

                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, 'w', encoding='utf-8') as f:
                    json.dump(dots, f)
    else:
        raise ValueError(
            f'Unknown direction: {direction!r}. '
            'Use "json2snap" or "snap2json".')


# ---------------------------------------------------------------------------
# convert-tree subcommand entry point
# ---------------------------------------------------------------------------

def _main_convert_tree(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog='soundcraftuisc convert-tree',
        description='Batch-convert between offline JSON export tree and USB '
        'uisnapshot tree'
    )
    parser.add_argument(
        'direction',
        choices=['json2snap', 'snap2json'],
        help='"json2snap": offline JSON folder → USB Exports/shows tree.  '
             '"snap2json": USB Exports/shows tree → offline JSON folder.')
    parser.add_argument('src', type=str, help='Source root directory')
    parser.add_argument('dst', type=str, help='Destination root directory')

    args = parser.parse_args(argv[2:])
    try:
        convert_tree(args.src, args.dst, args.direction)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    # Dispatch convert-tree subcommand before the main argument parser
    if len(argv) > 1 and argv[1] == 'convert-tree':
        return _main_convert_tree(argv)

    parser = argparse.ArgumentParser(
        description='Converts a Soundcraft Ui24R snapshot file from/to '
        'different formats'
    )

    parser.add_argument('actions', metavar='ACTIONS', type=str,
                        help='Comma-separated sequence of operations to be '
                        'performed. Examples: "diff,tree" "dots,full" '
                        '"tree,sort"')
    parser.add_argument('file_in', metavar='FILE_IN', type=str,
                        nargs='?', default='-',
                        help='Input file. If set to "-" then stdin is used '
                        '(default: %(default)s)')
    parser.add_argument('file_out', metavar='FILE_OUT', type=str,
                        nargs='?', default='-',
                        help='Output file. If set to "-" then stdout is used '
                        '(default: %(default)s)')

    parser.add_argument('-j', '--json', action='store_true',
                        help='If present, the output format will be forced to '
                        'JSON')
    parser.add_argument('-y', '--yaml', action='store_true',
                        help='If present, the output format will be forced to '
                        'YAML')

    args = parser.parse_args(argv[1:])
    args.actions = [] if args.actions == '' else \
        [x.strip().lower() for x in args.actions.split(',')]

    if args.json and args.yaml:
        print('Error: both --json and --yaml flags specified', file=sys.stderr)
        return 1

    ############################################################################

    with open(DEFAULT_INIT_PATH, 'r') as f:
        objref = yaml.safe_load(f)
        objref = obj2dots(objref)

    ############################################################################

    with ExitStack() as stack:
        file_in = (sys.stdin if args.file_in == '-'
                   else stack.enter_context(open(args.file_in, 'r')))

        # When the first action is fromuisnapshot, read raw text instead of
        # YAML/JSON so the uisnapshot parser receives the original string.
        if args.actions and args.actions[0] == 'fromuisnapshot':
            obj: Any = file_in.read()
        else:
            obj = yaml.safe_load(file_in)

    ############################################################################

    format = 'json' if args.json else 'yaml'

    funcs = {
        'diff': lambda x: obj2diff(x, objref)[1],
        'full': lambda x: obj2full(x, objref),
        'tree': obj2tree,
        'dots': obj2dots,
        'sort': objsort,
        'fromuisnapshot': uisnapshot2dots,
        'touisnapshot': dots2uisnapshot,
    }

    for a in args.actions:
        if a not in funcs:
            print('Unsupported action:', a, file=sys.stderr)
            return 1
        if a in ('diff', 'tree') and not args.json:
            format = 'yaml'
        if a in ('full', 'dots') and not args.yaml:
            format = 'json'
        if a == 'touisnapshot':
            format = 'uisnapshot'
        obj = funcs[a](obj)

    ############################################################################

    with ExitStack() as stack:
        file_out = (sys.stdout if args.file_out == '-'
                    else stack.enter_context(open(args.file_out, 'w')))

        if format == 'uisnapshot' or isinstance(obj, str):
            file_out.write(obj)
        elif format == 'json':
            json.dump(obj, file_out)
        else:
            yaml.safe_dump(obj, file_out, sort_keys=False)

    return 0
