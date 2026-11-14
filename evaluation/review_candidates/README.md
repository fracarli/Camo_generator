# Candidate background review

This folder contains unapproved Wikimedia Commons candidates. They are not part
of the official evaluation corpus yet.

From the repository root, download a local candidate set and build its review page:

```bash
terrainweave data download --output evaluation/review_candidates/backgrounds
terrainweave data review
```

Open [review.html](review.html) in a browser. For every image, choose:

- **Keep**: real, relevant photograph suitable for the environment;
- **Reject**: painting, screenshot, duplicate, irrelevant scene, or poor image;
- **Uncertain**: needs a second look.

Use **Export review decisions** to download `candidate_decisions.json`. Save the exported file here, replacing [candidate_decisions.json](candidate_decisions.json).
Run `terrainweave data promote` from the repository root to copy accepted images into
`evaluation/backgrounds/` and update the official manifest.

The source pages and reported licenses are stored in
[sources.json](./sources.json). The downloader filters obvious artwork terms,
but human review is still required before publication.
