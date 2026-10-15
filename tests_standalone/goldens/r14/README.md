# DrawTemp R14.5 reviewed visual goldens

No approved PNG has been invented or pre-approved here. The R14.5 capture
matrix creates twelve real candidate images per OS: Studio and Player,
1x/2x device pixel ratio and zoom 0.75/1.0/1.5.

Download and review the complete GitHub Actions r14-5-* artifacts before
approving. References are specific to OS, Qt version and renderer:

    linux-qt6.8.3-software/
    windows-qt6.8.3-software/
    darwin-qt6.8.3-software/

The approve subcommand of scripts/r14_visual_goldens.py requires a complete
capture and a named human reviewer. It writes real screenshots and their
SHA-256 manifest. Commit these files in a separately reviewed PR.

Normal CI never approves its own screenshot, and strict comparison blocks on
a missing or tampered reference. An all-green software renderer check is not
a certification of real hardware rendering or the R14.12 release gate.
