# Newsletter project

Notes for any agent working in this folder.

- Subscriber exports go in `data/`. Never commit real subscriber data.
- Email drafts go in `drafts/` as Markdown.
- Session state lives in `docs/state/`: `docs/state/NOW.md` is the current state (overwrite it), and `docs/state/LOG.md` is the history (append one line per session, format `YYYY-MM-DD | who | summary`).
