# Decisions

Everything the team has decided, in order. Details and reasons are in the specs.

## Phase 0 design discussion (August 2026)

- The system does three jobs: schedule exams, seat students, and assign invigilators.
- Fixed vocabulary: program, cohort, section, paper, course code, slot, duty.
- One paper can have several course codes. All codes of one paper are written in the same slot.
- Clashes come from registrations: two papers clash if any student takes both.
- A student gets at least one clear day between exams.
- Two students writing the same paper must not sit next to each other.
- Students are seated in roll-number order.
- Two invigilators per room.
- A teacher invigilates their own paper at least once, but never their own class. PhD scholars are exempt from the first part.
- Duty load is shared fairly.
- Two room types. S rooms seat 18 (one seat per bench). M rooms seat 42 (two seats per bench).
- Data is stored as CSV files: one per section, plus tables for courses, registrations, teachers, teaching and rooms. IDs only, no names.
- Out of scope: buildings, teacher preferences, special-needs seating, repeat students.
- Method: start with dummy data, solve small pieces, then scale up.
- Seat "stripes" and a cap of about four papers per room were proposed. Both were replaced in October.

## Prototype 1 scope (October 2026)

- Build prototype1 first: a small command-line tool the whole team can explain. Features come in later prototypes.
- In: a folder of CSV files plus `settings.yaml` and `constraints.yaml`. Out: a new folder named by the time it ran.
- It outputs a date sheet, a seating picture for each room in each session, and a duty list.
- If no plan is possible, it says why in a few lines.
- The clash graph is used inside the tool but is not an output.
- Gap rule: at least one clear day between a student's exams. Weekends count as gap days, so Friday then Monday is allowed.
- Two sessions per day.
- Seating rule: the same paper is never in two neighbouring seat columns. The neighbouring column must be empty or hold a different paper. The same paper directly in front or behind is fine.
- One paper per room where possible. Papers are mixed only when rooms run out.
- Teachers are assigned in prototype1.
- Rooms stay simple S/M. No buildings.
- Not in prototype1: repeat students and multidisciplinary courses. Papers shared across batches are in.
- Course codes that are the same paper are listed by hand in `constraints.yaml`.
- Data quality: IDs and input checks only.
- Designing the dataset is the team's job, and the hard part. It has to reflect the problems the exam cell actually faces.
- The exam cell's current practice is not copied. Their spreadsheet is never committed.
- The AI-built full system is archived, not built on.
- Any plan can change, but only with a proper written reason.
