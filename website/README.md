# LAN42 website

The shareable site uses the same `docs/quick-guide.html` opened by `/help`.
The concise project introduction is generated from the repository README at
`handbook.html` (the existing URL is kept). Its guide links lead to the topic
pages in `docs/` on GitHub; `docs/README.md` is their contents page. No duplicate
handbook copy is maintained. No API credentials, sessions or campus data go into the site.

Build locally:

```sh
python3 -m venv /tmp/lan42-web
/tmp/lan42-web/bin/pip install -r website/requirements.txt
/tmp/lan42-web/bin/python website/build.py
python3 -m http.server 8080 --directory _site
```

Open http://localhost:8080. Build output is ignored.

When terminal HELP changes, run `python3 website/build.py --refresh-guide` to
refresh its generated section in the offline guide. Hand-edit the guide's
curated command cards when behaviour changes; leave its generated block alone.
The Pages build also regenerates the current HELP block directly from the app's
AST without importing or starting the app. Run `test_website.py` after changes.

The Pages workflow rebuilds the site from the latest guide and README on every
main push. One-time owner setup: repository Settings → Pages → Build and
deployment → Source: **GitHub Actions**. Then rerun **Publish LAN42 guide** in
Actions (or push a new change). No token or private key needs to be added.

Expected public URL: https://CrispyNuggetD.github.io/42sg-campus-lan/
The `deploy` job reports the final live URL. Until Pages is enabled, GitHub can
build the artifact but will reject deployment; do not describe the URL as live.
