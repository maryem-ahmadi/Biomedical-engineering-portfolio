# ============================================================
# CHATBOT IA PEDIATRIQUE
# Extrait de app(2).ipynb pour intégration dans Flask
# ============================================================
# IMPORTANT :
# - Aucun pip install ici.
# - Le modèle Mistral est chargé une seule fois au démarrage de Flask.
# - Le dossier mes_documents_word doit être placé à la racine du projet.
# ============================================================

import os
import re
import numpy as np
import torch

from docx import Document as DocxDocument

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import (
    HuggingFaceEmbeddings,
    HuggingFacePipeline,
    ChatHuggingFace,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.output_parsers import StrOutputParser

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline,
)


# ============================================================
# LECTURE DES DOCUMENTS WORD
# ============================================================


def est_titre_section(paragraph) -> bool:
    texte = paragraph.text.strip()
    if not texte:
        return False
    if paragraph.style and paragraph.style.name and "Heading" in paragraph.style.name:
        return True
    if len(texte) < 60 and paragraph.runs:
        runs_non_vides = [r for r in paragraph.runs if r.text.strip()]
        if runs_non_vides and all(r.bold for r in runs_non_vides):
            return True
    return False


def est_puce(paragraph) -> bool:
    texte = paragraph.text.strip()
    if not texte:
        return False
    pPr = paragraph._p.pPr
    if pPr is not None and pPr.numPr is not None:
        return True
    return bool(re.match(r"^[-•*]\s+", texte))


def nettoyer_puce(texte: str) -> str:
    return re.sub(r"^[-•*]\s+", "", texte).strip()


def parser_docx_par_sections(chemin_fichier: str) -> dict:
    doc = DocxDocument(chemin_fichier)
    sections = {}
    titre_courant = "Général"
    sections[titre_courant] = []

    for paragraph in doc.paragraphs:
        texte = paragraph.text.strip()
        if not texte:
            continue
        if est_titre_section(paragraph):
            titre_courant = texte.rstrip(":").strip()
            sections.setdefault(titre_courant, [])
        else:
            sections[titre_courant].append(texte)

    return {titre: "\n".join(paras) for titre, paras in sections.items() if paras}


def critere_valide(texte: str) -> bool:
    t = texte.strip()
    if not t or len(t) > 140:
        return False
    if t.endswith(":"):
        return False
    phrases_meta = [
        "diagnostic est clinique", "sans besoin d'examen", "associe typiquement",
        "les signes évocateurs", "doivent alerter", "il faut consulter",
    ]
    t_lower = t.lower()
    if any(p in t_lower for p in phrases_meta):
        return False
    return True


def extraire_criteres_symptomes(chemin_fichier: str) -> list[str]:
    doc = DocxDocument(chemin_fichier)
    dans_section_symptomes = False
    criteres = []

    for paragraph in doc.paragraphs:
        texte = paragraph.text.strip()
        if not texte:
            continue
        if est_titre_section(paragraph):
            dans_section_symptomes = "sympt" in texte.lower()
            continue
        if dans_section_symptomes:
            texte_propre = nettoyer_puce(texte) if est_puce(paragraph) else texte
            if critere_valide(texte_propre):
                criteres.append(texte_propre)

    return criteres


def nom_maladie_depuis_fichier(chemin_fichier: str) -> str:
    base = os.path.splitext(os.path.basename(chemin_fichier))[0]
    base = re.sub(r"[_\-]+", " ", base).strip()
    return base.capitalize()
def charger_documents_structures(dossier_docs: str) -> list[Document]:
    """Charge tous les fichiers .docx du dossier, parse leurs sections
    et remplit le dictionnaire global criteres_par_maladie."""
    docs_charges = []
    
    if not os.path.exists(dossier_docs):
        return docs_charges

    for fichier in os.listdir(dossier_docs):
        if fichier.endswith(".docx") and not fichier.startswith("~$"):
            chemin_complet = os.path.join(dossier_docs, fichier)
            maladie = nom_maladie_depuis_fichier(chemin_complet)
            
            # Extraction des critères spécifiques pour la logique de triage
            criteres_par_maladie[maladie] = extraire_criteres_symptomes(chemin_complet)
            
            # Parsing des sections pour le RAG
            sections = parser_docx_par_sections(chemin_complet)
            for section, contenu in sections.items():
                docs_charges.append(
                    Document(
                        page_content=contenu,
                        metadata={"maladie": maladie, "section": section}
                    )
                )
    return docs_charges

