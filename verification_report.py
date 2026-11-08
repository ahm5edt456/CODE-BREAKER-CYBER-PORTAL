"""Atomic verification reports; never follow an existing report-file symlink."""
import datetime
import json
import os
from pathlib import Path
import tempfile


def write_report(root, report):
    root = Path(root).resolve()
    payload = dict(report)
    payload.setdefault('checked_at_utc', datetime.datetime.now(datetime.timezone.utc).isoformat())
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', prefix='.verification-',
                                         suffix='.json', dir=root, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        # Replace the directory entry itself, including a pre-existing symlink.
        os.replace(temporary, root/'local-verification.json')
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
