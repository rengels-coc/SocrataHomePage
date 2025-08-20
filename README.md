# Socrata Home Page snapshots

This repository hosts saved snapshots (MHTML) of an Open Data portal and a minimal static site to publish them via GitHub Pages.

## GitHub Pages

This repo contains a workflow (`.github/workflows/pages.yml`) that publishes the current branch to GitHub Pages on every push to `main`.

Steps to enable (one-time):

1. Push the changes to GitHub (see commands below).
2. In the repository Settings → Pages:
   - Source: GitHub Actions
   - Save. The first run will produce a URL like `https://<owner>.github.io/<repo>/`.

## Local editing

- Edit `index.html` to update the page content.
- Place additional snapshots in the repo and link them from `index.html`.

## Optional CLI

```bash
# Commit and push these changes
git add .
git commit -m "Set up GitHub Pages: index.html, workflow, .nojekyll"
git push origin main
```
