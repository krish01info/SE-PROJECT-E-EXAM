"""M9 — Report Generator (C10, MoSCoW R11/R14/R15/R16).

Pure formatting: no solving logic. Writes

CSV (relational, re-loadable; SRS 3.4)
  schedule.csv, seating.csv, duties.csv, student_timetables.csv,
  teacher_rosters.csv, slot_summary.csv, fairness.csv
Printable HTML (reports/)
  index.html                 — entry point with plan status
  slot_<date>_<session>.html — per room: seating chart, door list,
                               attendance sheet grouped by paper
  teacher_rosters.html       — per-teacher duty roster
  student_timetables.html    — searchable per-student timetable + seat
  summary.html               — per-slot summary, fairness evidence for the
                               HoD, utilisation, verification result
"""
from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from .geometry import Seat, layouts_for
from .model import Dataset

PALETTE = ["#cfe3ff", "#ffd9b3", "#c9f2d0", "#f7c8e0", "#fff0a8", "#d8ccff",
           "#b8efef", "#ffc9c9", "#e2f0b6", "#e6d3bf", "#cdd9e5", "#f2d0f7"]

CSS = """
:root{--ink:#1d2433;--muted:#5b6475;--line:#d5dae3;--bg:#fff;--accent:#2952cc}
*{box-sizing:border-box}body{font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);
background:var(--bg);margin:0;padding:24px 16px;max-width:1100px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:18px;margin:28px 0 8px}h3{font-size:15px;margin:18px 0 6px}
.muted{color:var(--muted)}a{color:var(--accent)}table{border-collapse:collapse;width:100%;margin:8px 0}
th,td{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}th{background:#f3f5f8}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.room{page-break-after:always;break-after:page;border-top:2px solid var(--ink);padding-top:10px;margin-top:24px}
.grid{display:grid;gap:3px;margin:8px 0}.seat{border:1px solid #9aa3b2;border-radius:3px;padding:2px 3px;
font-size:10.5px;line-height:1.2;min-height:30px;text-align:center}.seat b{display:block;font-size:10px}
.seat.empty{background:#f0f1f3;color:#aab}.aisle{width:10px}.front{text-align:center;font-size:11px;
letter-spacing:.2em;color:var(--muted);border:1px dashed var(--line);padding:2px;margin-bottom:4px}
.chip{display:inline-block;padding:1px 6px;border-radius:9px;font-size:12px;border:1px solid #9aa3b2}
.ok{color:#1a7f37;font-weight:600}.bad{color:#c62828;font-weight:600}.warn{color:#9a6700;font-weight:600}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:12px}
.card{border:1px solid var(--line);border-radius:6px;padding:10px;break-inside:avoid}
input[type=search]{font:inherit;padding:8px 10px;width:100%;max-width:360px;border:1px solid var(--line);border-radius:6px}
.sig{width:150px}
@media print{body{padding:0;max-width:none}.noprint{display:none}a{color:inherit;text-decoration:none}}
"""


def _page(title: str, body: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}</style>"
            f"</head><body>{body}</body></html>")


def _e(x) -> str:
    return html.escape(str(x))


def _w(path: Path, header, rows):
    with path.open("w", newline="") as fh:
        cw = csv.writer(fh)
        cw.writerow(header)
        cw.writerows(rows)


def _ranges(rolls: list[str]) -> str:
    rolls = sorted(rolls)
    return f"{rolls[0]} – {rolls[-1]}" if len(rolls) > 1 else rolls[0]


