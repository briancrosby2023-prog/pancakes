"""First-run setup and review-only roster screenshot staging.

Screenshots are deliberately stored as user evidence only. This module performs no OCR,
computer vision, card matching, or automatic extraction; UNKNOWN remains UNKNOWN until
an explicit reviewed canonical assignment is submitted.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SetupState:
    completed: bool = False


class SetupStore:
    def __init__(self, path: Path): self.path=path
    def load(self) -> SetupState:
        if not self.path.exists(): return SetupState()
        data=json.loads(self.path.read_text(encoding="utf-8")); return SetupState(bool(data.get("completed",False)))
    def complete(self) -> SetupState:
        self.path.parent.mkdir(parents=True,exist_ok=True); state=SetupState(True)
        self.path.write_text(json.dumps({"version":1,**asdict(state)},indent=2)+"\n",encoding="utf-8"); return state


@dataclass(frozen=True)
class ScreenshotStage:
    id: str
    filename: str
    status: str = "AWAITING REVIEW"
    extraction_status: str = "NOT AVAILABLE"


class ScreenshotStageStore:
    def __init__(self,path:Path): self.path=path
    def load(self)->list[ScreenshotStage]:
        if not self.path.exists(): return []
        data=json.loads(self.path.read_text(encoding="utf-8")); return [ScreenshotStage(**x) for x in data.get("screenshots",[])]
    def save(self,rows:list[ScreenshotStage])->None:
        self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(json.dumps({"version":1,"screenshots":[asdict(x) for x in rows]},indent=2)+"\n",encoding="utf-8")
    def stage(self,filenames:list[str])->list[ScreenshotStage]:
        rows=self.load(); used={x.id for x in rows}; added=[]
        for raw in filenames:
            name=Path(raw).name.strip()
            if not name: continue
            n=1
            while f"shot-{n}" in used: n+=1
            row=ScreenshotStage(f"shot-{n}",name); rows.append(row); added.append(row); used.add(row.id)
        self.save(rows); return added
