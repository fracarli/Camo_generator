# Public bilingual human test

This server presents the randomized recognition test in English or Italian.
It stores responses locally in `output/human_test/web_responses.csv` and can
also send them to Supabase through environment variables.

Run it from the repository root after generating scenes:

```bash
python human_test_web/server.py --host 0.0.0.0 --port 8502
```

Open `http://localhost:8502`. For public participation deploy it behind HTTPS
on a host such as Render or a small VPS. The QR code should point to that
public HTTPS URL.

For Supabase, create the table using `supabase_schema.sql`, then set
`SUPABASE_URL` and `SUPABASE_ANON_KEY`. Local CSV storage remains a fallback
if the cloud request fails. The app intentionally does not collect names,
email addresses, or IP addresses.

## Publish on Render

The repository includes `render.yaml`. In Render, choose **New > Blueprint**,
connect the GitHub repository, and deploy the blueprint. Set the two Supabase
environment variables in the Render service before inviting participants.
Render then provides an HTTPS URL such as:

```text
https://terrainweave-human-test.onrender.com
```

Create a QR code from that URL with:

```bash
python scripts/create_human_test_qr.py https://your-render-url.onrender.com
```

The online filesystem is temporary, so Supabase is required for reliable
long-term storage in the public deployment. Never put a Supabase service-role
key in the repository or in browser code; use only the restricted anonymous
key and the insert policy in `supabase_schema.sql`.
