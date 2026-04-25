# History Preservation Strategy

Niche is currently built in the local project workspace to preserve clean, app-specific history from the first commit.

## Policy

1. Keep monorepo references read-only.
2. Build, test, and commit only in this standalone repository.
3. Use topic branches and merge commits to preserve feature progression.
4. Never rewrite shared monorepo history to extract this app.

## Publish steps

1. Initialize `git` in the project root.
2. Commit baseline scaffold.
3. Commit each feature set as separate logical commits.
4. Add personal GitHub remote.
5. Push branch and open PR/review flow.