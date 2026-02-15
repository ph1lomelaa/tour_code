from typing import List, Optional, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests

app = FastAPI(title="Fondkamkor Wrapper API")

FONDKAMKOR_URL = "http://test.fondkamkor.kz"


# =========================
# МОДЕЛИ ДЛЯ СОЗДАНИЯ ТУРА
# =========================

class InputData(BaseModel):
    q_touragent: str
    q_touragent_bin: str
    q_country: str
    q_countryen: str
    q_airport_start: str
    q_airlines: str
    q_airport: str
    q_date_from: str
    q_date_to: str
    q_days: Optional[int] = None
    q_remark: Optional[str] = None
    q_hotel: Optional[str] = None
    q_flight: Optional[str] = None
    q_flight_from: Optional[str] = None
    clientcounter: int
    c_name_0: str
    c_borned_0: str
    c_doc_date_0: Optional[str] = None
    c_doc_number_0: str
    c_doc_production_0: Optional[str] = None


class CreateTourRequest(BaseModel):
    input: InputData


class CreateTourResponset(BaseModel):
    status: int
    string: str


# =========================
# МОДЕЛИ ДЛЯ СПРАВОЧНИКОВ
# =========================

class DictCountriesInput(BaseModel):
    what: List[str]
    output: str  # обычно "array"


class DictCountriesRequest(BaseModel):
    input: DictCountriesInput


# =========================
# ЭНДПОЙНТ: СОЗДАНИЕ ТУРА
# =========================

@app.post("/api/v1/tour/create", response_model=CreateTourResponse)
def create_tour(req: CreateTourRequest):
    payload = {
        "input": req.input.model_dump(exclude_none=True),
        "module": "voucher",
        "section": "partner",
        "object": "queries",
        "param1": "163",
        "param2": "save",
        "formid": 163,
        "agentlogin": "test",
        "agentpass": "test",
        "return": "q_number",
    }

    try:
        resp = requests.post(
            FONDKAMKOR_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Fondkamkor returned non-200 HTTP")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid JSON from Fondkamkor")

    if "status" not in data or "string" not in data:
        raise HTTPException(status_code=502, detail="Unexpected response format")

    return CreateTourResponse(**data)


# =========================
# ЭНДПОЙНТ: СПРАВОЧНИК СТРАН
# =========================

@app.post("/api/v1/dictionaries/countries")
def get_countries(req: DictCountriesRequest):
    payload = {
        "input": req.input.model_dump(),
        "module": "voucher",
        "section": "partner",
        "object": "dictionaries",
        "param1": "get",
        "param2": "countries",
        "agentlogin": "test",
        "agentpass": "test",
    }

    try:
        resp = requests.post(
            FONDKAMKOR_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Fondkamkor returned non-200 HTTP")

    try:
        data = resp.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Invalid JSON from Fondkamkor")

    return data
