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

## Branded small pages

Use `templates/page.html` and `page.css` for new standalone credit, milestone or
information pages. They follow the README/guide identity: **LAN42 BETA**, “Good
company. A few good commands.”, navy `#13293c`, mint `#a8e6cf`, pale background
`#eef3f7`, system fonts and rounded cards. Use Christopher Nah / hnah for current
public attribution. Keep historical names inside clearly labelled archives.

`alpha-tester.html` is an authored **content fragment**, not a standalone server
page. In `build.py`, call `branded_page(title, description, fragment)` and write
its output under the desired public filename. The renderer escapes metadata and
inlines the shared CSS; content fragments are trusted repository HTML, never
untrusted user input. Keep fragments semantic: one h1, labelled sections, visible
link text, accessible status messages, responsive cards and a usable no-script
fallback. Reuse `.hero`, `.eyebrow`, `.cards`, `.card`, `.label`, `.button`, `.muted`
and `.note` rather than copying page styles.

The original offline command guide remains self-contained; the README is still
the source for handbook content. Do not add a second manually maintained copy of
either. Build and preview the generated page, then run `test_website.py`. Avoid
new trackers, remote fonts or decorative dependencies. Darren’s page preserves
the existing GitHub account-ID lookup and last-known-profile fallback.

## Roadmap pages: Markdown is the source

`docs/roadmap.md` generates `roadmap.html`; `docs/frontend-milestone.md` generates
`frontend-milestone.html`. Both use the shared branded page shell, a generated
contents list and responsive document layout. Relative links between these plans
become local HTML links; other documentation links lead to their GitHub source.
Edit the Markdown, not generated `_site` files or a second HTML copy. Every main
push rebuilds both automatically. Keep statuses, collaborator-sized tasks and
known limitations current when plans change or features ship. Add further
published plan documents to `DOCUMENT_PAGES` in `build.py` and the output/link
checks in `test_website.py`.