# ============================================================
# CHARGEMENT DES DOCUMENTS ET CREATION DE FAISS
# ============================================================

DOCS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "mes_documents_word"
)

if not os.path.exists(DOCS_DIR):
    raise FileNotFoundError(
        f"Le dossier 'mes_documents_word' n'existe pas. "
        f"Chemin recherché : {os.path.abspath(DOCS_DIR)}"
    )

criteres_par_maladie = {}
split_documents = charger_documents_structures(DOCS_DIR)

if len(split_documents) == 0:
    raise ValueError(
        "Aucun contenu n'a été chargé depuis les fichiers Word. "
        "Vérifiez le dossier mes_documents_word."
    )

print(f"Nombre total de documents chargés : {len(split_documents)}")

print("Chargement du modèle d'embeddings...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
print("Modèle d'embeddings chargé.")

print("Création de la base vectorielle FAISS...")
vectorstore = FAISS.from_documents(
    documents=split_documents,
    embedding=embeddings
)
print("Base FAISS créée avec succès !")
print("Maladies chargées :", list(criteres_par_maladie.keys()))


# ============================================================
# TRIAGE ET ANALYSE DES SYMPTOMES
# ============================================================


import re
import numpy as np

import unicodedata

def normaliser_accents(texte: str) -> str:
    nfkd = unicodedata.normalize('NFKD', texte)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


QUESTIONS_TRIAGE_GENERIQUES = [
    ("age", "Quel est l'âge de votre bébé ?", [r"\d+\s*(ans?|mois)"]),
    ("duree_symptomes", "Depuis combien de temps les symptômes durent-ils ?", [
        r"depuis\s*\d+\s*jour",
        r"\d+\s*jours?",
        r"\d+\s*semaines?",
    ]),
    ("fievre", "Votre bébé a-t-il de la fièvre ? Si oui, à quelle température ?", [
        r"\d{1,2}[.,]?\d?\s*°?c\b",
        r"\d{1,2}[.,]?\d?\s*degr",
    ]),
]

def _racine(mot: str) -> str:
    mot = mot.lower().strip()
    mot = re.sub(r"[^a-zàâäéèêëïîôöùûüç]", "", mot)
    for suffixe in ("issement", "ation", "ante", "ant", "eux", "euse", "ent", "e", "s", "es"):
        if len(mot) - len(suffixe) >= 4 and mot.endswith(suffixe):
            mot = mot[: -len(suffixe)]
            break
    return mot

mots_vides = {"de", "du", "la", "le", "les", "un", "une", "et", "ou", "avec", "sans",
              "chez", "sur", "dans", "en", "possible", "parfois", "souvent", "des",
              "au", "aux", "ce", "cette", "ces", "que", "qui", "il", "elle"}

_embedding_cache = {}

def _cosine_sim(a, b) -> float:
    a, b = np.array(a), np.array(b)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-8
    return float(np.dot(a, b) / denom)

def _embed_cache(texte: str):
    if texte not in _embedding_cache:
        _embedding_cache[texte] = embeddings.embed_query(texte)
    return _embedding_cache[texte]
MOTS_CLES_TROP_GENERIQUES = {
    "pleurs", "pleure", "pleurent", "irritable", "irritabilite", "agitation",
    "fatigue", "fievre", "appetit", "sommeil", "troubles", "faiblesse",
    "possible", "legere", "leger", "parfois", "souvent", "intenses",
    "intense", "journee", "soiree", "chez",
    # mots temporels/quantitatifs génériques, source de faux positifs
    "jour", "jours", "heure", "heures", "semaine", "semaines",
    "mois", "fois", "temps", "depuis", "avant", "apres", "encore",
    "toujours", "jamais", "aussi", "meme", "tres", "beaucoup", "plus", "moins",
}

def extraire_mots_cles(critere: str) -> list[str]:
    mots = re.findall(r"[a-zàâäéèêëïîôöùûüç]+", critere.lower())
    mots_vides = {"de", "du", "la", "le", "les", "un", "une", "et", "ou", "avec", "sans",
                  "chez", "sur", "dans", "en", "possible", "parfois", "souvent", "des",
                  "au", "aux", "ce", "cette", "ces", "que", "qui", "il", "elle",
                  "bébé", "bebe", "enfant", "nourrisson"}
    mots_filtres = [m for m in mots if len(m) > 3 and m not in mots_vides]
    generiques_racines = {_racine(g) for g in MOTS_CLES_TROP_GENERIQUES}
    return [m for m in mots_filtres if _racine(m) not in generiques_racines]
def etat_symptomes(historique_texte: str, criteres: list[str], seuil: float = 0.65,
                    forces_connus: set[str] | None = None,
                    forces_ecartes: set[str] | None = None):
    forces_connus = forces_connus or set()
    forces_ecartes = forces_ecartes or set()

    phrases = [p.strip() for p in historique_texte.split("\n") if p.strip()]
    texte_complet_lower = historique_texte.lower()
    emb_phrases = [_embed_cache(p) for p in phrases] if phrases else []

    connus, manquants = [], []
    for critere in criteres:
        if critere in forces_connus:
            connus.append(critere)
            continue
        if critere in forces_ecartes:
            continue

        # 1. Match direct si N'IMPORTE LEQUEL des mots-clés du critère apparaît dans le texte
        mots_cles = extraire_mots_cles(critere)
        match_mot_cle = any(mc in texte_complet_lower for mc in mots_cles)

        # 2. Match sémantique (paraphrases)
        match_semantique = False
        if emb_phrases:
            emb_critere = _embed_cache(critere)
            meilleur_score = max(_cosine_sim(emb_critere, ep) for ep in emb_phrases)
            match_semantique = meilleur_score >= seuil

        if match_mot_cle or match_semantique:
            connus.append(critere)
        else:
            manquants.append(critere)

    return connus, manquants


def classer_maladies_par_symptomes(historique_texte: str, session_id: str = None) -> list[tuple[str, int, list[str]]]:
    forces_connus = criteres_confirmes_par_session.get(session_id, set()) if session_id else set()
    forces_ecartes = criteres_ecartes_par_session.get(session_id, set()) if session_id else set()

    resultats = []
    for maladie, criteres in criteres_par_maladie.items():
        connus, manquants = etat_symptomes(
            historique_texte, criteres,
            forces_connus=forces_connus, forces_ecartes=forces_ecartes
        )
        resultats.append((maladie, len(connus), manquants))
    resultats.sort(key=lambda t: t[1], reverse=True)
    return resultats


def questions_triage_manquantes(historique_texte: str) -> list[str]:
    texte_normalise = normaliser_accents(historique_texte.lower())
    manquantes = []
    for _cle, question, patterns in QUESTIONS_TRIAGE_GENERIQUES:
        deja_repondu = any(re.search(p, texte_normalise) for p in patterns)
        if not deja_repondu:
            manquantes.append(question)
    return manquantes


def maladies_candidates(historique_texte: str, session_id: str = None, top_n: int = 6) -> list[str]:
    classement = classer_maladies_par_symptomes(historique_texte, session_id=session_id)
    candidats_positifs = [m for m, nb, _ in classement if nb > 0]
    if candidats_positifs:
        return candidats_positifs[:top_n]
    return [m for m, _, _ in classement]


def prochaine_question_candidats(historique_texte: str, candidats: list[str],
                                   forces_connus=None, forces_ecartes=None):
    forces_connus = forces_connus or set()
    forces_ecartes = forces_ecartes or set()

    derniere_phrase = [p for p in historique_texte.split("\n") if p.strip()]
    derniere_phrase = derniere_phrase[-1] if derniere_phrase else ""
    emb_derniere = _embed_cache(derniere_phrase) if derniere_phrase else None

    meilleur_critere, meilleur_score = None, -1

    for m in candidats:
        criteres = criteres_par_maladie.get(m, [])
        _connus, manquants = etat_symptomes(
            historique_texte, criteres,
            forces_connus=forces_connus, forces_ecartes=forces_ecartes
        )
        for critere in manquants:
            if emb_derniere is not None:
                score = _cosine_sim(_embed_cache(critere), emb_derniere)
            else:
                score = 0
            if score > meilleur_score:
                meilleur_score = score
                meilleur_critere = critere

    return meilleur_critere


def normaliser_reponse_courte(texte: str) -> str | None:
    t = texte.strip().lower().rstrip(".!")
    t_nettoye = re.sub(r"[,]", " ", t)
    mots = t_nettoye.split()

    if not mots:
        return None

    premier_mot = mots[0]
    if premier_mot in {"oui", "ouais", "exact", "affirmatif", "voilà"}:
        return "oui"
    if premier_mot in {"non", "jamais", "aucun", "aucune"}:
        return "non"
    if t in {"c'est ça", "tout à fait", "pas vraiment", "pas trop", "pas du tout"}:
        return "non" if "pas" in t else "oui"

    return None


questions_posees_compteur = {}
MAX_QUESTIONS_SPECIFIQUES = 5


maladie_verrouillee_par_session = {}

def get_symptomes_avec_score(requete_complete: str, k: int = 8):
    resultats = vectorstore.similarity_search_with_score(requete_complete, k=k)
    return [
        (doc, score) for doc, score in resultats
        if "sympt" in doc.metadata.get("section", "").lower()
    ]

def identifier_maladie_avec_verrouillage(
    session_id: str,
    requete_complete: str,
    min_symptomes_specifiques: int = 2,
    marge_min_symptomes: int = 1,
):
    if session_id in maladie_verrouillee_par_session:
        return maladie_verrouillee_par_session[session_id], True

    if questions_triage_manquantes(requete_complete):
        return None, False

    classement = classer_maladies_par_symptomes(requete_complete, session_id=session_id)  # <-- corrigé ici
    if not classement:
        return None, False

    meilleure_maladie, meilleur_nb, _ = classement[0]

    assez_confiant = meilleur_nb >= min_symptomes_specifiques
    assez_distinct = True
    if len(classement) > 1:
        deuxieme_nb = classement[1][1]
        assez_distinct = (meilleur_nb - deuxieme_nb) >= marge_min_symptomes

    if assez_confiant and assez_distinct:
        maladie_verrouillee_par_session[session_id] = meilleure_maladie
        return meilleure_maladie, True

    return None, False


def format_symptomes(docs):
    if not docs:
        return "Aucune information de symptômes trouvée."
    blocs = []
    for doc in docs:
        blocs.append(f"[Maladie: {doc.metadata['maladie']}] - Symptômes:\n{doc.page_content}")
    return "\n\n".join(blocs)


def get_symptomes_pertinents_pour_contexte(session_id: str, historique_texte: str, k: int = 2):
    maladie, verrouillee = identifier_maladie_avec_verrouillage(session_id, historique_texte)
    resultats = get_symptomes_avec_score(historique_texte, k=k * 4)

    if verrouillee and maladie:
        docs_filtres = [doc for doc, _ in resultats if doc.metadata["maladie"] == maladie]
    else:
        docs_filtres = [doc for doc, _ in resultats]

    return docs_filtres[:k]




SIGNES_GRAVITE_PATTERNS = {
    "difficulté respiratoire": [
        r"(du mal|difficile|difficult\w*|peine|n'arrive pas bien)\s+(?:à|a)\s+respirer",
        r"respir\w*\s+(difficilement|mal|très vite|rapidement)",
        r"manque\w*\s+d.?air",
        r"respiration\s+(difficile|rapide|sifflante|très rapide)",
        r"essoufl\w*",
        r"peine\s+à\s+respirer",
    ],
    "cyanose (coloration bleutée)": [
        r"lèvres?\s+bleu\w*",
        r"peau\s+bleu\w*",
        r"cyanos\w*",
        r"visage\s+bleu\w*",
        r"teint\s+bleut\w*",
    ],
    "convulsions": [
        r"convulsion\w*",
        r"secousses?\s+(du corps|musculaires)",
    ],
    "trouble de la conscience": [
        r"inconscient\w*",
        r"ne se réveille pas",
        r"très somnolent\w*",
        r"léthargique",
        r"ne réagit plus",
    ],
    "refus de boire / déshydratation": [
        r"ne boit plus",
        r"refuse de boire",
        r"n'arrive pas à boire",
        r"arrête de boire",
    ],
}

def detecter_signes_gravite(texte: str) -> list[str]:
    texte_lower = texte.lower()
    signes_detectes = []
    for categorie, patterns in SIGNES_GRAVITE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, texte_lower):
                signes_detectes.append(categorie)
                break
    return signes_detectes

