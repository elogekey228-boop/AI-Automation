from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.database import init_db, get_connection
from backend.models import Lead
from backend.services import (
    calculate_lead_score,
    classify_lead,
    get_lead_action,
    generate_sales_message,
)

# ============================================================
# AGENT IA (APScheduler)
# ============================================================
from apscheduler.schedulers.background import BackgroundScheduler
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# ============================================================
# APP
# ============================================================
app = FastAPI(
    title="AI Automation Engine",
    description="AI-powered lead qualification, CRM and sales automation engine",
    version="2.0.0",
)

# ============================================================
# CORS
# ============================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# MODELS
# ============================================================
class StatusUpdate(BaseModel):
    status: str

# ============================================================
# CONSTANTS
# ============================================================
ALLOWED_STATUSES = {
    "NEW",
    "CONTACTED",
    "REPLIED",
    "QUALIFIED",
    "MEETING_BOOKED",
    "WON",
    "LOST",
    "FOLLOWED_UP",  # Nouveau : pour l'agent IA
}

# ============================================================
# STARTUP & SHUTDOWN
# ============================================================
@app.on_event("startup")
def startup():
    init_db()
    # Lancer le scheduler au démarrage
    logging.info("[AGENT] Démarrage du scheduler...")
    scheduler.start()

@app.on_event("shutdown")
def shutdown():
    logging.info("[AGENT] Arrêt du scheduler...")
    scheduler.shutdown()

# ============================================================
# AGENT IA : RELANCES AUTOMATIQUES
# ============================================================
def agent_auto_relance():
    logging.info(f"[AGENT] Vérification des leads à relancer - {datetime.now()}")
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, name, email, status, score, created_at
        FROM leads
        WHERE UPPER(status) IN ('NEW', 'CONTACTED')
        AND score >= 70
        AND datetime(created_at) <= datetime('now', '-1 day')
    """).fetchall()
    conn.close()

    if not rows:
        logging.info("[AGENT] Aucun lead à relancer pour l'instant.")
        return

    for row in rows:
        lead = dict(row)
        lead_id = lead["id"]
        email = lead["email"]
        name = lead["name"]
        
        # ICI : simulation d'envoi d'email
        # Plus tard, tu connecteras Sendinblue, Resend, SMTP, etc.
        logging.info(f"📧 [AGENT] Envoi d'une relance à {name} ({email})")
        logging.info(f"   → Message : Bonjour {name}, nous n'avons pas eu de retour...")
        
        # Mettre à jour le statut pour ne pas relancer sans cesse
        conn = get_connection()
        conn.execute("UPDATE leads SET status = 'FOLLOWED_UP' WHERE id = ?", (lead_id,))
        conn.commit()
        conn.close()
        logging.info(f"[AGENT] Lead #{lead_id} passé en statut FOLLOWED_UP")

# Planification : toutes les 5 minutes (pour les tests)
# Change l'intervalle plus tard : minutes=5 → hours=1 pour la prod
scheduler = BackgroundScheduler()
scheduler.add_job(agent_auto_relance, 'interval', minutes=5)

# ============================================================
# BASIC ROUTES
# ============================================================
@app.get("/")
def home():
    return {
        "status": "online",
        "message": "AI Automation Engine is running",
        "version": "2.0.0",
    }

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AI Automation Engine",
        "version": "2.0.0",
    }

@app.get("/api")
def api_overview():
    return {
        "name": "AI Automation Engine",
        "version": "2.0.0",
        "status": "online",
        "endpoints": {
            "create_lead": "POST /leads",
            "get_leads": "GET /leads",
            "search": "GET /leads/search?q=...",
            "hot_leads": "GET /leads/hot",
            "priorities": "GET /leads/priorities",
            "follow_ups": "GET /leads/follow-ups",
            "pipeline": "GET /pipeline",
            "stats": "GET /stats",
            "dashboard": "GET /dashboard",
            "lead": "GET /leads/{lead_id}",
            "lead_action": "GET /leads/{lead_id}/action",
            "update_status": "PUT /leads/{lead_id}/status",
            "delete_lead": "DELETE /leads/{lead_id}",
            "webhook": "POST /webhook/lead-action",
        },
    }

# ============================================================
# CREATE LEAD
# ============================================================
@app.post("/leads")
def create_lead(lead: Lead):
    score = calculate_lead_score(lead.budget, lead.urgency, lead.need)
    classification = classify_lead(score)
    action = get_lead_action(score)
    message = generate_sales_message(lead.name, lead.company, lead.need, classification)

    connection = get_connection()
    cursor = connection.execute(
        """
        INSERT INTO leads
        (name, email, company, need, budget, urgency, score, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (lead.name, lead.email, lead.company, lead.need, lead.budget, lead.urgency, score, classification),
    )
    connection.commit()
    lead_id = cursor.lastrowid
    connection.close()

    return {
        "success": True,
        "lead_id": lead_id,
        "score": score,
        "classification": classification,
        "action": action,
        "sales_message": message,
    }

