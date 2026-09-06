"""Deterministic starter/OVR/backup subregions for the accepted EA Team Manager geometry."""
from __future__ import annotations

from operation_pancake.team_import import SlotRegion


def _r(slot, cx, y1, y2, width=.095, backup_depth=.105):
    left, right = cx - width / 2, cx + width / 2
    container_bottom = min(.965, y2 + backup_depth)
    # Real acceptance fixtures place the starter name to the left of the OVR
    # inside each card.  Keep the bands slightly overlapping so split OCR glyphs
    # at the boundary are not lost, while semantic parsing remains independent.
    name_box = (left, y1, cx + .025, y2)
    ovr_box = (cx + .012, y1, right, y2)
    backup_top = y2 + .004
    backup_bottom = container_bottom
    step = (backup_bottom - backup_top) / 3 if backup_bottom > backup_top else 0
    backup_boxes = tuple(
        (left, backup_top + i * step, right, backup_top + (i + 1) * step)
        for i in range(3)
        if step > 0
    )
    return SlotRegion(slot, (left, y1, right, container_bottom), name_box, ovr_box, backup_boxes)


REAL_TEAM_MANAGER_SLOT_REGIONS = {
    "OFFENSE": [
        _r("LT1", .320, .405, .449), _r("LG1", .431, .405, .449),
        _r("C1", .544, .405, .449), _r("RG1", .656, .405, .449),
        _r("RT1", .768, .405, .449), _r("TE1", .880, .405, .449),
        _r("WR1", .320, .704, .752), _r("WR3", .431, .704, .752),
        _r("HB1", .544, .704, .752), _r("QB1", .656, .704, .752),
        _r("FB1", .768, .704, .752), _r("WR2", .880, .704, .752),
    ],
    "DEFENSE": [
        _r("FS1", .315, .426, .466), _r("WILL1", .418, .426, .466),
        _r("MIKE1", .522, .426, .466), _r("MIKE2", .625, .426, .466),
        _r("SAM1", .728, .426, .466), _r("SS1", .832, .426, .466),
        _r("CB1", .270, .690, .735), _r("CB3", .371, .690, .735),
        _r("REDG1", .472, .690, .735), _r("DT1", .573, .690, .735),
        _r("DT2", .674, .690, .735), _r("LEDG1", .775, .690, .735),
        _r("CB2", .876, .690, .735),
    ],
    "SPECIAL TEAMS": [
        _r("P1", .378, .435, .476), _r("K1", .468, .435, .476),
        _r("KR1", .700, .435, .476), _r("PR1", .802, .435, .476),
        _r("LS1", .378, .675, .716), _r("KOS1", .468, .675, .716),
    ],
    "SPECIALISTS": [
        _r("3DRB1", .365, .455, .505), _r("PWHB1", .468, .455, .505),
        _r("SLWR1", .570, .455, .505), _r("GAD1", .673, .455, .505),
        _r("NT1", .776, .455, .505), _r("SUBLB1", .365, .704, .755),
        _r("RRE1", .468, .704, .755), _r("RDT1", .570, .704, .755),
        _r("RLE1", .673, .704, .755), _r("SLCB1", .776, .704, .755),
    ],
}