def maman_demande_diagnostic(derniere_question: str) -> bool:
    texte = derniere_question.lower()
    patterns = [
        r"quelle\s+maladie", r"c'est quoi", r"qu'est[- ]ce que c'est",
        r"nom de la maladie", r"quel diagnostic", r"qu'est-ce qu'il a",
        r"c'est quelle maladie", r"est-ce que c'est",
    ]
    return any(re.search(p, texte) for p in patterns)


def construire_bloc_etat(session_id: str, historique_texte: str, derniere_question: str) -> str:
    maladie, verrouillee = identifier_maladie_avec_verrouillage(session_id, historique_texte)
    signes_gravite = detecter_signes_gravite(historique_texte)
    demande_explicite = maman_demande_diagnostic(derniere_question)

    bloc = "\n\n[Suivi interne]\n"

    if signes_gravite:
        bloc += f"⚠️ SIGNES DE GRAVITÉ DÉTECTÉS : {', '.join(signes_gravite)}\n"
        bloc += "-> Priorité absolue : recommandez une consultation médicale URGENTE, sans poser d'autre question.\n"
        return bloc

    if not verrouillee or not maladie or maladie not in criteres_par_maladie:
        bloc += "Phase : Triage générique.\n"
        return bloc

    criteres = criteres_par_maladie[maladie]

    # CORRECTION : on lit les confirmations globales (y compris les "oui" secs)
    forces_connus = criteres_confirmes_par_session.get(session_id, set())
    forces_ecartes = criteres_ecartes_par_session.get(session_id, set())

    connus, manquants = etat_symptomes(
        historique_texte, criteres,
        forces_connus=forces_connus, forces_ecartes=forces_ecartes
    )

    bloc += f"Maladie la plus probable en interne (NE PAS LA NOMMER sauf si demandé explicitement) : {maladie}\n"
    bloc += f"Symptômes déjà mentionnés: {', '.join(connus) if connus else 'aucun'}\n"
    bloc += f"Symptômes encore à vérifier: {', '.join(manquants) if manquants else 'aucun'}\n"

    if demande_explicite:
        bloc += (f"-> La maman demande explicitement le nom de la maladie probable. "
                  f"Indiquez '{maladie}' en précisant que ce n'est PAS un diagnostic médical "
                  f"et qu'une consultation reste nécessaire.\n")
    elif not manquants:
        bloc += "-> Toutes les infos sont réunies. Donnez des conseils pratiques et une orientation, SANS nommer la maladie.\n"
    else:
        bloc += "-> Continuez à poser UNE question ciblée parmi les symptômes encore à vérifier.\n"

    return bloc


