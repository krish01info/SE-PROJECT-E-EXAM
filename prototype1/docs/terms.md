# What the words in the plan mean

This page explains the words the exam planner uses on the screen, in `basis.txt` and in the plan files. Every plan folder has a copy of it, named `terms.md`.

The examples use small, made-up numbers. Your own plan has its own numbers.

---

## The plan folder

**Plan folder.** The folder the tool writes for one run, named by the date and time of the run (for example `output/2026-11-10_16-30-00`). An older plan is never overwritten.

**`schedule.csv`** (the date sheet). One row for each paper: its date, its session and how many students write it.

**`daywise_seating_plans/`.** One file for each room in use in each session, at `<date>/<session>/<room>.csv`. The file is a picture of the room: row 1 is the front row, column 1 is on the left, as the invigilator at the front sees it. A seat shows `PAPER:STUDENT` (for example `CSE3001:BT3ECOM0038`), and an empty seat is blank.

**`duties.csv`.** One row for each teacher in each room in each session: who invigilates where.

**`basis.txt`.** Two lines saying on what basis the timetable and the seating were made. The words in those lines are explained below.

**`why.txt`.** Written instead of a plan when no plan is possible. It says which rule could not be met. Then the folder holds only this file, never half a plan.

---

## Dates and sessions

**Exam day.** A day inside the exam window, on an exam weekday (Monday to Friday by default), and not a holiday.

**Session.** One sitting on an exam day, for example the morning or the evening.

**Slot.** One session on one day, for example "2 Nov morning".

**Paper.** One question paper. Course codes that write the same question paper together count as one paper.

**Gap rule.** A student's two papers are at least 2 days apart (the number is set in `settings.yaml`). So nobody writes two papers on one day or on two days in a row. Friday and then Monday is fine.

**Fullest session.** The slot with the most students. The screen shows how many seats it still has free, because a small change in student numbers could make it too full.

---

## How the timetable is made

The words in the "Timetable basis" line.

**Biggest papers first.** The tool places the papers with the most students first, while the sessions are still empty, and the smaller papers fill the gaps later.

**Fewest rooms (the session where a paper adds the fewest rooms).** Before it places a paper, the tool asks for each possible session: "if this paper goes here, how many more rooms will this session need?" It puts the paper in the session where that number is smallest.

The number changes from session to session because the rooms are of different sizes. If the big rooms of a session are already in use, a paper there has to use small rooms, so it needs more of them.

Example: a paper has 21 students.

| Session | Rooms still free | Rooms this paper adds |
|---|---|---|
| 2 Nov morning | only small rooms (S) | 2 (12 + 9 students) |
| 3 Nov morning | a big room (M) | 1 |

The paper goes to 3 Nov morning. Why it matters: every room needs invigilators, so fewer rooms means fewer duties, and teachers have more time to check answer copies and do their other work.

**Tie.** Two or more sessions add the same number of rooms, so "fewest rooms" alone cannot choose. A second rule, the tie-break, chooses.

**On a tie, the session with fewer students.** The tie-break the tool tries first. Of the sessions that tie, it takes the one with fewer students already in it, so fewer people come to the exam at the same time.

Example: a paper adds 1 room in both of these.

| Session | Students already there |
|---|---|
| 4 Nov morning | 300 |
| 13 Nov morning | 75 |

The paper goes to 13 Nov morning.

**On a tie, the earlier day.** The second tie-break. Of the sessions that tie, it takes the one with the earliest date. In the example above, the paper would go to 4 Nov morning.

**"Tried first, but could not place every paper."** The tool has three ways of choosing sessions and tries them in this order:

1. fewest rooms, on a tie the session with fewer students;
2. fewest rooms, on a tie the earlier day;
3. the earliest day (see below).

Sometimes a way leaves a paper with no day it can go on, usually because of the gap rule. Then the tool does not give up: it starts again with the next way. The "Timetable basis" line says which way made the timetable, and "Tried first..." names the ways that did not work. The plan follows every rule whichever way made it.

**Each paper goes on the earliest day it fits (the emptier session of that day).** The third, last way. Each paper takes the first exam day where it fits, and of that day's sessions, the one with fewer students. This finishes the exams soonest, but it often needs more rooms.

---

## How the seating is made

The words in the "Seating basis" line.

**S room and M room.** The two room sizes. An S room has 6 rows of 3 seats (18 seats). An M room has 7 rows of 6 seats (42 seats).

**Column rule.** Two students writing the same paper never sit side by side. Directly in front or behind is fine.

**One paper per room.** A room holds one paper where possible. Because of the column rule, that paper uses every other column (columns 1, 3, 5) and the columns in between stay empty. So with one paper, an S room seats 12 and an M room seats 21.

**Roll order.** The students of a paper sit in order of their student ID: down column 1 from the front, then down the next column, room after room.

**The mix of room sizes that needs the fewest rooms.** Before seating a session, the tool tries the combinations of S and M rooms and takes the one with the fewest rooms, then the fewest empty seats. Example: 45 students get 1 M room and 2 S rooms (21 + 12 + 12, no empty seat), not 2 M rooms and 1 S room (54 seats, 9 empty).

**Leftover.** A paper's last students, the ones in its last room when that room is not full. Example: a paper with 34 students fills one M room (21) and has 13 left over in a second room.

**Two papers' leftovers joined.** When two papers each end with a part-empty room, their leftovers share one room, and the other room is not needed. One paper sits in columns 1, 3, 5 and the other in columns 2, 4, 6, so the column rule still holds. The tool joins the pair that fills a room best first. Full rooms are never touched, and a room never holds three papers.

Example: paper A has 13 students left over and paper B has 10. Both go into one M room (23 of 42 seats), and one room with its invigilators is saved.

**Mixed where the rooms ran out.** If a session has more students than its rooms can seat with one paper per room, leftovers are put two to a room, in the same way, until everyone has a seat. If even that is not enough, there is no plan, and `why.txt` says so.

---

## Invigilation duties

**Invigilator.** A teacher who watches a room during the exam. Each room in use needs the number set in `settings.yaml` (2 by default).

**Duty.** One teacher in one room in one session.

**Own-paper duty (the duty room rule).** A teacher who teaches a paper invigilates in the same session, so they can answer questions about the paper. They never sit in a room with their own students. If no such room exists, the tool tries another session for the paper.

**PhD scholars.** They get a duty only when no other teacher is free, because invigilation is not their main work.

**Both shifts on one day.** A teacher with a duty in the morning and in the evening of the same day. The tool tries to avoid this, so teachers have time for copy checking and other work, and the screen shows how often it still happens.
