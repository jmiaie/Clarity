"""Work-style quiz.

Twenty questions across five dimensions. Each question has four options: two
lean toward one pole (strongly or mildly) and two toward the other. The result
is a self-description, not a validated psychometric instrument, and the UI says so.
"""

# Dimensions and their two poles (first pole, second pole)
DIMENSIONS = {
    "energy": ["morning", "evening"],
    "work_style": ["deep_work", "collaborative"],
    "decision_making": ["analytical", "intuitive"],
    "communication": ["direct", "thoughtful"],
    "goals": ["achievement", "growth"]
}

# 20 Assessment Questions
QUESTIONS = [
    {
        "id": 1,
        "text": "When do you feel most energized?",
        "dimension": "energy",
        "options": [
            {"pole": "morning", "text": "Early morning (6am-9am)", "weight": 2},
            {"pole": "morning", "text": "Late morning (9am-12pm)", "weight": 1},
            {"pole": "evening", "text": "Afternoon (12pm-5pm)", "weight": 1},
            {"pole": "evening", "text": "Evening (5pm-10pm)", "weight": 2}
        ]
    },
    {
        "id": 2,
        "text": "How do you prefer to work?",
        "dimension": "work_style",
        "options": [
            {"pole": "deep_work", "text": "Alone, in deep focus", "weight": 2},
            {"pole": "deep_work", "text": "Mostly alone with some collaboration", "weight": 1},
            {"pole": "collaborative", "text": "Mostly with others", "weight": 1},
            {"pole": "collaborative", "text": "Always in groups/teams", "weight": 2}
        ]
    },
    {
        "id": 3,
        "text": "When making decisions, you rely more on:",
        "dimension": "decision_making",
        "options": [
            {"pole": "analytical", "text": "Data and analysis", "weight": 2},
            {"pole": "analytical", "text": "Logic and reasoning", "weight": 1},
            {"pole": "intuitive", "text": "Gut feeling", "weight": 1},
            {"pole": "intuitive", "text": "Instinct and emotion", "weight": 2}
        ]
    },
    {
        "id": 4,
        "text": "Your communication style is typically:",
        "dimension": "communication",
        "options": [
            {"pole": "direct", "text": "Direct and to the point", "weight": 2},
            {"pole": "direct", "text": "Clear and concise", "weight": 1},
            {"pole": "thoughtful", "text": "Careful and considered", "weight": 1},
            {"pole": "thoughtful", "text": "Diplomatic and nuanced", "weight": 2}
        ]
    },
    {
        "id": 5,
        "text": "What drives you most?",
        "dimension": "goals",
        "options": [
            {"pole": "achievement", "text": "Completing tasks and hitting goals", "weight": 2},
            {"pole": "achievement", "text": "Winning and success", "weight": 1},
            {"pole": "growth", "text": "Learning and improving", "weight": 1},
            {"pole": "growth", "text": "Personal development", "weight": 2}
        ]
    },
    # Questions 6-20 (similar structure, different dimensions)
    {
        "id": 6,
        "text": "How do you tackle a large project?",
        "dimension": "work_style",
        "options": [
            {"pole": "deep_work", "text": "Block out time and work alone", "weight": 2},
            {"pole": "deep_work", "text": "Break it down, focus independently", "weight": 1},
            {"pole": "collaborative", "text": "Brainstorm with others", "weight": 1},
            {"pole": "collaborative", "text": "Divide and conquer as a team", "weight": 2}
        ]
    },
    {
        "id": 7,
        "text": "What time do you typically go to bed?",
        "dimension": "energy",
        "options": [
            {"pole": "morning", "text": "Before 10pm", "weight": 2},
            {"pole": "morning", "text": "10pm-11pm", "weight": 1},
            {"pole": "evening", "text": "11pm-12am", "weight": 1},
            {"pole": "evening", "text": "After midnight", "weight": 2}
        ]
    },
    {
        "id": 8,
        "text": "When solving a problem, you prefer to:",
        "dimension": "decision_making",
        "options": [
            {"pole": "analytical", "text": "Gather all facts first", "weight": 2},
            {"pole": "analytical", "text": "Create a structured approach", "weight": 1},
            {"pole": "intuitive", "text": "Try different approaches", "weight": 1},
            {"pole": "intuitive", "text": "Go with what feels right", "weight": 2}
        ]
    },
    {
        "id": 9,
        "text": "In meetings, you tend to:",
        "dimension": "communication",
        "options": [
            {"pole": "direct", "text": "Speak up quickly with ideas", "weight": 2},
            {"pole": "direct", "text": "Share opinions clearly", "weight": 1},
            {"pole": "thoughtful", "text": "Listen more than speak", "weight": 1},
            {"pole": "thoughtful", "text": "Think carefully before contributing", "weight": 2}
        ]
    },
    {
        "id": 10,
        "text": "Success for you means:",
        "dimension": "goals",
        "options": [
            {"pole": "achievement", "text": "Reaching specific targets", "weight": 2},
            {"pole": "achievement", "text": "Visible accomplishments", "weight": 1},
            {"pole": "growth", "text": "Becoming better over time", "weight": 1},
            {"pole": "growth", "text": "Mastering new skills", "weight": 2}
        ]
    },
    {
        "id": 11,
        "text": "Your ideal work environment is:",
        "dimension": "work_style",
        "options": [
            {"pole": "deep_work", "text": "Quiet, minimal distractions", "weight": 2},
            {"pole": "deep_work", "text": "Controlled interruptions", "weight": 1},
            {"pole": "collaborative", "text": "Open with team interaction", "weight": 1},
            {"pole": "collaborative", "text": "Buzzing with energy", "weight": 2}
        ]
    },
    {
        "id": 12,
        "text": "When do you do your best thinking?",
        "dimension": "energy",
        "options": [
            {"pole": "morning", "text": "First thing in the morning", "weight": 2},
            {"pole": "morning", "text": "Mid-morning", "weight": 1},
            {"pole": "evening", "text": "Afternoon/early evening", "weight": 1},
            {"pole": "evening", "text": "Late at night", "weight": 2}
        ]
    },
    {
        "id": 13,
        "text": "You make better decisions when:",
        "dimension": "decision_making",
        "options": [
            {"pole": "analytical", "text": "You have all the data", "weight": 2},
            {"pole": "analytical", "text": "You've analyzed options", "weight": 1},
            {"pole": "intuitive", "text": "You trust your instincts", "weight": 1},
            {"pole": "intuitive", "text": "You follow your heart", "weight": 2}
        ]
    },
    {
        "id": 14,
        "text": "When giving feedback, you:",
        "dimension": "communication",
        "options": [
            {"pole": "direct", "text": "Say it straight", "weight": 2},
            {"pole": "direct", "text": "Be clear and specific", "weight": 1},
            {"pole": "thoughtful", "text": "Consider their feelings", "weight": 1},
            {"pole": "thoughtful", "text": "Frame it very carefully", "weight": 2}
        ]
    },
    {
        "id": 15,
        "text": "You feel most satisfied when:",
        "dimension": "goals",
        "options": [
            {"pole": "achievement", "text": "You finish what you started", "weight": 2},
            {"pole": "achievement", "text": "You hit your milestones", "weight": 1},
            {"pole": "growth", "text": "You learn something new", "weight": 1},
            {"pole": "growth", "text": "You improve your skills", "weight": 2}
        ]
    },
    {
        "id": 16,
        "text": "Interruptions during work:",
        "dimension": "work_style",
        "options": [
            {"pole": "deep_work", "text": "Really frustrate me", "weight": 2},
            {"pole": "deep_work", "text": "Break my concentration", "weight": 1},
            {"pole": "collaborative", "text": "Are sometimes helpful", "weight": 1},
            {"pole": "collaborative", "text": "Lead to good ideas", "weight": 2}
        ]
    },
    {
        "id": 17,
        "text": "On weekends, you naturally:",
        "dimension": "energy",
        "options": [
            {"pole": "morning", "text": "Wake up early", "weight": 2},
            {"pole": "morning", "text": "Rise at normal time", "weight": 1},
            {"pole": "evening", "text": "Sleep in a bit", "weight": 1},
            {"pole": "evening", "text": "Sleep as late as possible", "weight": 2}
        ]
    },
    {
        "id": 18,
        "text": "When learning something new:",
        "dimension": "decision_making",
        "options": [
            {"pole": "analytical", "text": "Study the manual", "weight": 2},
            {"pole": "analytical", "text": "Understand the theory first", "weight": 1},
            {"pole": "intuitive", "text": "Jump in and figure it out", "weight": 1},
            {"pole": "intuitive", "text": "Learn by doing", "weight": 2}
        ]
    },
    {
        "id": 19,
        "text": "In written communication, you're:",
        "dimension": "communication",
        "options": [
            {"pole": "direct", "text": "Brief and efficient", "weight": 2},
            {"pole": "direct", "text": "Clear and structured", "weight": 1},
            {"pole": "thoughtful", "text": "Detailed and thorough", "weight": 1},
            {"pole": "thoughtful", "text": "Warm and personable", "weight": 2}
        ]
    },
    {
        "id": 20,
        "text": "Your primary focus is on:",
        "dimension": "goals",
        "options": [
            {"pole": "achievement", "text": "Getting results", "weight": 2},
            {"pole": "achievement", "text": "Delivering outcomes", "weight": 1},
            {"pole": "growth", "text": "Building capabilities", "weight": 1},
            {"pole": "growth", "text": "Expanding potential", "weight": 2}
        ]
    }
]