store_sessions = {}

def get_session_history(session_id: str):
    if session_id not in store_sessions:
        store_sessions[session_id] = ChatMessageHistory()
    return store_sessions[session_id]


# ============================================================
# MISTRAL 7B
# ============================================================


import torch

from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    pipeline
)

from langchain_huggingface import HuggingFacePipeline
from langchain_huggingface import ChatHuggingFace


MODEL_ID = "mistralai/Mistral-7B-Instruct-v0.3"

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_use_double_quant=True
)

print("🔄 Chargement du tokenizer...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)

if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

print("🔄 Chargement de Mistral 7B sur GPU...")

model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    quantization_config=bnb_config,
    device_map="cuda"
)

print("✅ Mistral chargé !")
print("📍 Device :", model.device)

pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=256,
    do_sample=False,
    pad_token_id=tokenizer.eos_token_id,
    return_full_text=False
)

llm = HuggingFacePipeline(
    pipeline=pipe
)

chat_model = ChatHuggingFace(
    llm=llm
)

print("✅ ChatModel prêt !")


system_prompt = (
    "Vous êtes un assistant médical clinique qui mène un interrogatoire progressif "
    "pour orienter une maman inquiète pour son bébé.\n\n"
    "RÈGLES ABSOLUES :\n"
    "1. Regardez le bloc [Suivi interne] pour connaître la phase actuelle.\n"
    "2. Ne posez JAMAIS une question sur une information déjà présente dans "
    "l'historique ou dans le bloc [Suivi interne].\n"
    "3. Phase 'Triage générique' : recopiez TEXTUELLEMENT l'une des questions "
    "listées après 'Posez UNE SEULE question'. N'en inventez pas d'autre.\n"
    "4. Phase 'Maladie verrouillée' : posez une question sur UN symptôme de la "
    "liste 'Symptômes encore à vérifier' uniquement.\n"
    "5. Si 'Symptômes encore à vérifier' est vide, répondez uniquement : "
    "'Diagnostic : ' suivi du nom de la maladie.\n"
    "6. Une seule question, une seule phrase, sans préambule.\n\n"
    "Contexte :\n{context}"
)

prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{question}")
])


def construire_contexte(x) -> str:
    session_id = x["session_id"]
    historique_texte = "\n".join(m.content for m in x["history"]) + "\n" + x["question"]

    maladie, verrouillee = identifier_maladie_avec_verrouillage(session_id, historique_texte)
    bloc_etat = construire_bloc_etat(session_id, historique_texte, x["question"])

    if verrouillee and maladie:
        docs = get_symptomes_pertinents_pour_contexte(session_id, historique_texte)
        contexte_docs = format_symptomes(docs)
        return contexte_docs + bloc_etat
    else:
        return bloc_etat

chain_sans_memoire = (
    {
        "context": lambda x: construire_contexte(x),
        "question": lambda x: x["question"],
        "history": lambda x: x["history"]
    }
    | prompt
    | chat_model
    | StrOutputParser()
)

chatbot_interactif = RunnableWithMessageHistory(
    chain_sans_memoire,
    get_session_history,
    input_messages_key="question",
    history_messages_key="history"
)


def prochaine_question_triage(historique_texte: str) -> str | None:
    manquantes = questions_triage_manquantes(historique_texte)
    return manquantes[0] if manquantes else None


def prochaine_question_maladie(maladie: str, historique_texte: str) -> str | None:
    criteres = criteres_par_maladie.get(maladie, [])
    connus, manquants = etat_symptomes(historique_texte, criteres)
    if manquants:
        return f"Avez-vous remarqué chez votre bébé : {manquants[0]} ?"
    return None


