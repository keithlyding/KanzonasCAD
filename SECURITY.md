# Security policy

KanzonasCAD opens drawings from anywhere (DXF and DWG files, pictures, projects shared by other
people). If you find a way a file can make it run code, write files elsewhere, contact a server,
or lose or expose your work, please report it privately so it can be fixed before it's public.

## How to report

Use GitHub's private reporting: open this repository's **Security** tab and click
**Report a vulnerability**. Only the maintainer can see the report.

Please include:

- the KanzonasCAD version (Help > About) and your Windows or Linux version;
- what you did, what you expected, and what happened;
- if possible, a small test file that shows the problem. **Never send a client's real
  drawing**: make a sample that shows the problem.

Please don't open a public issue for security problems.

## What to expect

KanzonasCAD is maintained by one person in their spare time. You can expect an acknowledgement
within about a week, and a fix as a new release as soon as practical. You'll be credited in the
changelog unless you'd rather not be.

## Supported versions

Only the newest release gets fixes. The app tells you when a newer one is out
(Help > Check for updates).

## Examples of security problems

- Opening a crafted DXF, DWG or project file makes the app run code, write files outside where
  you saved, or contact a server.
- An update installs something other than the release it shows.
- A project saved or exported without content the app shows, or with content you deleted.
