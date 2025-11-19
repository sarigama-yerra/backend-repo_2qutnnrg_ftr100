import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson.objectid import ObjectId
import requests

from database import db, create_document, get_documents
from schemas import Cat

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- Utilities ---------

def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid id format")


def fetch_weather(lat: float, lon: float):
    # Using Open-Meteo (no API key required)
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,wind_speed_10m,precipitation,is_day"
        "&hourly=temperature_2m,apparent_temperature,precipitation_probability,weather_code"
        "&timezone=auto"
    )
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()


def coat_recommendation(temp_c: float, wind_kmh: float, precipitation_mm: float, is_day: bool):
    # Simple heuristic tailored for cats
    # Convert to human-friendly bands
    # Consider wind chill by nudging temp down if windy
    adjusted = temp_c - (0.1 * wind_kmh / 5.0)

    if precipitation_mm >= 1.0:
        precip_note = "Rainy"
    elif precipitation_mm > 0.1:
        precip_note = "Drizzly"
    else:
        precip_note = "Dry"

    # Day vs Night nuance (outside vs inside rug)
    context = "Day (outside rug)" if is_day else "Night (inside rug)"

    if adjusted < -5:
        coat = "Thermal coat + booties"
        note = "Very cold. Limit outdoor time."
    elif adjusted < 5:
        coat = "Insulated coat"
        note = "Chilly. Keep sessions short."
    elif adjusted < 12:
        coat = "Light coat"
        note = "Cool but manageable."
    elif adjusted < 20:
        coat = "No coat, optional light vest"
        note = "Comfortable temps."
    else:
        coat = "No coat"
        note = "Warm. Provide shade and water."

    if not is_day:
        # At night, many cats are indoors; suggest rug/blanket context
        note += " Use a cozy indoor rug/blanket for naps."

    return {
        "context": context,
        "coat": coat,
        "note": note,
        "precip": precip_note,
        "adjusted_temp_c": round(adjusted, 1),
    }


# -------- Models ----------

class CatCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    city: Optional[str] = None
    notes: Optional[str] = None
    units: str = Field("metric", pattern="^(metric|imperial)$")


# -------- Routes ----------

@app.get("/")
def read_root():
    return {"message": "Cats Weather & Coat Advisor API"}


@app.get("/api/cats")
def list_cats():
    cats = get_documents("cat")
    # Convert ObjectId to string
    for c in cats:
        c["id"] = str(c.get("_id"))
        c.pop("_id", None)
    return {"cats": cats}


@app.post("/api/cats")
def create_cat(payload: CatCreate):
    cat = Cat(**payload.model_dump())
    new_id = create_document("cat", cat)
    return {"id": new_id}


@app.delete("/api/cats/{cat_id}")
def delete_cat(cat_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    result = db["cat"].delete_one({"_id": to_object_id(cat_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cat not found")
    return {"status": "deleted"}


@app.get("/api/recommendations/{cat_id}")
def get_recommendation(cat_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    doc = db["cat"].find_one({"_id": to_object_id(cat_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Cat not found")

    lat = float(doc["latitude"]) 
    lon = float(doc["longitude"]) 

    weather = fetch_weather(lat, lon)
    current = weather.get("current", {})

    temp_c = float(current.get("temperature_2m", 0))
    wind_kmh = float(current.get("wind_speed_10m", 0))
    precipitation_mm = float(current.get("precipitation", 0))
    is_day = bool(current.get("is_day", 1))

    rec_day = coat_recommendation(temp_c, wind_kmh, precipitation_mm, True)
    rec_night = coat_recommendation(temp_c, wind_kmh, precipitation_mm, False)

    payload = {
        "cat": {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "city": doc.get("city"),
            "notes": doc.get("notes"),
        },
        "weather": {
            "temperature_c": temp_c,
            "apparent_c": float(current.get("apparent_temperature", temp_c)),
            "wind_kmh": wind_kmh,
            "precipitation_mm": precipitation_mm,
            "is_day": is_day,
        },
        "recommendations": {
            "day": rec_day,
            "night": rec_night,
        },
    }
    return payload


@app.get("/api/dashboard")
def dashboard():
    # aggregate all cats with current weather and recs
    cats = get_documents("cat")
    items = []
    for doc in cats:
        try:
            weather = fetch_weather(float(doc["latitude"]), float(doc["longitude"]))
            current = weather.get("current", {})
            temp_c = float(current.get("temperature_2m", 0))
            wind_kmh = float(current.get("wind_speed_10m", 0))
            precipitation_mm = float(current.get("precipitation", 0))
            is_day = bool(current.get("is_day", 1))
            items.append({
                "cat": {
                    "id": str(doc["_id"]),
                    "name": doc.get("name"),
                    "city": doc.get("city"),
                    "notes": doc.get("notes"),
                },
                "weather": {
                    "temperature_c": temp_c,
                    "apparent_c": float(current.get("apparent_temperature", temp_c)),
                    "wind_kmh": wind_kmh,
                    "precipitation_mm": precipitation_mm,
                    "is_day": is_day,
                },
                "recommendations": {
                    "day": coat_recommendation(temp_c, wind_kmh, precipitation_mm, True),
                    "night": coat_recommendation(temp_c, wind_kmh, precipitation_mm, False),
                }
            })
        except Exception as e:
            items.append({
                "cat": {
                    "id": str(doc.get("_id")),
                    "name": doc.get("name"),
                    "city": doc.get("city"),
                },
                "error": str(e)[:120]
            })
    return {"items": items}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
