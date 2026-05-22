from fastapi import FastAPI

app = FastAPI(title="Prueba Técnica Polizas")


@app.get("/health")
def health_check():
    return {"status": "ok"}