# Personality Profiles
PROFILES = {
    "morning_achiever": {
        "name": "Morning Achiever",
        "emoji": "🌅",
        "description": "You're energized early in the day and goal-oriented. You perform best with focused morning work sessions and clear objectives.",
        "strengths": ["Early productivity", "Goal completion", "Focused execution"],
        "optimal_schedule": "Deep work 8-11am, meetings after 2pm",
        "meeting_preference": "Keep mornings clear for deep work",
        "tips": [
            "Block 8-11am for your most important work",
            "Schedule meetings in the afternoon",
            "Tackle hard problems before noon",
            "Set daily goals the night before"
        ]
    },
    "evening_creator": {
        "name": "Evening Creator",
        "emoji": "🌙",
        "description": "You're creative at night and big-picture focused. You thrive with flexible schedules and room for exploration.",
        "strengths": ["Creative thinking", "Innovation", "Flexible problem-solving"],
        "optimal_schedule": "Meetings in morning, creative work after 5pm",
        "meeting_preference": "Front-load meetings in the morning",
        "tips": [
            "Save creative work for evening",
            "Use mornings for collaborative tasks",
            "Don't schedule deep work before noon",
            "Allow flexibility in your schedule"
        ]
    },
    "steady_collaborator": {
        "name": "Steady Collaborator",
        "emoji": "🤝",
        "description": "You're consistent and team-focused. You excel in collaborative environments with steady rhythms.",
        "strengths": ["Team coordination", "Reliability", "Relationship building"],
        "optimal_schedule": "Mix of collaboration and focused time throughout day",
        "meeting_preference": "Regular team check-ins welcome",
        "tips": [
            "Balance solo and team work",
            "Keep consistent daily routines",
            "Schedule regular team touchpoints",
            "Use collaboration to energize"
        ]
    },
    "analytical_planner": {
        "name": "Analytical Planner",
        "emoji": "📊",
        "description": "You're strategic and detail-oriented. You perform best with structured plans and thorough analysis.",
        "strengths": ["Strategic thinking", "Detailed planning", "Systematic execution"],
        "optimal_schedule": "Planning in morning, execution in afternoon",
        "meeting_preference": "Structured agendas, pre-reading materials",
        "tips": [
            "Start day with planning",
            "Request meeting agendas in advance",
            "Block time for analysis",
            "Create detailed project plans"
        ]
    },
    "adaptive_executor": {
        "name": "Adaptive Executor",
        "emoji": "⚡",
        "description": "You're flexible and action-oriented. You thrive in dynamic environments with varied tasks.",
        "strengths": ["Quick execution", "Adaptability", "Multi-tasking"],
        "optimal_schedule": "Varied tasks throughout the day",
        "meeting_preference": "Flexible, can adapt to any time",
        "tips": [
            "Embrace variety in your schedule",
            "Keep tasks bite-sized",
            "Stay ready to pivot",
            "Use energy spikes for quick wins"
        ]
    },
    "reflective_learner": {
        "name": "Reflective Learner",
        "emoji": "📚",
        "description": "You're thoughtful and growth-minded. You excel with time for reflection and continuous improvement.",
        "strengths": ["Deep thinking", "Continuous learning", "Thoughtful communication"],
        "optimal_schedule": "Reflection time daily, learning blocks weekly",
        "meeting_preference": "Time to process before responding",
        "tips": [
            "Schedule daily reflection time",
            "Take notes in meetings",
            "Request time to think on decisions",
            "Build in learning blocks weekly"
        ]
    }
}

