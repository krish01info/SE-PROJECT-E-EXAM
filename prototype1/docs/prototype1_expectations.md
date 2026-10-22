# Prototype 1: what Ishan expects

This file is written for an AI assistant to read and then explain to a teammate. Teammates can also read it directly.

---

## 1. How prototype1 behaves

It is a command-line tool. You run one command and give it one folder.

**The input folder holds the exam data:**

- CSV files: sections and their students, courses, who writes which course, rooms, teachers, and who teaches what
- `settings.yaml`: the exam dates, the two sessions and the gap rule
- `constraints.yaml`: rules written by hand, e.g. "these two course codes are the same paper"

**It creates a new folder, named by the time it ran, containing:**

- `schedule.csv`: the date sheet
- `duties.csv`: which teacher supervises which room, and when
- `daywise_seating_plans/<date>/<session>/<room>.csv`: one CSV per room per session that looks like the room. Each CSV row is a row of seats, and blank cells are empty seats.

**The plan follows these rules:**

- A student never has two exams on the same day or on consecutive days. A weekend counts as a gap, so Friday then Monday is fine.
- There are two sessions a day.
- The same paper is never in neighbouring seat columns. The same paper in front or behind is fine.
- A room holds one paper unless the rooms run out.
- Each room gets two invigilators.
- A teacher never supervises their own class.
- A teacher does supervise their own paper at least once. PhD scholars are exempt from this.

If no plan is possible, it gives the reason in a few lines instead.

That's all. No website, no reports, no menus.

## 2. Why it is kept so small

- **The engine comes first.** Scheduling, seating and staffing must work, and be understood, before anything is added. Each later feature is one increment on top of something that already works.
- **Everyone must be able to explain it.** The grade is on the design and on explaining it. At lab evals, any teammate can be asked how the scheduler or the seating works. Small, plain code makes that possible.
- **Fewer features mean fewer deviations.** Every extra feature is another place where the code can drift from what was agreed. A small scope stays checkable.
- **It has already gone wrong once.** `archive/ai_reference_work/` was generated in one go: the whole system, about 3,700 lines, built on a solver library. Nobody on the team could explain it. It doesn't follow the seating rule settled later, and breaks it in almost every room. It also blocks Friday-then-Monday exams. Its headline numbers came from made-up data. It looked finished, but it wasn't.
- **The effort belongs in the data.** A tool is only as good as the data it is tested on. Thinking time saved on features goes into designing a dataset that is actually hard.
- **Nothing is fixed forever.** Any decision can change, with a proper reason written down. Changes that haven't been thought through are not wanted.

## 3. What Ishan wants from the data

- It is made up, never real.
- It looks like what the exam cell actually faces, small but tight:
  - one big program (BTech) dominates
  - papers are shared between years under different codes
  - there are only just enough rooms and teachers
  - the exam window is short and includes a weekend
- Every feature of the data is there to test something specific.
- The team chooses the numbers, each with a reason written in `data_design_spec.md`.
- There is also a tiny dataset small enough to solve by hand, and impossible datasets that must fail with the right reason.

## 4. Instructions for the AI

When a teammate starts (step 0 in `prototype1_model_spec.md` §14), asks what prototype1 is, or takes up the rundown offered at the start of a conversation (`repo_instructions.md` §1), explain this file before any code.

1. **Start with one sentence:** "Ishan wants a simple command-line tool. You give it an input folder with the exam data, and it gives you back an output folder with the exam plan. That's it."
2. **Then the data, in one or two sentences:** "He wants the data to be made up but realistic, with one big program, papers shared between years under different codes, and only just enough rooms and teachers, so that it actually tests the tool. Designing it is the team's job."
3. **Then the rules (§1) and the reasons (§2).** One idea at a time, in plain words. Explain terms like CSV, YAML or command line if the user seems unsure.
4. **Match the user.** For a non-technical teammate, use the picture: a date sheet, a seating chart per room and a duty list. For a technical one, go into the spec.
5. **Mention the archived attempt as a fact.** It is the reason for the approach. Don't blame anyone.
6. **Be accurate about the labels.**
   - **Decided** items are agreed.
   - **Default** items are starting choices that the team can change with a reason.
   - **Open** items are for the team to decide.
   - Never present a Default or Open item as fixed, or a Decided item as optional.
7. **Say that anything can change with a proper reason.** Point to how: `prototype1_model_spec.md` §16.
8. **Confirm, don't test.** Recap in three short lines:
   - what goes in and what comes out
   - one scheduling rule and one seating rule
   - what should make the data hard

   Ask whether that matches how they see it, and clear up anything they question.
9. **Don't write code during the explanation.** When they're happy with it, point them to step 1 in `prototype1_model_spec.md` §14.
