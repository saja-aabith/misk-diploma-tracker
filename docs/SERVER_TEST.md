# MISK Diploma Tracker, Server Test

This is a short checklist for the IT team to confirm the system works once it
is running on the school server, before we sign it off. It is a click through
test, not a setup guide. For setup, see DEPLOYMENT.md.

## Scope

This test covers the Grades 7 to 12 system, which is the version being deployed
now. Grades 4 to 6 will be added in a later update, so anything specific to the
lower grades is not expected to work yet and should not be treated as a fault.

## Before you start

1. The system is installed and running per DEPLOYMENT.md (backend running,
   front end served, database created on first start).
2. ADMIN_INITIAL_PASSWORD has been set in the server environment before the
   first start, so the admin account exists.
3. Use only throwaway test files and test accounts for this checklist. Do not
   upload real student work during testing. The test database can be rebuilt
   afterwards.

## Test accounts (seeded on a fresh database)

* Student: faisal2026@miskschools.edu.sa, password: password123
* Teacher: mthomas@miskschools.edu.sa, password: password123
* Admin: adminmdt@miskschools.edu.sa, password: the value you set in
  ADMIN_INITIAL_PASSWORD

The demo student and teacher accounts and the demo password are for testing
only. They must be reviewed and changed before real students use the system.

## The checklist

Work through these in order. Each step lists what you should see if it is
working.

1. Open the site address in a browser on the school network.
   Expect: the login page loads, with no certificate warning.

2. Log in as the demo student.
   Expect: you reach the student dashboard.

3. As the student, open an objective and upload a small test PDF or image.
   Expect: the upload succeeds and the file shows against the objective.

4. Try to upload a video file (for example a small .mp4).
   Expect: it is refused. Video is not an allowed file type.

5. Log out, then log in as the demo teacher.
   Expect: you reach the teacher dashboard and the review queue shows items,
   including the file the student just uploaded.

6. Open a submission and record a review.
   Expect: the review saves and the submission status updates.

7. As the teacher, download a student report.
   Expect: a PDF report downloads.

8. Log out, then log in as the admin.
   Expect: you reach the admin console.

9. As the admin, create a test student account (any first name, a grade, and a
   password of at least 8 characters).
   Expect: the account is created and the generated login username is shown
   on screen, for example faisal4821@miskschools.edu.sa.

10. Log out, then log in as that new test student.
    Expect: you reach the student dashboard.

11. Log back in as the admin and reset the test student's password.
    Expect: the reset succeeds. Logging in as the test student with the new
    password works.

If all of the above pass, the system is working on the server.

## If a step fails

* The page does not load, or the front end cannot reach the backend: the API
  address is likely wrong. Check REACT_APP_API_BASE_URL (set at build time)
  and, if the front end is served from a different address, CORS_ALLOW_ORIGINS.
* A certificate warning appears: the trusted certificate has not been pushed to
  the device. This is an MDM/Jamf task.
* Upload fails: the uploads folder is likely missing or not writable. Check
  UPLOAD_DIR and its permissions.
* Admin login fails: ADMIN_INITIAL_PASSWORD was probably not set before the
  first start, so no admin was created. Set it and restart.

## After the test

* Remove the test file and the test student account, or rebuild the database,
  so no test data carries into real use.
* Confirm a real SECRET_KEY and a proper admin password are set for real use,
  not the development defaults.
* Confirm the system is reachable on the school network only.