# Task Finish and Worktree Integration Guide

> **Purpose**: Make task completion reproducible when work is performed in an auxiliary
> worktree and later integrated into the main worktree.

## Completion Definition

A task is complete only when the implementation, verification, ownership, and integration
state are all clear. A successful commit in an auxiliary worktree is not by itself a
completed task.

## Required Closing Sequence

### 1. Classify the Current Worktree

Before changing branches or moving files, record:

- the absolute path of the current worktree;
- the current branch or detached commit;
- the current `git status --short` output;
- whether the main worktree has unrelated or uncommitted changes.

Do not assume that the worktree visible in the terminal is the main worktree.

### 2. Establish Commit Ownership

Every change must have an explicit owner:

- commit it in the auxiliary worktree with a Conventional Commit message; or
- identify it as an intentional uncommitted change that must be transferred; or
- stop and ask when ownership is unclear.

Do not silently include another agent's or another window's uncommitted files in a commit.

### 3. Integrate into the Main Worktree

When the task is meant to land in the main worktree:

1. Inspect the main worktree status before integration.
2. Merge or cherry-pick the owned commit into the main branch, preserving unrelated
   changes.
3. Resolve conflicts deliberately and verify the resulting diff, not just the merge
   command's exit code.
4. Re-run the task's risk-matched checks from the main worktree.

If the main worktree is dirty in overlapping paths, do not stash, reset, or overwrite it
without explicit authorization. Isolate the task or request direction.

### 4. Verify the Final State

The final handoff must include evidence for:

- the commit hash or the exact list of intentionally uncommitted files;
- the branch and worktree containing the final change;
- verification commands and their results;
- any known baseline failures that are unrelated to the task;
- whether the auxiliary worktree is safe to remove.

The main worktree must be checked explicitly. “Tests passed in the auxiliary worktree” is
not sufficient evidence that the main worktree contains the tested code.

### 5. Remove the Auxiliary Worktree

Remove an auxiliary worktree only after its owned changes are committed or intentionally
transferred, and after `git worktree list` confirms the target path. If a process still
holds a file handle, report the exact leftover path and lock rather than deleting a broad
directory or claiming removal succeeded.

After removal, run `git worktree prune` when stale registration is possible and verify that
the main worktree remains intact.

## Closing Checklist

- [ ] Current and main worktree paths were distinguished.
- [ ] All changed files have explicit ownership.
- [ ] The owned change is committed or intentionally left uncommitted.
- [ ] The commit is integrated into the intended main branch.
- [ ] Main-worktree status and diff were inspected after integration.
- [ ] Risk-matched tests or checks were run from the final worktree.
- [ ] Baseline failures are listed separately from regressions.
- [ ] Worktree removal was performed only after integration and ownership checks.
- [ ] Any OS-level lock or cleanup limitation is reported precisely.

## Common Incorrect Completion Claims

### Incorrect

> “The auxiliary worktree has a commit, so the task is done.”

The main branch may not contain that commit, and the tested files may disappear when the
auxiliary worktree is removed.

### Correct

> “Commit `<hash>` is present on `<branch>` in the main worktree; the final checks passed;
> the auxiliary worktree is integrated and removable.”

This statement ties completion to an inspectable repository state rather than to a local
terminal history.