def write_csvs(out: Path, ds: Dataset, pm, cg, sched, seating, duties, cap) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    slots = {s.key: s for s in sched.slot_of.values()}
    _w(out / "schedule.csv", ["paper_id", "title", "course_codes", "date", "weekday", "session", "students", "side"],
       sorted([(p, ds.papers[p].title, " ".join(pm.paper_codes[p]), s.date.isoformat(), s.date.strftime("%a"),
                s.session, pm.size(p), sched.side_of[p]) for p, s in sched.slot_of.items()],
              key=lambda r: (r[3], ds.config.sessions.index(r[5]), r[0])))
    if seating is None:
        return {}
    _w(out / "seating.csv", ["date", "session", "room_id", "seat", "row", "col", "student_id", "section_id",
                             "paper_id"],
       [(a.slot.date.isoformat(), a.slot.session, a.room_id, a.seat.label, a.seat.row + 1, a.seat.col + 1,
         a.student_id, a.section_id, a.paper_id) for a in seating.seats])
    _w(out / "student_timetables.csv", ["student_id", "section_id", "paper_id", "title", "date", "session",
                                        "room_id", "seat"],
       sorted([(a.student_id, a.section_id, a.paper_id, ds.papers[a.paper_id].title, a.slot.date.isoformat(),
                a.slot.session, a.room_id, a.seat.label) for a in seating.seats],
              key=lambda r: (r[0], r[4], ds.config.sessions.index(r[5]))))
    by_room = seating.by_room()
    room_cap = {l.room.room_id: l.room.capacity for l in cap.layouts}
    duty_rows, roster_rows = [], []
    if duties is not None:
        for d in duties.duties:
            s = slots[d.slot_key]
            duty_rows.append((s.date.isoformat(), s.session, d.room_id, d.teacher_id, ds.teachers[d.teacher_id].rank,
                              "yes" if d.in_domain else "no"))
            papers = sorted({a.paper_id for a in by_room[(d.slot_key, d.room_id)]})
            roster_rows.append((d.teacher_id, ds.teachers[d.teacher_id].rank, s.date.isoformat(), s.session,
                                d.room_id, " ".join(papers)))
        _w(out / "duties.csv", ["date", "session", "room_id", "teacher_id", "rank", "in_domain"], duty_rows)
        _w(out / "teacher_rosters.csv", ["teacher_id", "rank", "date", "session", "room_id", "papers_in_room"],
           sorted(roster_rows))
    inv = Counter(d.slot_key for d in duties.duties) if duties else Counter()
    summary = []
    for key in sorted(seating.rooms_open, key=lambda k: slots[k]):
        s = slots[key]
        papers = sorted(p for p, ss in sched.slot_of.items() if ss.key == key)
        students = sum(pm.size(p) for p in papers)
        rooms = seating.rooms_open[key]
        seats = sum(room_cap[r] for r in rooms)
        summary.append((s.date.isoformat(), s.session, " ".join(papers), students, len(rooms), seats,
                        f"{100 * students / max(seats, 1):.0f}%", inv[key]))
    _w(out / "slot_summary.csv", ["date", "session", "papers", "students", "rooms_open", "seats_in_open_rooms",
                                  "utilisation", "invigilators"], summary)
    fairness = []
    if duties is not None:
        weights = ds.config["duties"]["rank_weights"]
        load = Counter(d.teacher_id for d in duties.duties)
        per_day = Counter((d.teacher_id, d.slot_key.split("_")[0]) for d in duties.duties)
        own = defaultdict(bool)
        for d in duties.duties:
            if {a.paper_id for a in by_room[(d.slot_key, d.room_id)]} & cg.teacher_papers.get(d.teacher_id, set()):
                own[d.teacher_id] = True
        for t in sorted(ds.teachers):
            r = ds.teachers[t].rank
            teaches = bool(cg.teacher_papers.get(t))
            own_s = ("n/a (invigilation-only)" if r in ("phd", "staff") else "n/a (no paper)" if not teaches else
                     "yes" if own[t] else f"exempt — {duties.exempt[t]}" if t in duties.exempt else "NO")
            fairness.append((t, r, ds.teachers[t].department, weights[r], load[t], f"{load[t] / weights[r]:.2f}",
                             sum(1 for (tt, _), c in per_day.items() if tt == t and c > 1), own_s))
        _w(out / "fairness.csv", ["teacher_id", "rank", "department", "rank_weight", "duties",
                                  "weighted_load", "days_with_2plus_duties", "own_paper_duty"], fairness)
    return {"summary": summary, "fairness": fairness}


