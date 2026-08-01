# Troop 52 Calendar Timezone Fix

Fixes the Scoutbook Plus / Internet Advancement export bug where event times are
published in raw UTC with no timezone tag, causing GoDaddy's Calendar widget to
display them incorrectly (e.g. 8:30 AM Central showing as 1:30 PM).

This repo runs a small script on a schedule (via GitHub Actions, free) that
downloads your real Scoutbook Plus `.ics` feed, converts all the UTC timestamps
into properly-tagged `America/Chicago` local times, and republishes the result
as a static file via GitHub Pages. You then point GoDaddy at that corrected URL
instead of the raw Scoutbook Plus link.

## One-time setup (about 10 minutes)

1. **Create a free GitHub account** if you don't already have one: https://github.com/signup

2. **Create a new repository**
   - Click "+" → "New repository" (top right of github.com)
   - Name it something like `troop52-calendar-fix`
   - Set it to **Public** (required for free GitHub Pages)
   - Click "Create repository"

3. **Upload these three files** to the repo (use "Add file" → "Upload files" in the GitHub web UI):
   - `fix_ics_timezone.py`
   - `.github/workflows/update-calendar.yml` (note: this must go inside a folder
     path literally named `.github/workflows/` — when uploading via the web UI,
     type that full path into the file name box and GitHub will create the folders)

4. **Add your real Scoutbook Plus .ics link as a secret** (so it's not exposed publicly in the repo):
   - Go to the repo's **Settings** tab → **Secrets and variables** → **Actions**
   - Click **New repository secret**
   - Name: `SCOUTBOOK_ICS_URL`
   - Value: paste your actual Scoutbook Plus `.ics` link
   - Save

5. **Turn on GitHub Pages**:
   - Repo **Settings** → **Pages**
   - Under "Build and deployment" → Source: **Deploy from a branch**
   - Branch: `main`, folder: `/docs`
   - Save

6. **Run it once manually** to generate the first file:
   - Go to the **Actions** tab → select "Fix Troop 52 Calendar Timezone" workflow → **Run workflow** (manual trigger button)
   - Wait ~30 seconds, then refresh — you should see a new commit adding `docs/troop52-calendar.ics`

7. **Find your corrected calendar URL**:
   - It will be: `https://<your-github-username>.github.io/<repo-name>/troop52-calendar.ics`
   - GitHub Pages usually takes a minute or two to go live after first enabling it

8. **Update GoDaddy**:
   - Go into your Calendar section on the Website + Marketing editor
   - Replace the existing Scoutbook Plus .ics URL with your new GitHub Pages URL above
   - Publish

From then on, the GitHub Action re-fetches your Scoutbook Plus feed and
refreshes the corrected file automatically every 30 minutes — no ongoing work
needed on your end. If you add/change events in Scoutbook, they'll show up on
the website with the correct time within that window.

## Notes

- If you ever need to change how often it updates, edit the `cron` line in
  `.github/workflows/update-calendar.yml` (it's in UTC time and standard cron
  syntax; every 30 min is `*/30 * * * *`, every 15 min is `*/15 * * * *`).
- All-day events (like holidays) are left untouched — they have no time
  component, so there's nothing to convert.
- The fix assumes Central Time (`America/Chicago`) and correctly handles the
  switch between CDT and CST automatically.
