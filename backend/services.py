def calculate_lead_score(budget, urgency, need):
    score = 0

    if budget is not None:
        if budget >= 5000:
            score += 40
        elif budget >= 2000:
            score += 30
        elif budget >= 1000:
            score += 20
        elif budget >= 500:
            score += 10

    urgency_scores = {
        "high": 30,
        "medium": 20,
        "low": 10
    }

    score += urgency_scores.get(
        urgency.lower() if urgency else "medium",
        0
    )

    if need and len(need.strip()) >= 20:
        score += 30
    elif need and len(need.strip()) >= 10:
        score += 20
    else:
        score += 10

    return min(score, 100)


def classify_lead(score):
    if score >= 80:
        return "HOT"
    elif score >= 50:
        return "WARM"
    return "COLD"


def get_lead_action(score):
    if score >= 80:
        return {
            "priority": "URGENT",
            "action": "contact_immediately",
            "channel": "email_or_whatsapp",
            "response_time": "under_5_minutes"
        }

    if score >= 50:
        return {
            "priority": "HIGH",
            "action": "contact_today",
            "channel": "email",
            "response_time": "under_1_hour"
        }

    return {
        "priority": "NORMAL",
        "action": "automated_nurturing",
        "channel": "email",
        "response_time": "within_24_hours"
    }


def generate_sales_message(name, company, need, classification):
    first_name = name.split()[0] if name else "there"

    if classification == "HOT":
        return f"""Hi {first_name},

I saw that {company} is looking to solve this:

"{need}"

This is exactly the type of process we help businesses automate.

We can build an AI-powered system that handles lead qualification, follow-ups and appointment booking automatically, so your team spends more time closing deals.

Would you be available for a quick 15-minute call to see what this could look like for {company}?

Best,
AI Automation Team"""

    if classification == "WARM":
        return f"""Hi {first_name},

I noticed that {company} is interested in:

"{need}"

We help businesses automate repetitive sales and customer processes using AI.

I'd be happy to show you a simple approach that could fit your current workflow.

Would you be open to a quick conversation?

Best,
AI Automation Team"""

    return f"""Hi {first_name},

I noticed that {company} may be looking into:

"{need}"

We help businesses identify processes that can be simplified or automated with AI.

If this is something you're exploring, I'd be happy to share a few ideas.

Best,
AI Automation Team"""