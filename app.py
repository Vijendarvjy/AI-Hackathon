import os
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (  # pyright: ignore[reportMissingImports]
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Allow overriding the SQLite path (e.g. Render persistent disk mount).
_database_override = os.environ.get("DATABASE_PATH")
if _database_override:
    DATABASE = _database_override
# Serverless environments often provide only /tmp as writable storage.
# SQLite data in /tmp is ephemeral and not shared across instances.
elif os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
    DATABASE = os.path.join("/tmp", "hackathon.db")
else:
    DATABASE = os.path.join(BASE_DIR, "instance", "hackathon.db")

# Hackathon configuration
THEME_TITLE = "Meri Samasya, Mera Samadhan (My Problem, My Solution)"
THEME_DESCRIPTION = (
    "Students solve a real problem from their own home, school, or village. "
    "Judges reward thinking about the problem over technical polish."
)

TRACKS = [
    {
        "name": "Safe and healthy communities",
        "examples": "Medicine reminder for a grandparent, clean-water checklist, first-aid game",
    },
    {
        "name": "Farming and local livelihoods",
        "examples": "Crop-price record, a small seller’s profit calculator, pest identification guide",
    },
    {
        "name": "Climate and environment",
        "examples": "Water-tank overflow alert, waste-sorting game, heat-safety awareness tool",
    },
    {
        "name": "Better learning at school",
        "examples": "Local-language maths game, attendance tracker, science model with sensors",
    },
    {
        "name": "Inclusion and girls’ safety",
        "examples": "Tool for a classmate with a disability, safe-route map, story game about rights",
    },
    {
        "name": "AI for good (optional, Class 8-9)",
        "examples": "Simple image or sound classifier, plus a discussion of where it could go wrong",
    },
]

JUDGING_PARAMETERS = [
    {
        "key": "problem_understanding",
        "label": "Problem Understanding",
        "description": "Clarity and depth of understanding of the real-life problem (Meri Samasya).",
    },
    {
        "key": "solution_relevance",
        "label": "Solution Relevance & Impact",
        "description": "How well the solution addresses the problem and benefits the community (Mera Samadhan).",
    },
    {
        "key": "creativity",
        "label": "Creativity & Innovation",
        "description": "Originality and thoughtful approach to solving the problem.",
    },
    {
        "key": "feasibility",
        "label": "Feasibility & Implementation",
        "description": "Practicality and how realistically the idea can be implemented or demonstrated.",
    },
    {
        "key": "presentation",
        "label": "Presentation & Explanation",
        "description": "Clarity of explanation, communication, and ability to discuss limitations or improvements.",
    },
]

EVALUATION_LEVELS = [
    {
        "key": "school",
        "label": "Level 1: School Round",
        "short_label": "School Round",
        "participants": "Every student, about 50 teams per school",
        "teams": "4,500",
        "students": "18,000",
        "mode": "Paper scoresheets, with a panel at each school",
    },
    {
        "key": "online_screening",
        "label": "Level 2: Online Screening",
        "short_label": "Online Screening",
        "participants": "2 teams per age group from each school",
        "teams": "360",
        "students": "1,440",
        "mode": "Short video and project form, scored online",
    },
    {
        "key": "regional_finals",
        "label": "Level 3: Regional Finals",
        "short_label": "Regional Finals",
        "participants": "30 teams per region",
        "teams": "180",
        "students": "720",
        "mode": "Live demos at 6 venues",
    },
    {
        "key": "national_finals",
        "label": "Level 4: National Finals",
        "short_label": "National Finals",
        "participants": "Top 5 teams per region",
        "teams": "30",
        "students": "120",
        "mode": "Live demos, user-feedback sprint and showcase",
    },
]
DEFAULT_EVALUATION_LEVEL = EVALUATION_LEVELS[0]["key"]
EVALUATION_LEVEL_KEYS = {level["key"] for level in EVALUATION_LEVELS}

MIN_SCORE = 1
MAX_SCORE = 10

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'judge')),
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_number TEXT UNIQUE NOT NULL,
            team_type TEXT NOT NULL CHECK(team_type IN ('solo', 'group')),
            track TEXT NOT NULL,
            problem_title TEXT NOT NULL,
            problem_description TEXT NOT NULL,
            school_name TEXT NOT NULL,
            leader_name TEXT NOT NULL,
            leader_class TEXT NOT NULL,
            leader_contact TEXT,
            leader_email TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            member_name TEXT NOT NULL,
            member_class TEXT NOT NULL,
            FOREIGN KEY(registration_id) REFERENCES registrations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            judge_id INTEGER NOT NULL,
            round TEXT NOT NULL DEFAULT 'school',
            problem_understanding INTEGER NOT NULL,
            solution_relevance INTEGER NOT NULL,
            creativity INTEGER NOT NULL,
            feasibility INTEGER NOT NULL,
            presentation INTEGER NOT NULL,
            comments TEXT,
            total_score INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(registration_id, judge_id, round),
            FOREIGN KEY(registration_id) REFERENCES registrations(id) ON DELETE CASCADE,
            FOREIGN KEY(judge_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS registration_rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registration_id INTEGER NOT NULL,
            round TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'qualified', 'not_qualified')),
            notes TEXT,
            updated_at TEXT NOT NULL,
            UNIQUE(registration_id, round),
            FOREIGN KEY(registration_id) REFERENCES registrations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """
    )

    # Migrate legacy evaluations table (without round) to round-aware schema.
    eval_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(evaluations)").fetchall()
    }
    if "round" not in eval_columns:
        db.executescript(
            """
            ALTER TABLE evaluations RENAME TO evaluations_old;
            CREATE TABLE evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER NOT NULL,
                judge_id INTEGER NOT NULL,
                round TEXT NOT NULL DEFAULT 'school',
                problem_understanding INTEGER NOT NULL,
                solution_relevance INTEGER NOT NULL,
                creativity INTEGER NOT NULL,
                feasibility INTEGER NOT NULL,
                presentation INTEGER NOT NULL,
                comments TEXT,
                total_score INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(registration_id, judge_id, round),
                FOREIGN KEY(registration_id) REFERENCES registrations(id) ON DELETE CASCADE,
                FOREIGN KEY(judge_id) REFERENCES users(id) ON DELETE CASCADE
            );
            INSERT INTO evaluations (
                id, registration_id, judge_id, round, problem_understanding, solution_relevance,
                creativity, feasibility, presentation, comments, total_score, created_at, updated_at
            )
            SELECT
                id, registration_id, judge_id, 'school', problem_understanding, solution_relevance,
                creativity, feasibility, presentation, comments, total_score, created_at, updated_at
            FROM evaluations_old;
            DROP TABLE evaluations_old;
            """
        )

    # Seed default admin and judge accounts if missing
    now = datetime.utcnow().isoformat(timespec="seconds")
    existing_admin = db.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing_admin:
        db.execute(
            "INSERT INTO users (username, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?)",
            ("admin", generate_password_hash("admin123"), "admin", "Administrator", now),
        )
    existing_judge = db.execute(
        "SELECT id FROM users WHERE username = ?", ("judge",)
    ).fetchone()
    if not existing_judge:
        db.execute(
            "INSERT INTO users (username, password_hash, role, name, created_at) VALUES (?, ?, ?, ?, ?)",
            ("judge", generate_password_hash("judge123"), "judge", "Demo Judge", now),
        )

    db.execute(
        """
        INSERT OR IGNORE INTO registration_rounds (registration_id, round, status, updated_at)
        SELECT id, ?, 'pending', ? FROM registrations
        """,
        (DEFAULT_EVALUATION_LEVEL, now),
    )
    db.commit()


REGISTRATION_DEADLINE_KEY = "registration_deadline"


def get_setting(key, default=None):
    db = get_db()
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    db = get_db()
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db.commit()


def delete_setting(key):
    db = get_db()
    db.execute("DELETE FROM settings WHERE key = ?", (key,))
    db.commit()


def get_registration_deadline():
    value = get_setting(REGISTRATION_DEADLINE_KEY)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def is_registration_open():
    deadline = get_registration_deadline()
    if deadline is None:
        return True
    return datetime.utcnow() <= deadline


def generate_registration_number():
    db = get_db()
    year = datetime.utcnow().year
    prefix = f"AIH-{year}-"
    row = db.execute(
        "SELECT registration_number FROM registrations WHERE registration_number LIKE ? ORDER BY id DESC LIMIT 1",
        (f"{prefix}%",),
    ).fetchone()
    if row:
        try:
            last_seq = int(row["registration_number"].split("-")[-1])
        except (ValueError, IndexError):
            last_seq = 0
    else:
        last_seq = 0
    return f"{prefix}{last_seq + 1:04d}"


def login_required(role=None):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                flash("Please log in to continue.", "error")
                target = "admin_login" if role == "admin" else "judge_login" if role == "judge" else "index"
                return redirect(url_for(target))
            if role and user.get("role") != role:
                flash("You do not have access to that page.", "error")
                return redirect(url_for("index"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


@app.before_request
def ensure_db():
    init_db()


@app.context_processor
def inject_globals():
    deadline = get_registration_deadline()
    return {
        "theme_title": THEME_TITLE,
        "theme_description": THEME_DESCRIPTION,
        "tracks": TRACKS,
        "judging_parameters": JUDGING_PARAMETERS,
        "current_user": session.get("user"),
        "registration_deadline": deadline,
        "registration_open": is_registration_open() if deadline is not None else True,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    registration_open = is_registration_open()
    deadline = get_registration_deadline()
    if request.method == "POST":
        if not registration_open:
            flash("Registration deadline has passed. New registrations are closed.", "error")
            return render_template("register.html", form=request.form)
        team_type = (request.form.get("team_type") or "").strip()
        track = (request.form.get("track") or "").strip()
        problem_title = (request.form.get("problem_title") or "").strip()
        problem_description = (request.form.get("problem_description") or "").strip()
        school_name = (request.form.get("school_name") or "").strip()
        leader_name = (request.form.get("leader_name") or "").strip()
        leader_class = (request.form.get("leader_class") or "").strip()
        leader_contact = (request.form.get("leader_contact") or "").strip()
        leader_email = (request.form.get("leader_email") or "").strip()

        errors = []
        if team_type not in {"solo", "group"}:
            errors.append("Please select a valid registration type (solo or group).")
        valid_track_names = {t["name"] for t in TRACKS}
        if track not in valid_track_names:
            errors.append("Please select a valid track.")
        if not problem_title:
            errors.append("Problem/solution title is required.")
        if not problem_description:
            errors.append("Problem description is required.")
        if not school_name:
            errors.append("School name is required.")
        if not leader_name:
            errors.append("Leader/student name is required.")
        if not leader_class:
            errors.append("Leader/student class is required.")

        members = []
        if team_type == "group":
            member_indices = set()
            for key in request.form.keys():
                if key.startswith("member_") and key.endswith("_name"):
                    middle = key[len("member_") : -len("_name")]
                    if middle.isdigit():
                        member_indices.add(int(middle))
            for i in sorted(member_indices):
                name = (request.form.get(f"member_{i}_name") or "").strip()
                cls = (request.form.get(f"member_{i}_class") or "").strip()
                if name or cls:
                    if not name or not cls:
                        errors.append(f"Member {i}: please provide both name and class, or leave both blank.")
                    else:
                        members.append((name, cls))
            # Group registration must include at least one additional member besides the leader.
            if len(members) < 1:
                errors.append("Group registration must include at least one additional member besides the leader.")
        else:
            members = []

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template(
                "register.html",
                form=request.form,
            )

        db = get_db()
        reg_no = generate_registration_number()
        now = datetime.utcnow().isoformat(timespec="seconds")
        cur = db.execute(
            """
            INSERT INTO registrations
            (registration_number, team_type, track, problem_title, problem_description,
             school_name, leader_name, leader_class, leader_contact, leader_email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reg_no,
                team_type,
                track,
                problem_title,
                problem_description,
                school_name,
                leader_name,
                leader_class,
                leader_contact or None,
                leader_email or None,
                now,
            ),
        )
        reg_id = cur.lastrowid
        for m_name, m_class in members:
            db.execute(
                "INSERT INTO team_members (registration_id, member_name, member_class) VALUES (?, ?, ?)",
                (reg_id, m_name, m_class),
            )
        db.execute(
            "INSERT OR IGNORE INTO registration_rounds (registration_id, round, status, updated_at) VALUES (?, ?, 'pending', ?)",
            (reg_id, DEFAULT_EVALUATION_LEVEL, now),
        )
        db.commit()
        return redirect(url_for("register_success", reg_no=reg_no))

    return render_template("register.html", form={})


