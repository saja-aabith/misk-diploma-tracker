# Misk Skills Profile engine.
#
# Computes the MSHPL skills profile ON READ from existing tables — nothing is
# stored. Live calculation is always correct (no cache to go stale) and trivially
# cheap at MVP scale.
#
# Sources of evidence (pooled per dimension):
#   1. Approved mandatory objectives (student_objective_progress + objectives),
#      mapped to the 5 ACP GROUPS / 11 VAA dimensions via OBJECTIVE_MAP. Result-
#      based academics performance-scale (1 + 2p); pass/fail contribute the fixed
#      default rating.
#   2. Approved Misk Core skill ratings (core_skill_ratings), teacher-levelled
#      (Emerging 1 / Evident 2 / Embedded 3), tagged at the LEAF level (20 ACP
#      leaves) or VAA dimension.
#
# Scoring (per dimension, 0-100), with the profile-wide growth curve:
#   Quality      Q = mean(ratings) / 3
#   Consistency  C = share(ratings >= 2) / count           (>= the diploma floor)
#   Breadth      B = n / (n + BREADTH_K)   n = distinct sources (mandatory + Core)
#   Score        = round(100 * (0.40*B + 0.30*Q + 0.30*C))
# B saturates and never reaches 1, so NO dimension ever reaches 100 (growth
# mindset: always headroom). Every approved activity counts; farming dies
# naturally because each extra source closes only a fraction of the remaining gap.
#
# ACP is leaf-level: each of the 20 leaves pools its parent GROUP's mandatory
# ratings (shared) PLUS that leaf's own Core ratings, so a leaf with strong Core
# evidence rises above its siblings. An ACP group's score is the MEAN of its
# leaves. acp_average = mean of the 20 leaves; vaa_average = mean of the 11;
# overall_average = mean of all 31.
#
# The profile is SEPARATE from the formal diploma award (manual, never computed).

import json
import sqlite3

# ---------------------------------------------------------------------------
# Dimensions.
# ---------------------------------------------------------------------------
ACP_DIMENSIONS = [
    "Meta-Thinking", "Linking", "Analysing", "Creating", "Realising",
]

# The 20 HPL ACP leaf characteristics under their 5 group headings (verbatim from
# the MISK/HPL ACP progression poster). Leaves are scored individually: they
# share their parent group's mandatory ratings, but each carries its own Core
# ratings, so leaves can diverge once Core evidence exists. Keys MUST match
# ACP_DIMENSIONS.
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

# The 11 VAA dimensions under their HPL behavioural clusters (+ Digital Thinker as
# the MISK extension). Display grouping only. Union MUST equal VAA_DIMENSIONS.
VAA_CLUSTERS = {
    "Empathetic": ["Collaborative", "Concerned for Society", "Confident"],
    "Agile": ["Enquiring", "Creative & Enterprising", "Open-Minded", "Risk-Taking"],
    "Hard Working": ["Practice", "Perseverance", "Resilience"],
    "Digital Thinker": ["Digital Thinker"],
}

# Flat allow-list of every valid stored dimension string (20 ACP leaves + 11 VAA).
# Core ratings MUST validate against this on write.
ALL_LEAF_DIMENSIONS = [leaf for g in ACP_DIMENSIONS for leaf in ACP_LEAVES[g]] + VAA_DIMENSIONS

_GROUP_OF = {d: "VAA" for d in VAA_DIMENSIONS}
_CATEGORY_OF = {}
for _cluster, _cluster_dims in VAA_CLUSTERS.items():
    for _cd in _cluster_dims:
        _CATEGORY_OF[_cd] = _cluster
_LEAF_PARENT = {leaf: g for g in ACP_DIMENSIONS for leaf in ACP_LEAVES[g]}

# ---------------------------------------------------------------------------
# Objective -> (group/VAA dimension) map, keyed by exact objectives.title.
# "result" objectives performance-scale via 1 + 2p; "passfail" contribute the
# fixed default. ACP entries are the 5 GROUP names (leaves inherit the group's
# mandatory ratings).
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

