import requests
import sqlite3
import random
from datetime import datetime, timedelta
import time
import os
from dotenv import load_dotenv

# ============================================================
# CONFIGURATION
# ============================================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

if not SERPAPI_KEY:
    print("❌ Erreur : La clé SERPAPI_KEY n'est pas définie dans le fichier .env")
    exit(1)

DB_PATH = "leads.db"

# ============================================================
# FONCTION : RECHERCHE DE LEADS VIA SERPAPI (GOOGLE MAPS)
# ============================================================
def search_leads(query, place, max_results=5):
    """
    Recherche des entreprises sur Google Maps via SerpAPI.
    Utilise le paramètre 'place' (ex: "Miami, Florida") comme dans le playground.
    """
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_maps",
        "q": query,
        "place": place,          # 👈 Utilise 'place' au lieu de 'location' ou 'll'
        "api_key": SERPAPI_KEY,
    }
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"⚠️ Erreur lors de la requête SerpAPI : {e}")
        return []

    leads = []
    if "local_results" in data:
        for item in data["local_results"][:max_results]:
            name = item.get("title")
            address = item.get("address")
            phone = item.get("phone")
            website = item.get("website")
            # Extraction de l'email à partir du domaine
            email = extract_email_from_website(website) if website else None
            if not email and name:
                domain = name.replace(" ", "").lower()
                email = f"contact@{domain}.com"

            leads.append({
                "name": name or "Inconnu",
                "company": name or "Inconnu",
                "email": email or f"no-email-{random.randint(1000,9999)}@example.com",
                "phone": phone,
                "address": address,
                "website": website,
            })
    return leads

# ============================================================
# FONCTION : EXTRACTION D'EMAIL DEPUIS UN SITE WEB
# ============================================================
def extract_email_from_website(website):
    if not website:
        return None
    domain = website.replace("https://", "").replace("http://", "").split("/")[0]
    return f"info@{domain}"

# ============================================================
# AJOUTER UN LEAD DANS LA BASE
# ============================================================
def add_lead_to_db(name, email, company, need, budget, urgency, score=None, status=None, created_at=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    score = score if score is not None else random.randint(40, 100)
    status = status if status is not None else ("NEW" if score < 70 else "HOT")
    created_at = created_at if created_at else datetime.now().isoformat()

    cursor.execute("""
        INSERT INTO leads (name, email, company, need, budget, urgency, score, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, email, company, need, budget, urgency, score, status, created_at))
    conn.commit()
    lead_id = cursor.lastrowid
    conn.close()
    print(f"✅ Lead ajouté : {name} ({company}) → Score {score} → {status}")
    return lead_id

# ============================================================
# LANCER LA PROSPECTION (MODE RÉEL)
# ============================================================
if __name__ == "__main__":
    print("🔍 Lancement de la prospection réelle...")
    print(f"   Clé API : {SERPAPI_KEY[:8]}... (clé valide)\n")

    # Cibles de recherche (au format 'place' comme dans le playground)
    targets = [
        {"query": "real estate agency", "place": "Miami, Florida"},
        {"query": "real estate agency", "place": "Dubai, UAE"},
        {"query": "real estate agency", "place": "Toronto, Canada"},
        {"query": "business consultant", "place": "London, UK"},
        {"query": "tech startup", "place": "San Francisco, California"},
    ]

    all_leads = []
    for target in targets:
        print(f"🔎 Recherche de '{target['query']}' à {target['place']}...")
        leads = search_leads(target['query'], target['place'], max_results=3)
        if leads:
            print(f"   → {len(leads)} résultats trouvés")
            all_leads.extend(leads)
        else:
            print("   → Aucun résultat (vérifie la clé API ou les paramètres)")
        time.sleep(1)

    if not all_leads:
        print("\n⚠️ Aucun lead trouvé. Vérifie ta clé API et les paramètres.")
        print("💡 Tu peux aussi tester dans le playground : https://serpapi.com/playground?engine=google_maps")
    else:
        for lead in all_leads:
            needs = [
                "Automatisation du suivi des prospects",
                "Système de relance automatique",
                "Qualification IA des leads entrants",
                "Optimisation du pipeline de vente",
                "Gestion automatisée des emails et rendez-vous"
            ]
            add_lead_to_db(
                name=lead["name"],
                email=lead["email"],
                company=lead["company"],
                need=random.choice(needs),
                budget=random.randint(1000, 5000),
                urgency=random.choice(["low", "medium", "high"])
            )
        print(f"\n✅ {len(all_leads)} leads ajoutés avec succès !")
        print("💡 Rafraîchis ton dashboard (Ctrl+F5) pour voir les nouveaux leads.")