# Identifier and filename rules

Apply these rules before creating manifests, samples, cards, filenames, Word documents, ZIPs, or delivery links. Treat identifiers as strings; never let CSV or spreadsheet parsing discard leading zeroes.

## Required audit fields

Retain these values for every action:

- Source row number.
- Raw identifier exactly as received.
- Exact English and Chinese action text.
- Normalized identifier used downstream.
- Any automatic change or batch-level decision applied.

When blocking, list the raw and normalized identifiers, action title, and source row. Do not silently discard, merge, overwrite, or reorder actions.

## Normalization order

Normalize identifiers in this order:

1. Convert full-width ASCII letters, digits, punctuation, and spaces to their half-width ASCII equivalents. For example, convert `Ａ－０１` to `A-01`.
2. Convert em dash `—`, en dash `–`, and mathematical minus `−` to the ASCII hyphen `-`.
3. Remove all leading spaces.
4. Remove all leading periods.
5. Remove all trailing periods and spaces. Repeat until neither remains. For example, convert `A01...   ` to `A01`.
6. Run the unsafe-name checks below.
7. Auto-assign identifiers that are empty after normalization.
8. Re-run every exact, numeric-equivalence, letter-case, type, reserved-name, and filename-safety check on the complete normalized set.

Propagate the final normalized identifier to the filename, manifest/CSV, visible PNG card number, Word ordering, and package range. Word may hide the printed identifier by its recorded visibility policy, but this never removes or changes the identifier used for ordering and audit. Never keep different identifier forms on different audit surfaces.

## Unsafe names that block

Pause the batch when a normalized identifier contains `/` or `\`, or any of `: * ? " < > |`. Do not automatically replace, delete, or preserve these characters in a filename. Report every affected action and wait for the user to specify the replacement. After replacement, restart normalization and all conflict checks.

Also pause for Windows reserved device names, case-insensitively:

- `CON`, `PRN`, `AUX`, or `NUL`.
- `COM1` through `COM9`.
- `LPT1` through `LPT9`.

Treat a reserved name followed by any extension as reserved. Check the portion before the first period, so `CON.txt`, `LPT1.card`, and names with additional periods all block. Do not create related files until the user supplies a rename.

These pauses remain required because automatic rewriting could change identifier meaning or cause data loss. For other low-risk naming details, choose a safe, consistent default without asking. Ask only when the choice can change action meaning, lose data, or has no reliable safe default.

## Empty identifiers and automatic numbering

If normalization leaves an empty identifier, assign one automatically in original source-list order:

1. Start at `001`.
2. Keep at least three digits: use `001` through `999`, then continue naturally with `1000`, `1001`, and so on without a fixed upper bound.
3. Skip a candidate already used as an exact normalized identifier.
4. Skip a candidate numerically equal to an existing pure-digit identifier. For example, existing `1` occupies candidate `001`; retain the existing identifier's original text.
5. Continue to the next available candidate. Never overwrite or merge an existing action.

After assigning all empty identifiers, run the complete validation set again.

## Leading-numeric alphanumeric overlap

For an existing alphanumeric identifier that begins with a continuous digit run, compare that leading run numerically with an automatic pure-digit candidate. Leading zeroes do not prevent a match: existing `001A` or `1A` overlaps candidate `001`.

On the first such overlap in a batch:

- Pause all remaining automatic numbering.
- Report the candidate, every overlapping identifier, action title, and source row.
- Show two clickable choices: treat the alphanumeric prefixes as occupied, or allow pure-digit candidates to coexist.
- Apply the user's choice to every same-kind overlap in the current batch only; do not make it a permanent default.
- Re-run occupancy and conflict checks before continuing.

Only inspect a continuous digit run anchored at the start of the normalized identifier. Do not scan numbers in the middle or at the end. Existing `A001`, `A-001`, or `X001Y` does not overlap candidate `001` under this rule.

## Conflict checks

Block rather than overwrite or merge when normalization creates:

- An exact duplicate normalized identifier.
- Two pure-digit identifiers with equal numeric value, such as `1` and `001`.
- A case-only collision or other letter-case ambiguity that makes identifiers equivalent on a case-insensitive filesystem.
- An identifier that fails the batch's declared identifier type or format.
- A filename collision after all filename-safe transformations.

Report every member of each conflict group with its raw identifier, normalized identifier, action title, and source row. Apply the user's resolution consistently to filenames, CSV, visible PNG card numbers, Word order, and package names, then rerun the full pipeline of checks before generating anything.
