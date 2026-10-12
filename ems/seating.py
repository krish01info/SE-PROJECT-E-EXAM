"""M5 — Seating Engine (C5, MoSCoW R5).

For every slot:
  1. The scheduling engine has already put each paper on side A or side B.
  2. Rooms open in flat priority order (Plan §9.1); only the rooms the
     invigilator pool can staff are used.
  3. Each side's papers (largest first, so few papers are split across rooms)
     are laid down in roll order, stripe by stripe, room by room.

Because every paper sits on one side only, and no two seats on the same side
of a room are adjacent, no two neighbours can ever write the same paper.
``verify.py`` re-checks this independently on the finished plan.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .feasibility import Diagnosis, Finding, SlotCapacity
from .geometry import RoomLayout, Seat
from .mapping import PaperMap
from .model import Dataset, Slot
from .scheduling import ScheduleResult


@dataclass(frozen=True)
class SeatAssignment:
    slot: Slot
    room_id: str
    seat: Seat
    student_id: str
    paper_id: str
    section_id: str


@dataclass
class SeatingResult:
    ok: bool
    seats: list[SeatAssignment] = field(default_factory=list)
    rooms_open: dict[str, list[str]] = field(default_factory=dict)  # slot key -> rooms
    slots: dict[str, Slot] = field(default_factory=dict)
    diagnosis: Diagnosis | None = None

    def by_room(self) -> dict[tuple[str, str], list[SeatAssignment]]:
        out: dict[tuple[str, str], list[SeatAssignment]] = defaultdict(list)
        for a in self.seats:
            out[(a.slot.key, a.room_id)].append(a)
        return out


def allocate_seating(ds: Dataset, pm: PaperMap, sched: ScheduleResult, cap: SlotCapacity) -> SeatingResult:
    res = SeatingResult(True)
    by_slot: dict[str, list[str]] = defaultdict(list)
    for p, s in sched.slot_of.items():
        by_slot[s.key].append(p)
        res.slots[s.key] = s
    layouts: list[RoomLayout] = cap.layouts
    problems = []

    for key in sorted(by_slot, key=lambda k: res.slots[k]):
        slot = res.slots[key]
        papers = by_slot[key]
        sides = {
            "A": sorted([p for p in papers if sched.side_of[p] == "A"], key=lambda p: (-pm.size(p), p)),
            "B": sorted([p for p in papers if sched.side_of[p] == "B"], key=lambda p: (-pm.size(p), p)),
        }
        used_rooms = set()
        for side, plist in sides.items():
            seq = [(lay.room.room_id, seat) for lay in layouts
                   for seat in (lay.side_a if side == "A" else lay.side_b)]
            need = sum(pm.size(p) for p in plist)
            if need > len(seq):
                problems.append(Finding("blocking", "side-capacity",
                                        f"{slot.label}: side {side} needs {need} seats for {', '.join(plist)} "
                                        f"but the usable rooms offer {len(seq)}", plist))
                continue
            i = 0
            for p in plist:
                for sid in pm.paper_students[p]:
                    room_id, seat = seq[i]
                    i += 1
                    used_rooms.add(room_id)
                    res.seats.append(SeatAssignment(slot, room_id, seat, sid, p, ds.students[sid].section_id))
        res.rooms_open[key] = [l.room.room_id for l in layouts if l.room.room_id in used_rooms]

    if problems:
        res.ok = False
        res.diagnosis = Diagnosis("seating", "Some slots cannot seat their papers with neighbours separated.",
                                  problems)
    return res