# ----------------------------------------------------------------------------- HTML
def write_html(out: Path, ds: Dataset, pm, cg, sched, seating, duties, cap, ctx: dict):
    rep = out / "reports"
    rep.mkdir(parents=True, exist_ok=True)
    slots = sorted({s.key: s for s in sched.slot_of.values()}.values())
    layouts = {l.room.room_id: l for l in layouts_for(ds.rooms, ds.config["seating"])}
    by_room = seating.by_room()
    inv = defaultdict(list)
    for d in duties.duties:
        inv[(d.slot_key, d.room_id)].append(d.teacher_id)
    title = _e(ds.config.name)

    # --- per-slot room packs -------------------------------------------------
    for s in slots:
        papers = sorted((p for p, ss in sched.slot_of.items() if ss.key == s.key), key=lambda p: (-pm.size(p), p))
        colour = {p: PALETTE[i % len(PALETTE)] for i, p in enumerate(papers)}
        legend = " ".join(f"<span class='chip' style='background:{colour[p]}'>{_e(p)} — {_e(ds.papers[p].title)} "
                          f"({pm.size(p)})</span>" for p in papers)
        parts = [f"<p class='noprint'><a href='index.html'>← index</a></p><h1>{_e(s.label)}</h1>"
                 f"<p class='muted'>{title} · {len(seating.rooms_open[s.key])} room(s) · "
                 f"{sum(pm.size(p) for p in papers)} students</p><p>{legend}</p>"]
        for rid in seating.rooms_open[s.key]:
            lay = layouts[rid]
            seats = {a.seat: a for a in by_room[(s.key, rid)]}
            ncols = lay.seat_cols
            spb = lay.room.seats_per_bench
            tmpl = []
            for c in range(ncols):
                tmpl.append("minmax(64px,1fr)")
                if (c + 1) % spb == 0 and c + 1 < ncols:
                    tmpl.append("10px")
            cells = []
            for r in range(lay.room.rows):
                for c in range(ncols):
                    seat = Seat(r, c)
                    a = seats.get(seat)
                    if a:
                        cells.append(f"<div class='seat' style='background:{colour[a.paper_id]}'><b>{seat.label}</b>"
                                     f"{_e(a.student_id)}<br>{_e(a.paper_id)}</div>")
                    else:
                        cells.append(f"<div class='seat empty'><b>{seat.label}</b>—</div>")
                    if (c + 1) % spb == 0 and c + 1 < ncols:
                        cells.append("<div class='aisle'></div>")
            by_paper = defaultdict(list)
            for a in by_room[(s.key, rid)]:
                by_paper[a.paper_id].append(a)
            door = "".join(f"<tr><td>{_e(p)}</td><td>{_e(ds.papers[p].title)}</td><td>{_e(_ranges([a.student_id for a in v]))}</td>"
                           f"<td class='num'>{len(v)}</td></tr>" for p, v in sorted(by_paper.items()))
            att = []
            for p, v in sorted(by_paper.items()):
                rows = "".join(f"<tr><td>{a.seat.label}</td><td>{_e(a.student_id)}</td><td>{_e(a.section_id)}</td>"
                               f"<td class='sig'></td></tr>" for a in sorted(v, key=lambda a: a.student_id))
                att.append(f"<h3>Attendance — {_e(p)} {_e(ds.papers[p].title)} ({len(v)})</h3><table><tr><th>Seat</th>"
                           f"<th>Roll no.</th><th>Section</th><th>Signature</th></tr>{rows}</table>")
            invs = ", ".join(_e(t) for t in sorted(inv[(s.key, rid)])) or "<span class='bad'>none</span>"
            parts.append(
                f"<section class='room'><h2>Room {_e(rid)} <span class='muted'>· {_e(lay.room.building)} · "
                f"{len(seats)}/{lay.room.capacity} seated</span></h2><p>Invigilators: <b>{invs}</b></p>"
                f"<h3>Seating chart</h3><div class='front'>FRONT / BOARD</div>"
                f"<div class='grid' style='grid-template-columns:{' '.join(tmpl)}'>{''.join(cells)}</div>"
                f"<h3>Door list</h3><table><tr><th>Paper</th><th>Title</th><th>Roll numbers</th><th class='num'>Count</th></tr>"
                f"{door}</table>{''.join(att)}</section>")
        (rep / f"slot_{s.key}.html").write_text(_page(f"{s.label} — room pack", "".join(parts)))

    # --- teacher rosters -----------------------------------------------------
    by_t = defaultdict(list)
    for d in duties.duties:
        by_t[d.teacher_id].append(d)
    slot_by_key = {s.key: s for s in slots}
    cards = []
    for t in sorted(ds.teachers):
        rows = "".join(f"<tr><td>{_e(slot_by_key[d.slot_key].label)}</td><td>{_e(d.room_id)}</td><td>"
                       f"{_e(' '.join(sorted({a.paper_id for a in by_room[(d.slot_key, d.room_id)]})))}</td></tr>"
                       for d in sorted(by_t[t], key=lambda d: slot_by_key[d.slot_key]))
        cards.append(f"<div class='card' data-t='{_e(t)}'><h3>{_e(t)} <span class='muted'>· {_e(ds.teachers[t].rank)} · "
                     f"{_e(ds.teachers[t].department)}</span></h3><table><tr><th>Slot</th><th>Room</th><th>Papers</th>"
                     f"</tr>{rows or '<tr><td colspan=3 class=muted>No duties</td></tr>'}</table></div>")
    (rep / "teacher_rosters.html").write_text(_page("Duty rosters",
        f"<p class='noprint'><a href='index.html'>← index</a></p><h1>Invigilation duty rosters</h1>"
        f"<p class='muted'>{title}</p><p class='noprint'><input type='search' placeholder='Filter by teacher ID' "
        f"oninput=\"for(const c of document.querySelectorAll('.card'))c.style.display=c.dataset.t.includes(this.value.toUpperCase())?'':'none'\">"
        f"</p><div class='cards'>{''.join(cards)}</div>"))

    # --- student timetables (searchable) -------------------------------------
    tt = defaultdict(list)
    for a in seating.seats:
        tt[a.student_id].append([a.slot.date.strftime("%a %d %b"), a.slot.session, a.paper_id,
                                 ds.papers[a.paper_id].title, a.room_id, a.seat.label, a.slot.day_index,
                                 a.slot.session_index])
    for v in tt.values():
        v.sort(key=lambda r: (r[6], r[7]))
    data = json.dumps({k: [r[:6] for r in v] for k, v in sorted(tt.items())}, separators=(",", ":"))
    js = ("const D=" + data + ";function show(q){q=q.trim().toUpperCase();const o=document.getElementById('o');"
          "if(!q){o.innerHTML='';return}const ks=Object.keys(D).filter(k=>k.includes(q)).slice(0,20);"
          "o.innerHTML=ks.map(k=>'<h3>'+k+'</h3><table><tr><th>Date</th><th>Session</th><th>Paper</th><th>Title</th>"
          "<th>Room</th><th>Seat</th></tr>'+D[k].map(r=>'<tr>'+r.map(x=>'<td>'+x+'</td>').join('')+'</tr>').join('')"
          "+'</table>').join('')||'<p class=muted>No match</p>'}")
    (rep / "student_timetables.html").write_text(_page("Student timetables",
        f"<p class='noprint'><a href='index.html'>← index</a></p><h1>Personal exam timetables</h1>"
        f"<p class='muted'>{title} · {len(tt)} students · full table in student_timetables.csv</p>"
        f"<input type='search' autofocus placeholder='Roll number, e.g. {next(iter(sorted(tt)), '')}' "
        f"oninput='show(this.value)'><div id='o'></div><script>{js}</script>"))

    # --- summary for exam cell + HoD -----------------------------------------
    summ = ctx["tables"]["summary"]
    srows = "".join(f"<tr><td>{_e(r[0])}</td><td>{_e(r[1])}</td><td>{_e(r[2])}</td><td class='num'>{r[3]}</td>"
                    f"<td class='num'>{r[4]}</td><td class='num'>{r[5]}</td><td class='num'>{r[6]}</td>"
                    f"<td class='num'>{r[7]}</td></tr>" for r in summ)
    fair = ctx["tables"]["fairness"]
    frows = "".join(f"<tr><td>{_e(r[0])}</td><td>{_e(r[1])}</td><td>{_e(r[2])}</td><td class='num'>{r[3]}</td>"
                    f"<td class='num'>{r[4]}</td><td class='num'>{r[5]}</td><td class='num'>{r[6]}</td>"
                    f"<td class='{'bad' if r[7] == 'NO' else ''}'>{_e(r[7])}</td></tr>" for r in fair)
    by_rank = defaultdict(list)
    for r in fair:
        by_rank[r[1]].append(r[4])
    rank_rows = "".join(f"<tr><td>{_e(k)}</td><td class='num'>{len(v)}</td><td class='num'>{min(v)}</td>"
                        f"<td class='num'>{max(v)}</td><td class='num'>{sum(v) / len(v):.1f}</td>"
                        f"<td class='num'>{ds.config['duties']['rank_weights'][k]}</td></tr>"
                        for k, v in sorted(by_rank.items()))
    ver = ctx["verification"]
    vrows = "".join(f"<tr><td>{_e(c['id'])}</td><td>{_e(c['rule'])}</td><td class='{'ok' if c['passed'] else 'bad'}'>"
                    f"{'PASS' if c['passed'] else 'FAIL'}</td><td>{_e(c['detail'])}</td></tr>" for c in ver["hard"])
    soft = "".join(f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>" for k, v in ver["soft"].items())
    (rep / "summary.html").write_text(_page("Plan summary",
        f"<p class='noprint'><a href='index.html'>← index</a></p><h1>Examination plan summary</h1>"
        f"<p class='muted'>{title}</p>"
        f"<h2>Hard-constraint verification</h2><p>Independent re-check of the finished plan: "
        f"<span class='{'ok' if ver['all_passed'] else 'bad'}'>{'ALL PASSED' if ver['all_passed'] else 'FAILURES'}</span></p>"
        f"<table><tr><th>#</th><th>Rule</th><th>Result</th><th>Detail</th></tr>{vrows}</table>"
        f"<h3>Soft rules and quality measures</h3><table>{soft}</table>"
        f"<h2>Per-slot summary</h2><table><tr><th>Date</th><th>Session</th><th>Papers</th><th class='num'>Students</th>"
        f"<th class='num'>Rooms</th><th class='num'>Seats</th><th class='num'>Use</th><th class='num'>Invigilators</th></tr>"
        f"{srows}</table>"
        f"<h2>Fairness evidence (HoD)</h2><table><tr><th>Rank</th><th class='num'>Teachers</th><th class='num'>Min</th>"
        f"<th class='num'>Max</th><th class='num'>Mean</th><th class='num'>Rank weight</th></tr>{rank_rows}</table>"
        f"<p class='muted'>Weighted load = duties ÷ rank weight. The solver first minimises the highest weighted load, "
        f"then narrows the gap to the lowest.</p>"
        f"<table><tr><th>Teacher</th><th>Rank</th><th>Dept</th><th class='num'>Weight</th><th class='num'>Duties</th>"
        f"<th class='num'>Weighted</th><th class='num'>Days with 2+</th><th>Own-paper duty</th></tr>{frows}</table>"))

    # --- index ---------------------------------------------------------------
    slot_links = "".join(f"<tr><td><a href='slot_{s.key}.html'>{_e(s.label)}</a></td><td>"
                         f"{_e(', '.join(sorted(p for p, ss in sched.slot_of.items() if ss.key == s.key)))}</td>"
                         f"<td class='num'>{len(seating.rooms_open[s.key])}</td></tr>" for s in slots)
    st = ctx["state"]
    stats = ctx["stats"]
    (rep / "index.html").write_text(_page("Exam plan",
        f"<h1>Examination plan</h1><p class='muted'>{title}</p>"
        f"<p>Plan state: <b>{_e(st)}</b> · verification: <span class='{'ok' if ver['all_passed'] else 'bad'}'>"
        f"{'all hard rules pass' if ver['all_passed'] else 'FAILED'}</span></p>"
        f"<table><tr><td>Papers</td><td class='num'>{stats['papers']}</td><td>Students</td><td class='num'>{stats['students']}</td>"
        f"<td>Paper-sittings</td><td class='num'>{stats['sittings']}</td></tr><tr><td>Exam days used</td>"
        f"<td class='num'>{stats['span_days']}</td><td>Slots used</td><td class='num'>{stats['slots_used']}</td>"
        f"<td>Invigilation duties</td><td class='num'>{stats['duties']}</td></tr></table>"
        f"<h2>For everyone</h2><ul><li><a href='summary.html'>Plan summary, verification and fairness evidence</a></li>"
        f"<li><a href='teacher_rosters.html'>Teacher duty rosters</a></li>"
        f"<li><a href='student_timetables.html'>Student timetable lookup</a></li></ul>"
        f"<h2>Room packs (seating chart · door list · attendance sheets)</h2><table><tr><th>Slot</th><th>Papers</th>"
        f"<th class='num'>Rooms</th></tr>{slot_links}</table>"))
