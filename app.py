from datetime import datetime, timedelta, date
from functools import wraps
import os

import uuid
from flask import request, jsonify, render_template
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash
from flask import jsonify


# ==========================================
# --- CONFIGURATION FLASK ---
# ==========================================

app = Flask(__name__)

DEBUG_MODE = os.environ.get('FLASK_DEBUG', '0') == '1'

secret_key = os.environ.get('SECRET_KEY')

if not secret_key:
    raise RuntimeError("La variable d'environnement SECRET_KEY est obligatoire.")



app.config['SECRET_KEY'] = secret_key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sahet_sghiri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['WTF_CSRF_ENABLED'] = False  # Désactivé pour le dev local

# Initialisation des extensions
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

# ==========================================
# --- MODÈLES DE BASE DE DONNÉES ---
# ==========================================

class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom_complet = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # maman ou medecin


class Enfant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(50), nullable=False)
    prenom = db.Column(db.String(50), nullable=False)
    date_naissance = db.Column(db.String(20), nullable=False)
    sexe = db.Column(db.String(10), nullable=False)
    poids = db.Column(db.Float, nullable=True)
    taille = db.Column(db.Float, nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)

    parent = db.relationship('Utilisateur', foreign_keys=[parent_id])

    ordonnances = db.relationship('Ordonnance', backref='enfant', lazy=True, cascade='all, delete-orphan')
    vaccins = db.relationship('Vaccin', backref='enfant', lazy=True, cascade='all, delete-orphan')
    recommandations = db.relationship('Recommandation', backref='enfant', lazy=True, cascade='all, delete-orphan')
    croissances = db.relationship('Croissance', backref='enfant', lazy=True, cascade='all, delete-orphan')
    consultations_details = db.relationship('ConsultationDetails', backref='enfant', lazy=True, cascade='all, delete-orphan')


class Consultation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=True)
    date_rdv = db.Column(db.String(20), nullable=False)
    motif = db.Column(db.Text, nullable=False)
    statut = db.Column(db.String(20), default='En attente')
    urgence = db.Column(db.Boolean, default=False)

    enfant = db.relationship('Enfant', backref='consultations')
    parent = db.relationship('Utilisateur', foreign_keys=[parent_id], backref='consultations_parent')


class PatientMedecin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    date_association = db.Column(db.String(20), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('medecin_id', 'enfant_id', name='uq_medecin_enfant'),
    )


class Disponibilite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    date_debut = db.Column(db.String(20), nullable=False)
    date_fin = db.Column(db.String(20), nullable=False)
    type_dispo = db.Column(db.String(20), default='normal')
    medecin = db.relationship('Utilisateur', backref='disponibilites')


class ConsultationDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    date_consultation = db.Column(db.String(20), nullable=False)
    symptomes = db.Column(db.Text, nullable=True)
    diagnostic = db.Column(db.Text, nullable=True)
    observations = db.Column(db.Text, nullable=True)
    antecedents = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)


class Croissance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    poids = db.Column(db.Float, nullable=False)
    taille = db.Column(db.Float, nullable=False)
    date_mesure = db.Column(db.String(20), nullable=False)


class Ordonnance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    date_creation = db.Column(db.String(20), nullable=False)
    contenu = db.Column(db.Text, nullable=True)

    medecin = db.relationship('Utilisateur', foreign_keys=[medecin_id])
    lignes = db.relationship('LigneOrdonnance', backref='ordonnance', lazy=True, cascade='all, delete-orphan')


class LigneOrdonnance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ordonnance_id = db.Column(db.Integer, db.ForeignKey('ordonnance.id'), nullable=False)
    nom_medicament = db.Column(db.String(100), nullable=False)
    posologie = db.Column(db.String(100), nullable=False)
    frequence = db.Column(db.String(100), nullable=False)
    duree = db.Column(db.String(50), nullable=False)
    instructions = db.Column(db.Text, nullable=True)
    statut_suivi = db.Column(db.String(20), default='En cours')
    remarque_maman = db.Column(db.Text, nullable=True)


class Vaccin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    nom_vaccin = db.Column(db.String(100), nullable=False)
    date_administration = db.Column(db.String(20), nullable=True)
    statut = db.Column(db.String(20), default='Planifié')
    remarques = db.Column(db.String(255), nullable=True)