# ---------------------------------------------------------------------------
# Signed-off constants.
# ---------------------------------------------------------------------------
DEFAULT_RATING = 2.0          # pass/fail (and approved-but-no-result) rating
RATING_MAX = 3.0              # intrinsic rating ceiling (1 + 2*1)
CONSISTENCY_BAR = 2.0         # the diploma floor ("Evident")
W_BREADTH = 0.40
W_QUALITY = 0.30
W_CONSISTENCY = 0.30
# Growth curve: B = n / (n + BREADTH_K). Higher K => growth is harder / ceiling
# feels further. Tunable governance dial; never lets B (or the score) reach the
# top. Signed off at K=3 (the 80s are the realistic top; 90s rare and hard-earned;
# 100 unreachable, profile-wide).
BREADTH_K = 3.0

# Grade -> points.
IGCSE_POINTS = {"U": 0, "G": 1, "F": 2, "E": 3, "D": 4, "C": 5, "B": 6, "A": 7, "A*": 9}
IAL_POINTS = {"U": 0, "E": 1, "D": 2, "C": 3, "B": 4, "A": 5, "A*": 6}
IGCSE_FLOOR, IGCSE_PER_SUBJECT_MAX = 3, 6
IAL_FLOOR, IAL_PER_SUBJECT_MAX = 1, 5

RESULT_BASED_TITLES = {"IELTS", "IGCSE", "IAL", "Qudurat", "Tahsili"}
MAX_ATTEMPTS = {"Qudurat": 5, "Tahsili": 2}


def _clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def _performance_ratio(title, result_value):
    """Performance ratio p in [0,1] for a result-based objective, or None if no
    usable numeric result is present (caller falls back to the default rating)."""
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
    """The 0-3 rating a single approved mandatory objective contributes."""
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


def _year_of(stamp):
    """Best-effort calendar year from a stored timestamp/date string, else None."""
    if not stamp:
        return None
    s = str(stamp)
    return s[:4] if len(s) >= 4 and s[:4].isdigit() else None


def _score_pool(ratings, n_sources):
    """Score one dimension (0-100) from its pooled 0-3 ratings and distinct source
    count, using the growth curve B = n/(n+BREADTH_K). Returns (score, status)."""
    if not ratings or n_sources <= 0:
        return 0, "no_evidence"
    quality = (sum(ratings) / len(ratings)) / RATING_MAX
    consistency = sum(1 for r in ratings if r >= CONSISTENCY_BAR) / len(ratings)
    breadth = n_sources / (n_sources + BREADTH_K)
    score = round(100.0 * (W_BREADTH * breadth + W_QUALITY * quality + W_CONSISTENCY * consistency))
    return score, "scored"


def _entry(dimension, group, category, mand_list, core_list):
    """Build one dimension/leaf entry from its mandatory ratings (rating, title,
    year) and Core ratings (level, activity_id, year)."""
    ratings = [m[0] for m in mand_list] + [c[0] for c in core_list]
    sources = {("m", m[1]) for m in mand_list} | {("c", c[1]) for c in core_list}
    years = {m[2] for m in mand_list if m[2]} | {c[2] for c in core_list if c[2]}
    score, status = _score_pool(ratings, len(sources))
    return {
        "dimension": dimension, "group": group, "category": category,
        "score": score, "status": status,
        "evidence_count": len(ratings), "activity_count": len(sources),
        "core_count": len(core_list), "year_count": len(years),
    }


