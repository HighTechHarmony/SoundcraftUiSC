# ui24rsc

![device](device.png)

[![GitHub main workflow](https://img.shields.io/github/actions/workflow/status/dmotte/ui24rsc/main.yml?branch=main&logo=github&label=main&style=flat-square)](https://github.com/dmotte/ui24rsc/actions)
[![PyPI](https://img.shields.io/pypi/v/ui24rsc?logo=python&style=flat-square)](https://pypi.org/project/ui24rsc/)

:snake: **Ui24R** **S**napshot **C**onverter.

The official Soundcraft Ui24R JSON snapshot export format is very hard to understand and work with; thus, manually editing mixer snapshots from code can be extremely uncomfortable. This Python script lets you convert snapshots exported from the mixer Web UI to other more human-readable formats and vice versa. It can read/write both _JSON_ and _YAML_ documents.

> **Note**: this project handles both the **Soundcraft JSON snapshot format** (a.k.a. "_Offline Files_") and the **`.uisnapshot` / `.uishow` files** used on USB show exports.

> **Important**: this has been tested with the firmware version **3.5.8328-ui24**.

## Installation

This utility is available as a Python package on **PyPI**:

```bash
python3 -mpip install ui24rsc
```

## Usage

The first parameter of this command is `ACTIONS`, a **comma-separated sequence of operations** which will be used in order to process the input document and produce the output. See [the code](ui24rsc/cli.py) for more information on what each action does.

This is a basic example of how to convert from official Soundcraft JSON format to a custom tree-like, human-friendly, differential YAML format:

```bash
python3 -mui24rsc diff,tree original.json human-friendly.yml
```

And the opposite is:

```bash
python3 -mui24rsc dots,full human-friendly.yml official.json
```

For more details on how to use this command, you can also refer to its help message (`--help`).

## Working with USB show exports (`.uisnapshot`)

The Soundcraft Ui24R can also export shows to a USB drive. Each snapshot is
stored as a `.uisnapshot` file — a plain-text `key=value` format with an MD5
checksum footer — inside a folder hierarchy like:

```
Exports/
  shows/
    My Show/
      Snapshot A.uisnapshot
      Snapshot B.uisnapshot
      .uishow
```

This tool can convert between this format and the familiar offline JSON format
in both single-file and batch (tree) modes.

### Single-file conversion

Convert a `.uisnapshot` file to a flat JSON dots file:

```bash
python3 -mui24rsc fromuisnapshot snapshot.uisnapshot snapshot.json
```

Convert a flat JSON dots file back to a `.uisnapshot` file (MD5 checksum is
computed and appended automatically):

```bash
python3 -mui24rsc touisnapshot snapshot.json snapshot.uisnapshot
```

You can also chain these with other actions. For example, to convert a
`.uisnapshot` directly to a human-readable YAML diff:

```bash
python3 -mui24rsc fromuisnapshot,diff,tree snapshot.uisnapshot human-friendly.yml
```

### Batch tree conversion

The `convert-tree` subcommand converts an entire folder of offline JSON
snapshots to the USB export tree structure, or vice versa.

**Offline JSON → USB uisnapshot tree:**

```bash
python3 -mui24rsc convert-tree json2snap /path/to/offline/exports /path/to/usb
```

This will create the following structure under `/path/to/usb`:

```
Exports/
  shows/
    S%26S Gigs/           ← show folder name is percent-encoded
      My Snapshot.uisnapshot
      .uishow             ← generated automatically (see below)
```

Any character that is hazardous in a file path (e.g. `&`) is
percent-encoded in the output folder/file names. Spaces are kept as-is to
match the device's own naming convention.

**USB uisnapshot tree → offline JSON:**

```bash
python3 -mui24rsc convert-tree snap2json /path/to/usb /path/to/offline/exports
```

Percent-encoded folder and file names are decoded back to their original form
in the output.

### `.uishow` files

Each show directory on the USB drive contains a `.uishow` file that stores
per-show metadata (channel isolation groups, VCA groups, safe/mgmask
flags per channel).

When running `convert-tree json2snap`, a default `.uishow` file is generated
automatically for each show. It sets all `safe` and `mgmask` values to `0`
and leaves iso/VG group fields empty.

> **Note**: if a `.uishow` file already exists in the destination, it will
> **not** be overwritten. This lets you customise the file once and keep your
> changes across repeated conversions.

## Development

If you want to contribute to this project, you can create a Python **virtual environment** ("venv") with the package in **editable** mode:

```bash
python3 -mvenv venv
venv/bin/python3 -mpip install -e .
```

This will link the package to the original location, so any changes to the code will reflect directly in your environment ([source](https://stackoverflow.com/a/35064498)).

If you want to run the tests:

```bash
venv/bin/python3 -mpip install pytest
venv/bin/python3 -mpytest test
```

## Other useful stuff

The [`default-init.yml`](ui24rsc/default-init.yml) file was built by exporting the `* Init *` snapshot (from the `Default` show of the Soundcraft Ui24R), which should contain the mixer factory default settings, and then executing the following command:

```bash
python3 -mui24rsc tree,sort default-init.json default-init.yml
```

If you want to check that the two files are equivalent, you can install [`jq`](https://stedolan.github.io/jq/) on your PC and then run:

```bash
diff <(jq --sort-keys < default-init.json) <(python3 -mui24rsc dots default-init.yml | jq --sort-keys)
```

In general, if you want to see the differences between two snapshot files in different formats, you can use the following command:

```bash
diff <(jq --sort-keys < snapshot01.json) <(python3 -mui24rsc dots,full snapshot01.yml | jq --sort-keys)
```
