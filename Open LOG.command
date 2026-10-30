#!/bin/zsh
APP='/Users/loghlenrickard/Desktop/LOG/log-app/server.py'
if /usr/bin/curl -fsS http://127.0.0.1:8765/api/projects >/dev/null 2>&1; then
  /usr/bin/open http://127.0.0.1:8765
  exit 0
fi
/usr/bin/python3 "$APP" --connection --public-url https://log.aisteer.org &
LOG_PID=$!
trap 'kill "$LOG_PID" 2>/dev/null' EXIT INT TERM
for n in {1..30}; do
  if /usr/bin/curl -fsS http://127.0.0.1:8765/api/projects >/dev/null 2>&1; then
    /usr/bin/open http://127.0.0.1:8765
    break
  fi
  /bin/sleep 0.2
done
printf 'LOG is running locally. Keep this window open; press Control-C to stop.\n'
wait "$LOG_PID"
