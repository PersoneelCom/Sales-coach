$python = "C:\Users\floor\AppData\Local\Programs\Python\Python312\python.exe"
$streamlit = "C:\Users\floor\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python is not installed at the expected path: $python"
    exit 1
}

if (-not (Test-Path $streamlit)) {
    Write-Error "Streamlit is not installed at the expected path: $streamlit"
    exit 1
}

& $streamlit run app.py
