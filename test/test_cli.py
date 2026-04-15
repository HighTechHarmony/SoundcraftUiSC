#!/usr/bin/env python3

import hashlib
import json
import os
import tempfile

import ui24rsc

from util import pfmt

# ---------------------------------------------------------------------------
# Paths to example files (relative to repository root)
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_EXAMPLE_SNAP = os.path.join(
    _REPO_ROOT,
    'example_ui24_show_exports',
    'S%26S Gigs',
    'ScottStartTemplate.uisnapshot',
)
_EXAMPLE_JSON = os.path.join(
    _REPO_ROOT,
    'example_ui24_offline_exports',
    'S&S Gigs',
    'ScottStartTemplate.json',
)


def test_obj2diff() -> None:
    equal, objdiff = ui24rsc.obj2diff({}, {})

    assert equal
    assert pfmt(objdiff) == '{}'

    equal, objdiff = ui24rsc.obj2diff(
        {
            'baz': 123,
            'foo': 'XYZ',
            'sub01': {'hey': 1, 'ho': 3},
            'sub02': [4, 5, 10, 7],
        },
        {
            'baz': 123,
            'foo': 'bar',
            'sub01': {'hey': 1, 'ho': 2},
            'sub02': [4, 5, 6, 7],
        },
    )

    assert not equal
    assert pfmt(objdiff) == pfmt({
        'foo': 'XYZ',
        'sub01': {'ho': 3},
        'sub02': {2: 10},
    })


def test_obj2full() -> None:
    objfull = ui24rsc.obj2full({}, {})

    assert pfmt(objfull) == '{}'

    objfull = ui24rsc.obj2full(
        {
            'foo': 'XYZ',
            'sub01': {'ho': 3},
            'sub02': {2: 10},
        },
        {
            'baz': 123,
            'foo': 'bar',
            'sub01': {'hey': 1, 'ho': 2},
            'sub02': [4, 5, 6, 7],
        },
    )

    assert pfmt(objfull) == pfmt({
        'baz': 123,
        'foo': 'XYZ',
        'sub01': {'hey': 1, 'ho': 3},
        'sub02': [4, 5, 10, 7],
    })


def test_obj2tree() -> None:
    objtree = ui24rsc.obj2tree({})

    assert pfmt(objtree) == '{}'

    objtree = ui24rsc.obj2tree(
        {'one.two.three': 3, 'one.two.six': 6, 'one.seven': 7})

    assert pfmt(objtree) == pfmt(
        {'one': {'two': {'three': 3, 'six': 6}, 'seven': 7}})


def test_obj2dots() -> None:
    objdots = ui24rsc.obj2dots({})

    assert pfmt(objdots) == '{}'

    objdots = ui24rsc.obj2dots(
        {'one': {'two': {'three': 3, 'six': 6}, 'seven': 7}})

    assert pfmt(objdots) == pfmt({
        'one.two.three': 3,
        'one.two.six': 6,
        'one.seven': 7,
    })


def test_obj2sort() -> None:
    obj = ui24rsc.objsort({})

    assert pfmt(obj) == '{}'

    obj = ui24rsc.objsort(
        {
            'b': 123,
            'a': 456,
            'sub01': {'x': {}, 'f': 'g'},
            'name': 'xyz',
            'sub02': [9, 3, 7],
        }
    )

    assert pfmt(obj) == pfmt({
        'name': 'xyz',
        'a': 456,
        'b': 123,
        'sub02': [9, 3, 7],
        'sub01': {'f': 'g', 'x': {}},
    })


# ===========================================================================
# uisnapshot format tests
# ===========================================================================

def test_uisnapshot2dots_basic() -> None:
    text = (
        '# comment line\n'
        'i.0.mute=1\n'
        'i.0.gain=0.5\n'
        'i.0.name=Kick\n'
        '##MD5: AABBCCDD\n'
    )
    dots = ui24rsc.uisnapshot2dots(text)
    assert dots == {'i.0.mute': 1, 'i.0.gain': 0.5, 'i.0.name': 'Kick'}
    # MD5 footer and comment must not appear in result
    assert '##MD5' not in dots
    assert not any(k.startswith('#') for k in dots)


def test_uisnapshot2dots_types() -> None:
    text = 'a=0\nb=3.14\nc=hello\nd=1\n##MD5: X\n'
    d = ui24rsc.uisnapshot2dots(text)
    assert d['a'] == 0 and isinstance(d['a'], int)
    assert d['b'] == 3.14 and isinstance(d['b'], float)
    assert d['c'] == 'hello' and isinstance(d['c'], str)
    assert d['d'] == 1 and isinstance(d['d'], int)


