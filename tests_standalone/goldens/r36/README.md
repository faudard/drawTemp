# R36 visual goldens — intentionally unapproved

This directory **does not contain any pre-approved screenshots**.
`scripts/r36_visual_candidates.py capture --output <dir>` must first
capture **twelve real** Qt 6.8.3 software/offscreen images (R36 Studio
timeline + R26 Action Player, DPI 1/2, zoom .75/1.0/1.5).

A qualified human must review the images, then run the separate explicit
`approve` command to create a platform-specific checked manifest and
signed-off baseline. CI captures candidates **only**; it must never run
approval. Missing goldens remain blocked.

A passing software image comparison is **not** GPU hardware validation,
license approval or a complete R36 release certification.
