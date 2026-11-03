"""The one error the planner raises when no plan is possible (model spec
section 12). It lives in its own file because both schedule.py and seat.py
raise it, and schedule.py also uses seat.py (step 4 asks step 5 whether a
session can really be seated)."""


class NoPlan(Exception):
    """Raised when no plan is possible. str(error) is the reason."""