def texte_maman_uniquement(history) -> str:
    """Ne garde QUE les messages de la maman, jamais les questions du bot,
    pour éviter que le bot ne se confirme à lui-même un symptôme qu'il a
    juste cité dans une question."""
    return "\n".join(m.content for m in history.messages if m.type == "human")



def reformuler_avec_mistral(message_brut: str) -> str:
    """Mistral reformule le texte de façon plus chaleureuse,
    SANS avoir le droit d'ajouter la moindre information."""

    prompt_reformulation = (
        "Reformule le texte suivant de façon chaleureuse et naturelle, "
        "comme si tu parlais directement à une maman inquiète pour son bébé. "
        "RÈGLE ABSOLUE : ne change AUCUNE information médicale, "
        "n'ajoute AUCUN conseil ou symptôme qui n'est pas déjà présent dans le texte. "
        "Reformule uniquement le TON et la fluidité, jamais le CONTENU.\n\n"
        f"Texte à reformuler :\n{message_brut}"
    )

    try:
        resultat = pipe(prompt_reformulation)[0]["generated_text"].strip()
        return resultat if resultat else message_brut
    except Exception:
        return message_brut  # sécurité : si Mistral échoue, on garde le message original fiable
    


# ============================================================
# GESTION DES SESSIONS ET REPONSES
# ============================================================

