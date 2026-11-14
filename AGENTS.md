# Agent instructions

These rules apply to every change in this repository.

## One change per commit

Put each logical change in its own commit. Do not bundle unrelated edits. Leave unrelated files untouched.

A review comment, a bugfix, and a test addition are separate commits when they are separate changes. The test that shows a bugfix belongs in that bugfix commit.

## Adversarial review of every commit

Review every commit before the next change starts. The wording fixes at the end of that review stay in the same commit and are not reviewed again.

1. Send the commit to several independent adversarial review agents. Three is the minimum. They try to break the change: wrong behavior, lost coverage, a test that does not exercise the code it names, a fix that hides an error, and anything that would fail the project's lint or type checks.
2. Apply every finding that is more than a nit to that same commit. Amend the commit when it has not been published.
3. Review the updated commit again. Report what it still gets wrong, including leftover nits. Do not repeat a finding the update already fixed.
4. Repeat until every remaining finding is a nit.
5. Apply those nits to that same commit, then move on to the next change. Do not open another review round for the nits.

A nit is wording, naming, or formatting that does not change behavior and would not fail CI. Anything that can mislead a later reader about what the test guarantees is not a nit.

Reviewers report findings. They do not edit the tree. The implementing agent applies the fixes.