# Each option gets a stable id so two options pointing the same way stay distinguishable.
OPTION_IDS = "abcd"
for _question in QUESTIONS:
    for _index, _option in enumerate(_question["options"]):
        _option["id"] = OPTION_IDS[_index]

# Each profile is defined by the two traits it leans on.
PROFILE_TRAITS = {
    "morning_achiever": (("energy", "morning"), ("goals", "achievement")),
    "evening_creator": (("energy", "evening"), ("decision_making", "intuitive")),
    "steady_collaborator": (("work_style", "collaborative"), ("communication", "thoughtful")),
    "analytical_planner": (("decision_making", "analytical"), ("work_style", "deep_work")),
    "adaptive_executor": (("work_style", "collaborative"), ("communication", "direct")),
    "reflective_learner": (("goals", "growth"), ("communication", "thoughtful")),
}

DISCLAIMER = (
    "This is a short self-reflection quiz based on your own answers. "
    "It is not a validated psychological test."
)


class AssessmentError(ValueError):
    """Answers were missing or did not match the questions."""


def public_questions() -> list:
    """Questions as shown to the user: option ids and wording only, no scoring keys."""
    return [
        {
            "id": q["id"],
            "text": q["text"],
            "options": [{"id": o["id"], "text": o["text"]} for o in q["options"]],
        }
        for q in QUESTIONS
    ]