SESSION_ID = "maman_bebe_1"

der_question_critere_par_session = {}
criteres_confirmes_par_session = {}
criteres_ecartes_par_session = {}
langue_par_session = {}


def reset_session(session_id: str):
    if session_id in store_sessions:
        del store_sessions[session_id]

    questions_posees_compteur.pop(session_id, None)
    der_question_critere_par_session.pop(session_id, None)
    criteres_confirmes_par_session.pop(session_id, None)
    criteres_ecartes_par_session.pop(session_id, None)
    maladie_verrouillee_par_session.pop(session_id, None)
    langue_par_session.pop(session_id, None)


def construire_message_urgence(signes: list[str]) -> str:
    liste_signes = ", ".join(signes)
    return (
        f"⚠️ Ce que vous décrivez ({liste_signes}) peut être le signe d'une situation "
        "qui nécessite une évaluation médicale rapide.\n\n"
        "Je vous recommande de consulter un médecin ou les urgences pédiatriques "
        "sans attendre. Ce n'est pas un diagnostic, mais ces signes méritent "
        "d'être vus par un professionnel de santé rapidement."
    )


def message_fallback_securise() -> str:
    return (
        "Je n'ai pas assez d'éléments pour identifier précisément la cause des "
        "symptômes de votre bébé. Ces informations ne remplacent pas un avis "
        "médical : je vous recommande de consulter un médecin ou un pédiatre "
        "pour un examen adapté."
    )


def construire_message_final(maladie: str) -> str:
    sections_maladie = {}

    for doc in split_documents:
        if doc.metadata["maladie"] == maladie:
            sections_maladie[doc.metadata["section"]] = doc.page_content

    conseils = None
    quand_consulter = None

    for titre, contenu in sections_maladie.items():
        t = titre.lower()

        if "conseil" in t and "domicile" in t:
            conseils = contenu

        elif "quand consulter" in t or ("consulter" in t and "quand" in t):
            quand_consulter = contenu

    message = "D'après ce que vous décrivez, voici quelques informations utiles.\n\n"

    if conseils:
        message += f"**Conseils à la maison :**\n{conseils}\n\n"

    if quand_consulter:
        message += f"**Quand consulter :**\n{quand_consulter}\n\n"

    message += (
        "⚠️ Ceci n'est pas un diagnostic médical. Si vous avez le moindre doute, "
        "ou si les symptômes s'aggravent, consultez un médecin ou un pédiatre."
    )

    return message


def maman_demande_conseils(texte: str) -> bool:
    t = texte.lower()

    patterns = [
        r"que faire",
        r"quoi faire",
        r"comment faire",
        r"des conseils",
        r"un conseil",
        r"comment le soigner",
        r"comment la soigner",
        r"qu'est-ce que je dois faire",
        r"comment l'aider",
        r"que dois-je faire",
    ]

    return any(re.search(p, t) for p in patterns)