def compute_skills_profile(cursor, student_id):
    """Compute the full skills profile for one student. Pure read; never writes.

    Returns { student_id, dimensions (5 ACP groups + 11 VAA), acp_leaves (20),
    acp_average, vaa_average, overall_average }.
    """
    # --- 1. Mandatory ratings, keyed by the 5 ACP GROUPS + 11 VAA dims ---
    cursor.execute(
        """
        SELECT o.title AS title, sop.result_value AS result_value,
               sop.attempts AS attempts, sop.updated_at AS updated_at
        FROM student_objective_progress sop
        JOIN objectives o ON o.id = sop.objective_id
        WHERE sop.student_id = ? AND o.is_active = 1 AND sop.status = 'approved'
        """,
        (student_id,),
    )
    mand = {d: [] for d in (ACP_DIMENSIONS + VAA_DIMENSIONS)}  # (rating, title, year)
    for row in (dict(r) for r in cursor.fetchall()):
        mapping = OBJECTIVE_MAP.get(row["title"])
        if mapping is None:
            continue
        dims, kind = mapping
        year = _year_of(row["updated_at"])
        for d in dims:
            rating = _rating_for(row["title"], d, kind, row["result_value"], row["attempts"])
            mand[d].append((rating, row["title"], year))

    # --- 2. Approved Core ratings, keyed by leaf / VAA dimension ---
    core = {}  # dimension -> list of (level, activity_id, year)
    try:
        cursor.execute(
            """
            SELECT csr.dimension AS dimension, csr.level AS level,
                   csr.activity_id AS activity_id, sa.activity_date AS activity_date
            FROM core_skill_ratings csr
            LEFT JOIN student_activities sa ON sa.id = csr.activity_id
            WHERE csr.student_id = ? AND csr.status = 'approved' AND csr.level >= 1
            """,
            (student_id,),
        )
        for r in (dict(x) for x in cursor.fetchall()):
            core.setdefault(r["dimension"], []).append(
                (float(r["level"]), r["activity_id"], _year_of(r["activity_date"]))
            )
    except sqlite3.OperationalError:
        pass  # core_skill_ratings not migrated yet -> no Core contribution

    # --- 3. VAA dimensions (flat: own mandatory + own Core) ---
    vaa_entries = [
        _entry(d, "VAA", _CATEGORY_OF.get(d), mand[d], core.get(d, []))
        for d in VAA_DIMENSIONS
    ]

    # --- 4. ACP leaves: parent group's mandatory ratings + leaf's own Core ---
    acp_leaves = []
    for group in ACP_DIMENSIONS:
        for leaf in ACP_LEAVES[group]:
            acp_leaves.append(
                _entry(leaf, "ACP", group, mand[group], core.get(leaf, []))
            )

    # --- 5. ACP group rows = MEAN of their leaves (score); pooled counts ---
    acp_groups = []
    for group in ACP_DIMENSIONS:
        leaves = [e for e in acp_leaves if e["category"] == group]
        gcore = [c for leaf in ACP_LEAVES[group] for c in core.get(leaf, [])]
        gratings = [m[0] for m in mand[group]] + [c[0] for c in gcore]
        gsources = {("m", m[1]) for m in mand[group]} | {("c", c[1]) for c in gcore}
        gyears = {m[2] for m in mand[group] if m[2]} | {c[2] for c in gcore if c[2]}
        gscore = round(sum(l["score"] for l in leaves) / len(leaves)) if leaves else 0
        gstatus = "scored" if any(l["status"] == "scored" for l in leaves) else "no_evidence"
        acp_groups.append({
            "dimension": group, "group": "ACP", "category": None,
            "score": gscore, "status": gstatus,
            "evidence_count": len(gratings), "activity_count": len(gsources),
            "core_count": len(gcore), "year_count": len(gyears),
        })

    dimensions = acp_groups + vaa_entries  # 5 + 11 (payload shape unchanged)

    def _mean(vals):
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    leaf_scores = [e["score"] for e in acp_leaves]
    vaa_scores = [e["score"] for e in vaa_entries]
    return {
        "student_id": student_id,
        "dimensions": dimensions,
        "acp_leaves": acp_leaves,
        "acp_average": _mean(leaf_scores),                 # mean of the 20 leaves
        "vaa_average": _mean(vaa_scores),                  # mean of the 11 VAA
        "overall_average": _mean(leaf_scores + vaa_scores),  # mean of all 31
    }