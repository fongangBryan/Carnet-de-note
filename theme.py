"""Palette de couleurs et styles ttk partagés par toutes les fenêtres.

On reprend les couleurs de la version customtkinter d'origine
(bleu #1f538d, rouge #C0392B, vert #27AE60, bleu clair #2980B9).
"""

from tkinter import ttk

POLICE = "Segoe UI"

PRIMAIRE, PRIMAIRE_HOVER = "#1f538d", "#163d69"
DANGER, DANGER_HOVER = "#C0392B", "#922B21"
SUCCES, SUCCES_HOVER = "#27AE60", "#1E8449"
INFO, INFO_HOVER = "#2980B9", "#1F618D"
VIOLET, VIOLET_HOVER = "#8E44AD", "#6C3483"
NEUTRE, NEUTRE_HOVER = "#5D6D7E", "#455463"

FOND = "#eef1f5"
CARTE = "#ffffff"
TEXTE = "#1c2833"
TEXTE_DOUX = "#5d6d7e"
BORDURE = "#d5dbe3"
LIGNE_PAIRE = "#f5f7fa"
GRILLE = "#e5e8ec"

BOUTONS = {
    "Primaire": (PRIMAIRE, PRIMAIRE_HOVER),
    "Danger": (DANGER, DANGER_HOVER),
    "Succes": (SUCCES, SUCCES_HOVER),
    "Info": (INFO, INFO_HOVER),
    "Violet": (VIOLET, VIOLET_HOVER),
    "Neutre": (NEUTRE, NEUTRE_HOVER),
}


def appliquer_style(racine):
    """Configure le thème ttk « clam » (obligatoire pour personnaliser les couleurs)."""
    racine.configure(bg=FOND)
    style = ttk.Style(racine)
    style.theme_use("clam")

    style.configure(".", font=(POLICE, 10), background=FOND, foreground=TEXTE)
    style.configure("TFrame", background=FOND)
    style.configure("Carte.TFrame", background=CARTE)

    style.configure("TLabel", background=FOND, foreground=TEXTE)
    style.configure("Carte.TLabel", background=CARTE)
    style.configure("Entete.TLabel", font=(POLICE, 18, "bold"), foreground=PRIMAIRE)
    style.configure("Sous.TLabel", foreground=TEXTE_DOUX)
    style.configure("CarteSous.TLabel", background=CARTE, foreground=TEXTE_DOUX)
    style.configure("CarteTitre.TLabel", background=CARTE, foreground=PRIMAIRE,
                    font=(POLICE, 16, "bold"))
    style.configure("Statut.TLabel", font=(POLICE, 11, "bold"))
    style.configure("Valeur.TLabel", background=CARTE, font=(POLICE, 11, "bold"))
    style.configure("Grand.TLabel", background=CARTE, foreground=PRIMAIRE,
                    font=(POLICE, 20, "bold"))
    style.configure("Erreur.TLabel", background=CARTE, foreground=DANGER)
    style.configure("Utilisateur.TLabel", font=(POLICE, 10, "bold"), foreground=PRIMAIRE)

    style.configure("TLabelframe", background=CARTE, bordercolor=BORDURE, relief="solid")
    style.configure("TLabelframe.Label", background=CARTE, foreground=PRIMAIRE,
                    font=(POLICE, 11, "bold"))
    style.configure("TCheckbutton", background=CARTE)
    style.map("TCheckbutton", background=[("active", CARTE)])

    style.configure("TEntry", padding=4, fieldbackground="white", bordercolor=BORDURE)
    style.configure("Invalide.TEntry", padding=4, fieldbackground="#fdecea", bordercolor=DANGER)
    style.configure("TCombobox", padding=3, bordercolor=BORDURE)
    style.map("TCombobox",
              fieldbackground=[("readonly", "white"), ("disabled", FOND)],
              selectbackground=[("readonly", "white")],
              selectforeground=[("readonly", TEXTE)])

    for nom, (couleur, survol) in BOUTONS.items():
        style.configure(f"{nom}.TButton", background=couleur, foreground="white",
                        borderwidth=0, focusthickness=0, padding=(12, 6),
                        font=(POLICE, 10, "bold"))
        style.map(f"{nom}.TButton",
                  background=[("disabled", "#b3bcc6"), ("pressed", survol), ("active", survol)],
                  foreground=[("disabled", "#eef1f5")])

    # Tableau : mêmes réglages que la version d'origine
    style.configure("Treeview", background=CARTE, fieldbackground=CARTE, foreground=TEXTE,
                    rowheight=30, font=(POLICE, 11), bordercolor=BORDURE)
    style.configure("Treeview.Heading", background=PRIMAIRE, foreground="white",
                    font=(POLICE, 11, "bold"), relief="flat", padding=6)
    style.map("Treeview.Heading", background=[("active", PRIMAIRE_HOVER)])
    style.map("Treeview", background=[("selected", PRIMAIRE)],
              foreground=[("selected", "white")])

    style.configure("TNotebook", background=CARTE, bordercolor=BORDURE)
    style.configure("TNotebook.Tab", padding=(14, 6), font=(POLICE, 10, "bold"))
    style.map("TNotebook.Tab", background=[("selected", CARTE)],
              foreground=[("selected", PRIMAIRE)])
    return style
