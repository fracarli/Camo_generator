# Candidate background review

This folder contains unapproved Wikimedia Commons candidates. They are not part
of the official evaluation corpus yet.

Open [review.html](./review.html) in a browser. For every image, choose:

- **Keep**: real, relevant photograph suitable for the environment;
- **Reject**: painting, screenshot, duplicate, irrelevant scene, or poor image;
- **Uncertain**: needs a second look.

Use **Export review decisions** to download `candidate_decisions.json`. After
the review, the accepted images can be promoted into
`evaluation/backgrounds/` and added to the official manifest.

The source pages and reported licenses are stored in
[sources.json](./sources.json). The downloader filters obvious artwork terms,
but human review is still required before publication.
