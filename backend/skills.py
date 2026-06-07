# Misk Skills Profile engine (Chunk 33; ACP leaf view added Chunk 34).
#
# Computes the MSHPL skills profile ON READ from existing tables
# (student_objective_progress + objectives) — nothing is stored. This is a
# deliberate choice: live calculation is always correct (no cache to go stale
# when a result is entered or an objective approved) and trivially cheap at
# MVP scale. A separate, append-only snapshots table is a POST-MVP item for
# trajectory history; this module does not write anything.
#
# The profile is SEPARATE from the formal diploma award (which is manual and
# never computed). See misk_source_of_truth.md sections 7-13 for the agreed
# model; the exact Breadth/Quality/Consistency formulas and the constants
# below were signed off in the Chunk-33 formula spec.

import json

# ---------------------------------------------------------------------------
# The 16 MSHPL dimensions, in their two display groups (the two radars).
# ---------------------------------------------------------------------------
ACP_DIMENSIONS = [
    "Meta-Thinking", "Linking", "Analysing", "Creating", "Realising",
]

# The 20 HPL ACP leaf characteristics under their 5 group headings (verbatim
# from the MISK/HPL ACP progression poster). These drive the LEAF-LEVEL display
# only (constellation stars + the grouped "How I Think — detail" list). Scoring
# still happens at the 5 group level via OBJECTIVE_MAP; each leaf INHERITS its
# parent group's computed score and counts (decision: inheritance, Chunk 34).
# Until Gemini-rated Core activities arrive to differentiate them, a covered
# group's leaves read alike — that is intended. Keys MUST match ACP_DIMENSIONS.
ACP_LEAVES = {
    "Meta-Thinking": [
        "Meta-cognition", "Self-regulation", "Strategy-planning",
        "Intellectual confidence",
    ],
    "Linking": [
        "Generalisation", "Connection finding", "Big picture thinking",
        "Abstraction", "Imagination", "Seeing alternative perspectives",
    ],
    "Analysing": [
        "Critical or logical thinking", "Precision",
        "Complex and multi-step problem solving",
    ],
    "Creating": [
        "Intellectual playfulness", "Flexible thinking", "Fluent thinking",
        "Originality", "Evolutionary and revolutionary thinking",
    ],
    "Realising": [
        "Automaticity", "Speed and accuracy",
    ],
}
VAA_DIMENSIONS = [
    "Collaborative", "Concerned for Society", "Confident", "Enquiring",
    "Creative & Enterprising", "Open-Minded", "Risk-Taking", "Practice",
    "Perseverance", "Resilience", "Digital Thinker",
]

# The 11 VAA dimensions under their HPL behavioural clusters (verbatim from the
# MISK/HPL VAA progression poster), plus Digital Thinker as the MISK extension.
# Display grouping only (the "Who I Am — detail" table); scoring is unaffected.
# Keys' union MUST equal VAA_DIMENSIONS.
VAA_CLUSTERS = {
    "Empathetic": ["Collaborative", "Concerned for Society", "Confident"],
    "Agile": ["Enquiring", "Creative & Enterprising", "Open-Minded", "Risk-Taking"],
    "Hard Working": ["Practice", "Perseverance", "Resilience"],
    "Digital Thinker": ["Digital Thinker"],
}
ALL_DIMENSIONS = ACP_DIMENSIONS + VAA_DIMENSIONS
_GROUP_OF = {d: "ACP" for d in ACP_DIMENSIONS}
_GROUP_OF.update({d: "VAA" for d in VAA_DIMENSIONS})

# Display category for each dimension in `dimensions`: VAA dimensions carry
# their HPL cluster; the 5 ACP group rows carry None (their leaf breakdown and
# per-leaf categories live in `acp_leaves`).
_CATEGORY_OF = {}
for _cluster, _cluster_dims in VAA_CLUSTERS.items():
    for _cd in _cluster_dims:
        _CATEGORY_OF[_cd] = _cluster

# ---------------------------------------------------------------------------
# Objective -> dimension map (source-of-truth section 11), keyed by the exact
# objectives.title strings. "result" objectives performance-scale their listed
# dimensions via 1 + 2p; "passfail" objectives write the fixed default rating.
# Dimensions not listed for an objective receive no mandatory credit from it.
# ---------------------------------------------------------------------------
OBJECTIVE_MAP = {
    "IELTS":               (["Confident"], "result"),
    "IGCSE":               (["Analysing", "Perseverance", "Enquiring"], "result"),
    "IAL":                 (["Analysing", "Perseverance", "Meta-Thinking"], "result"),
    "Qudurat":             (["Analysing", "Resilience"], "result"),
    "Tahsili":             (["Analysing", "Resilience"], "result"),
    "HPQ or EPQ":          (["Meta-Thinking", "Creating", "Perseverance"], "passfail"),
    "Industry Internship": (["Collaborative", "Concerned for Society", "Confident"], "passfail"),
    "Arabic Language":     (["Confident", "Open-Minded"], "passfail"),
    "Islamic Studies":     (["Concerned for Society", "Open-Minded"], "passfail"),
    "Social Studies":      (["Concerned for Society", "Open-Minded"], "passfail"),
    "CMI Level 2":         (["Collaborative", "Confident", "Meta-Thinking"], "passfail"),
}