def test_dots2uisnapshot_md5() -> None:
    dots = {'i.0.mute': 1, 'i.0.gain': 0.75}
    text = ui24rsc.dots2uisnapshot(dots)
    # Must end with ##MD5: line
    lines = text.splitlines()
    assert lines[-1].startswith('##MD5: ')
    md5_val = lines[-1].split(' ', 1)[1]
    # Verify checksum manually
    body = '\n'.join(lines[:-1]) + '\n'
    expected = hashlib.md5(body.encode('utf-8')).hexdigest().upper()
    assert md5_val == expected


def test_dots2uisnapshot_excludes_LOCAL() -> None:
    dots = {'i.0.mute': 0, 'LOCAL.foo': 'bar', 'LOCAL': 'baz'}
    text = ui24rsc.dots2uisnapshot(dots)
    assert 'LOCAL' not in text.split('##MD5:')[0]


def test_uisnapshot_roundtrip() -> None:
    '''Parsing then re-serialising a real snapshot must yield valid MD5.'''
    if not os.path.exists(_EXAMPLE_SNAP):
        return  # skip if example file absent
    with open(_EXAMPLE_SNAP, 'r', encoding='utf-8') as f:
        original = f.read()
    dots = ui24rsc.uisnapshot2dots(original)
    regenerated = ui24rsc.dots2uisnapshot(dots)
    lines = regenerated.splitlines()
    assert lines[-1].startswith('##MD5: ')
    md5_val = lines[-1].split(' ', 1)[1]
    body = '\n'.join(lines[:-1]) + '\n'
    assert hashlib.md5(body.encode('utf-8')).hexdigest().upper() == md5_val


def test_encode_decode_name() -> None:
    assert ui24rsc._encode_name('S&S Gigs') == 'S%26S Gigs'
    assert ui24rsc._decode_name('S%26S Gigs') == 'S&S Gigs'
    # Round-trip identity
    assert ui24rsc._decode_name(ui24rsc._encode_name('S&S Gigs')) == 'S&S Gigs'
    # Spaces are kept literal
    assert ' ' in ui24rsc._encode_name('My Show')


def test_convert_tree_json2snap(tmp_path) -> None:
    '''json2snap should create correctly-named uisnapshot files with valid MD5.'''
    # Build a minimal offline JSON show tree
    show_dir = tmp_path / 'S&S Gigs'
    show_dir.mkdir()
    dots = {'i.0.mute': 1, 'i.1.gain': 0.5}
    with open(show_dir / 'MySnap.json', 'w') as f:
        json.dump(dots, f)

    dst = tmp_path / 'dst'
    ui24rsc.convert_tree(tmp_path, dst, direction='json2snap')

    expected_snap = dst / 'Exports' / 'shows' / 'S%26S Gigs' / 'MySnap.uisnapshot'
    assert expected_snap.exists(), f'Expected {expected_snap}'

    # Verify written snapshot has valid MD5
    text = expected_snap.read_text(encoding='utf-8')
    lines = text.splitlines()
    assert lines[-1].startswith('##MD5: ')
    md5_val = lines[-1].split(' ', 1)[1]
    body = '\n'.join(lines[:-1]) + '\n'
    assert hashlib.md5(body.encode('utf-8')).hexdigest().upper() == md5_val


def test_convert_tree_snap2json(tmp_path) -> None:
    '''snap2json should decode percent-encoded folder names correctly.'''
    # Build a minimal USB snapshot tree
    snap_dir = tmp_path / 'Exports' / 'shows' / 'S%26S Gigs'
    snap_dir.mkdir(parents=True)
    dots_in = {'i.0.mute': 1, 'i.1.gain': 0.5}
    snap_text = ui24rsc.dots2uisnapshot(dots_in)
    (snap_dir / 'MySnap.uisnapshot').write_text(snap_text, encoding='utf-8')

    dst = tmp_path / 'json_out'
    ui24rsc.convert_tree(tmp_path, dst, direction='snap2json')

    out_file = dst / 'S&S Gigs' / 'MySnap.json'
    assert out_file.exists(), f'Expected {out_file}'
    with open(out_file) as f:
        result = json.load(f)
    assert result['i.0.mute'] == 1


def test_uishow_not_overwritten(tmp_path) -> None:
    '''.uishow must not be overwritten by convert_tree if it already exists.'''
    show_dir = tmp_path / 'ShowA'
    show_dir.mkdir()
    with open(show_dir / 'snap.json', 'w') as f:
        json.dump({'i.0.mute': 0}, f)

    sentinel = 'SENTINEL_CONTENT\n'
    dst = tmp_path / 'dst'
    uishow_path = dst / 'Exports' / 'shows' / 'ShowA' / '.uishow'
    uishow_path.parent.mkdir(parents=True, exist_ok=True)
    uishow_path.write_text(sentinel, encoding='utf-8')

    ui24rsc.convert_tree(tmp_path, dst, direction='json2snap')

    assert uishow_path.read_text(encoding='utf-8') == sentinel

