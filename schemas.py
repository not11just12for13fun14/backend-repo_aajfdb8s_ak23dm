from typing import Optional, Literal, List
from pydantic import BaseModel, Field, EmailStr

# ERIKA platform schemas

class School(BaseModel):
    name: str = Field(..., description="Verified school name")
    address: str = Field(..., description="Full address from Photon/OSM")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    admin_email: EmailStr = Field(..., description="Primary admin email")
    osm_id: Optional[str] = Field(None, description="OSM/Photon place id for dedupe")

class PlatformUser(BaseModel):
    email: EmailStr
    display_name: str = Field(..., description="Full name to show in UI")
    role: Literal['admin','student','teacher','parent']
    school_id: str = Field(..., description="Reference to schools _id")
    disabled: bool = False

class Assignment(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    subject: Optional[str] = None
    school_id: str
    teacher_id: str
    class_id: Optional[str] = None

class AttendanceRecord(BaseModel):
    school_id: str
    class_id: Optional[str] = None
    student_id: str
    date: str
    status: Literal['present','absent','late','excused']

class Quiz(BaseModel):
    school_id: str
    title: str
    questions: List[dict] = Field(default_factory=list)
    source: Optional[str] = Field(None, description="material|ai|manual")