# ============================================================
# GET ALL LEADS (avec filtres)
# ============================================================
@app.get("/leads")
def get_leads(
    status: Optional[str] = Query(default=None),
    classification: Optional[str] = Query(default=None),
):
    connection = get_connection()
    query = """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
    """
    conditions = []
    parameters = []

    if status:
        conditions.append("UPPER(status) = ?")
        parameters.append(status.upper())

    if classification:
        upper = classification.upper()
        if upper == "HOT":
            conditions.append("score >= ?")
            parameters.append(70)
        elif upper == "WARM":
            conditions.append("score >= ? AND score < ?")
            parameters.extend([40, 70])
        elif upper == "COLD":
            conditions.append("score < ?")
            parameters.append(40)
        else:
            raise HTTPException(status_code=400, detail="classification must be HOT, WARM or COLD")

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY score DESC, created_at DESC"

    rows = connection.execute(query, parameters).fetchall()
    connection.close()

    return {
        "success": True,
        "count": len(rows),
        "leads": [dict(row) for row in rows],
    }

# ============================================================
# HOT LEADS
# ============================================================
@app.get("/leads/hot")
def get_hot_leads():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE score >= 70
        ORDER BY score DESC, created_at DESC
        """
    ).fetchall()
    connection.close()
    return {
        "success": True,
        "count": len(rows),
        "leads": [dict(row) for row in rows],
    }

# ============================================================
# SEARCH
# ============================================================
@app.get("/leads/search")
def search_leads(q: str = Query(min_length=1)):
    search = f"%{q}%"
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE name LIKE ? OR email LIKE ? OR company LIKE ? OR need LIKE ?
        ORDER BY score DESC, created_at DESC
        """,
        (search, search, search, search),
    ).fetchall()
    connection.close()
    return {
        "success": True,
        "query": q,
        "count": len(rows),
        "leads": [dict(row) for row in rows],
    }

