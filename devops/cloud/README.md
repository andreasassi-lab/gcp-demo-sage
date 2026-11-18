# Infrastruttura di Sage (Terraform)

Un solo ambiente: queste risorse coprono l'intero progetto di corso, non c'è una
separazione dev/test/prod. Ogni studente applica questo modulo sul proprio progetto GCP.

## Risorse create

| File | Risorsa | A cosa serve |
|---|---|---|
| `services.tf` | `google_project_service` | Abilita le API GCP usate dal progetto |
| `docs.tf` | `google_storage_bucket` | Bucket `<project_id>-sage-docs` per i documenti sorgente |
| `instructions.tf` | `google_storage_bucket`, `google_storage_bucket_iam_member` | Bucket `its-ict-sage-andrea-sassi-instructions` per `istruzioni.md`; Cloud Run può solo leggere gli oggetti |
| `firestore.tf` | `google_firestore_database`, `google_firestore_index` | Firestore Native + indice vettoriale sul campo `embedding` della collection `chunks` |
| `bigquery.tf` | `google_bigquery_dataset`, `google_bigquery_table` | Dataset `sage_analytics` e tabella `question_log` per l'analytics delle domande |
| `artifact_registry.tf` | `google_artifact_registry_repository` | Repository Docker per le immagini dell'API |
| `iam.tf` | `google_service_account`, `google_project_iam_member` | Service account runtime di Cloud Run, a privilegio minimo |
| `cloud_run.tf` | `google_cloud_run_v2_service`, `google_cloud_run_v2_service_iam_member` | Il servizio che espone `/api/ask` |

Niente Secret Manager: Sage chiama Vertex AI con Application Default Credentials, non
servono API key esterne da custodire come segreto.

## Nomi delle risorse: `resource_prefix`

`locals.tf` è l'unico punto in cui si decide come si chiamano le risorse. Con
`resource_prefix` vuoto (default) il progetto è dedicato e i nomi sono quelli fissi
(`sage`, `(default)`, `sage_analytics`; bucket `<project_id>-...`). Con `resource_prefix`
valorizzato (es. `its-ict-sage-mario-rossi`) il progetto è condiviso e ogni nome parte dal
prefisso, adattato alle regole di ogni servizio:

- Cloud Run e Artifact Registry: `<prefisso>-sage`
- Bucket: `<prefisso>-sage-docs`, `its-ict-sage-andrea-sassi-instructions` per le istruzioni (e `<prefisso>-tfstate` per lo state)
- Firestore: un database per persona, chiamato come il prefisso (in un progetto c'è un solo `(default)`)
- BigQuery: dataset `<prefisso con _ al posto di ->_sage_analytics` (i dataset non ammettono trattini)
- Service account: `<prefisso>-sage-run`, accorciato con un hash se supera i 30 caratteri

## Perché l'immagine Cloud Run non è gestita da Terraform

`cloud_run.tf` imposta `container_image` su un placeholder pubblico e poi lo ignora
(`lifecycle.ignore_changes`). L'immagine reale viene pubblicata dalla pipeline applicativa
(`.github/workflows/deploy.yml`, `gcloud run deploy --image ...`), tenuta volutamente
separata dalla pipeline Terraform (`.github/workflows/terraform.yml`): una modifica al
codice non richiede di rieseguire un piano Terraform, e viceversa.

## Comandi

```bash
cd devops/cloud

# una tantum: crea il bucket di state se non esiste già
gcloud storage buckets create gs://<project_id o resource_prefix>-tfstate \
  --project <project_id> --location europe-west6 --uniform-bucket-level-access

cp backend.hcl.example backend.hcl        # e modifica il bucket
cp terraform.tfvars.example terraform.tfvars  # e modifica project_id (e resource_prefix se condiviso)

terraform init -backend-config=backend.hcl
terraform plan  -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
```

In CI, lo stesso flusso gira nel workflow `terraform.yml`, avviato manualmente (tab
**Actions** del repository → *terraform* → *Run workflow*, oppure `gh workflow run
terraform.yml`): `plan`, poi un job `approval` che attende un'approvazione manuale su una
issue GitHub prima di eseguire `apply` sul piano già salvato.

## Istruzioni aggiuntive (task 2)

`sources/backend/istruzioni.md` è l'oggetto da caricare nel bucket; resta fuori da
`sources/backend/data/`, quindi non viene indicizzato come documento RAG. Dopo aver
configurato `backend.hcl` e `terraform.tfvars`, crea l'infrastruttura e carica il file
(esegui i comandi dalla root del repository; sostituisci i valori secondo `terraform.tfvars`):

```powershell
Set-Location devops\cloud
terraform init -backend-config=backend.hcl
terraform plan -var-file=terraform.tfvars
terraform apply -var-file=terraform.tfvars
Set-Location ..\..

$InstructionsBucket = "its-ict-sage-andrea-sassi-instructions"
gcloud storage cp .\sources\backend\istruzioni.md "gs://${InstructionsBucket}/istruzioni.md"
```

Il bucket ha accesso uniforme e pubblico disabilitato; il service account runtime di Cloud Run
riceve `roles/storage.objectViewer` solo su questo bucket. Dopo l'upload, avvia manualmente
**Actions → deploy → Run workflow** per pubblicare la versione aggiornata dell'app.

Recupera l'URL Cloud Run e apri Swagger:

```powershell
$ProjectId = "<project_id>"
$Region = "europe-west6"
$Service = "${Prefix}-sage-backend"
$Url = gcloud run services describe $Service --project $ProjectId --region $Region --format="value(status.url)"
Start-Process "$Url/docs"
```

In `/docs`, prova `POST /api/ask` con `{"question":"Chi sei e come rispondi?"}` e controlla
che la risposta adotti lo stile richiesto; il JSON continua a contenere `answer` e `sources`.
