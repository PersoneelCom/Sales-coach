# Sales Coach

A simple browser app for uploading WAV sales calls, generating a transcript, creating a sales summary, and exporting the result to Google Docs or PDF.

## What this MVP does

- Upload one `.wav` file
- Transcribe Dutch and English calls
- Show speaker-labeled transcript
- Let you rename `Speaker 1` and `Speaker 2`
- Generate a clean markdown summary
- Export to Google Docs
- Download a PDF

## Project structure

```text
Sales-coach-main/
  app.py
  requirements.txt
  services/
    config.py
    google_docs.py
    openai_service.py
    pdf_export.py
    transcript_utils.py
```

## 1. Create your OpenAI API key

You still need an OpenAI API key for transcription and summaries.

Add it to a local `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_TRANSCRIPTION_MODEL=gpt-4o-transcribe-diarize
OPENAI_SUMMARY_MODEL=gpt-4o-mini
AUTH_REQUIRED=true
APP_PASSWORD_HASH='pbkdf2_sha256$390000$replace_me$replace_me'
MAX_UPLOAD_MB=50
MAX_AUDIO_MINUTES=30
PROCESS_COOLDOWN_SECONDS=60
ALLOW_GOOGLE_EXPORT=true
```

Generate `APP_PASSWORD_HASH` with:

```powershell
python -c "from services.security import build_password_hash; print(build_password_hash('choose-a-strong-password'))"
```

If you store the hash in a local `.env` file that Docker Compose will read, keep the value quoted because the hash contains `$` characters.

## 2. Set up Google Docs export

This app uses a Google service account for document creation.

### Create the Google Cloud project

1. Go to Google Cloud Console.
2. Create a new project.
3. Enable the Google Docs API.
4. Enable the Google Drive API.
5. Create a service account.
6. Create a JSON key for that service account.

### Add the Google credential

Put the whole JSON into `.env` as one line:

```env
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"..."}
GOOGLE_DOC_SHARE_EMAIL=your_google_email@gmail.com
GOOGLE_DRIVE_FOLDER_ID=
```

`GOOGLE_DOC_SHARE_EMAIL` is the Google account that should receive access to the generated document.

`GOOGLE_DRIVE_FOLDER_ID` is optional. If you leave it empty, the document is still created and shared.

For Streamlit Community Cloud, copy the same values into app secrets. A starter example is in `.streamlit/secrets.toml.example`.

## 3. Install and run locally

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the app:

```powershell
streamlit run app.py
```

For this machine, you can also start it with:

```powershell
.\run_app.ps1
```

## 3a. What you still need to fill in

Open `.env` and add:

- `OPENAI_API_KEY`: your new rotated OpenAI key
- `APP_PASSWORD_HASH`: a strong password hash for the access gate
- `GOOGLE_SERVICE_ACCOUNT_JSON`: the full JSON from your Google service account
- `GOOGLE_DOC_SHARE_EMAIL`: your Gmail address

Without those values:

- transcription and summaries will not work
- access control will block the app when `AUTH_REQUIRED=true`
- Google Docs export will not work
- PDF export is already wired in the app

## 4. Deploy with Coolify

This repo now includes a `Dockerfile` and `docker-compose.yml`, so Coolify can deploy it as a Docker-based app without a custom start command.

For a Coolify deployment on a bare metal server:

1. Create a new Docker-based application in Coolify from this repository.
2. Use the included `Dockerfile`.
3. Expose port `8501` internally. Coolify can keep handling the public port and HTTPS.
2. Set these environment variables in Coolify:
- `OPENAI_API_KEY`
- `APP_PASSWORD_HASH`
- `AUTH_REQUIRED=true`
- `MAX_UPLOAD_MB`
- `MAX_AUDIO_MINUTES`
- `PROCESS_COOLDOWN_SECONDS`
- `ALLOW_GOOGLE_EXPORT`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_DOC_SHARE_EMAIL`
- `GOOGLE_DRIVE_FOLDER_ID` if you want a fixed folder
4. Enable HTTPS on the Coolify-managed domain before real users access the app.
5. Configure an ingress request-body limit that matches `MAX_UPLOAD_MB`.
6. Add edge rate limiting in the reverse proxy. The in-app cooldown helps, but it is not a substitute for network-layer throttling.

### Local Docker run

For local parity with the containerized deployment:

```powershell
docker compose up --build
```

The app will be available on `http://localhost:8501`.

## 5. Auth model

The current auth is a single shared password gate inside the Streamlit app.

- `AUTH_REQUIRED=true` makes the app fail closed and show only the login form until a user enters the correct password.
- `APP_PASSWORD_HASH` stores a PBKDF2-SHA256 hash, not the raw password.
- The password is verified in-app against that hash before upload or processing controls are shown.
- This is suitable for a small internal tool, but it is not user-based auth and it does not give you audit trails, per-user permissions, or SSO.

Generate a new hash with:

```powershell
python -c "from services.security import build_password_hash; print(build_password_hash('choose-a-strong-password'))"
```

For anything beyond a small internal deployment, put the app behind stronger edge auth as well, such as Coolify behind an OAuth proxy, Cloudflare Access, or your existing SSO layer.

### Recommended production controls

- Keep `AUTH_REQUIRED=true`.
- Use a long random password and rotate it if access changes.
- Restrict the Google service account to a dedicated folder and least-privilege workspace access.
- Keep the app internal or behind an additional edge access layer if possible.
- Do not upload customer calls until your OpenAI and Google data handling is approved internally.

## Important limitations in this MVP

- Speaker diarization quality depends on the transcription model output.
- Access control is password-based unless you add stronger auth in front of the app.
- The app does not store transcripts in a database yet.
- Google Docs export needs setup before it will work.
