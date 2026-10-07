# Publishing the dashboard with a public link (Render)

1. Create a free account at https://github.com and a new repository
   (e.g. `olive-harvester`).
2. Upload the whole project folder to it (do NOT upload `venv`). On the
   repository page: Add file -> Upload files -> drag the folder contents -> Commit.
3. Create a free account at https://render.com (sign in with GitHub).
4. New -> Web Service -> pick your `olive-harvester` repository.
   Render reads `render.yaml`, so the settings are filled in for you:
   - Build command:  pip install -r requirements.txt
   - Start command:  gunicorn run:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT
5. (Recommended) Under Environment, add OLIVE_PASSWORD = a password of your
   choice. Anyone opening the link must then enter it (username: anything).
6. Click Create / Deploy. After a few minutes Render shows your public link,
   e.g. https://olive-harvester.onrender.com

Notes
- All visitors share ONE dashboard (one machine state).
- Free hosting sleeps when idle (first load is slow) and may forget history
  and captured images after a restart.
- Do not expose the real Raspberry Pi motor controls to the open internet
  without authentication.
