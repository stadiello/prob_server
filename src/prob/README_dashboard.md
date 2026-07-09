# Dashboard local micro:bit v2

Dashboard Flask ultra minimaliste pour afficher les mesures CSV du micro:bit.

## Nouveautés V2

- Graphique minimal.
- Sélection date début / date fin.
- Raccourcis : aujourd'hui, 7 jours, 30 jours.
- Choix de la métrique : température, luminosité, son.
- Déduplication simple par `device_id + seq`.
- Compatible Python 3.9.

## Installation

Depuis le Raspberry Pi :

```bash
cd ~/prob
poetry add flask
nano src/prob/dashboard.py
```

Colle le contenu de `dashboard.py`.

Puis lance :

```bash
poetry run python src/prob/dashboard.py
```

Depuis ton Mac, ouvre :

```text
http://IP_DU_RASPBERRY:8080
```

Exemple :

```text
http://192.168.1.42:8080
```

## Service systemd

Crée le fichier :

```bash
sudo nano /etc/systemd/system/microbit-dashboard.service
```

Vérifie d'abord le chemin Python exact :

```bash
cd ~/prob
poetry run which python
```

Puis adapte `ExecStart`.

Commandes :

```bash
sudo systemctl daemon-reload
sudo systemctl enable microbit-dashboard.service
sudo systemctl restart microbit-dashboard.service
journalctl -u microbit-dashboard.service -f
```

## API locale

Dernière mesure :

```text
http://IP_DU_RASPBERRY:8080/api/latest
```

Données filtrées :

```text
http://IP_DU_RASPBERRY:8080/api/data?period=7d&metric=temperature_c
```

ou :

```text
http://IP_DU_RASPBERRY:8080/api/data?start=2026-07-01&end=2026-07-09&metric=light_level
```

