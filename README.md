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
```

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
- `GOOGLE_SERVICE_ACCOUNT_JSON`: the full JSON from your Google service account
- `GOOGLE_DOC_SHARE_EMAIL`: your Gmail address

Without those values:

- transcription and summaries will not work
- Google Docs export will not work
- PDF export is already wired in the app

## 4. How publishing works later

The easiest path is Streamlit Community Cloud:

1. Push this repo to GitHub.
2. Create a Streamlit Community Cloud account.
3. Connect the GitHub repo.
4. Set your secrets there instead of using `.env`.
5. Deploy `app.py`.

## 5. Deploy with a real custom domain

If you want a domain like `salescoach.personeel.com`, use Render instead of Streamlit Community Cloud.

This repo includes `render.yaml`, so Render can read the app settings directly from the repository.

### Render deployment flow

1. Create or sign in to your Render account.
2. Create a new Blueprint instance from this GitHub repository.
3. Let Render read `render.yaml`.
4. Add these environment variables in Render:
- `OPENAI_API_KEY`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_DOC_SHARE_EMAIL`
- `GOOGLE_DRIVE_FOLDER_ID` if you want a fixed folder
5. Deploy the web service.

After deployment, Render will give you a public `onrender.com` URL.

### Connect `salescoach.personeel.com`

1. In Render, open the deployed service.
2. Go to `Settings` -> `Custom Domains`.
3. Add `salescoach.personeel.com`.
4. In your DNS provider for `personeel.com`, create the CNAME record that Render tells you to create.
5. Wait for verification and SSL certificate issuance.

After DNS verification, `https://salescoach.personeel.com` will point to the app.

## Important limitations in this MVP

- Speaker diarization quality depends on the transcription model output.
- This version assumes only one person uses the app.
- The app does not store transcripts in a database yet.
- Google Docs export needs setup before it will work.
