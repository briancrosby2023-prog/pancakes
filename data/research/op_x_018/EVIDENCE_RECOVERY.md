# OP-X-018 WR evidence recovery and pre-blind freeze

The repository did not contain an executable WR coefficient vector. Its canonical source registry did, however, preserve `SRC-M19-001`, which led to the still-public Madden 19 guide, its image, and its linked workbook. The guide credits Teutonic with extracting the weights from Madden 19 XML.

The workbook's `Data Version` rows 75–78 contain exact WR vectors for Deep Threat, Possession, Red Zone, and Slot. Their source totals are 99, 100, 101, and 100. `WR-M19-ARCH-001 v1.0` preserves the integers and divides by the actual included-weight total; it does not force totals to 100 and does not fit a displayed-OVR calibration.

## Pre-blind terminology inventory

- CFB25 (1,305): Deep Threat 495, Route Runner 419, Physical 377, Slot 14.
- CFB26 (1,158): Speedster 561, Elusive Route Runner 313, Route Artist 133, Contested Specialist 102, Physical Route Runner 31, Gritty Possession 9, Gadget Receiver 8, Legacy Receiver 1.
- CFB27 repository evidence is structural/partial and does not establish an exact population-scale WR coefficient vector or prove cross-generation name equivalence.

Exact-name mappings are `PROVEN`. Clear role continuities are `SUPPORTED`. Semantic mappings without direct identity evidence are `HYPOTHESIS`. The one-off Legacy Receiver is `UNSUPPORTED` and excluded. These grades were recorded before blind scoring.

## Recovered artifacts

- Guide: https://forums.operationsports.com/forums/forum/football/madden-nfl-football/862218-guide-weightings-towards-the-ovr-for-each-attribute-at-every-position-archetype
- Source image: https://i.imgur.com/iLPIamw.jpg
- Source workbook: https://drive.google.com/file/d/1C5J9Qo6-EF__YtKqdzbL3csgNP_fgapc/view
- Workbook SHA-256: `6ceeee58a2fe358422476262d6cefaba48c0ec2503d4aa5a9d71ba406c016aa5`
- Image SHA-256: `fea8891288bf668ad8e35db2c4d7b49f35fcdefdbaff49b862f06a0ae6a1273c`

Freeze state: repository HEAD `44dbd9f7bcca87f62ad654f5dec124cbeaaba745`, timestamp `2026-08-19T23:52:17.0990680-07:00`, blind outcomes observed: **false**.
