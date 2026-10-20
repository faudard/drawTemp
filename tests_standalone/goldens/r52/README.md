# R52.B3 candidate visual golden references

No pre-approved PNG images are checked in. Run `python scripts/r52_visual_goldens.py capture --output r52-visual-report` under Qt 6.8.3 software to produce 36 real Qt screenshots. Inspect those captures manually, then use `approve --capture ... --reviewer "Name"` in a separate review PR. Until the reviewed OS/Qt-specific baseline is committed, visual certification remains **blocked**. Software offscreen screenshots do not certify physical GPU/CPU budgets.
