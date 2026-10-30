# LOG

LOG is a local, file-based project memory system for AI-assisted work. Project files record purpose, current status, and lasting knowledge so work can continue across conversations and assistants.

This repository contains the app source, automated tests, specifications, and build documentation. Local project data, saved conversations, access settings, credentials, and the original workspace's Git history are excluded.

## Run locally

Python 3 and Git are required. No third-party Python packages are needed.

```sh
cd log-app
python3 server.py --root /path/to/your/project-folder
```

Open http://127.0.0.1:8765. Keep the app on loopback: its web interface has no sign-in and is designed for one user on the local computer.

See [the app README](log-app/README.md) for usage, credential storage, the optional connected-AI service, and current limits. Original specification documents are included at the repository root.

## Tests

```sh
cd log-app
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s . -p 'test_*.py'
```
