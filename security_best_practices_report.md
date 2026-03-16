# Security Best Practices Report

## Executive Summary

This repository is not ready for a public go-live in its current form. The highest-risk issue is that the deployed Streamlit app exposes transcription, summarization, PDF generation, and Google Docs export to any visitor without authentication or rate limiting. That creates an immediate path for cost abuse, unauthorized processing of sensitive call recordings, and unwanted document creation in the connected Google workspace.

## Critical

### SBP-001
- Rule ID: ACCESS-001
- Severity: Critical
- Location: `app.py:49`, `app.py:65`, `app.py:69`, `app.py:144`, `render.yaml:6`, `README.md:149`
- Evidence:

```python
st.title("Sales Coach")
uploaded_file = st.file_uploader("Upload a WAV sales call", type=["wav"])
generate_clicked = st.button("Process call", type="primary", disabled=uploaded_file is None)

if st.button("Export to Google Docs"):
```

```yaml
startCommand: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
```

```md
- This version assumes only one person uses the app.
```

- Impact: Any person who can reach the deployed URL can spend your OpenAI budget, submit arbitrary audio for transcription, trigger exports into your Google environment, and process potentially sensitive customer calls without authorization.
- Fix: Put the app behind real authentication before launch. At minimum, require SSO or a reverse-proxy auth gate, restrict access to approved users, and block Google Docs export for anonymous traffic.
- Mitigation: If a public launch is unavoidable, disable the processing and export actions until auth, quota controls, and abuse monitoring exist.
- False positive notes: This is only mitigated if an access-control layer exists outside the repo, such as Cloudflare Access, OAuth proxy, or equivalent enforced before requests hit Streamlit.

## High

### SBP-002
- Rule ID: UPLOAD-001
- Severity: High
- Location: `app.py:65`, `app.py:74`
- Evidence:

```python
uploaded_file = st.file_uploader("Upload a WAV sales call", type=["wav"])
transcript = transcribe_call(uploaded_file.name, uploaded_file.getvalue())
```

- Impact: The app accepts arbitrary WAV uploads with no size, duration, or request-rate controls, then reads the full file into memory and sends it to a paid upstream API. An attacker can use this to drive cost spikes or exhaust app memory and worker capacity.
- Fix: Enforce server-side upload size and duration limits, reject oversized files before `getvalue()`, and add rate limiting or per-user quotas at the edge.
- Mitigation: Restrict access to known users and add infrastructure-level request body limits immediately.
- False positive notes: An upstream proxy may already cap body size, but no such limit is defined in this repo and the application itself performs no validation.

### SBP-003
- Rule ID: PRIVACY-001
- Severity: High
- Location: `services/openai_service.py:49`, `services/openai_service.py:79`, `services/google_docs.py:34`, `services/google_docs.py:127`
- Evidence:

```python
response = client.audio.transcriptions.create(**request_kwargs)
response = client.responses.create(
```

```python
document = self.docs_service.documents().create(body={"title": title}).execute()
if self.share_email:
    self.drive_service.permissions().create(
```

- Impact: Uploaded sales calls and derived transcripts are transmitted to third-party processors and optionally shared into Google Drive without any consent flow, policy checks, or user-level authorization. For customer calls, this is a live data-handling risk, not just a product detail.
- Fix: Document and approve the data flow before launch, add explicit user notice/consent, restrict who can upload, and consider disabling Google export until privacy/legal review is complete.
- Mitigation: Limit usage to internal test data only until vendor approval, retention expectations, and access controls are in place.
- False positive notes: This may be acceptable for an internal-only tool with approved vendors and contracts, but that approval is not visible in code.

## Medium

### SBP-004
- Rule ID: LEAST-PRIV-001
- Severity: Medium
- Location: `services/google_docs.py:9`
- Evidence:

```python
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]
```

- Impact: The Google integration requests full Drive access instead of the narrowest scope needed. If the app or service account is abused, the blast radius is larger than necessary.
- Fix: Reduce Drive access to the minimum scope that supports document creation and placement, such as `drive.file` if it satisfies the workflow, and constrain the service account to a dedicated folder.
- Mitigation: Use a dedicated Google project and service account that has access only to a non-sensitive workspace location.
- False positive notes: The real blast radius depends on what this service account can reach in Google Drive; verify its folder and sharing permissions.

### SBP-005
- Rule ID: ERRORS-001
- Severity: Medium
- Location: `app.py:78`, `app.py:91`
- Evidence:

```python
except Exception as exc:  # noqa: BLE001
    st.error(f"Transcription failed: {exc}")
```

```python
except Exception as exc:  # noqa: BLE001
    st.error(f"Summary generation failed: {exc}")
```

- Impact: Raw exception messages from upstream services are shown directly to end users. Those messages can reveal internal implementation details, request metadata, or operational state that should stay server-side.
- Fix: Replace user-facing raw exceptions with generic messages and log detailed errors privately.
- Mitigation: Ensure production logging is protected and avoid exposing stack traces or provider error payloads to browsers.
- False positive notes: The severity depends on what upstream SDKs include in exception text, but exposing raw backend exceptions in production is still a weak default.

## Launch Recommendation

Do not expose this app publicly yet. The minimum go-live bar is:

1. Add authentication in front of the Streamlit app.
2. Add upload limits and rate limiting.
3. Review and approve the OpenAI and Google data flow for real customer calls.
4. Reduce Google permissions and scope the service account down.
5. Sanitize user-facing error handling.
