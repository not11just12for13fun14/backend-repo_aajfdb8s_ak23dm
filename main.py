import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import httpx
from pydantic import BaseModel, EmailStr
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import School, PlatformUser

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PHOTON_URL = "https://photon.komoot.io/api/"

class NewAdminRequest(BaseModel):
    school_name: str
    admin_email: EmailStr

class NewAdminResponse(BaseModel):
    ok: bool
    school_id: Optional[str] = None
    message: str

@app.get("/")
def read_root():
    return {"message": "ERIKA Backend is running"}

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
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = os.getenv("DATABASE_NAME") or "❌ Not Set"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:20]
                response["connection_status"] = "Connected"
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

@app.get("/photon/search")
async def photon_search(q: str = Query(..., description="School name or address to search")):
    params = {"q": q, "limit": 5}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(PHOTON_URL, params=params)
        r.raise_for_status()
        data = r.json()
        results = []
        for f in data.get("features", []):
            props = f.get("properties", {})
            geometry = f.get("geometry", {})
            coords = geometry.get("coordinates", [None, None])
            results.append({
                "name": props.get("name") or props.get("country") or "Unknown",
                "osm_id": str(props.get("osm_id")),
                "type": props.get("type"),
                "city": props.get("city"),
                "country": props.get("country"),
                "address": props.get("name") or props.get("osm_value"),
                "lon": coords[0],
                "lat": coords[1]
            })
        return {"results": results}

@app.post("/admin/new", response_model=NewAdminResponse)
async def register_new_admin(payload: NewAdminRequest):
    # Call Photon from backend on behalf of frontend (to keep logic server-side)
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(PHOTON_URL, params={"q": payload.school_name, "limit": 1})
        r.raise_for_status()
        data = r.json()
    features = data.get("features", [])
    if not features:
        return NewAdminResponse(ok=False, message="No school match found in Photon/OSM")

    f = features[0]
    props = f.get("properties", {})
    geometry = f.get("geometry", {})
    coords = geometry.get("coordinates", [None, None])

    school_doc = School(
        name=props.get("name") or payload.school_name,
        address=props.get("osm_value") or props.get("name") or payload.school_name,
        latitude=coords[1],
        longitude=coords[0],
        admin_email=payload.admin_email,
        osm_id=str(props.get("osm_id")) if props.get("osm_id") is not None else None,
    )

    # Prevent duplicates by osm_id + admin_email
    existing = db["schools"].find_one({
        "$or": [
            {"osm_id": school_doc.osm_id},
            {"name": school_doc.name, "admin_email": school_doc.admin_email}
        ]
    })
    if existing:
        return NewAdminResponse(ok=False, message="School already registered")

    school_id = create_document("schools", school_doc)

    # Create PlatformUser with admin role (note: in real app, also create Firebase Auth)
    admin_user = PlatformUser(
        email=payload.admin_email,
        display_name="Administrator",
        role="admin",
        school_id=school_id,
    )
    create_document("users", admin_user)

    return NewAdminResponse(ok=True, school_id=school_id, message="School verified and admin created")

@app.get("/users/by-role")
def get_users_by_role(role: str, school_id: Optional[str] = None):
    filt = {"role": role}
    if school_id:
        filt["school_id"] = school_id
    users = get_documents("users", filt, limit=200)
    # Convert ObjectId
    out = []
    for u in users:
        u["_id"] = str(u.get("_id"))
        out.append(u)
    return {"users": out}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