class Recommandation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enfant_id = db.Column(db.Integer, db.ForeignKey('enfant.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    conseil = db.Column(db.Text, nullable=False)

    medecin = db.relationship('Utilisateur', foreign_keys=[medecin_id])


# ==========================================
# --- FONCTIONS UTILITAIRES ---
# ==========================================

def associer_patient_medecin(medecin_id, enfant_id):
    deja_associe = PatientMedecin.query.filter_by(medecin_id=medecin_id, enfant_id=enfant_id).first()
    if not deja_associe:
        nouvelle_association = PatientMedecin(
            medecin_id=medecin_id,
            enfant_id=enfant_id,
            date_association=date.today().isoformat()
        )
        db.session.add(nouvelle_association)


def medecin_a_acces_patient(medecin_id, enfant_id):
    association = PatientMedecin.query.filter_by(medecin_id=medecin_id, enfant_id=enfant_id).first()
    return association is not None


def role_required(role):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('connexion'))
            
            roles_autorises = [role] if isinstance(role, str) else role
            if session.get('user_role') not in roles_autorises:
                flash('Accès non autorisé.', 'danger')
                return redirect(url_for('dashboard'))
            return view(*args, **kwargs)
        return wrapped
    return decorator


def parse_float(valeur):
    if not valeur:
        return None
    try:
        return float(valeur)
    except (ValueError, TypeError):
        return None


# ==========================================
# --- ACCUEIL & AUTHENTIFICATION ---
# ==========================================

@app.route('/')
def accueil():
    return render_template('accueil.html')


@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        role = request.form.get('role')
        nom_complet = request.form.get('nom_complet')
        email = request.form.get('email')
        password = request.form.get('password')

        if role not in ('maman', 'medecin'):
            flash('Rôle invalide.', 'danger')
            return redirect(url_for('inscription'))

        if not nom_complet or not email or not password:
            flash('Tous les champs sont obligatoires.', 'danger')
            return redirect(url_for('inscription'))

        utilisateur_existant = Utilisateur.query.filter_by(email=email).first()
        if utilisateur_existant:
            flash('Cet email est déjà utilisé !', 'danger')
            return redirect(url_for('inscription'))

        hashed_password = generate_password_hash(password)
        nouvel_utilisateur = Utilisateur(
            nom_complet=nom_complet,
            email=email,
            mot_de_passe=hashed_password,
            role=role
        )
        db.session.add(nouvel_utilisateur)
        db.session.commit()

        if role == 'medecin':
            from datetime import datetime, timedelta
            aujourdhui = datetime.now().date()
            lundi = aujourdhui - timedelta(days=aujourdhui.weekday())
            jours_semaine = [lundi + timedelta(days=i) for i in range(5)]
            for jour in jours_semaine:
                date_str = jour.strftime('%Y-%m-%d')
                db.session.add(Disponibilite(
                    medecin_id=nouvel_utilisateur.id,
                    date_debut=f"{date_str} 09:00",
                    date_fin=f"{date_str} 12:00",
                    type_dispo='normal'
                ))
                db.session.add(Disponibilite(
                    medecin_id=nouvel_utilisateur.id,
                    date_debut=f"{date_str} 14:00",
                    date_fin=f"{date_str} 16:00",
                    type_dispo='normal'
                ))
            dimanche = lundi + timedelta(days=6)
            date_dimanche = dimanche.strftime('%Y-%m-%d')
            db.session.add(Disponibilite(
                medecin_id=nouvel_utilisateur.id,
                date_debut=f"{date_dimanche} 00:00",
                date_fin=f"{date_dimanche} 23:59",
                type_dispo='dimanche'
            ))
            db.session.add(Disponibilite(
                medecin_id=nouvel_utilisateur.id,
                date_debut=f"{date_dimanche} 00:00",
                date_fin=f"{date_dimanche} 23:59",
                type_dispo='garde_nuit'
            ))
            db.session.commit()

        flash('Compte créé avec succès !', 'success')
        return redirect(url_for('connexion'))

    return render_template('inscription.html')


@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')

        utilisateur = Utilisateur.query.filter_by(email=email).first()

        if (
            utilisateur
            and check_password_hash(utilisateur.mot_de_passe, password)
            and utilisateur.role == role
        ):
            session.clear()
            session['user_id'] = utilisateur.id
            session['user_nom'] = utilisateur.nom_complet
            session['user_role'] = utilisateur.role

            flash('Connexion réussie !', 'success')

            if utilisateur.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))

        flash('Email, mot de passe ou rôle incorrect.', 'danger')

    return render_template('connexion.html')


@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('accueil'))


# ==========================================
# --- DASHBOARD ---
# ==========================================

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    if session.get('user_role') == 'medecin':
        medecin_id = session['user_id']
        search_query = request.args.get('search', '').strip()
        statut_rdv = request.args.get('statut_rdv', 'Tous')

        patients_query = (
            Enfant.query
            .join(PatientMedecin, PatientMedecin.enfant_id == Enfant.id)
            .join(Utilisateur, Enfant.parent_id == Utilisateur.id)
            .filter(PatientMedecin.medecin_id == medecin_id)
        )

        if search_query:
            patients_query = patients_query.filter(
                (Enfant.nom.ilike(f'%{search_query}%'))
                | (Enfant.prenom.ilike(f'%{search_query}%'))
                | (Utilisateur.nom_complet.ilike(f'%{search_query}%'))
            )

        patients = patients_query.order_by(Enfant.nom).all()

        dernier_rdv_par_patient = {}
        if patients:
            patient_ids = [p.id for p in patients]
            rdv_medecin = (
                Consultation.query
                .filter(
                    Consultation.medecin_id == medecin_id,
                    Consultation.enfant_id.in_(patient_ids)
                )
                .order_by(Consultation.id.desc())
                .all()
            )
            for rdv in rdv_medecin:
                if rdv.enfant_id not in dernier_rdv_par_patient:
                    dernier_rdv_par_patient[rdv.enfant_id] = rdv

        query_rdv = Consultation.query.filter_by(medecin_id=medecin_id)
        statuts_valides = ('En attente', 'Confirmé', 'Terminé', 'Annulé')

        if statut_rdv != 'Tous' and statut_rdv in statuts_valides:
            query_rdv = query_rdv.filter_by(statut=statut_rdv)
        elif statut_rdv not in statuts_valides:
            statut_rdv = 'Tous'

        tous_rdv = query_rdv.all()

        disponibilites = Disponibilite.query.filter_by(medecin_id=medecin_id).order_by(Disponibilite.date_debut.asc()).all()

        return render_template(
            'dashboard_medecin.html',
            nom=session.get('user_nom'),
            patients=patients,
            dernier_rdv_par_patient=dernier_rdv_par_patient,
            tous_rdv=tous_rdv,
            search_query=search_query,
            statut_rdv=statut_rdv,
            disponibilites=disponibilites
        )

    enfants = Enfant.query.filter_by(parent_id=session['user_id']).all()
    return render_template('dashboard.html', nom=session.get('user_nom'), enfants=enfants)


