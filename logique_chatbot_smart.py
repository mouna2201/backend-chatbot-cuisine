import re


# =========================
# DICTIONNAIRES TOUNSI
# =========================

TOUNSI_WORDS = {
    "nheb": "je veux",
    "nhb": "je veux",
    "chnoua": "quoi",
    "chnowa": "quoi",
    "chniya": "quoi",
    "najem": "je peux",
    "naamel": "faire",
    "n3amel": "faire",
    "bel": "avec",
    "b": "avec",
    "maa": "avec",
    "m3a": "avec",
    "haja": "plat",
    "akla": "plat",
    "khfifa": "light",
    "khfif": "light",
    "s7i": "healthy",
    "sa7i": "healthy",
    "se7i": "healthy",
    "sariaa": "rapide",
    "sari3": "rapide",
    "sra3": "rapide",
    "bsif": "épicé",
    "har": "épicé",
    "ma9la": "frit",
    "maqli": "frit",
    "meshwi": "grillé",
    "machwi": "grillé",
    "lahma": "viande",
    "l7am": "viande",
    "djaj": "poulet",
    "djej": "poulet",
    "ton": "thon",
    "toun": "thon",
    "batata": "pommes de terre",
    "btata": "pommes de terre",
    "maticha": "tomates",
    "tomatich": "tomates",
    "felfel": "poivrons",
    "besla": "oignon",
    "thoum": "ail",
    "aadhma": "oeufs",
    "bidh": "oeufs",
    "khobz": "pain",
    "ma9rouna": "pâtes",
    "makarouna": "pâtes",
    "rouz": "riz",
    "roz": "riz",
    "hommos": "pois chiches",
    "loubia": "haricots blancs",
    "zit zitouna": "huile d'olive",
    "zit": "huile",
    "7arissa": "harissa",
    "hrissa": "harissa",
    "fromage": "fromage"
}


TOUNSI_PATTERNS = {
    r"\bnheb haja khfifa\b": "je veux un plat light",
    r"\bnheb haja s7iya\b": "je veux un plat healthy",
    r"\bnheb haja sariaa\b": "je veux une recette rapide",
    r"\bchnoua najem naamel\b": "que puis-je cuisiner",
    r"\bchnoua naamel\b": "que puis-je cuisiner",
    r"\bnheb haja bel\b": "je veux une recette avec ",
    r"\bnheb recette bel\b": "je veux une recette avec ",
    r"\bma nhebch lahma\b": "sans viande",
    r"\bmanhebch lahma\b": "sans viande",
    r"\bnheb haja protéiné\b": "je veux une recette protéinée",
    r"\bnheb haja lel regime\b": "je veux une recette light",
    r"\bnheb haja diet\b": "je veux une recette light"
}


# =========================
# NORMALISATION
# =========================

def nettoyer_message(message: str) -> str:
    msg = message.lower().strip()

    replacements = {
        "é": "e",
        "è": "e",
        "ê": "e",
        "à": "a",
        "â": "a",
        "î": "i",
        "ï": "i",
        "ô": "o",
        "ù": "u",
        "û": "u",
        "ç": "c",
        "’": "'"
    }

    for a, b in replacements.items():
        msg = msg.replace(a, b)

    msg = re.sub(r"\s+", " ", msg)
    return msg


def normaliser_tounsi(message: str) -> str:
    msg = nettoyer_message(message)

    # expressions complètes d'abord
    for pattern, replacement in TOUNSI_PATTERNS.items():
        msg = re.sub(pattern, replacement, msg)

    # mots simples ensuite
    words = msg.split()
    normalized_words = []

    for w in words:
        normalized_words.append(TOUNSI_WORDS.get(w, w))

    msg = " ".join(normalized_words)
    msg = re.sub(r"\s+", " ", msg).strip()
    return msg


# =========================
# INTENTION
# =========================

def analyser_intention(message: str):
    msg = normaliser_tounsi(message)

    if any(x in msg for x in [
        "light", "leger", "legere", "plat light"
    ]):
        return "light"

    if any(x in msg for x in [
        "healthy", "sante", "plat healthy"
    ]):
        return "healthy"

    if any(x in msg for x in [
        "rapide", "vite", "quick"
    ]):
        return "rapide"

    if any(x in msg for x in [
        "sans viande", "vegetarien", "vegetarian", "veg"
    ]):
        return "vegetarien"

    if any(x in msg for x in [
        "proteine", "proteinee", "protein", "muscle", "sport"
    ]):
        return "proteine"

    if any(x in msg for x in [
        "pas cher", "economique", "cheap", "budget"
    ]):
        return "budget"

    return "normal"


# =========================
# INGREDIENTS
# =========================

def extraire_noms_ingredients(recette):
    noms = []
    for ing in recette.get("ingredients", []):
        if isinstance(ing, dict):
            noms.append(str(ing.get("nom", "")).lower())
        else:
            noms.append(str(ing).lower())
    return noms


def normaliser_ingredient_user(ingredient: str) -> str:
    return normaliser_tounsi(ingredient)


def filtrer_par_intention(recettes, intention):
    if intention == "light":
        return [
            r for r in recettes
            if r.get("nutrition", {}).get("light") is True
        ]

    if intention == "healthy":
        return [
            r for r in recettes
            if r.get("nutrition", {}).get("healthy") is True
        ]

    if intention == "rapide":
        return [
            r for r in recettes
            if r.get("temps_cuisson", 999) <= 20
        ]

    if intention == "vegetarien":
        mots_viande = ["poulet", "viande", "merguez", "thon", "boeuf", "bœuf", "agneau"]
        resultat = []

        for r in recettes:
            noms = extraire_noms_ingredients(r)
            texte = " ".join(noms)
            if not any(v in texte for v in mots_viande):
                resultat.append(r)

        return resultat

    if intention == "proteine":
        mots_prot = ["oeufs", "œufs", "thon", "poulet", "viande", "merguez", "pois chiches", "boeuf", "bœuf"]
        resultat = []

        for r in recettes:
            noms = extraire_noms_ingredients(r)
            texte = " ".join(noms)
            if any(v in texte for v in mots_prot):
                resultat.append(r)

        return resultat

    if intention == "budget":
        return [
            r for r in recettes
            if r.get("nutrition", {}).get("calories", 999) <= 450
        ]

    return recettes


def filtrer_par_calories(recettes, max_calories=400):
    return [
        r for r in recettes
        if r.get("nutrition", {}).get("calories", 999) <= max_calories
    ]