def calculate_profile(answers: dict) -> dict:
    """Score a full set of answers.

    answers maps question id (int or str) to the chosen option id ("a".."d").
    Every question must be answered.
    """
    normalized = {str(key): str(value).strip().lower() for key, value in (answers or {}).items()}

    totals = {dimension: {pole: 0 for pole in poles} for dimension, poles in DIMENSIONS.items()}
    maximum = {dimension: 0 for dimension in DIMENSIONS}
    for question in QUESTIONS:
        choice = normalized.get(str(question["id"]))
        if choice is None:
            raise AssessmentError(f"Question {question['id']} has not been answered.")
        option = next((o for o in question["options"] if o["id"] == choice), None)
        if option is None:
            raise AssessmentError(f"Question {question['id']} has no option '{choice}'.")
        totals[question["dimension"]][option["pole"]] += option["weight"]
        maximum[question["dimension"]] += max(o["weight"] for o in question["options"])

    # Lean per dimension from -1 (fully second pole) to +1 (fully first pole).
    lean = {}
    traits = {}
    for dimension, (first, second) in DIMENSIONS.items():
        difference = totals[dimension][first] - totals[dimension][second]
        lean[dimension] = difference / maximum[dimension] if maximum[dimension] else 0.0
        traits[dimension] = first if difference > 0 else second if difference < 0 else "balanced"

    def match(profile_key: str) -> float:
        score = 0.0
        for dimension, pole in PROFILE_TRAITS[profile_key]:
            first = DIMENSIONS[dimension][0]
            score += lean[dimension] if pole == first else -lean[dimension]
        return score

    # Highest match wins; ties go to the first profile in the table so results are repeatable.
    profile_type = max(PROFILE_TRAITS, key=match)
    profile = PROFILES[profile_type]

    return {
        "profile_type": profile_type,
        "profile_name": profile["name"],
        "profile_emoji": profile["emoji"],
        "description": profile["description"],
        "strengths": profile["strengths"],
        "optimal_schedule": profile["optimal_schedule"],
        "meeting_preference": profile["meeting_preference"],
        "tips": profile["tips"],
        "traits": traits,
        "lean": {dimension: round(value, 2) for dimension, value in lean.items()},
        "disclaimer": DISCLAIMER,
    }
