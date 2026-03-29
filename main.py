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

# Variables globales chargées plus tard
model = None
client = None
collection = None
toutes_recettes = []

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECETTES_PATH = os.path.join(BASE_DIR, "data", "recettes.json")

def contains_arabic(text: str) -> bool:
    return any('\u0600' <= c <= '\u06FF' for c in str(text))

def traduire_ingredient(nom, langue):
    nom_lower = str(nom).strip().lower()
    if nom_lower in INGREDIENT_TRANSLATIONS:
        if langue == "ar":
            return INGREDIENT_TRANSLATIONS[nom_lower]["ar"]
        if langue == "en":
            return INGREDIENT_TRANSLATIONS[nom_lower]["en"]
    return nom

def traduire_unite(unite, langue):
    unite = str(unite).strip()
    if unite in UNIT_TRANSLATIONS:
        if langue == "ar":
            return UNIT_TRANSLATIONS[unite]["ar"]
        if langue == "en":
            return UNIT_TRANSLATIONS[unite]["en"]
    return unite

def traduire_etape_fr_vers_ar(etape: str) -> str:
    texte = str(etape).strip()

    # remplacer d'abord les grandes expressions
    replacements = sorted(STEP_TRANSLATIONS_FR_AR.items(), key=lambda x: len(x[0]), reverse=True)

    texte_lower = texte.lower()

    for fr, ar in replacements:
        texte_lower = texte_lower.replace(fr.lower(), ar)

    # petite correction de style
    texte_lower = texte_lower.replace("  ", " ").strip()

    # majuscule arabe pas nécessaire, on renvoie direct
    if not texte_lower.endswith("."):
        texte_lower += "."

    return texte_lower

def formatter_element_ingredient(ing, langue):
    if isinstance(ing, dict):
        quantite = str(ing.get("quantite", "")).strip()
        unite = traduire_unite(ing.get("unite", ""), langue)
        nom = traduire_ingredient(ing.get("nom", ""), langue)

        if langue == "ar":
            parts = [p for p in [quantite, unite, nom] if p]
            return " ".join(parts)

        parts = [p for p in [quantite, unite, nom] if p]
        return " ".join(parts)

    return traduire_ingredient(ing, langue)

def extraire_ingredients(recette):
    if "ingredients_simple" in recette:
        return recette["ingredients_simple"]

    return [
        ing["nom"] if isinstance(ing, dict) else ing
        for ing in recette.get("ingredients", [])
    ]


def normaliser_texte(txt):
    return str(txt).strip().lower()


def ingredient_match(ingredient_recette, ingredient_dispo):
    a = normaliser_texte(ingredient_recette)
    b = normaliser_texte(ingredient_dispo)
    return a in b or b in a


def calculer_score(recette, ingredients_dispo):
    ingredients_recette = extraire_ingredients(recette)

    if not ingredients_recette:
        return 0, [], []

    disponibles = []
    manquants = []

    ingredients_recette_normalises = [normaliser_tounsi(x) for x in ingredients_recette]

    for i, ing in enumerate(ingredients_recette_normalises):
        trouve = any(ingredient_match(ing, dispo) for dispo in ingredients_dispo)
        if trouve:
            disponibles.append(ingredients_recette[i])
        else:
            manquants.append(ingredients_recette[i])

    score = int((len(disponibles) / len(ingredients_recette)) * 100)
    return score, disponibles, manquants


def get_recette_par_id(recette_id):
    for r in toutes_recettes:
        if r["id"] == recette_id:
            return r
    return None


def trouver_recette_par_nom(message):
    msg = normaliser_tounsi(message)

    for r in toutes_recettes:
        noms = [
            r.get("name", {}).get("fr", ""),
            r.get("name", {}).get("en", ""),
            r.get("name", {}).get("ar", "")
        ]

        aliases = r.get("aliases", [])
        candidats = noms + aliases

        for nom in candidats:
            if nom and normaliser_tounsi(nom) in msg:
                return r

    return None


def formatter_liste_ingredients(noms, langue):
    labels = UI_LABELS.get(langue, UI_LABELS["fr"])

    if not noms:
        return labels["none"]

    return ", ".join([traduire_ingredient(x, langue) for x in noms])