# ============================================================
# PRIORITY ENGINE
# ============================================================
@app.get("/leads/priorities")
def get_lead_priorities():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE UPPER(status) NOT IN ('WON', 'LOST')
        ORDER BY
            score DESC,
            CASE LOWER(urgency)
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            created_at ASC
        """
    ).fetchall()
    connection.close()

    priorities = []
    for row in rows:
        lead = dict(row)
        score = lead["score"] or 0
        if score >= 70:
            priority = "URGENT"
            recommended_action = "contact_immediately"
        elif score >= 40:
            priority = "HIGH"
            recommended_action = "follow_up"
        else:
            priority = "NORMAL"
            recommended_action = "follow_up"

        priorities.append({
            "lead_id": lead["id"],
            "name": lead["name"],
            "company": lead["company"],
            "email": lead["email"],
            "score": score,
            "status": lead["status"],
            "urgency": lead["urgency"],
            "priority": priority,
            "recommended_action": recommended_action,
        })

    return {"success": True, "count": len(priorities), "priorities": priorities}

# ============================================================
# FOLLOW-UP ENGINE
# ============================================================
@app.get("/leads/follow-ups")
def get_follow_ups():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE UPPER(status) NOT IN ('WON', 'LOST')
        ORDER BY score DESC, created_at ASC
        """
    ).fetchall()
    connection.close()

    now = datetime.now()
    follow_ups = []

    for row in rows:
        lead = dict(row)
        try:
            created_at = datetime.strptime(lead["created_at"], "%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            created_at = now

        age_hours = (now - created_at).total_seconds() / 3600
        score = lead["score"] or 0
        status = str(lead["status"]).upper()

        if score >= 70:
            if status in {"HOT", "NEW"}:
                delay_hours = 0
                action = "contact_immediately"
            elif status == "CONTACTED":
                delay_hours = 24
                action = "follow_up_after_24h"
            elif status == "REPLIED":
                delay_hours = 0
                action = "respond_and_qualify"
            elif status == "QUALIFIED":
                delay_hours = 0
                action = "book_meeting"
            elif status == "MEETING_BOOKED":
                delay_hours = 24
                action = "prepare_meeting"
            else:
                delay_hours = 24
                action = "follow_up"
        elif score >= 40:
            delay_hours = 48
            action = "follow_up_after_48h"
        else:
            delay_hours = 168
            action = "follow_up_after_7_days"

        due = age_hours >= delay_hours
        next_follow_up = created_at + timedelta(hours=delay_hours)

        follow_ups.append({
            "lead_id": lead["id"],
            "name": lead["name"],
            "company": lead["company"],
            "email": lead["email"],
            "score": score,
            "status": lead["status"],
            "urgency": lead["urgency"],
            "action": action,
            "due": due,
            "age_hours": round(age_hours, 2),
            "next_follow_up": next_follow_up.strftime("%Y-%m-%d %H:%M:%S"),
        })

    due_now = [item for item in follow_ups if item["due"]]

    return {
        "success": True,
        "count": len(follow_ups),
        "due_now": len(due_now),
        "follow_ups": follow_ups,
    }

# ============================================================
# PIPELINE
# ============================================================
@app.get("/pipeline")
def get_pipeline():
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, name, company, email, budget, score, status, created_at
        FROM leads
        ORDER BY score DESC, created_at DESC
        """
    ).fetchall()
    connection.close()

    pipeline = {
        "NEW": [],
        "CONTACTED": [],
        "REPLIED": [],
        "QUALIFIED": [],
        "MEETING_BOOKED": [],
        "WON": [],
        "LOST": [],
        "FOLLOWED_UP": [],
        "OTHER": [],
    }

    for row in rows:
        lead = dict(row)
        status = str(lead["status"] or "OTHER").upper()
        if status in pipeline:
            pipeline[status].append(lead)
        else:
            pipeline["OTHER"].append(lead)

    return {"success": True, "pipeline": pipeline}

# ============================================================
# STATISTICS
# ============================================================
@app.get("/stats")
def get_stats():
    connection = get_connection()

    total = connection.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"]
    hot = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score >= 70").fetchone()["count"]
    warm = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score >= 40 AND score < 70").fetchone()["count"]
    cold = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score < 40").fetchone()["count"]
    contacted = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'CONTACTED'").fetchone()["count"]
    replied = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'REPLIED'").fetchone()["count"]
    qualified = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'QUALIFIED'").fetchone()["count"]
    meetings = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'MEETING_BOOKED'").fetchone()["count"]

    potential_revenue = connection.execute("SELECT COALESCE(SUM(budget), 0) AS total FROM leads WHERE UPPER(status) != 'LOST'").fetchone()["total"]
    won_revenue = connection.execute("SELECT COALESCE(SUM(budget), 0) AS total FROM leads WHERE UPPER(status) = 'WON'").fetchone()["total"]
    lost_revenue = connection.execute("SELECT COALESCE(SUM(budget), 0) AS total FROM leads WHERE UPPER(status) = 'LOST'").fetchone()["total"]

    connection.close()

    revenue_conversion_rate = round((won_revenue / potential_revenue) * 100, 2) if potential_revenue else 0

    return {
        "success": True,
        "stats": {
            "total_leads": total,
            "hot_leads": hot,
            "warm_leads": warm,
            "cold_leads": cold,
            "contacted": contacted,
            "replied": replied,
            "qualified": qualified,
            "meetings_booked": meetings,
            "potential_revenue": potential_revenue,
            "won_revenue": won_revenue,
            "lost_revenue": lost_revenue,
            "revenue_conversion_rate": revenue_conversion_rate,
        },
    }

# ============================================================
# DASHBOARD
# ============================================================
@app.get("/dashboard")
def dashboard():
    connection = get_connection()

    total = connection.execute("SELECT COUNT(*) AS count FROM leads").fetchone()["count"]
    active = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) NOT IN ('WON', 'LOST')").fetchone()["count"]
    hot = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score >= 70").fetchone()["count"]
    warm = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score >= 40 AND score < 70").fetchone()["count"]
    cold = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE score < 40").fetchone()["count"]
    meetings = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'MEETING_BOOKED'").fetchone()["count"]
    won = connection.execute("SELECT COUNT(*) AS count FROM leads WHERE UPPER(status) = 'WON'").fetchone()["count"]

    potential_revenue = connection.execute("SELECT COALESCE(SUM(budget), 0) AS total FROM leads WHERE UPPER(status) != 'LOST'").fetchone()["total"]
    won_revenue = connection.execute("SELECT COALESCE(SUM(budget), 0) AS total FROM leads WHERE UPPER(status) = 'WON'").fetchone()["total"]

    connection.close()

    return {
        "success": True,
        "dashboard": {
            "total_leads": total,
            "active_leads": active,
            "hot": hot,
            "warm": warm,
            "cold": cold,
            "meetings_booked": meetings,
            "won": won,
            "potential_revenue": potential_revenue,
            "won_revenue": won_revenue,
        },
    }

# ============================================================
# UPDATE STATUS
# ============================================================
@app.put("/leads/{lead_id}/status")
def update_lead_status(lead_id: int, data: StatusUpdate):
    status = data.status.strip().upper()
    if status not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid status", "allowed_statuses": sorted(ALLOWED_STATUSES)},
        )

    connection = get_connection()
    existing = connection.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if existing is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Lead not found")

    connection.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
    connection.commit()
    connection.close()

    return {"success": True, "lead_id": lead_id, "status": status, "message": "Lead status updated successfully"}

# ============================================================
# DELETE LEAD
# ============================================================
@app.delete("/leads/{lead_id}")
def delete_lead(lead_id: int):
    connection = get_connection()
    existing = connection.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if existing is None:
        connection.close()
        raise HTTPException(status_code=404, detail="Lead not found")
    connection.execute("DELETE FROM leads WHERE id = ?", (lead_id,))
    connection.commit()
    connection.close()
    return {"success": True, "message": f"Lead {lead_id} deleted"}

# ============================================================
# GET ONE LEAD
# ============================================================
@app.get("/leads/{lead_id}")
def get_lead(lead_id: int):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()
    connection.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = dict(row)
    score = lead["score"] or 0
    classification = classify_lead(score)
    action = get_lead_action(score)
    message = generate_sales_message(lead["name"], lead["company"], lead["need"], classification)

    return {
        "success": True,
        "lead": lead,
        "classification": classification,
        "action": action,
        "sales_message": message,
    }

# ============================================================
# LEAD ACTION
# ============================================================
@app.get("/leads/{lead_id}/action")
def get_lead_action_details(lead_id: int):
    connection = get_connection()
    row = connection.execute(
        """
        SELECT id, name, email, company, need, budget, urgency, score, status, created_at
        FROM leads
        WHERE id = ?
        """,
        (lead_id,),
    ).fetchone()
    connection.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead = dict(row)
    score = lead["score"] or 0
    classification = classify_lead(score)
    action = get_lead_action(score)
    message = generate_sales_message(lead["name"], lead["company"], lead["need"], classification)

    return {
        "success": True,
        "lead_id": lead_id,
        "classification": classification,
        "status": lead["status"],
        "action": action,
        "sales_message": message,
    }

# ============================================================
# WEBHOOK (pour les futurs agents externes)
# ============================================================
@app.post("/webhook/lead-action")
def webhook_lead_action(data: dict):
    lead_id = data.get("lead_id")
    action = data.get("action")
    value = data.get("value")

    if not lead_id or not action:
        raise HTTPException(status_code=400, detail="Missing lead_id or action")

    if action == "update_status":
        status = str(value).strip().upper()
        if status not in ALLOWED_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        conn = get_connection()
        existing = conn.execute("SELECT id FROM leads WHERE id = ?", (lead_id,)).fetchone()
        if existing is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Lead not found")
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (status, lead_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": f"Lead {lead_id} status updated to {status}"}

    elif action == "send_email":
        # Simulation : plus tard on connectera un vrai SMTP
        print(f"📧 [WEBHOOK] Envoi d'un email au lead {lead_id}: {value}")
        return {"success": True, "message": f"Email triggered for lead {lead_id}"}

    else:
        raise HTTPException(status_code=400, detail="Action not supported")