@app.route("/register/success/<reg_no>")
def register_success(reg_no):
    db = get_db()
    reg = db.execute(
        "SELECT * FROM registrations WHERE registration_number = ?", (reg_no,)
    ).fetchone()
    if not reg:
        flash("Registration not found.", "error")
        return redirect(url_for("index"))
    members = db.execute(
        "SELECT member_name, member_class FROM team_members WHERE registration_id = ? ORDER BY id",
        (reg["id"],),
    ).fetchall()
    return render_template("register_success.html", registration=reg, members=members)


def authenticate(username, password, role):
    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE username = ? AND role = ?", (username, role)
    ).fetchone()
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = authenticate(username, password, "admin")
        if user:
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "name": user["name"],
            }
            flash("Welcome, admin.", "success")
            return redirect(url_for("admin_dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("login.html", role="admin")


@app.route("/judge/login", methods=["GET", "POST"])
def judge_login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = authenticate(username, password, "judge")
        if user:
            session["user"] = {
                "id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "name": user["name"],
            }
            flash(f"Welcome, {user['name']}.", "success")
            return redirect(url_for("judge_dashboard"))
        flash("Invalid judge credentials.", "error")
    return render_template("login.html", role="judge")


@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


def _registration_filters(args):
    reg_round = (args.get("reg_round") or "all").strip()
    if reg_round != "all" and reg_round not in EVALUATION_LEVEL_KEYS:
        reg_round = "all"
    track = (args.get("track") or "all").strip()
    valid_tracks = {t["name"] for t in TRACKS}
    if track != "all" and track not in valid_tracks:
        track = "all"
    team_type = (args.get("team_type") or "all").strip()
    if team_type not in {"all", "solo", "group"}:
        team_type = "all"
    q = (args.get("q") or "").strip()
    return {"reg_round": reg_round, "track": track, "team_type": team_type, "q": q}


def _query_registrations(db, filters, include_round_status=False):
    params = []
    where = []
    reg_round = filters["reg_round"]
    if reg_round == "all":
        base = "SELECT r.* FROM registrations r"
    else:
        select_extra = ", rr.status as current_round_status" if include_round_status else ""
        base = (
            f"SELECT r.*{select_extra} FROM registrations r "
            "INNER JOIN registration_rounds rr ON rr.registration_id = r.id AND rr.round = ?"
        )
        params.append(reg_round)
    if filters["track"] != "all":
        where.append("r.track = ?")
        params.append(filters["track"])
    if filters["team_type"] != "all":
        where.append("r.team_type = ?")
        params.append(filters["team_type"])
    if filters["q"]:
        like = f"%{filters['q']}%"
        where.append("(r.registration_number LIKE ? OR r.school_name LIKE ? OR r.leader_name LIKE ? OR r.problem_title LIKE ?)")
        params.extend([like, like, like, like])
    sql = base
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.created_at DESC, r.id DESC"
    return db.execute(sql, params).fetchall()


@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    db = get_db()
    selected_round = request.args.get("round", DEFAULT_EVALUATION_LEVEL)
    if selected_round not in EVALUATION_LEVEL_KEYS:
        selected_round = DEFAULT_EVALUATION_LEVEL
    reg_filters = _registration_filters(request.args)
    reg_round = reg_filters["reg_round"]
    registrations = _query_registrations(db, reg_filters, include_round_status=True)
    members_by_reg = {}
    for r in registrations:
        members_by_reg[r["id"]] = db.execute(
            "SELECT member_name, member_class FROM team_members WHERE registration_id = ? ORDER BY id",
            (r["id"],),
        ).fetchall()

    results = db.execute(
        """
        SELECT r.id, r.registration_number, r.team_type, r.track, r.problem_title,
               r.school_name, r.leader_name,
               rr.status as round_status,
               COUNT(e.id) as eval_count,
               ROUND(AVG(e.total_score), 2) as avg_total,
               ROUND(AVG(e.problem_understanding), 2) as avg_problem_understanding,
               ROUND(AVG(e.solution_relevance), 2) as avg_solution_relevance,
               ROUND(AVG(e.creativity), 2) as avg_creativity,
               ROUND(AVG(e.feasibility), 2) as avg_feasibility,
               ROUND(AVG(e.presentation), 2) as avg_presentation
        FROM registrations r
        INNER JOIN registration_rounds rr ON rr.registration_id = r.id AND rr.round = ?
        LEFT JOIN evaluations e ON e.registration_id = r.id AND e.round = ?
        GROUP BY r.id, rr.status
        ORDER BY avg_total IS NULL, avg_total DESC, r.created_at ASC
        """,
        (selected_round, selected_round),
    ).fetchall()

    round_counts = {}
    for level in EVALUATION_LEVELS:
        row = db.execute(
            """
            SELECT
                SUM(CASE WHEN status != 'not_qualified' THEN 1 ELSE 0 END) as active_count,
                SUM(CASE WHEN status = 'qualified' THEN 1 ELSE 0 END) as qualified_count,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count
            FROM registration_rounds WHERE round = ?
            """,
            (level["key"],),
        ).fetchone()
        eval_row = db.execute(
            """
            SELECT COUNT(DISTINCT e.registration_id) as evaluated_count
            FROM evaluations e
            INNER JOIN registration_rounds rr ON rr.registration_id = e.registration_id AND rr.round = e.round
            WHERE e.round = ? AND rr.status != 'not_qualified'
            """,
            (level["key"],),
        ).fetchone()
        round_counts[level["key"]] = {
            "active": (row["active_count"] or 0) if row else 0,
            "qualified": (row["qualified_count"] or 0) if row else 0,
            "pending": (row["pending_count"] or 0) if row else 0,
            "evaluated": (eval_row["evaluated_count"] or 0) if eval_row else 0,
        }

    judges = db.execute(
        "SELECT id, username, name, created_at FROM users WHERE role = 'judge' ORDER BY created_at DESC"
    ).fetchall()
    all_reg_stats = db.execute(
        """
        SELECT
            COUNT(*) as total_registrations,
            SUM(CASE WHEN team_type = 'solo' THEN 1 ELSE 0 END) as solo,
            SUM(CASE WHEN team_type = 'group' THEN 1 ELSE 0 END) as group_count
        FROM registrations
        """
    ).fetchone()
    stats = {
        "total_registrations": all_reg_stats["total_registrations"] or 0,
        "solo": all_reg_stats["solo"] or 0,
        "group": all_reg_stats["group_count"] or 0,
        "evaluated": sum(1 for r in results if r["eval_count"] and r["eval_count"] > 0),
        "judges": len(judges),
    }
    selected_round_info = next(level for level in EVALUATION_LEVELS if level["key"] == selected_round)
    selected_reg_round_info = next((level for level in EVALUATION_LEVELS if level["key"] == reg_round), None)
    return render_template(
        "admin_dashboard.html",
        registrations=registrations,
        members_by_reg=members_by_reg,
        results=results,
        judges=judges,
        stats=stats,
        evaluation_levels=EVALUATION_LEVELS,
        selected_round=selected_round,
        selected_round_info=selected_round_info,
        round_counts=round_counts,
        reg_round=reg_round,
        selected_reg_round_info=selected_reg_round_info,
        reg_filters=reg_filters,
        tracks=TRACKS,
    )


@app.route("/admin/registrations/<int:registration_id>/round-status", methods=["POST"])
@login_required(role="admin")
def admin_update_round_status(registration_id):
    db = get_db()
    round_key = (request.form.get("round") or "").strip()
    status = (request.form.get("status") or "").strip()
    if round_key not in EVALUATION_LEVEL_KEYS:
        flash("Invalid evaluation round.", "error")
        return redirect(url_for("admin_dashboard"))
    if status not in {"pending", "qualified", "not_qualified"}:
        flash("Invalid round status.", "error")
        return redirect(url_for("admin_dashboard", round=round_key))

    reg = db.execute("SELECT id, registration_number FROM registrations WHERE id = ?", (registration_id,)).fetchone()
    if not reg:
        flash("Registration not found.", "error")
        return redirect(url_for("admin_dashboard", round=round_key))

    now = datetime.utcnow().isoformat(timespec="seconds")
    db.execute(
        """
        INSERT INTO registration_rounds (registration_id, round, status, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(registration_id, round) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
        """,
        (registration_id, round_key, status, now),
    )

    if status == "qualified":
        keys = [level["key"] for level in EVALUATION_LEVELS]
        try:
            idx = keys.index(round_key)
        except ValueError:
            idx = -1
        if idx >= 0 and idx + 1 < len(keys):
            next_round = keys[idx + 1]
            db.execute(
                """
                INSERT OR IGNORE INTO registration_rounds (registration_id, round, status, updated_at)
                VALUES (?, ?, 'pending', ?)
                """,
                (registration_id, next_round, now),
            )
            flash(
                f"{reg['registration_number']} marked qualified in {round_key.replace('_', ' ').title()} and moved to next round.",
                "success",
            )
        else:
            flash(f"{reg['registration_number']} marked qualified in {round_key.replace('_', ' ').title()}.", "success")
    else:
        flash(f"{reg['registration_number']} marked {status.replace('_', ' ')} in {round_key.replace('_', ' ').title()}.", "success")

    db.commit()
    return redirect(url_for("admin_dashboard", round=round_key))


@app.route("/admin/settings/deadline", methods=["POST"])
@login_required(role="admin")
def admin_set_registration_deadline():
    deadline_raw = (request.form.get("registration_deadline") or "").strip()
    if not deadline_raw:
        delete_setting(REGISTRATION_DEADLINE_KEY)
        flash("Registration deadline cleared. Registrations are now open.", "success")
        return redirect(url_for("admin_dashboard"))

    try:
        deadline = datetime.strptime(deadline_raw, "%Y-%m-%dT%H:%M")
    except ValueError:
        flash("Invalid deadline format. Please use the datetime picker.", "error")
        return redirect(url_for("admin_dashboard"))

    set_setting(REGISTRATION_DEADLINE_KEY, deadline.isoformat(timespec="seconds"))
    flash(f"Registration deadline set to {deadline.strftime('%d %b %Y, %I:%M %p')}.", "success")
    return redirect(url_for("admin_dashboard"))


def _registration_export_rows(db, filters):
    registrations = _query_registrations(db, filters)
    headers = [
        "Registration Number",
        "Team Type",
        "Track",
        "Problem Title",
        "Problem Description",
        "School Name",
        "Leader Name",
        "Leader Class",
        "Leader Contact",
        "Leader Email",
        "Team Members",
        "Registered At (UTC)",
    ] + [f"{level['short_label']} Status" for level in EVALUATION_LEVELS]
    rows = []
    for reg in registrations:
        members = db.execute(
            "SELECT member_name, member_class FROM team_members WHERE registration_id = ? ORDER BY id",
            (reg["id"],),
        ).fetchall()
        members_text = "; ".join(
            f"{m['member_name']} (Class {m['member_class']})" for m in members
        )
        round_statuses = []
        for level in EVALUATION_LEVELS:
            rr = db.execute(
                "SELECT status FROM registration_rounds WHERE registration_id = ? AND round = ?",
                (reg["id"], level["key"]),
            ).fetchone()
            round_statuses.append(rr["status"] if rr else "")
        rows.append(
            [
                reg["registration_number"],
                reg["team_type"],
                reg["track"],
                reg["problem_title"],
                reg["problem_description"],
                reg["school_name"],
                reg["leader_name"],
                reg["leader_class"],
                reg["leader_contact"] or "",
                reg["leader_email"] or "",
                members_text,
                reg["created_at"],
            ] + round_statuses
        )
    return headers, rows


@app.route("/admin/export/registrations.xlsx")
@login_required(role="admin")
def admin_export_registrations():
    from io import BytesIO

    from openpyxl import Workbook

    db = get_db()
    filters = _registration_filters(request.args)
    headers, rows = _registration_export_rows(db, filters)

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    ws.append(headers)
    for row in rows:
        ws.append(row)

    for column_cells in ws.columns:
        max_length = 12
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            cell_value = "" if cell.value is None else str(cell.value)
            max_length = min(max(max_length, len(cell_value) + 2), 50)
        ws.column_dimensions[column_letter].width = max_length

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"registrations-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.xlsx"
    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/admin/export/registrations.csv")
@login_required(role="admin")
def admin_export_registrations_csv():
    import csv
    from io import BytesIO, StringIO

    db = get_db()
    filters = _registration_filters(request.args)
    headers, rows = _registration_export_rows(db, filters)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    mem = BytesIO(output.getvalue().encode("utf-8-sig"))
    filename = f"registrations-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
    return send_file(
        mem,
        as_attachment=True,
        download_name=filename,
        mimetype="text/csv",
    )


@app.route("/admin/judges", methods=["GET", "POST"])
@login_required(role="admin")
def admin_judges():
    db = get_db()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        errors = []
        if not name:
            errors.append("Judge name is required.")
        if not username:
            errors.append("Username is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if username:
            existing = db.execute(
                "SELECT id FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                errors.append("That username is already taken.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            now = datetime.utcnow().isoformat(timespec="seconds")
            db.execute(
                "INSERT INTO users (username, password_hash, role, name, created_at) VALUES (?, ?, 'judge', ?, ?)",
                (username, generate_password_hash(password), name, now),
            )
            db.commit()
            session["new_judge_credentials"] = {
                "name": name,
                "username": username,
                "password": password,
            }
            flash(f"Judge '{name}' created successfully.", "success")
            return redirect(url_for("admin_judges"))

    judges = db.execute(
        "SELECT id, username, name, created_at FROM users WHERE role = 'judge' ORDER BY created_at DESC"
    ).fetchall()
    new_judge_credentials = session.pop("new_judge_credentials", None)
    reset_judge_credentials = session.pop("reset_judge_credentials", None)
    return render_template(
        "admin_judges.html",
        judges=judges,
        new_judge_credentials=new_judge_credentials,
        reset_judge_credentials=reset_judge_credentials,
    )


@app.route("/admin/judges/<int:judge_id>/reset-password", methods=["POST"])
@login_required(role="admin")
def admin_reset_judge_password(judge_id):
    db = get_db()
    judge = db.execute(
        "SELECT id, name, username FROM users WHERE id = ? AND role = 'judge'",
        (judge_id,),
    ).fetchone()
    if not judge:
        flash("Judge account not found.", "error")
        return redirect(url_for("admin_judges"))

    password = request.form.get("password") or ""
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("admin_judges"))

    db.execute(
        "UPDATE users SET password_hash = ? WHERE id = ? AND role = 'judge'",
        (generate_password_hash(password), judge_id),
    )
    db.commit()
    session["reset_judge_credentials"] = {
        "name": judge["name"],
        "username": judge["username"],
        "password": password,
    }
    flash(f"Password reset for judge '{judge['name']}'.", "success")
    return redirect(url_for("admin_judges"))


@app.route("/judge")
@login_required(role="judge")
def judge_dashboard():
    db = get_db()
    judge_id = session["user"]["id"]
    selected_round = request.args.get("round", DEFAULT_EVALUATION_LEVEL)
    if selected_round not in EVALUATION_LEVEL_KEYS:
        selected_round = DEFAULT_EVALUATION_LEVEL

    rows = db.execute(
        """
        SELECT r.*, rr.status as round_status, rr.notes as round_notes,
               e.id as evaluation_id, e.total_score, e.updated_at as eval_updated_at
        FROM registrations r
        INNER JOIN registration_rounds rr ON rr.registration_id = r.id AND rr.round = ?
        LEFT JOIN evaluations e ON e.registration_id = r.id AND e.judge_id = ? AND e.round = ?
        WHERE rr.status != 'not_qualified'
        ORDER BY e.id IS NULL DESC, r.created_at ASC
        """,
        (selected_round, judge_id, selected_round),
    ).fetchall()
    members_by_reg = {}
    for r in rows:
        members_by_reg[r["id"]] = db.execute(
            "SELECT member_name, member_class FROM team_members WHERE registration_id = ? ORDER BY id",
            (r["id"],),
        ).fetchall()

    round_counts = {}
    for level in EVALUATION_LEVELS:
        count_row = db.execute(
            "SELECT COUNT(*) as cnt FROM registration_rounds WHERE round = ? AND status != 'not_qualified'",
            (level["key"],),
        ).fetchone()
        round_counts[level["key"]] = count_row["cnt"] if count_row else 0

    pending = sum(1 for r in rows if not r["evaluation_id"])
    completed = sum(1 for r in rows if r["evaluation_id"])
    selected_round_info = next(level for level in EVALUATION_LEVELS if level["key"] == selected_round)
    return render_template(
        "judge_dashboard.html",
        registrations=rows,
        members_by_reg=members_by_reg,
        pending=pending,
        completed=completed,
        evaluation_levels=EVALUATION_LEVELS,
        selected_round=selected_round,
        selected_round_info=selected_round_info,
        round_counts=round_counts,
    )


@app.route("/judge/evaluate/<int:registration_id>", methods=["GET", "POST"])
@app.route("/judge/evaluate/<int:registration_id>/<round_key>", methods=["GET", "POST"])
@login_required(role="judge")
def evaluate(registration_id, round_key=DEFAULT_EVALUATION_LEVEL):
    db = get_db()
    judge_id = session["user"]["id"]
    if round_key not in EVALUATION_LEVEL_KEYS:
        flash("Invalid evaluation round.", "error")
        return redirect(url_for("judge_dashboard"))

    registration = db.execute(
        "SELECT * FROM registrations WHERE id = ?", (registration_id,)
    ).fetchone()
    if not registration:
        flash("Registration not found.", "error")
        return redirect(url_for("judge_dashboard"))

    members = db.execute(
        "SELECT member_name, member_class FROM team_members WHERE registration_id = ? ORDER BY id",
        (registration_id,),
    ).fetchall()
    existing = db.execute(
        "SELECT * FROM evaluations WHERE registration_id = ? AND judge_id = ? AND round = ?",
        (registration_id, judge_id, round_key),
    ).fetchone()
    round_info = next(level for level in EVALUATION_LEVELS if level["key"] == round_key)

    if request.method == "POST":
        scores = {}
        errors = []
        for p in JUDGING_PARAMETERS:
            raw = (request.form.get(p["key"]) or "").strip()
            try:
                val = int(raw)
            except ValueError:
                errors.append(f"{p['label']}: please enter a number between {MIN_SCORE} and {MAX_SCORE}.")
                continue
            if val < MIN_SCORE or val > MAX_SCORE:
                errors.append(f"{p['label']}: score must be between {MIN_SCORE} and {MAX_SCORE}.")
            scores[p["key"]] = val
        comments = (request.form.get("comments") or "").strip()

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            total = sum(scores[p["key"]] for p in JUDGING_PARAMETERS)
            now = datetime.utcnow().isoformat(timespec="seconds")
            if existing:
                db.execute(
                    """
                    UPDATE evaluations SET
                        problem_understanding = ?, solution_relevance = ?, creativity = ?,
                        feasibility = ?, presentation = ?, comments = ?, total_score = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        scores["problem_understanding"],
                        scores["solution_relevance"],
                        scores["creativity"],
                        scores["feasibility"],
                        scores["presentation"],
                        comments or None,
                        total,
                        now,
                        existing["id"],
                    ),
                )
                flash(f"Evaluation updated for {round_info['short_label']}.", "success")
            else:
                db.execute(
                    """
                    INSERT INTO evaluations
                    (registration_id, judge_id, round, problem_understanding, solution_relevance, creativity,
                     feasibility, presentation, comments, total_score, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        registration_id,
                        judge_id,
                        round_key,
                        scores["problem_understanding"],
                        scores["solution_relevance"],
                        scores["creativity"],
                        scores["feasibility"],
                        scores["presentation"],
                        comments or None,
                        total,
                        now,
                        now,
                    ),
                )
                flash(f"Evaluation submitted for {round_info['short_label']}.", "success")
            db.commit()
            return redirect(url_for("judge_dashboard", round=round_key))

    return render_template(
        "evaluate.html",
        registration=registration,
        members=members,
        existing=existing,
        min_score=MIN_SCORE,
        max_score=MAX_SCORE,
        round_key=round_key,
        round_info=round_info,
        evaluation_levels=EVALUATION_LEVELS,
    )


if __name__ == "__main__":
    with app.app_context():
        init_db()
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)

