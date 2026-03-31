from pymongo import MongoClient
from datetime import datetime
import os

MONGO_URI = os.getenv("MONGO_URI", "")

_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None and MONGO_URI:
        try:
            _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            _db = _client["chatbot_cuisine"]
            print("MongoDB connecté ✅")
        except Exception as e:
            print(f"Erreur MongoDB : {e}")
            _db = None
    return _db


def sauvegarder_conversation(
    user_id: str,
    message: str,
    reponse: str,
    langue: str,
    recettes_ids: list,
    liste_courses: list,
    ingredients: list,
):
    db = get_db()
    if db is None:
        return False
    try:
        db["historique"].insert_one({
            "user_id": user_id,
            "message": message,
            "reponse": reponse,
            "langue": langue,
            "recettes_ids": recettes_ids,
            "liste_courses": liste_courses,
            "ingredients": ingredients,
            "date": datetime.utcnow(),
        })
        return True
    except Exception as e:
        print(f"Erreur sauvegarde conversation : {e}")
        return False


def sauvegarder_notation(
    user_id: str,
    recette_id: str,
    recette_nom: str,
    etoiles: int,
    commentaire: str = "",
):
    db = get_db()
    if db is None:
        return False
    try:
        db["notations"].update_one(
            {"user_id": user_id, "recette_id": recette_id},
            {"$set": {
                "recette_nom": recette_nom,
                "etoiles": etoiles,
                "commentaire": commentaire,
                "date": datetime.utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception as e:
        print(f"Erreur sauvegarde notation : {e}")
        return False


def charger_historique(user_id: str, limite: int = 20):
    db = get_db()
    if db is None:
        return []
    try:
        cursor = db["historique"].find(
            {"user_id": user_id},
            sort=[("date", -1)],
            limit=limite,
        )
        result = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["date"] = doc["date"].isoformat()
            result.append(doc)
        return result
    except Exception as e:
        print(f"Erreur chargement historique : {e}")
        return []


def charger_notations(user_id: str):
    db = get_db()
    if db is None:
        return []
    try:
        cursor = db["notations"].find(
            {"user_id": user_id},
            sort=[("date", -1)],
        )
        result = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            doc["date"] = doc["date"].isoformat()
            result.append(doc)
        return result
    except Exception as e:
        print(f"Erreur chargement notations : {e}")
        return []


def supprimer_notation(user_id: str, recette_id: str):
    db = get_db()
    if db is None:
        return False
    try:
        db["notations"].delete_one(
            {"user_id": user_id, "recette_id": recette_id}
        )
        return True
    except Exception as e:
        print(f"Erreur suppression notation : {e}")
        return False