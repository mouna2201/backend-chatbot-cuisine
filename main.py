from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os
from langdetect import detect

from logique_chatbot_smart import (
    analyser_intention,
    filtrer_par_intention,
    filtrer_par_calories,
    normaliser_tounsi
)

from dictionary_data import (
    INGREDIENT_TRANSLATIONS,
    UNIT_TRANSLATIONS,
    UI_LABELS,
    STEP_TRANSLATIONS_FR_AR
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# variables globales
toutes_recettes = []
model = None
client = None
collection = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECETTES_PATH = os.path.join(BASE_DIR, "data", "recettes.json")


@app.on_event("startup")
def startup_event():
    global toutes_recettes

    print("Démarrage...")

    try:
        with open(RECETTES_PATH, encoding="utf-8") as f:
            toutes_recettes = json.load(f)
        print("Recettes chargées ✅")
    except Exception as e:
        print("Erreur chargement recettes:", e)

    print("Startup terminé ")


@app.get("/")
def home():
    return {"status": "Chatbot cuisine en ligne !"}


class MessageRequest(BaseModel):
    message: str
    ingredients_frigo: list[str] = []
    ingredients_placard: list[str] = []


@app.post("/chat")
def chat(req: MessageRequest):
    global toutes_recettes

    tous_ingredients = req.ingredients_frigo + req.ingredients_placard
    ingredients_normalises = [normaliser_tounsi(x) for x in tous_ingredients]
    message_normalise = normaliser_tounsi(req.message)

    try:
        langue = detect(req.message)
    except:
        langue = "fr"

    if contains_arabic(req.message):
        langue = "ar"

    if langue not in ["fr", "en", "ar"]:
        langue = "fr"

    # 1) vérifier si l'utilisateur demande une recette précise
    recette_demandee = trouver_recette_par_nom(message_normalise)

    if recette_demandee:
        score, disponibles, manquants = calculer_score(recette_demandee, ingredients_normalises)

        reponse = formater_reponse_recette_precise(
            recette_demandee,
            score,
            disponibles,
            manquants,
            langue
        )

        return {
            "reponse": reponse,
            "langue": langue,
            "mode": "recette_precise",
            "recettes_trouvees": [recette_demandee["id"]],
            "liste_courses": [traduire_ingredient(x, langue) for x in manquants]
        }

    # 2) analyser intention
    intention = analyser_intention(message_normalise)

    # 3) filtrer recettes selon intention
    recettes_filtrees = filtrer_par_intention(toutes_recettes, intention)

    # 4) si healthy ou light, on peut filtrer aussi par calories
    if intention in ["light", "healthy"]:
        recettes_filtrees = filtrer_par_calories(recettes_filtrees, 400)

    # sécurité
    if not recettes_filtrees:
        recettes_filtrees = toutes_recettes

    # 5) calculer score sur toutes les recettes filtrées
    recettes_scorees = []

    for recette in recettes_filtrees:
        score, disponibles, manquants = calculer_score(recette, ingredients_normalises)

        if score > 0:
            recettes_scorees.append((recette, score, disponibles, manquants))

    # 6) si aucune recette trouvée
    if not recettes_scorees:
        labels = UI_LABELS.get(langue, UI_LABELS["fr"])
        return {
            "reponse": labels["no_recipe"],
            "langue": langue,
            "mode": "aucun_resultat",
            "recettes_trouvees": [],
            "liste_courses": []
        }

    # 7) trier par score décroissant
    recettes_scorees.sort(key=lambda x: x[1], reverse=True)

    # 8) formater la réponse
    reponse, recettes_a_afficher = formater_reponse_generale(
        recettes_scorees,
        langue,
        intention
    )

    # 9) construire la liste de courses globale
    tous_manquants = []
    for _, _, _, manquants in recettes_a_afficher:
        for ing in manquants:
            traduit = traduire_ingredient(ing, langue)
            if traduit not in tous_manquants:
                tous_manquants.append(traduit)

    return {
        "reponse": reponse,
        "langue": langue,
        "mode": "suggestion_generale",
        "intention": intention,
        "recettes_trouvees": [r[0]["id"] for r in recettes_a_afficher],
        "liste_courses": tous_manquants
    }