def get_steps_by_language(recette, langue):
    steps = recette.get("steps", {})

    # si arabe demandé
    if langue == "ar":
        ar_steps = steps.get("ar", [])
        
        # si on a de vraies étapes arabes, on les prend
        if ar_steps and not all(str(s).startswith("الخطوة") for s in ar_steps):
            return ar_steps

        # sinon on traduit les étapes françaises
        fr_steps = steps.get("fr", [])
        if fr_steps:
            return [traduire_etape_fr_vers_ar(step) for step in fr_steps]

        return []

    if langue == "en":
        en_steps = steps.get("en", [])
        if en_steps and not all(str(s).lower().startswith("step") for s in en_steps):
            return en_steps

    return steps.get("fr", [])


def formatter_ingredients_complets(recette, langue):
    ingredients = recette.get("ingredients", [])
    labels = UI_LABELS.get(langue, UI_LABELS["fr"])

    if not ingredients:
        return labels["none"]

    lignes = []
    for ing in ingredients:
        lignes.append(f"- {formatter_element_ingredient(ing, langue)}")

    return "\n".join(lignes)


def formater_reponse_recette_precise(recette, score, disponibles, manquants, langue):
    labels = UI_LABELS.get(langue, UI_LABELS["fr"])
    nom = recette["name"].get(langue, recette["name"].get("fr", "Recette"))
    etapes = get_steps_by_language(recette, langue)
    temps_prep = recette.get("temps_prep", "?")
    temps_cuisson = recette.get("temps_cuisson", "?")

    lines = [
        f"✅ **{nom}**",
        f"📊 **{labels['availability']}:** {score}%",
        f"⏱️ **{labels['prep']}:** {temps_prep} دقيقة | **{labels['cook']}:** {temps_cuisson} دقيقة" if langue == "ar"
        else f"⏱️ **{labels['prep']}:** {temps_prep} min | **{labels['cook']}:** {temps_cuisson} min",
        "",
        f"📋 **{labels['available']}:**",
        formatter_liste_ingredients(disponibles, langue),
        "",
        f"� **{labels['missing']}:**",
        formatter_liste_ingredients(manquants, langue) if manquants else labels["no_missing"],
        "",
        f"🥘 **{labels['all_ingredients']}:**",
        formatter_ingredients_complets(recette, langue),
        "",
        f"👨‍🍳 **{labels['steps']}:**"
    ]

    for i, e in enumerate(etapes, 1):
        lines.append(f"{i}. {e}")

    return "\n".join(lines)


def formater_reponse_generale(recettes_scorees, langue, ingredients_dispo, intention):
    recettes_a_afficher = recettes_scorees[:3]

    if langue == "ar":
        if intention == "light":
            intro = "بالمكونات المتوفرة لديك، هذه أفضل الأكلات الخفيفة الممكنة:"
        elif intention == "healthy":
            intro = "بالمكونات المتوفرة لديك، هذه أفضل الأكلات الصحية:"
        elif intention == "rapide":
            intro = "بالمكونات المتوفرة لديك، هذه أفضل الوصفات السريعة:"
        else:
            intro = "بالمكونات المتوفرة لديك، هذه أفضل الوصفات الممكنة:"
    elif langue == "en":
        if intention == "light":
            intro = "With your ingredients, here are the best light recipes:"
        elif intention == "healthy":
            intro = "With your ingredients, here are the best healthy recipes:"
        elif intention == "rapide":
            intro = "With your ingredients, here are the best quick recipes:"
        else:
            intro = "With your ingredients, here are the best possible recipes:"
    else:
        if intention == "light":
            intro = "Avec les ingrédients disponibles, voici les meilleures recettes légères :"
        elif intention == "healthy":
            intro = "Avec les ingrédients disponibles, voici les meilleures recettes healthy :"
        elif intention == "rapide":
            intro = "Avec les ingrédients disponibles, voici les meilleures recettes rapides :"
        else:
            intro = "Avec les ingrédients disponibles, voici les meilleures recettes possibles :"

    parties = [intro, ""]

    for recette, score, disponibles, manquants in recettes_a_afficher:
        nom = recette["name"].get(langue, recette["name"].get("fr", "Recette"))

        if langue == "ar":
            parties += [
                f"✅ **{nom}** — {score}%",
                f"📋 متوفر: {', '.join(disponibles) if disponibles else 'لا شيء'}",
                f"🛒 ناقص: {', '.join(manquants) if manquants else 'لا شيء'}",
                ""
            ]
        elif langue == "en":
            parties += [
                f"✅ **{nom}** — {score}%",
                f"📋 Available: {', '.join(disponibles) if disponibles else 'none'}",
                f"🛒 Missing: {', '.join(manquants) if manquants else 'none'}",
                ""
            ]
        else:
            parties += [
                f"✅ **{nom}** — {score}%",
                f"📋 Disponibles : {', '.join(disponibles) if disponibles else 'aucun'}",
                f"🛒 Manquants : {', '.join(manquants) if manquants else 'aucun'}",
                ""
            ]

    return "\n".join(parties), recettes_a_afficher