# How many mandatory objectives COULD evidence each dimension — the denominator
# for relative Breadth. Derived from OBJECTIVE_MAP so it can never drift from it.
POSSIBLE_SOURCES = {d: 0 for d in ALL_DIMENSIONS}
for _title, (_dims, _kind) in OBJECTIVE_MAP.items():
    for _d in _dims:
        POSSIBLE_SOURCES[_d] += 1

# ---------------------------------------------------------------------------
# Signed-off constants.
# ---------------------------------------------------------------------------
DEFAULT_RATING = 2.0          # pass/fail (and approved-but-no-result) rating
RATING_MAX = 3.0              # intrinsic rating ceiling (1 + 2*1)
CONSISTENCY_BAR = 2.0         # "solid pass" bar for the consistency proportion
W_BREADTH = 0.40
W_QUALITY = 0.30
W_CONSISTENCY = 0.30
CORE_CAP_POINTS = 30.0        # max points Misk Core may add to a dimension.
                              # Inert in the MVP (no Core ratings exist yet).

# Grade -> points (source-of-truth section 12).
IGCSE_POINTS = {"U": 0, "G": 1, "F": 2, "E": 3, "D": 4, "C": 5, "B": 6, "A": 7, "A*": 9}
IAL_POINTS = {"U": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "A*": 6}
IGCSE_FLOOR, IGCSE_PER_SUBJECT_MAX = 3, 6   # A*(9) - floor(3) = 6
IAL_FLOOR, IAL_PER_SUBJECT_MAX = 1, 5       # A*(6) - floor(1) = 5

RESULT_BASED_TITLES = {"IELTS", "IGCSE", "IAL", "Qudurat", "Tahsili"}
MAX_ATTEMPTS = {"Qudurat": 5, "Tahsili": 2}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _performance_ratio(title, result_value):
    """Performance ratio p in [0,1] for a result-based objective, or None if no
    usable numeric result is present (caller falls back to the default rating).

    result_value is the string stored by the result-capture endpoint: a numeric
    string for IELTS/Qudurat/Tahsili, or a JSON array of grade tokens for
    IGCSE/IAL. Denominators for IGCSE/IAL scale to the student's actual subject
    count; each subject contributes max(0, points - floor) so a sub-floor grade
    adds nothing rather than going negative.
    """
    if result_value is None or result_value == "":
        return None
    try:
        if title == "IELTS":
            return _clamp((float(result_value) - 7.0) / 2.0)
        if title in ("Qudurat", "Tahsili"):
            return _clamp((float(result_value) - 65.0) / 35.0)
        if title in ("IGCSE", "IAL"):
            grades = json.loads(result_value)
            if not isinstance(grades, list) or not grades:
                return None
            if title == "IGCSE":
                pts = [IGCSE_POINTS.get(str(g).strip().upper(), 0) for g in grades]
                numerator = sum(max(0, p - IGCSE_FLOOR) for p in pts)
                denominator = len(pts) * IGCSE_PER_SUBJECT_MAX
            else:
                pts = [IAL_POINTS.get(str(g).strip().upper(), 0) for g in grades]
                numerator = sum(max(0, p - IAL_FLOOR) for p in pts)
                denominator = len(pts) * IAL_PER_SUBJECT_MAX
            if denominator == 0:
                return None
            return _clamp(numerator / denominator)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    return None


def _rating_for(title, dim, kind, result_value, attempts):
    """The 0-3 rating a single approved objective contributes to one dimension.

    - pass/fail objective -> DEFAULT_RATING.
    - result-based objective -> 1 + 2p (clamped to [1,3]); for Resilience on
      Qudurat/Tahsili, plus the attempt bonus, combined rating capped at 3.
    - result-based but no usable numeric result yet -> DEFAULT_RATING
      (participation credit, no performance scaling).
    """
    if kind == "passfail":
        return DEFAULT_RATING

    p = _performance_ratio(title, result_value)
    if p is None:
        return DEFAULT_RATING

    base = _clamp(1.0 + 2.0 * p, 1.0, 3.0)
    if dim == "Resilience" and title in MAX_ATTEMPTS:
        max_att = MAX_ATTEMPTS[title]
        att = attempts if isinstance(attempts, int) and attempts >= 1 else 1
        bonus = 0.2 * (att - 1) / (max_att - 1) if max_att > 1 else 0.0
        return min(3.0, base + bonus)
    return base


