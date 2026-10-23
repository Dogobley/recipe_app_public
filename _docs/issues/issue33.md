# Issue 33: Show a recorded demo of the local deployment

Status: open (not yet groomed)

## Goal

A reviewer who cannot run our self-hosted runner can see, from the repository,
that the pipeline deploys to dev automatically, promotes to production by hand,
and rolls back.

## Acceptance criteria

- [ ] The README links to a short recorded demo (video or screenshot sequence)
      stored in or linked from the repository.
- [ ] The demo shows a push to `main`, the CI tests passing, the image built and
      deployed to dev, and dev serving the new release on port `8000`.
- [ ] The demo shows **Promote dev to production** being confirmed and
      production serving the same release on port `8001`.
- [ ] The demo shows a rollback with **Deploy** and an older release tag.
- [ ] Every release tag and commit in the demo is visible and matches the
      repository history.

## Out of scope

- Hosting the application at a public URL.

## Constraints

- No secrets, tokens or passwords appear in any recording.
