# Jobs API quickref

## Endpoints
- Enqueue : `POST /jobs/test?n=<int>` (header **X-Job-Token** requis)
- Status  : `GET  /jobs/<job_id>`
- Download: `GET  /jobs/<job_id>/download`

Notes :
- `GET /jobs/test` → **405** (POST only)
- Rate limit Nginx sur `/jobs/test` → **429** si dépassé
- TTL résultat: **24h** ; TTL erreurs: **7j**
- Purge fichiers: cron quotidien côté hôte

## Exemples `curl`

# Récupérer le token réellement chargé par le conteneur
TOKEN=$(docker compose exec -T web printenv JOB_ENQUEUE_TOKEN | tr -d '\r')

# Enqueue (POST + token)
curl -sk -X POST -H "X-Job-Token: $TOKEN" \
  "https://diagpilote.app/jobs/test?n=2"

# Enqueue + récupérer uniquement le job_id
JOB=$(curl -sk -X POST -H "X-Job-Token: $TOKEN" \
  "https://diagpilote.app/jobs/test?n=2" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["job_id"])')
echo "JOB=$JOB"

# Statut
curl -sk "https://diagpilote.app/jobs/$JOB"

# (optionnel) Poll jusqu'à terminé
for i in {1..15}; do
  R=$(curl -sk "https://diagpilote.app/jobs/$JOB")
  echo "$R" | grep -q '"status":"finished"' && { echo "$R"; break; }
  sleep 1
done

# Download
curl -sk -OJ "https://diagpilote.app/jobs/$JOB/download"
### Idempotence
- Envoie l’en-tête `Idempotency-Key: <clé-unique>` pour éviter les doublons.
- Fenêtre configurable via `IDEMPOTENCY_TTL` (par défaut **900s**).

Exemple :
```bash
TOKEN=$(docker compose exec -T web printenv JOB_ENQUEUE_TOKEN | tr -d '\r')
KEY="demo-$(date +%s)"

# 1er POST -> crée le job
curl -sk -X POST -H "X-Job-Token: $TOKEN" -H "Idempotency-Key: $KEY" \
  "https://diagpilote.app/jobs/test?n=2"

# 2e POST (même clé) -> renvoie le même job_id
curl -sk -X POST -H "X-Job-Token: $TOKEN" -H "Idempotency-Key: $KEY" \
  "https://diagpilote.app/jobs/test?n=2"

```
