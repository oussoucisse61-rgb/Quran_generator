# 🕌 Quran Generator — Web App

Interface web pour générer automatiquement des vidéos coraniques.
Accessible depuis n'importe quel appareil (téléphone, tablette, PC).

---

## 🚀 Déploiement sur Render.com (gratuit)

### Étape 1 — Mettre le code sur GitHub
1. Créez un compte sur [github.com](https://github.com)
2. Créez un nouveau repository public
3. Uploadez tous les fichiers de ce dossier

### Étape 2 — Déployer sur Render
1. Créez un compte sur [render.com](https://render.com)
2. Cliquez **"New Web Service"**
3. Connectez votre repository GitHub
4. Render détecte automatiquement la config grâce au `render.yaml`
5. Dans **Environment Variables**, ajoutez :
   - `PEXELS_API_KEY` = votre clé Pexels

### Étape 3 — Installer FFmpeg sur Render
Dans les paramètres du service Render, ajoutez cette commande de build :
```
pip install -r requirements.txt && apt-get install -y ffmpeg
```

### Étape 4 — C'est en ligne !
Render vous donne une URL du type `https://quran-tiktok-generator.onrender.com`
Partagez ce lien et tout le monde peut l'utiliser !

---

## ⚠️ Limitations du plan gratuit Render

- Le serveur "s'endort" après 15 min d'inactivité (premier chargement lent)
- 512 MB de RAM (suffisant pour les courtes sourates)
- Pour les longues sourates (Al-Baqara etc.), préférez le plan payant (7$/mois)

---

## 📁 Structure

```
quran_web/
├── server.py          ← Backend Flask
├── templates/
│   └── index.html     ← Interface web
├── requirements.txt   ← Dépendances Python
├── Procfile           ← Commande de démarrage
├── render.yaml        ← Config Render automatique
└── README.md          ← Ce fichier
```

---

## 🛠️ Lancer en local (pour tester)

```bash
pip install -r requirements.txt
set PEXELS_API_KEY=votre_cle_ici
python server.py
```

Puis ouvrez : `http://localhost:5000`

---

*Qu'Allah accepte ce travail. 🤲*
