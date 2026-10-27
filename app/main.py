"""Small independent consumer of the Aegis Python web delivery profile."""

from typing import Annotated

from fastapi import FastAPI, Query

from app import __version__

app = FastAPI(title="Hello Aegis", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/")
def greeting():
    return {
        "app": "hello-aegis",
        "message": "Hello from an application deployed by Aegis",
        "version": __version__,
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {"app": "hello-aegis", "version": __version__}


@app.get("/api/echo")
def echo(message: Annotated[str, Query(min_length=1, max_length=120)]):
    return {"message": message}