class MessageRequest(BaseModel):
    message: str
    ingredients_frigo: list[str] = []
    ingredients_placard: list[str] = []


@app.get("/")
def home():
    return {"status": "Chatbot cuisine en ligne !"}


@app.post("/chat")
def chat(req: MessageRequest):
    # Sécurité : vérifier que les données sont chargées
    if not toutes_recettes:
        return {
            "reponse": "Les recettes ne sont pas encore chargées.",
            "langue": "fr",
            "mode": "erreur",
            "recettes_trouvees": [],
            "liste_courses": []
        }

    # Sécurité : vérifier que le modèle et la collection sont disponibles
    if model is None or collection is None:
        return {
            "reponse": "Le modèle ou la collection n'est pas disponible.",
            "langue": "fr",
            "mode": "erreur",
            "recettes_trouvees": [],
            "liste_courses": []
        }

    tous_ingredients = req.ingredients_frigo + req.ingredients_placard
    message_normalise = normaliser_tounsi(req.message)
    ingredients_normalises = [normaliser_tounsi(x) for x in tous_ingredients]

    try:
        langue = detect(req.message)
    except:
        langue = "fr"

    if contains_arabic(req.message):
        langue = "ar"

    if langue not in ["fr", "en", "ar"]:
        langue = "fr"

    recette_demandee = trouver_recette_par_nom(message_normalise)

    if recette_demandee:
        score, disponibles, manquants = calculer_score(recette_demandee, tous_ingredients)

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
            "liste_courses": manquants
        }

    intention = analyser_intention(message_normalise)

    recettes_filtrees = filtrer_par_intention(toutes_recettes, intention)

    if intention in ["light", "healthy"]:
        recettes_filtrees = filtrer_par_calories(recettes_filtrees, 400)

    if not recettes_filtrees:
        recettes_filtrees = toutes_recettes

    recettes_scorees = []

    for recette in recettes_filtrees:
        score, disponibles, manquants = calculer_score(recette, ingredients_normalises)
        if score > 0:
            recettes_scorees.append((recette, score, disponibles, manquants))

    if not recettes_scorees:
        return {
            "reponse": "Aucune recette adaptée n'a été trouvée avec les ingrédients disponibles.",
            "langue": langue,
            "mode": "aucun_resultat",
            "recettes_trouvees": [],
            "liste_courses": []
        }

    recettes_scorees.sort(key=lambda x: x[1], reverse=True)

    reponse, recettes_a_afficher = formater_reponse_generale(
        recettes_scorees,
        langue,
        tous_ingredients,
        intention
    )

    tous_manquants = []
    for _, _, _, manquants in recettes_a_afficher:
        tous_manquants.update(manquants)

    return {
        "reponse": reponse,
        "langue": langue,
        "mode": "suggestion_generale",
        "intention": intention,
        "recettes_trouvees": [r[0]["id"] for r in recettes_a_afficher],
        "liste_courses": list(tous_manquants)
    }


@app.on_event("startup")
def startup_event():
    global toutes_recettes

    print("Démarrage...")

    try:
        with open(RECETTES_PATH, encoding="utf-8") as f:
            toutes_recettes = json.load(f)
        print("Recettes chargées ")
    except Exception as e:
        print("Erreur chargement recettes:", e)

    print("Startup terminé ")