def envoyer_message(texte_maman: str, session_id: str = SESSION_ID) -> str:
    """
    Fonction principale utilisée par Flask.

    Elle conserve la logique du notebook mais, contrairement au notebook,
    elle RETOURNE la réponse au lieu de seulement l'afficher.
    """

    print(f"\n👩 Maman : {texte_maman}")

    history = get_session_history(session_id)

    reponse_courte = normaliser_reponse_courte(texte_maman)
    critere_en_attente = der_question_critere_par_session.get(session_id)

    criteres_confirmes_par_session.setdefault(session_id, set())
    criteres_ecartes_par_session.setdefault(session_id, set())

    if reponse_courte and critere_en_attente:
        if reponse_courte == "oui":
            criteres_confirmes_par_session[session_id].add(critere_en_attente)
        else:
            criteres_ecartes_par_session[session_id].add(critere_en_attente)

        texte_pour_historique = ""
    else:
        texte_pour_historique = texte_maman

    historique_texte = (
        texte_maman_uniquement(history)
        + "\n"
        + texte_pour_historique
    )

    forces_connus = criteres_confirmes_par_session[session_id]
    forces_ecartes = criteres_ecartes_par_session[session_id]

    # 1. Priorité absolue : signes de gravité
    signes = detecter_signes_gravite(historique_texte)

    if signes:
        reponse = construire_message_urgence(signes)

        history.add_user_message(texte_maman)
        history.add_ai_message(reponse)

        return reponse

    # 2. La maman demande directement des conseils
    if maman_demande_conseils(texte_maman):
        maladie_actuelle, verrouillee_actuelle = (
            identifier_maladie_avec_verrouillage(
                session_id,
                historique_texte
            )
        )

        if verrouillee_actuelle and maladie_actuelle:
            reponse = construire_message_final(maladie_actuelle)
        else:
            reponse = (
                "Je n'ai pas encore assez d'informations pour vous donner des conseils "
                "précis et adaptés. En attendant, voici quelques règles générales : "
                "surveillez la température, assurez-vous qu'il boive normalement, "
                "et n'hésitez pas à consulter un médecin si vous êtes inquiète ou si "
                "les symptômes s'aggravent.\n\n"
                "Pour vous aider plus précisément, pourriez-vous répondre aux questions "
                "que je vous pose ?"
            )

        history.add_user_message(texte_maman)
        history.add_ai_message(reponse)

        return reponse

    # 3. Triage générique
    maladie, verrouillee = identifier_maladie_avec_verrouillage(
        session_id,
        historique_texte
    )

    if not verrouillee or not maladie or maladie not in criteres_par_maladie:
        question_triage = prochaine_question_triage(historique_texte)

        if question_triage:
            reponse = question_triage
            der_question_critere_par_session.pop(session_id, None)

            history.add_user_message(texte_maman)
            history.add_ai_message(reponse)

            return reponse

        candidats = maladies_candidates(
            historique_texte,
            session_id=session_id
        )

        question_candidat = (
            prochaine_question_candidats(
                historique_texte,
                candidats,
                forces_connus=forces_connus,
                forces_ecartes=forces_ecartes
            )
            if candidats
            else None
        )

        nb_questions = questions_posees_compteur.get(session_id, 0)

        if question_candidat and nb_questions < MAX_QUESTIONS_SPECIFIQUES:
            questions_posees_compteur[session_id] = nb_questions + 1
            der_question_critere_par_session[session_id] = question_candidat

            reponse = (
                f"Avez-vous remarqué chez votre bébé : "
                f"{question_candidat} ?"
            )

            history.add_user_message(texte_maman)
            history.add_ai_message(reponse)

            return reponse

        reponse = message_fallback_securise()

        history.add_user_message(texte_maman)
        history.add_ai_message(reponse)

        return reponse

    # 4. Maladie verrouillée
    criteres = criteres_par_maladie[maladie]

    _connus, manquants = etat_symptomes(
        historique_texte,
        criteres,
        forces_connus=forces_connus,
        forces_ecartes=forces_ecartes
    )

    if manquants:
        reponse = (
            f"Avez-vous remarqué chez votre bébé : "
            f"{manquants[0]} ?"
        )

        der_question_critere_par_session[session_id] = manquants[0]

        history.add_user_message(texte_maman)
        history.add_ai_message(reponse)

        return reponse

    # 5. Toutes les informations réunies
    demande_explicite = maman_demande_diagnostic(texte_maman)

    if demande_explicite:
        message_brut = (
            f"D'après les symptômes décrits, cela évoque : {maladie}. "
            "Ce n'est pas un diagnostic médical certain.\n\n"
            + construire_message_final(maladie)
        )
    else:
        message_brut = construire_message_final(maladie)

    reponse = reformuler_avec_mistral(message_brut)

    history.add_user_message(texte_maman)
    history.add_ai_message(reponse)

    return reponse


# Alias clair pour l'intégration Flask.
obtenir_reponse = envoyer_message


# ============================================================
# TEST MANUEL OPTIONNEL
# ============================================================
# Ne pas mettre ici les appels envoyer_message(...) du notebook.
# Pour tester depuis Flask, utilisez la route /send_message.
