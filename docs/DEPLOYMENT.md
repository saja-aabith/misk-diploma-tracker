# MISK Diploma Tracker, Deployment Guide

This guide is for running the MISK Diploma Tracker on the school server. It
covers what you need, how to set up the backend and the frontend, and the
checks to run before it goes live.

The tracker is a whole school tool (Grades 4 to 12). It runs on the school
network only. There is no public internet access and no access from home.

Note on scope: the version being deployed now covers Grades 7 to 12. Grades 4
to 6 will be added in a later update, as a code update and restart, not a fresh
deployment.

Once setup is complete, use SERVER_TEST.md to confirm the system works.

---

## 1. Overview

The system has two parts:

* **Backend**: a Python (FastAPI) API. Stores data in a single SQLite file and
  saves uploaded evidence files to a folder on school controlled storage.
* **Frontend**: a React app (Create React App). It is built into a set of
  static files that any web server (for example nginx) can serve.

Students and staff use the frontend in a browser. The frontend talks to the
backend over the school network.

---

## 2. What you need on the server

* **Python 3** (please match the version used in development; see Section 9 to
  confirm the exact version before setup).
* **Node.js and npm** (used once, to build the frontend; not needed to run it).
* A folder on the 1 TB school storage for uploaded evidence files. This path
  is set in the backend through the `UPLOAD_DIR` setting (Section 4).
* A web server such as nginx to serve the built frontend and to pass API
  requests to the backend.

The backend is a light workload. It does not need a powerful machine.

---

## 3. Folder layout

```
backend/    FastAPI app, database setup, API routes
frontend/   React app (build this into static files)
```

Inside `backend/` the key files are `app.py` (the API entry point),
`database.py` (schema and seed data), and `utils.py` (login and file rules).

---

## 4. Backend settings (environment variables)

The backend reads these from the environment. Set them on the server before
starting it. Do not commit real values into the code.

* **`SECRET_KEY`** (required). The key used to sign login tokens. **Set a long,
  random value on the server.** If it is not set, the app falls back to a known
  development key and prints a warning. That fallback is not safe for real use,
  so a proper value must be set here.
* **`UPLOAD_DIR`** (required for real use). The folder where uploaded evidence
  files are saved. Point this at the folder on the 1 TB school storage. Files
  must stay on school controlled storage. Default if unset: `./uploads`.
* **`MAX_FILE_SIZE_MB`** (optional). The largest allowed upload size in MB.
  Default: `50`.
* **`ADMIN_INITIAL_PASSWORD`** (required to create the first admin). On the
  first start, if this is set and no admin account exists yet, the app creates
  one admin account with username `adminmdt@miskschools.edu.sa` and this
  password. If it is not set, no admin is created and a notice is printed; set
  it and restart to create the admin. It is only used to create the first
  admin; it is not read again after that.
* **`CORS_ALLOW_ORIGINS`** (only if the frontend is served from a different
  address than the API). A comma-separated list of the web addresses the
  frontend is served from. Default if unset: `http://localhost:3000`. If the
  frontend and API share one address behind a reverse proxy (the recommended
  setup), this does not need to be set. Do not set it to `*`.

Set these in the way your server normally manages service settings (for
example a systemd unit `Environment=` line, or an environment file that is not
shared in the codebase).

---

## 5. Backend setup and run

From inside the `backend/` folder:

```
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set the environment variables from Section 4
#    (SECRET_KEY, UPLOAD_DIR, ADMIN_INITIAL_PASSWORD, and MAX_FILE_SIZE_MB /
#     CORS_ALLOW_ORIGINS if needed)

# 4. Create the database (schema and demo data)
#    This is safe to run more than once. It only creates what is missing.
python -c "from database import init_database; init_database()"

# 5. Start the API
uvicorn app:app --host 0.0.0.0 --port 8000
```

Notes:

* In development the app is started with `uvicorn app:app --reload`. On the
  server, **do not use `--reload`**. It is for development only.
