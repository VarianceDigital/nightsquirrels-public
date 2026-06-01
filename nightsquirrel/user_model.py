# nightsquirrel/user_model.py
# nightsquirrel/user_model.py
"""
Flask-Login user model.

We don't use SQLAlchemy. This User object is a lightweight wrapper around the DB row
so that:
- Flask-Login can persist/restore the user
- the rest of the app can read role flags consistently (student/tutor/admin)
"""

from flask_login import UserMixin


class User(UserMixin):
    def __init__(
        self,
        usr_id: int,
        usr_email: str,
        usr_name: str = "",
        usr_confirmed: bool = False,
        usr_isvalid: bool = True,
        usr_tile: str | None = None,
        usr_is_student: bool = True,
        usr_is_tutor: bool = False,
        usr_is_admin: bool = False,
        usr_is_payer: bool = False,
        sct_id = None,
        usr_school_grade = None,
    ):
        # Flask-Login expects .id to be a str
        self.id = str(usr_id)

        # Common identity fields
        self.email = usr_email or ""
        self.name = usr_name or ""
        self.confirmed = bool(usr_confirmed)
        self.is_valid = bool(usr_isvalid)
        self.tile = usr_tile

        # Role flags
        self.usr_is_student = bool(usr_is_student)
        self.usr_is_tutor = bool(usr_is_tutor)
        self.usr_is_admin = bool(usr_is_admin)
        self.usr_is_payer = bool(usr_is_payer)

        # Extra profile-ish fields (optional but useful)
        self.sct_id = sct_id
        self.usr_school_grade = usr_school_grade

    @classmethod
    def from_db_row(cls, row: dict):
        """
        `row` is a RealDictCursor result (dict-like) coming from db_auth.py
        """
        if not row:
            return None

        return cls(
            usr_id=row.get("usr_id"),
            usr_email=row.get("usr_email"),
            usr_name=row.get("usr_name") or "",
            usr_confirmed=row.get("usr_confirmed", False),
            usr_isvalid=row.get("usr_isvalid", True),
            usr_tile=row.get("usr_tile"),
            usr_is_student=row.get("usr_is_student", True),
            usr_is_tutor=row.get("usr_is_tutor", False),
            usr_is_admin=row.get("usr_is_admin", False),
            usr_is_payer=row.get("usr_is_payer", False),
            sct_id=row.get("sct_id"),
            usr_school_grade=row.get("usr_school_grade"),
        )
