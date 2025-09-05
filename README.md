# DiagPilote – Backend (API + Worker + Scheduler)

Backend Flask/SQLAlchemy déployé via **Docker Compose** avec Nginx en reverse proxy.

## ✅ Endpoints principaux

- `GET /health` → statut simple `{ "status": "ok" }`
- `GET /kanban/` → blueprint *agenda* (renvoie `{ "status": "ok", "agenda": [] }`)
- `GET /dossiers` → liste les dossiers
- `POST /dossiers` → crée un dossier  
  Exemple :
  ```bash
  curl -X POST http://127.0.0.1/dossiers \
       -H 'Content-Type: application/json' \
       -d '{"client":"ACME","status":"nouveau"}'