* The database is created automatically the first time the backend starts.
  `app.py` runs `init_database()` (in `database.py`) on startup. All of its
  steps are additive and idempotent, so starting again does not delete or
  overwrite existing data. Step 4 above runs the same setup explicitly, which
  is useful if you want to create the database before the first start; it is
  harmless to run even though startup also runs it.
* For a real deployment you will want the API to start on boot and restart if
  it stops. Please wrap it in the server's normal service manager (for example
  systemd) and run it under a limited, non admin account.
* The first admin account is created on first start from
  `ADMIN_INITIAL_PASSWORD` (Section 4). Set that variable before the first
  start, or no admin will exist. The admin login is then
  `adminmdt@miskschools.edu.sa` with that password.

---

## 6. Frontend build and serve

The frontend needs to know the address of the backend. This is set **at build
time** through `REACT_APP_API_BASE_URL`. Create React App reads this value when
you build, not when it runs, so it must be set before `npm run build`.

Two common choices:

* **Same address, behind a reverse proxy** (recommended). Serve the frontend
  and the API under one address, with the web server passing `/api` requests to
  the backend on port 8000. Then build with:

  ```
  REACT_APP_API_BASE_URL=/api/v1
  ```

* **Separate address or port.** Point the frontend straight at the backend:

  ```
  REACT_APP_API_BASE_URL=http://<server-address>:8000/api/v1
  ```

Build steps, from inside the `frontend/` folder:

```
# 1. Install dependencies
npm ci

# 2. Build, with the API address set for this build
REACT_APP_API_BASE_URL=/api/v1 npm run build
```

This produces a `build/` folder of static files. Serve that folder with nginx
(or your preferred web server). Point the same web server's `/api` path at the
backend so the two parts share one address.

If you instead choose to serve the frontend on a different address from the
API, set `CORS_ALLOW_ORIGINS` (Section 4) to the frontend's address so the
backend accepts its requests.

---

## 7. Storage and data protection

* Uploaded evidence files are saved to the `UPLOAD_DIR` folder. This must be a
  school controlled location on the 1 TB storage. Files must not be moved to
  any outside service.
* Files are served only through an authenticated route. A student can read
  only their own files; a teacher can read any file; a request with no login is
  refused. Direct, unauthenticated links to files do not work by design.
* The login passwords stored by the app are hashed (bcrypt). The database file
  and the uploads folder should sit on encrypted disk with strict file
  permissions, and should be included in the encrypted, school controlled
  backups.

---

## 8. First run check

After the backend is running and the frontend is served:

1. Open the frontend address in a browser on the school network.
2. Log in with one of the seeded demo accounts (these are created by
   `database.py`; confirm the exact username and password with the developer
   before testing). The demo accounts and the demo password are for testing
   only and must be reviewed before real students use the system.
3. As a student, open an objective and upload a small PDF or image. Confirm it
   uploads and can be viewed again.
4. As a teacher, confirm the uploaded item appears for review.

If uploads fail, the most common causes are a missing or unwritable
`UPLOAD_DIR`, or the frontend pointing at the wrong API address (Section 6).

For the full step by step acceptance test (login, upload, review, admin account
creation, and what a pass looks like), see SERVER_TEST.md.

---

## 9. To confirm with the developer before setup

A few values depend on the development machine or on choices made during
hosting. Please confirm these before or during setup:

* **Exact Python version** used in development (run `python --version` in the
  development virtual environment).
* **How the frontend is served** (same address behind a proxy, or a separate
  address). If separate, set `CORS_ALLOW_ORIGINS` (Section 4) and the matching
  `REACT_APP_API_BASE_URL` (Section 6) to the frontend's address.

---

## 10. Before go live (security and handover)

* A real `SECRET_KEY` is set on the server (Section 4), not the development
  fallback.
* A proper `ADMIN_INITIAL_PASSWORD` was used to create the admin account, and
  the demo accounts and demo password are reviewed or removed before real
  students use the system.
* `UPLOAD_DIR` points at the school storage folder, and that folder is
  writable by the service account.
* The database file and uploads folder are on encrypted disk and are included
  in backups.
* The system is reachable on the school network only, with no public internet
  access.
* A security review and sign off has been completed, given the sensitivity of
  the data.