@app.route('/medecin/disponibilite/ajouter', methods=['POST'])
@role_required('medecin')
def ajouter_disponibilite_dashboard():
    medecin_id = session['user_id']
    date_debut = request.form.get('date_debut')
    date_fin = request.form.get('date_fin')
    type_dispo = request.form.get('type_dispo', 'normal')
    if date_debut and date_fin:
        dispo = Disponibilite(medecin_id=medecin_id, date_debut=date_debut, date_fin=date_fin, type_dispo=type_dispo)
        db.session.add(dispo)
        db.session.commit()
        flash('Créneau ajouté.', 'success')
    return redirect(url_for('dashboard'))


@app.route('/medecin/disponibilite/<int:dispo_id>/supprimer', methods=['POST'])
@role_required('medecin')
def supprimer_disponibilite_dashboard(dispo_id):
    if dispo_id == 'ajouter':
        return redirect(url_for('dashboard'))
    dispo = Disponibilite.query.get_or_404(dispo_id)
    if dispo.medecin_id != session['user_id']:
        flash("Action non autorisée.", 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(dispo)
    db.session.commit()
    flash('Créneau supprimé.', 'info')
    return redirect(url_for('dashboard'))


# ==========================================
# --- GESTION DES RENDEZ-VOUS ---
# ==========================================

@app.route('/changer-statut-rdv/<int:rdv_id>/<string:nouveau_statut>', methods=['POST'])
@role_required('medecin')
def changer_statut_rdv(rdv_id, nouveau_statut):
    medecin_id = session['user_id']
    statuts_valides = ('En attente', 'Confirmé', 'Terminé', 'Annulé')

    if nouveau_statut not in statuts_valides:
        flash('Statut invalide.', 'danger')
        return redirect(url_for('dashboard'))

    rdv = Consultation.query.get_or_404(rdv_id)
    if rdv.medecin_id != medecin_id:
        flash("Vous n'êtes pas autorisé à modifier ce rendez-vous.", 'danger')
        return redirect(url_for('dashboard'))

    rdv.statut = nouveau_statut

    if nouveau_statut in ('Confirmé', 'Terminé') and rdv.enfant_id:
        associer_patient_medecin(rdv.medecin_id, rdv.enfant_id)

    db.session.commit()
    flash('Statut du rendez-vous mis à jour.', 'success')
    return redirect(url_for('dashboard'))


# ==========================================
# --- ESPACE MAMAN : GESTION & SUIVI ---
# ==========================================

CALENDRIER_TUNISIEN = [
    {"nom": "BCG + HBV-0", "age_mois": 0},
    {"nom": "Pentavalent-1 + VPI-1 + PCV-1", "age_mois": 2},
    {"nom": "Pentavalent-2 + VPI-2", "age_mois": 3},
    {"nom": "PCV-2", "age_mois": 4},
    {"nom": "Pentavalent-3 + VPI-3", "age_mois": 6},
    {"nom": "PCV-3", "age_mois": 11},
    {"nom": "RR-1 + HVA", "age_mois": 12},
    {"nom": "DTC-4 + VPO + RR-2", "age_mois": 18},
    {"nom": "DTCa + VPI + HVA", "age_mois": 72},
    {"nom": "dT + VPO + VPH (HPV)", "age_mois": 144},
    {"nom": "dT + VPO", "age_mois": 216}
]

@app.route('/ajouter-enfant', methods=['GET', 'POST'])
@role_required('maman')
def ajouter_enfant():
    if request.method == 'POST':
        nom = request.form.get('nom')
        prenom = request.form.get('prenom')
        date_naissance_str = request.form.get('date_naissance')
        sexe = request.form.get('sexe')
        poids = parse_float(request.form.get('poids'))
        taille = parse_float(request.form.get('taille'))

        if not nom or not prenom or not date_naissance_str or not sexe:
            flash('Veuillez remplir tous les champs obligatoires.', 'danger')
            return redirect(url_for('ajouter_enfant'))

        date_naissance_dt = None
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
            try:
                date_naissance_dt = datetime.strptime(date_naissance_str.strip(), fmt).date()
                break
            except (ValueError, TypeError):
                continue

        if not date_naissance_dt:
            date_naissance_dt = date.today()

        date_naissance_formatted = date_naissance_dt.strftime('%d/%m/%Y')

        nouvel_enfant = Enfant(
            nom=nom,
            prenom=prenom,
            date_naissance=date_naissance_formatted,
            sexe=sexe,
            poids=poids,
            taille=taille,
            parent_id=session['user_id']
        )
        db.session.add(nouvel_enfant)
        db.session.commit()

        if poids is not None and taille is not None:
            premiere_mesure = Croissance(
                enfant_id=nouvel_enfant.id,
                poids=poids,
                taille=taille,
                date_mesure=date.today().strftime('%d/%m/%Y')
            )
            db.session.add(premiere_mesure)

        for v in CALENDRIER_TUNISIEN:
            date_prevue_dt = date_naissance_dt + timedelta(days=int(v['age_mois'] * 30.4375))
            vaccin = Vaccin(
                enfant_id=nouvel_enfant.id,
                nom_vaccin=v['nom'],
                date_administration=date_prevue_dt.strftime('%d/%m/%Y'),
                statut='Planifié',
                remarques=f"Âge recommandé : {v['age_mois']} mois"
            )
            db.session.add(vaccin)

        db.session.commit()
        flash('Enfant ajouté et son carnet vaccinal tunisien a été généré avec succès !', 'success')
        return redirect(url_for('dashboard'))

    return render_template('ajouter_enfant.html')


@app.route('/mon-enfant/<int:enfant_id>/suivi')
@role_required('maman')
def suivi_enfant(enfant_id):
    enfant = Enfant.query.filter_by(id=enfant_id, parent_id=session['user_id']).first_or_404()
    recommandations = Recommandation.query.filter_by(enfant_id=enfant.id).order_by(Recommandation.date.desc()).all()
    croissances = Croissance.query.filter_by(enfant_id=enfant.id).order_by(Croissance.date_mesure.desc()).all()
    ordonnances = Ordonnance.query.filter_by(enfant_id=enfant.id).order_by(Ordonnance.date_creation.desc()).all()
    vaccins = Vaccin.query.filter_by(enfant_id=enfant.id).order_by(Vaccin.id.desc()).all()

    return render_template(
        'suivi_enfant.html',
        enfant=enfant,
        recommandations=recommandations,
        croissances=croissances,
        ordonnances=ordonnances,
        vaccins=vaccins
    )


# ==========================================
# --- GESTION DES VACCINS ---
# ==========================================

@app.route('/enfant/<int:enfant_id>/vaccin/ajouter', methods=['POST'])
def ajouter_vaccin(enfant_id):
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    user_id = session['user_id']
    user_role = session['user_role']
    enfant = Enfant.query.get_or_404(enfant_id)

    if user_role == 'maman' and enfant.parent_id != user_id:
        flash("Action non autorisée.", 'danger')
        return redirect(url_for('dashboard'))
    elif user_role == 'medecin' and not medecin_a_acces_patient(user_id, enfant_id):
        flash("Action non autorisée.", 'danger')
        return redirect(url_for('dashboard'))

    nom_vaccin = request.form.get('nom_vaccin')
    date_admin = request.form.get('date_administration')
    statut = request.form.get('statut', 'Planifié')
    remarques = request.form.get('remarques')

    if nom_vaccin:
        nouveau_vaccin = Vaccin(
            enfant_id=enfant.id,
            nom_vaccin=nom_vaccin,
            date_administration=date_admin,
            statut=statut,
            remarques=remarques
        )
        db.session.add(nouveau_vaccin)
        db.session.commit()
        flash('Vaccin ajouté avec succès !', 'success')

    if user_role == 'medecin':
        return redirect(url_for('dossier_patient', id=enfant.id))
    return redirect(url_for('suivi_enfant', enfant_id=enfant.id))


@app.route('/vaccin/<int:vaccin_id>/modifier', methods=['POST'])
def modifier_vaccin(vaccin_id):
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    vaccin = Vaccin.query.get_or_404(vaccin_id)
    enfant = Enfant.query.get_or_404(vaccin.enfant_id)
    user_id = session['user_id']
    user_role = session['user_role']

    if user_role == 'maman' and enfant.parent_id != user_id:
        flash("Action non autorisée.", 'danger')
        return redirect(url_for('dashboard'))
    elif user_role == 'medecin' and not medecin_a_acces_patient(user_id, enfant.id):
        flash("Action non autorisée.", 'danger')
        return redirect(url_for('dashboard'))

    vaccin.nom_vaccin = request.form.get('nom_vaccin', vaccin.nom_vaccin)
    vaccin.date_administration = request.form.get('date_administration', vaccin.date_administration)
    vaccin.statut = request.form.get('statut', vaccin.statut)
    vaccin.remarques = request.form.get('remarques', vaccin.remarques)

    db.session.commit()
    flash('Informations du vaccin mises à jour !', 'success')

    if user_role == 'medecin':
        return redirect(url_for('dossier_patient', id=enfant.id))
    return redirect(url_for('suivi_enfant', enfant_id=enfant.id))


# ==========================================
# --- ESPACE MÉDECIN : DOSSIER PATIENT ---
# ==========================================

@app.route('/patient/<int:id>', methods=['GET', 'POST'])
@role_required('medecin')
def dossier_patient(id):
    medecin_id = session['user_id']

    if not medecin_a_acces_patient(medecin_id, id):
        flash("Vous n'êtes pas autorisé à accéder au dossier de cet enfant.", 'danger')
        return redirect(url_for('dashboard'))

    enfant = Enfant.query.get_or_404(id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'consultation_details':
            date_consultation = request.form.get('date_consultation')
            poids_str = request.form.get('poids')
            taille_str = request.form.get('taille')

            if not date_consultation:
                flash('La date de consultation est obligatoire.', 'danger')
                return redirect(url_for('dossier_patient', id=enfant.id))

            nouvelle_consultation = ConsultationDetails(
                enfant_id=enfant.id,
                medecin_id=medecin_id,
                date_consultation=date_consultation,
                symptomes=request.form.get('symptomes'),
                diagnostic=request.form.get('diagnostic'),
                observations=request.form.get('observations'),
                antecedents=request.form.get('antecedents'),
                notes=request.form.get('notes')
            )
            db.session.add(nouvelle_consultation)

            poids_val = parse_float(poids_str)
            taille_val = parse_float(taille_str)

            if poids_val is not None:
                enfant.poids = poids_val
            if taille_val is not None:
                enfant.taille = taille_val

            if poids_val is not None and taille_val is not None:
                nouvelle_mesure = Croissance(
                    enfant_id=enfant.id,
                    date_mesure=date_consultation,
                    poids=poids_val,
                    taille=taille_val
                )
                db.session.add(nouvelle_mesure)

            db.session.commit()
            flash('Consultation et paramètres enregistrés avec succès !', 'success')
            return redirect(url_for('dossier_patient', id=enfant.id))

        elif action == 'recommandation':
            date_reco = request.form.get('date_reco')
            conseil = request.form.get('conseil')

            if not conseil:
                flash('Le conseil ne peut pas être vide.', 'danger')
                return redirect(url_for('dossier_patient', id=enfant.id))

            nouvelle_reco = Recommandation(
                enfant_id=enfant.id,
                medecin_id=medecin_id,
                date=date_reco or date.today().isoformat(),
                conseil=conseil
            )
            db.session.add(nouvelle_reco)
            db.session.commit()

            flash('Recommandation ajoutée avec succès !', 'success')
            return redirect(url_for('dossier_patient', id=enfant.id))

    consultations = ConsultationDetails.query.filter_by(enfant_id=enfant.id, medecin_id=medecin_id).order_by(ConsultationDetails.date_consultation.desc()).all()
    recommandations = Recommandation.query.filter_by(enfant_id=enfant.id, medecin_id=medecin_id).order_by(Recommandation.date.desc()).all()
    croissances = Croissance.query.filter_by(enfant_id=enfant.id).order_by(Croissance.date_mesure.desc()).all()
    ordonnances = Ordonnance.query.filter_by(enfant_id=enfant.id).order_by(Ordonnance.date_creation.desc()).all()
    vaccins = Vaccin.query.filter_by(enfant_id=enfant.id).order_by(Vaccin.id.desc()).all()

    return render_template(
        'dossier_patient.html',
        enfant=enfant,
        consultations=consultations,
        recommandations=recommandations,
        croissances=croissances,
        ordonnances=ordonnances,
        vaccins=vaccins
    )


# ==========================================
# --- CRÉATION D'UNE ORDONNANCE ---
# ==========================================

@app.route('/patient/<int:enfant_id>/ordonnance/creer', methods=['GET', 'POST'])
@role_required('medecin')
def creer_ordonnance(enfant_id):
    medecin_id = session.get('user_id')

    if not medecin_a_acces_patient(medecin_id, enfant_id):
        flash("Vous n'êtes pas autorisé à créer une ordonnance pour cet enfant.", 'danger')
        return redirect(url_for('dashboard'))

    enfant = Enfant.query.get_or_404(enfant_id)

    if request.method == 'GET':
        return render_template('creer_ordonnance.html', enfant=enfant, today_date=date.today().isoformat())

    date_creation_raw = request.form.get('date_creation')
    if not date_creation_raw:
        flash("La date de l'ordonnance est obligatoire.", 'danger')
        return redirect(url_for('creer_ordonnance', enfant_id=enfant.id))

    try:
        date_creation = datetime.strptime(date_creation_raw, '%Y-%m-%d').date()
    except ValueError:
        date_creation = date_creation_raw

    medicaments = request.form.getlist('nom_medicament[]')
    medicaments_autre = request.form.getlist('nom_medicament_autre[]')
    posologies = request.form.getlist('posologie[]')
    posologies_autre = request.form.getlist('posologie_autre[]')
    frequences = request.form.getlist('frequence[]')
    frequences_autre = request.form.getlist('frequence_autre[]')
    durees = request.form.getlist('duree[]')
    durees_autre = request.form.getlist('duree_autre[]')
    instructions_list = request.form.getlist('instructions[]')
    instructions_autre = request.form.getlist('instructions_autre[]')

    nb_lignes = len(medicaments)
    nb_lignes_non_vides = sum(1 for m in medicaments if m.strip())
    if nb_lignes_non_vides == 0:
        flash("Veuillez ajouter au moins un médicament.", 'danger')
        return redirect(url_for('creer_ordonnance', enfant_id=enfant.id))

    try:
        nouvelle_ordo = Ordonnance(
            enfant_id=enfant.id,
            medecin_id=medecin_id,
            date_creation=date_creation,
            contenu='Ordonnance électronique'
        )
        db.session.add(nouvelle_ordo)
        db.session.flush()

        idx_medoc_autre = 0
        idx_poso_autre = 0
        idx_freq_autre = 0
        idx_duree_autre = 0
        idx_inst_autre = 0

        for i in range(nb_lignes):
            nom_medicament = medicaments[i].strip()
            if not nom_medicament:
                continue
            if nom_medicament == 'Autre':
                if idx_medoc_autre < len(medicaments_autre) and medicaments_autre[idx_medoc_autre].strip():
                    nom_medicament = medicaments_autre[idx_medoc_autre].strip()
                    idx_medoc_autre += 1
                else:
                    raise ValueError("Veuillez préciser le nom du médicament saisi comme 'Autre'.")

            posologie = posologies[i].strip() if i < len(posologies) else ''
            if posologie == 'Autre':
                if idx_poso_autre < len(posologies_autre) and posologies_autre[idx_poso_autre].strip():
                    posologie = posologies_autre[idx_poso_autre].strip()
                    idx_poso_autre += 1
                else:
                    raise ValueError("Veuillez préciser la posologie saisie comme 'Autre'.")

            frequence = frequences[i].strip() if i < len(frequences) else ''
            if frequence == 'Autre':
                if idx_freq_autre < len(frequences_autre) and frequences_autre[idx_freq_autre].strip():
                    frequence = frequences_autre[idx_freq_autre].strip()
                    idx_freq_autre += 1
                else:
                    raise ValueError("Veuillez préciser la fréquence saisie comme 'Autre'.")

            duree = durees[i].strip() if i < len(durees) else ''
            if duree == 'Autre':
                if idx_duree_autre < len(durees_autre) and durees_autre[idx_duree_autre].strip():
                    duree = durees_autre[idx_duree_autre].strip()
                    idx_duree_autre += 1
                else:
                    raise ValueError("Veuillez préciser la durée saisie comme 'Autre'.")

            instructions = instructions_list[i].strip() if i < len(instructions_list) else 'Aucune'
            if instructions == 'Autre':
                if idx_inst_autre < len(instructions_autre) and instructions_autre[idx_inst_autre].strip():
                    instructions = instructions_autre[idx_inst_autre].strip()
                    idx_inst_autre += 1
                else:
                    instructions = 'Aucune'

            nouvelle_ligne = LigneOrdonnance(
                ordonnance_id=nouvelle_ordo.id,
                nom_medicament=nom_medicament,
                posologie=posologie,
                frequence=frequence,
                duree=duree,
                instructions=instructions,
                statut_suivi='En cours'
            )
            db.session.add(nouvelle_ligne)

        db.session.commit()
        flash("Ordonnance créée avec succès !", 'success')
        return redirect(url_for('dossier_patient', id=enfant.id))

    except ValueError as erreur:
        db.session.rollback()
        flash(str(erreur), 'danger')
        return redirect(url_for('creer_ordonnance', enfant_id=enfant.id))
    except Exception as erreur:
        db.session.rollback()
        print("Erreur ordonnance :", erreur)
        flash("Une erreur s'est produite lors de la création de l'ordonnance.", 'danger')
        return redirect(url_for('creer_ordonnance', enfant_id=enfant.id))


# ==========================================
# --- CONSULTER UNE ORDONNANCE ---
# ==========================================

@app.route('/ordonnance/<int:ordonnance_id>')
def voir_ordonnance(ordonnance_id):
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    ordonnance = Ordonnance.query.get_or_404(ordonnance_id)
    enfant = Enfant.query.get_or_404(ordonnance.enfant_id)

    user_id = session['user_id']
    user_role = session['user_role']

    if user_role == 'maman':
        if enfant.parent_id != user_id:
            flash("Vous n'êtes pas autorisée à consulter cette ordonnance.", 'danger')
            return redirect(url_for('dashboard'))
    elif user_role == 'medecin':
        if ordonnance.medecin_id != user_id:
            flash("Vous n'êtes pas autorisé à consulter cette ordonnance.", 'danger')
            return redirect(url_for('dashboard'))
    else:
        flash("Accès non autorisé.", 'danger')
        return redirect(url_for('dashboard'))

    return render_template('voir_ordonnance.html', ordonnance=ordonnance, enfant=enfant)


# ==========================================
# --- MODIFICATION DU STATUT DU MÉDICAMENT ---
# ==========================================

@app.route('/medicament/<int:ligne_id>/modifier-statut', methods=['POST'])
@role_required('maman')
def modifier_statut_medicament(ligne_id):
    ligne = LigneOrdonnance.query.get_or_404(ligne_id)
    ordonnance = Ordonnance.query.get_or_404(ligne.ordonnance_id)
    enfant = Enfant.query.get_or_404(ordonnance.enfant_id)

    if enfant.parent_id != session['user_id']:
        flash("Vous n'êtes pas autorisée à modifier ce médicament.", 'danger')
        return redirect(url_for('dashboard'))

    nouveau_statut = request.form.get('statut_suivi')
    remarque = request.form.get('remarque_maman', '').strip()

    if nouveau_statut not in ['En cours', 'Terminé']:
        flash('Statut invalide.', 'danger')
        return redirect(url_for('suivi_enfant', enfant_id=enfant.id))

    ligne.statut_suivi = nouveau_statut
    ligne.remarque_maman = remarque if remarque else None

    try:
        db.session.commit()
        flash(f"Le suivi du médicament « {ligne.nom_medicament} » a été mis à jour.", 'success')
    except Exception as erreur:
        db.session.rollback()
        print("Erreur mise à jour suivi médicament :", erreur)
        flash("Une erreur est survenue lors de la mise à jour.", 'danger')

    referrer = request.referrer
    if referrer and 'ordonnance' in referrer:
        return redirect(url_for('voir_ordonnance', ordonnance_id=ordonnance.id))

    return redirect(url_for('suivi_enfant', enfant_id=enfant.id))


# ==========================================
# --- ESPACE ADMINISTRATEUR ---
# ==========================================

@app.route('/admin/dashboard')
@role_required('admin')
def admin_dashboard():
    total_mamans = Utilisateur.query.filter_by(role='maman').count()
    total_medecins = Utilisateur.query.filter_by(role='medecin').count()
    total_enfants = Enfant.query.count()
    total_ordonnances = Ordonnance.query.count()
    utilisateurs = Utilisateur.query.order_by(Utilisateur.id.desc()).all()

    return render_template(
        'admin/dashboard.html',
        total_mamans=total_mamans,
        total_medecins=total_medecins,
        total_enfants=total_enfants,
        total_ordonnances=total_ordonnances,
        utilisateurs=utilisateurs
    )


@app.route('/admin/utilisateur/<int:user_id>/changer-role', methods=['POST'])
@role_required('admin')
def admin_changer_role(user_id):
    utilisateur = Utilisateur.query.get_or_404(user_id)
    nouveau_role = request.form.get('role')

    if nouveau_role in ['maman', 'medecin', 'admin']:
        utilisateur.role = nouveau_role
        db.session.commit()
        flash(f"Le rôle de {utilisateur.nom_complet} a été modifié en {nouveau_role}.", 'success')
    else:
        flash("Rôle invalide.", 'danger')

    return redirect(url_for('admin_dashboard'))
@app.route('/admin/utilisateur/<int:user_id>/supprimer', methods=['POST'], endpoint='admin_supprimer_utilisateur')
@role_required('admin')
def supprimer_un_utilisateur(user_id):
    utilisateur = Utilisateur.query.get_or_404(user_id)
    db.session.delete(utilisateur)
    db.session.commit()
    flash("Utilisateur supprimé avec succès.", "success")
    return redirect(url_for('admin_dashboard'))
# --- SUIVI DES VACCINS ---
# ==========================================

@app.route('/enfant/<int:enfant_id>/vaccins')
def voir_vaccins_enfant(enfant_id):
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    enfant = Enfant.query.get_or_404(enfant_id)
    user_id = session['user_id']
    user_role = session['user_role']

    if user_role == 'maman' and enfant.parent_id != user_id:
        flash("Vous n'êtes pas autorisée à consulter ce carnet.", 'danger')
        return redirect(url_for('dashboard'))

    vaccins = Vaccin.query.filter_by(enfant_id=enfant.id).all()

    if not vaccins:
        dt_naiss = None
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
            try:
                dt_naiss = datetime.strptime(str(enfant.date_naissance).strip(), fmt).date()
                break
            except (ValueError, TypeError):
                continue
        
        if not dt_naiss:
            dt_naiss = date.today()

        for v in CALENDRIER_TUNISIEN:
            date_prevue_dt = dt_naiss + timedelta(days=int(v['age_mois'] * 30.4375))
            nouveau_v = Vaccin(
                enfant_id=enfant.id,
                nom_vaccin=v['nom'],
                date_administration=date_prevue_dt.strftime('%d/%m/%Y'),
                statut='Planifié',
                remarques=f"Âge recommandé : {v['age_mois']} mois"
            )
            db.session.add(nouveau_v)
        
        db.session.commit()
        vaccins = Vaccin.query.filter_by(enfant_id=enfant.id).all()

    aujourdhui = date.today()
    statut_modifie = False

    for v in vaccins:
        if v.statut not in ['Administré', 'Effectué', 'Fait']:
            try:
                date_v = None
                for fmt in ['%d/%m/%Y', '%Y-%m-%d']:
                    try:
                        date_v = datetime.strptime(str(v.date_administration).strip(), fmt).date()
                        break
                    except ValueError:
                        continue

                if date_v and date_v < aujourdhui:
                    if v.statut != 'En retard':
                        v.statut = 'En retard'
                        statut_modifie = True
                elif date_v and date_v >= aujourdhui:
                    if v.statut != 'Planifié':
                        v.statut = 'Planifié'
                        statut_modifie = True
            except Exception:
                pass

    if statut_modifie:
        db.session.commit()

    return render_template('vaccins.html', enfant=enfant, vaccins=vaccins)


@app.route('/cocher_vaccin/<int:vaccin_id>', methods=['POST'])
def cocher_vaccin(vaccin_id):
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    vaccin = Vaccin.query.get_or_404(vaccin_id)
    enfant = Enfant.query.get_or_404(vaccin.enfant_id)

    user_id = session['user_id']
    user_role = session['user_role']

    if user_role == 'maman' and enfant.parent_id != user_id:
        flash("Vous n'êtes pas autorisée à modifier ce carnet.", 'danger')
        return redirect(url_for('dashboard'))

    is_done = request.form.get('is_done') == 'true'
    aujourdhui = date.today()

    if is_done:
        date_prevue = None
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
            try:
                date_prevue = datetime.strptime(str(vaccin.date_administration).strip(), fmt).date()
                break
            except (ValueError, TypeError):
                continue

        if date_prevue and date_prevue > aujourdhui:
            flash(f"Impossible de marquer ce vaccin comme administré : sa date prévue est le {date_prevue.strftime('%d/%m/%Y')}.", 'danger')
            return redirect(url_for('voir_vaccins_enfant', enfant_id=enfant.id))

        vaccin.statut = 'Administré'
        vaccin.date_administration = aujourdhui.strftime('%d/%m/%Y')
        flash("Vaccin marqué comme administré avec la date du jour.", 'success')

    else:
        dt_naiss = None
        for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d']:
            try:
                dt_naiss = datetime.strptime(str(enfant.date_naissance).strip(), fmt).date()
                break
            except (ValueError, TypeError):
                continue

        age_mois = 0
        for v in CALENDRIER_TUNISIEN:
            if v['nom'] == vaccin.nom_vaccin:
                age_mois = v['age_mois']
                break

        if dt_naiss:
            date_prevue_dt = dt_naiss + timedelta(days=int(age_mois * 30.4375))
            vaccin.date_administration = date_prevue_dt.strftime('%d/%m/%Y')

            if date_prevue_dt < aujourdhui:
                vaccin.statut = 'En retard'
            else:
                vaccin.statut = 'Planifié'
        else:
            vaccin.statut = 'Planifié'

        flash("Statut du vaccin réinitialisé.", 'info')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("Une erreur est survenue lors de la mise à jour.", 'danger')

    return redirect(url_for('voir_vaccins_enfant', enfant_id=enfant.id))


# ==========================================
# --- MEDECINS & PRISE DE RDV ---
# ==========================================

@app.route('/medecins', methods=['GET', 'POST'])
@role_required('maman')
def liste_medecins():
    medecins = Utilisateur.query.filter_by(role='medecin').all()
    enfants = Enfant.query.filter_by(parent_id=session['user_id']).all()

    if request.method == 'POST':
        medecin_id = request.form.get('medecin_id')
        enfant_id = request.form.get('enfant_id')
        date_rdv_raw = request.form.get('date_rdv')
        motif = request.form.get('motif')
        urgence = request.form.get('urgence') == 'on'

        medecin_valide = Utilisateur.query.filter_by(id=medecin_id, role='medecin').first()
        enfant_valide = Enfant.query.filter_by(id=enfant_id, parent_id=session['user_id']).first()

        if not medecin_valide or not enfant_valide or not date_rdv_raw or not motif:
            flash('Demande de rendez-vous invalide.', 'danger')
            return redirect(url_for('liste_medecins'))

        if not urgence:
            conflit = Disponibilite.query.filter(
                Disponibilite.medecin_id == medecin_valide.id,
                Disponibilite.date_debut <= date_rdv_raw,
                Disponibilite.date_fin >= date_rdv_raw,
            ).first()
            if not conflit:
                flash("Ce créneau n'est pas disponible. Choisissez un autre temps ou demandez une consultation urgente.", 'warning')
                return redirect(url_for('liste_medecins'))

        date_rdv = date_rdv_raw.replace('T', ' ')

        nouvelle_consultation = Consultation(
            parent_id=session['user_id'],
            medecin_id=medecin_valide.id,
            enfant_id=enfant_valide.id,
            date_rdv=date_rdv,
            motif=motif,
            urgence=urgence,
            statut='En attente'
        )
        db.session.add(nouvelle_consultation)
        db.session.commit()
        
        if urgence:
            flash('Demande de consultation URGENTE envoyée.', 'danger')
        else:
            flash('Demande de rendez-vous envoyée avec succès !', 'success')
        return redirect(url_for('dashboard'))

    return render_template('medecins.html', medecins=medecins, enfants=enfants)


# ==========================================
# --- CHATBOT IA ---
# ==========================================

print(">>> LE FICHIER APP.PY EST BIEN CHARGÉ !")

@app.route("/chat", methods=['GET', 'POST'])
def chat_page():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    # Créer une nouvelle session chatbot si nécessaire
    if 'chat_session_id' not in session:
        session['chat_session_id'] = str(uuid.uuid4())

    chat_session_id = session['chat_session_id']

    if request.method == 'POST':
        message = request.form.get('message', '').strip()

        if message:
            from ia.chatbot import obtenir_reponse
            obtenir_reponse(
                message,
                session_id=chat_session_id
            )

    # Récupérer l'historique via la fonction du chatbot
    from ia.chatbot import get_session_history

    history = get_session_history(chat_session_id)

    return render_template(
        "chat.html",
        session_id=chat_session_id,
        history=history.messages
    )


@app.route("/new_session", methods=["POST"])
def new_session():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    # Nouvelle session
    session_id = str(uuid.uuid4())
    session['chat_session_id'] = session_id

    return jsonify({
        "session_id": session_id
    })


@app.route("/send_message", methods=["POST"])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))

    chat_session_id = session.get('chat_session_id')

    if not chat_session_id:
        chat_session_id = str(uuid.uuid4())
        session['chat_session_id'] = chat_session_id

    message = request.form.get('message', '').strip()

    if not message:
        return redirect(url_for('chat_page'))

    from ia.chatbot import obtenir_reponse

    obtenir_reponse(
        message,
        session_id=chat_session_id
    )

    return redirect(url_for('chat_page'))
