# CFB27 Alpha data policy

Operation Pancake Alpha uses **CFB27 game terminology** as its canonical terminology and **CFB.FAN** as its canonical external CUT card-data source.

For card identity, displayed OVR, program, archetype, position terminology, and observed card ratings, retain the CFB.FAN/CFB27 representation when available. In particular, defensive labels such as `SAM`, `MIKE`, `WILL`, `LEDG`, and `REDG` are not translated into Madden/NFL-style `LOLB`, `MLB`, `ROLB`, `LE`, or `RE` labels.

Secondary-source or secondary-interface terminology is provenance. A position-label difference alone does not invalidate an otherwise matching CFB.FAN card or rating vector. Other identity disagreements (player, OVR, program, archetype) and rating disagreements remain blocking until investigated.

This is an Alpha engineering convention, not a claim that CFB.FAN is infallible. Original source labels and conflict evidence should be preserved so a later release can revisit normalization without losing evidence.

Historical Madden terminology is allowed in formula archaeology only when explicitly identified as historical; it must not overwrite CFB27-native labels in canonical or Alpha research data.
