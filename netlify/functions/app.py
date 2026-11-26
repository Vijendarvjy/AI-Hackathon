import os
import sys


def _find_project_root():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..")),  # repo layout: netlify/functions/app.py
        here,  # bundled alongside app.py
        os.getcwd(),
    ]
    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "app.py")):
            return candidate
    return candidates[0]


ROOT_DIR = _find_project_root()
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.chdir(ROOT_DIR)

import serverless_wsgi  # type: ignore[import-not-found]

from app import app as flask_app


def handler(event, context):
    # Netlify Functions/Lambda can provide a base64-encoded body.
    return serverless_wsgi.handle_request(flask_app, event, context)
