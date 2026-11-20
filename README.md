# Carnet de notes – Master 1 DAT

Mini application de bureau en **Python / Tkinter** pour gérer les étudiants, les matières et les notes, avec connexion par compte utilisateur, statistiques et export des relevés.

## Fonctionnalités

### Connexion et rôles

- Écran de connexion avec identifiant et mot de passe (option « Afficher le mot de passe »)
- Mots de passe stockés de façon sécurisée (hachage PBKDF2-SHA256 salé)
- Trois rôles, chacun avec ses propres droits :

| Action                                         | Administrateur | Enseignant             | Étudiant              |
|------------------------------------------------|:--------------:|:----------------------:|:---------------------:|
| Voir la promotion                              | ✅             | ✅                     | Sa propre fiche       |
| Ajouter un étudiant / modifier son identité    | ✅             | ✅                     | ❌                    |
| Saisir ou modifier des notes                   | ✅             | Ses matières seulement | ❌                    |
| Supprimer un étudiant                          | ✅             | ❌                     | ❌                    |
| Gérer les matières et coefficients             | ✅             | Lecture seule          | ❌                    |
| Statistiques et export CSV                     | ✅             | ✅                     | ❌                    |
| Relevé de notes HTML                           | ✅             | ✅                     | ✅                    |
| Gérer les comptes utilisateurs                 | ✅             | ❌                     | ❌                    |

### Gestion des étudiants et des notes

- Ajout rapide d'un étudiant et d'une note depuis la fenêtre principale (virgule ou point acceptés, notes de 0 à 20)
- Fiche détaillée de chaque étudiant (double-clic) : identité, notes par matière, appréciation générale, moyenne, rang et mention
- Tableau de la promotion avec filtre par matière, recherche par nom et tri en cliquant sur les en-têtes
- Mise en couleur des étudiants sous la moyenne et des étudiants sans note

### Calculs

- Moyenne générale pondérée par les coefficients des matières
- Classement de la promotion (ex æquo gérés : 1, 2, 2, 4), avec podium 🥇 🥈 🥉
- Mentions : Ajourné, Passable, Assez bien, Bien, Très bien
- Décision Admis / Ajourné (seuil à 10/20)

### Statistiques et graphiques

- Fenêtre dédiée, par matière ou sur la moyenne générale
- Indicateurs : effectif, moyenne, médiane, écart-type, minimum, maximum, taux de réussite
- Histogramme de répartition des notes par tranches
- Graphique des notes individuelles avec le seuil d'admission
- Top 3 des étudiants
- Graphiques dessinés avec `tk.Canvas`, sans bibliothèque externe

### Matières et utilisateurs (administrateur)

- Création, modification et suppression des matières avec leur coefficient
- Attribution des matières aux enseignants
- Création de comptes administrateur, enseignant ou étudiant (un compte étudiant est rattaché à sa fiche)
- Réinitialisation du mot de passe et suppression de comptes

### Exports et import

- **Export CSV** de la promotion, compatible Excel (rang, notes, moyenne, mention, décision, appréciation)
- **Relevé de notes individuel en HTML**, imprimable ou enregistrable en PDF depuis le navigateur
- **Import** d'un ancien carnet au format JSON

## Prérequis

- **Python 3.10+** (Tkinter est inclus dans l'installateur officiel Windows)
- Aucune bibliothèque externe : seule la bibliothèque standard est utilisée (`tkinter`, `sqlite3`, …)

Vérifier que Tkinter est disponible :

```bash
python -m tkinter
```

Une petite fenêtre de test doit s'ouvrir.

## Lancement

Depuis le dossier du projet :

```bash
python main.py
```

## Premier lancement

Au premier démarrage, la base SQLite `carnet_notes.db` est créée automatiquement. Elle est pré-remplie avec des données de démonstration (3 matières, 4 étudiants et leurs notes) et contient un compte administrateur :

| Identifiant | Mot de passe |
|-------------|--------------|
| `admin`     | `admin123`   |

> ⚠️ Pensez à changer ce mot de passe après la première connexion :
> **Gestion des utilisateurs → Nouveau mot de passe**.

## Vérification (optionnel)

Un script teste la syntaxe, la logique métier et l'ouverture de toutes les fenêtres, sur une base temporaire (la vraie base n'est pas modifiée) :

```bash
python verification.py
```

## Structure du projet

| Fichier            | Rôle                                          |
|--------------------|-----------------------------------------------|
| `main.py`          | Point d'entrée de l'application               |
| `login_window.py`  | Écran de connexion                            |
| `ui_main.py`       | Fenêtre principale                            |
| `ui_dialogs.py`    | Dialogues : étudiants, matières, utilisateurs |
| `ui_stats.py`      | Fenêtre de statistiques                       |
| `database.py`      | Accès à la base SQLite                        |
| `auth.py`          | Authentification et gestion des rôles         |
| `calculs.py`       | Calculs de moyennes et statistiques           |
| `export.py`        | Export des relevés (HTML / CSV)               |
| `theme.py`         | Style graphique de l'interface                |
| `verification.py`  | Script de tests                               |

Les relevés exportés sont enregistrés dans le dossier `exports/`.

## Réinitialiser l'application

Supprimer le fichier `carnet_notes.db` : au prochain lancement, il sera recréé avec le compte `admin` / `admin123` et les données de démonstration. Toutes les données saisies seront perdues.

Si un fichier `carnet.json` (ancienne version de l'application) se trouve dans le dossier du projet ou dans le dossier parent, ses notes seront de nouveau importées.
