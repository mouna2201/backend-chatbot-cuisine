import chromadb
import json
from sentence_transformers import SentenceTransformer

print("Chargement du modèle...")
model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

print("Connexion à Chroma...")
client = chromadb.PersistentClient(path="./chroma_db")

# Supprimer l'ancienne collection si elle existe
try:
    client.delete_collection("recettes")
    print("Ancienne collection supprimée.")
except:
    pass

collection = client.get_or_create_collection("recettes")

print("Chargement des recettes...")
with open("data/recettes.json", encoding="utf-8") as f:
    recettes = json.load(f)

print(f"{len(recettes)} recettes trouvées. Vectorisation en cours...")

for r in recettes:
    # noms d'ingrédients
    if "ingredients_simple" in r:
        ingredients = r["ingredients_simple"]
    else:
        ingredients = [
            ing["nom"] if isinstance(ing, dict) else ing
            for ing in r.get("ingredients", [])
        ]

    nom_fr = r.get("name", {}).get("fr", "")
    nom_en = r.get("name", {}).get("en", "")
    nom_ar = r.get("name", {}).get("ar", "")
    aliases = ", ".join(r.get("aliases", []))
    tags = ", ".join(r.get("tags", []))

    texte = f"""
    Nom FR: {nom_fr}
    Nom EN: {nom_en}
    Nom AR: {nom_ar}
    Aliases: {aliases}
    Ingrédients: {", ".join(ingredients)}
    Tags: {tags}
    """.strip()

    embedding = model.encode(texte).tolist()

    collection.add(
        documents=[texte],
        embeddings=[embedding],
        ids=[r["id"]],
        metadatas=[{
            "nom_fr": nom_fr,
            "tags": tags,
            "difficulte": str(r.get("difficulte", "")),
            "temps_prep": str(r.get("temps_prep", "")),
            "temps_cuisson": str(r.get("temps_cuisson", ""))
        }]
    )

    print(f"✓ {nom_fr}")

print("\nVectorisation terminée avec succès.")