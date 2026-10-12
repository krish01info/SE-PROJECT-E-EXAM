"""Room geometry: seats, adjacency, stripes and the two room sides.

A room is ``bench_cols`` columns of benches, ``rows`` benches deep, each bench
seating 1 (a 2-wide bench) or 2 (a 3-wide bench) students. That gives a grid
of ``bench_cols * seats_per_bench`` seat-columns.

Adjacency (configurable — Plan open question 1, resolved by MoSCoW R5):
  * side by side on the same bench — always adjacent;
  * side by side across an aisle — ``across_aisle_adjacent``;
  * directly in front / behind — ``front_back_adjacent``.

Stripes (Plan §4.3): a set of seats that must all hold the same paper.
  * front/back adjacency ON  -> each seat-column splits into two interleaved
    half-depth stripes (odd rows, even rows);
  * front/back adjacency OFF -> each seat-column is one full-depth stripe.
This one rule reproduces every case in the plan: a 2-wide bench yields the
"sem 1, sem 3, sem 1" alternation, a 3-wide bench yields left/right stripes,
and mixed rows need no special case.

Two stripes are adjacent if any of their seats are. The stripe graph of a grid
is bipartite, so every room splits into two **sides** (A and B) with no
adjacency inside a side. The seating engine places each paper of a slot on
exactly one side, which guarantees the anti-copying rule by construction, and
it is also exactly why "no paper may take more than about half the seats" is
the scheduling feasibility condition.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from functools import lru_cache

from .model import Room


@dataclass(frozen=True)
class Seat:
    row: int  # 0 = front
    col: int  # seat-column, 0 = leftmost

    @property
    def label(self) -> str:
        return f"R{self.row + 1:02d}-{_col_letter(self.col)}"


def _col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, rem = divmod(i - 1, 26)
        s = chr(65 + rem) + s
    return s


@dataclass(frozen=True)
class RoomLayout:
    room: Room
    seats: tuple[Seat, ...]
    neighbours: dict  # Seat -> frozenset[Seat]
    stripes: tuple[tuple[Seat, ...], ...]  # each stripe front-to-back
    side_a: tuple[Seat, ...]  # fill order: stripe by stripe, roll order
    side_b: tuple[Seat, ...]

    @property
    def seat_cols(self) -> int:
        return self.room.bench_cols * self.room.seats_per_bench


def build_layout(room: Room, front_back: bool, across_aisle: bool) -> RoomLayout:
    return _build_layout(room, front_back, across_aisle)


@lru_cache(maxsize=None)
def _build_layout(room: Room, front_back: bool, across_aisle: bool) -> RoomLayout:
    spb = room.seats_per_bench
    ncols = room.bench_cols * spb
    seats = [Seat(r, c) for r in range(room.rows) for c in range(ncols)]
    nb: dict[Seat, set[Seat]] = {s: set() for s in seats}

    def link(a: Seat, b: Seat):
        nb[a].add(b)
        nb[b].add(a)

    for r in range(room.rows):
        for c in range(ncols - 1):
            same_bench = c // spb == (c + 1) // spb
            if same_bench or across_aisle:
                link(Seat(r, c), Seat(r, c + 1))
    if front_back:
        for r in range(room.rows - 1):
            for c in range(ncols):
                link(Seat(r, c), Seat(r + 1, c))

    # Stripes
    def stripe_key(s: Seat):
        return (s.col, s.row % 2) if front_back else (s.col, 0)

    groups: dict[tuple, list[Seat]] = {}
    for s in seats:
        groups.setdefault(stripe_key(s), []).append(s)
    keys = sorted(groups)
    stripes = {k: tuple(sorted(groups[k], key=lambda s: s.row)) for k in keys}
    owner = {s: k for k, ss in stripes.items() for s in ss}

    # Sanity: seats inside a stripe are never adjacent.
    for k, ss in stripes.items():
        for s in ss:
            if any(owner[n] == k for n in nb[s]):
                raise ValueError(f"room {room.room_id}: stripe {k} contains adjacent seats")

    sadj: dict[tuple, set[tuple]] = {k: set() for k in keys}
    for s in seats:
        for n in nb[s]:
            if owner[n] != owner[s]:
                sadj[owner[s]].add(owner[n])

    # Two-colour the stripe graph.
    colour: dict[tuple, int] = {}
    isolated = []
    for k in keys:
        if k in colour:
            continue
        if not sadj[k]:
            isolated.append(k)
            continue
        colour[k] = 0
        q = deque([k])
        while q:
            u = q.popleft()
            for v in sadj[u]:
                if v not in colour:
                    colour[v] = 1 - colour[u]
                    q.append(v)
                elif colour[v] == colour[u]:
                    raise ValueError(f"room {room.room_id}: stripe graph is not bipartite")
    # Isolated stripes touch nothing, so they may join either side: balance.
    for k in isolated:
        a = sum(len(stripes[x]) for x in colour if colour[x] == 0)
        b = sum(len(stripes[x]) for x in colour if colour[x] == 1)
        colour[k] = 1 if b < a else 0

    side0 = [s for k in keys if colour[k] == 0 for s in stripes[k]]
    side1 = [s for k in keys if colour[k] == 1 for s in stripes[k]]
    if len(side1) > len(side0):
        side0, side1 = side1, side0

    return RoomLayout(
        room=room,
        seats=tuple(seats),
        neighbours={s: frozenset(v) for s, v in nb.items()},
        stripes=tuple(stripes[k] for k in keys),
        side_a=tuple(side0),
        side_b=tuple(side1),
    )


def layouts_for(rooms, seating_cfg: dict) -> list[RoomLayout]:
    return [
        build_layout(r, bool(seating_cfg["front_back_adjacent"]), bool(seating_cfg["across_aisle_adjacent"]))
        for r in rooms
    ]