# ==========================================
# --- INITIALISATION & LANCEMENT UNIQUE ---
# ==========================================

def initialiser_base_de_donnees():
    with app.app_context():
        db.create_all()

        try:
            db.session.execute(db.text('ALTER TABLE consultation ADD COLUMN urgence BOOLEAN DEFAULT 0'))
        except Exception:
            pass

        try:
            db.session.execute(db.text('''
                CREATE TABLE IF NOT EXISTS disponibilite (
                    id INTEGER PRIMARY KEY,
                    medecin_id INTEGER NOT NULL,
                    date_debut VARCHAR(20) NOT NULL,
                    date_fin VARCHAR(20) NOT NULL,
                    type_dispo VARCHAR(20) DEFAULT 'normal',
                    FOREIGN KEY(medecin_id) REFERENCES utilisateur(id)
                )
            '''))
        except Exception:
            pass

        db.session.commit()

        anciens_rdv = Consultation.query.filter(
            Consultation.statut.in_([
                'Confirmé',
                'Terminé'
            ]),
            Consultation.enfant_id.isnot(None)
        ).all()

        for rdv in anciens_rdv:
            associer_patient_medecin(
                rdv.medecin_id,
                rdv.enfant_id
            )

        db.session.commit()


if __name__ == '__main__':
    initialiser_base_de_donnees()
    print("Verification des routes :")
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if 'admin' in rule.endpoint:
            print(f"  {rule.rule} -> {rule.endpoint}")
    app.run(debug=False, use_reloader=False, port=5001)