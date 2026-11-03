"""Duty rules (model spec section 10).

For now this module holds the rule that step 4 asks before it books a
session. Step 6 (giving every room its teachers) will be added here.

The rule for a teacher's own paper (2026-11-03, Krish):

  Every teacher who teaches a paper (PhD scholars are exempt) needs one
  room in that paper's slot that they are allowed to invigilate:

    1. first choice: a room WITH their paper and none of their own students;
    2. if there is no such room: a room in the same slot WITHOUT their paper
       and with none of their own students, so they are nearby if the
       question paper has a mistake (the 2026-10-22 team rule, widened).

  "Their own students" are the students of every section they teach, for
  any paper written in that room (teaching.csv: teacher, code, section).
"""

PHD = "PHD"


def build_teaching(data, papers):
    """{teacher_id: set of (paper_id, section_id)} from teaching.csv.
    `papers` is schedule.build_papers(data), used to turn a course code
    into its paper ID."""
    paper_of_code = {code: paper.paper_id
                     for paper in papers.values()
                     for code in paper.course_codes}
    teaching = {}
    for row in data["teaching"]:
        pair = (paper_of_code[row["course_code"]], row["section_id"])
        teaching.setdefault(row["teacher_id"], set()).add(pair)
    return teaching


def section_of_student(data):
    """{student_id: section_id}."""
    return {student["student_id"]: student["section_id"]
            for student in data["students"]}


def room_contents(plan, section_of):
    """The (paper_id, section_id) pairs seated in one room (a RoomPlan)."""
    return {(cell[0], section_of[cell[1]])
            for row in plan.grid for cell in row if cell}


def paper_duty_rooms(paper_id, teaches, plans, section_of):
    """The rooms a teacher may take for their paper `paper_id`, as a list of
    room IDs: rule 1 if any room meets it, otherwise rule 2 (may be empty).
    `teaches` is that teacher's set of (paper_id, section_id); `plans` are
    the RoomPlans of the paper's slot."""
    with_paper = []
    without_paper = []
    for plan in plans:
        contents = room_contents(plan, section_of)
        if contents & teaches:
            continue                      # never with their own students
        if paper_id in plan.papers:
            with_paper.append(plan.room_id)
        else:
            without_paper.append(plan.room_id)
    return with_paper if with_paper else without_paper


def teachers_without_room(papers, plans, teaching, rank_of, section_of):
    """Check one slot. `papers` are the papers written in it and `plans`
    its RoomPlans. Returns a sorted list of (teacher_id, paper_id) for every
    teacher (not a PhD scholar) who has no room they may take for that
    paper. An empty list means the rule holds."""
    in_slot = {paper.paper_id for paper in papers}
    missing = []
    for teacher_id in sorted(teaching):
        if rank_of.get(teacher_id) == PHD:
            continue
        teaches = teaching[teacher_id]
        for paper_id in sorted({pair[0] for pair in teaches} & in_slot):
            if not paper_duty_rooms(paper_id, teaches, plans, section_of):
                missing.append((teacher_id, paper_id))
    return missing