def _year_of(updated_at):
    """Best-effort calendar year from a stored timestamp string, else None."""
    if not updated_at:
        return None
    s = str(updated_at)
    return s[:4] if len(s) >= 4 and s[:4].isdigit() else None


def compute_skills_profile(cursor, student_id):
    """Compute the full 16-dimension skills profile for one student.

    Pure read: queries approved progress rows + objectives and applies the
    signed-off formulas. Returns a dict ready to serialise; never writes.
    """
    cursor.execute(
        """
        SELECT o.title AS title, sop.status AS status,
               sop.result_value AS result_value, sop.attempts AS attempts,
               sop.updated_at AS updated_at
        FROM student_objective_progress sop
        JOIN objectives o ON o.id = sop.objective_id
        WHERE sop.student_id = ? AND o.is_active = 1 AND sop.status = 'approved'
        """,
        (student_id,),
    )
    approved = [dict(r) for r in cursor.fetchall()]

    # Gather contributing ratings per dimension.
    per_dim = {d: [] for d in ALL_DIMENSIONS}  # list of (rating, source_title, year)
    for row in approved:
        title = row["title"]
        mapping = OBJECTIVE_MAP.get(title)
        if mapping is None:
            continue  # objective not part of the mandatory skills map
        dims, kind = mapping
        year = _year_of(row["updated_at"])
        for d in dims:
            rating = _rating_for(title, d, kind, row["result_value"], row["attempts"])
            per_dim[d].append((rating, title, year))

    dimensions = []
    for d in ALL_DIMENSIONS:
        entries = per_dim[d]
        if not entries:
            dimensions.append({
                "dimension": d, "group": _GROUP_OF[d], "category": _CATEGORY_OF.get(d),
                "score": 0,
                "evidence_count": 0, "activity_count": 0, "year_count": 0,
                "status": "no_evidence",
            })
            continue

        ratings = [e[0] for e in entries]
        sources = {e[1] for e in entries}
        years = {e[2] for e in entries if e[2] is not None}

        quality = (sum(ratings) / len(ratings)) / RATING_MAX
        consistency = sum(1 for r in ratings if r >= CONSISTENCY_BAR) / len(ratings)
        possible = POSSIBLE_SOURCES[d] or len(sources)
        breadth = _clamp(len(sources) / possible)

        score_mandatory = 100.0 * (
            W_BREADTH * breadth + W_QUALITY * quality + W_CONSISTENCY * consistency
        )
        # Core uplift is 0 in the MVP (no Core ratings yet); the cap is wired
        # so enabling Gemini-rated Core activities later just engages it.
        core_uplift = 0.0
        final = _clamp(score_mandatory + min(CORE_CAP_POINTS, core_uplift), 0.0, 100.0)

        dimensions.append({
            "dimension": d, "group": _GROUP_OF[d], "category": _CATEGORY_OF.get(d),
            "score": round(final),
            "evidence_count": len(ratings), "activity_count": len(sources),
            "year_count": len(years), "status": "scored",
        })

    # Leaf-level ACP view: each of the 20 HPL leaves inherits the score and
    # evidence counts of its parent group (decision: inheritance). This drives
    # the constellation and the grouped leaf list ONLY; `dimensions` (the 5 ACP
    # groups + 11 VAA) and every average below are computed exactly as before,
    # so the verified group-level profile is unaffected.
    by_dim = {x["dimension"]: x for x in dimensions}
    acp_leaves = []
    for group in ACP_DIMENSIONS:
        parent = by_dim[group]
        for leaf in ACP_LEAVES[group]:
            acp_leaves.append({
                "dimension": leaf,
                "group": "ACP",
                "category": group,
                "score": parent["score"],
                "evidence_count": parent["evidence_count"],
                "activity_count": parent["activity_count"],
                "year_count": parent["year_count"],
                "status": parent["status"],
            })

    def _avg(group):
        vals = [x["score"] for x in dimensions if x["group"] == group]
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    return {
        "student_id": student_id,
        "dimensions": dimensions,
        "acp_leaves": acp_leaves,
        "acp_average": _avg("ACP"),
        "vaa_average": _avg("VAA"),
        "overall_average": round(sum(x["score"] for x in dimensions) / len(dimensions), 1),
    }