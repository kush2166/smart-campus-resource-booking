from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import mysql.connector
from pydantic import BaseModel
from datetime import datetime

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Kush@123$",  # Keep your working MySQL password here
    "database": "smart_campus_db"
}

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# Modern Lifespan context manager replacing startup events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic: Auto-create tables if they don't exist
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            category VARCHAR(100) NOT NULL,
            total_quantity INT DEFAULT 1
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_name VARCHAR(255) NOT NULL,
            resource_id INT NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            status VARCHAR(50) DEFAULT 'Confirmed',
            FOREIGN KEY (resource_id) REFERENCES resources(id) ON DELETE CASCADE
        );
    """)
    conn.commit()
    cursor.close()
    conn.close()
    yield

app = FastAPI(title="Smart Campus Facility & Resource Booking System", lifespan=lifespan)

# Enable CORS for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class ResourceCreate(BaseModel):
    name: str
    category: str
    total_quantity: int = 1

class BookingCreate(BaseModel):
    user_name: str
    resource_id: int
    start_time: datetime
    end_time: datetime
    status: str = "Confirmed"

# API Routes
@app.get("/api/resources")
def get_resources():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM resources")
    resources = cursor.fetchall()
    cursor.close()
    conn.close()
    return resources

@app.post("/api/resources", status_code=status.HTTP_201_CREATED)
def create_resource(resource: ResourceCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO resources (name, category, total_quantity) VALUES (%s, %s, %s)",
        (resource.name, resource.category, resource.total_quantity)
    )
    conn.commit()
    resource_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": resource_id, **resource.dict()}

@app.get("/api/bookings")
def get_bookings():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM bookings")
    bookings = cursor.fetchall()
    cursor.close()
    conn.close()
    return bookings

@app.post("/api/bookings", status_code=status.HTTP_201_CREATED)
def create_booking(booking: BookingCreate):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check for time slot overlap conflicts
    cursor.execute("""
        SELECT * FROM bookings 
        WHERE resource_id = %s 
        AND start_time < %s 
        AND end_time > %s
    """, (booking.resource_id, booking.end_time, booking.start_time))
    
    conflict = cursor.fetchone()
    if conflict:
        cursor.close()
        conn.close()
        raise HTTPException(
            status_code=400, 
            detail="Time slot conflict: This resource is already booked for the selected period."
        )

    cursor.execute(
        "INSERT INTO bookings (user_name, resource_id, start_time, end_time, status) VALUES (%s, %s, %s, %s, %s)",
        (booking.user_name, booking.resource_id, booking.start_time, booking.end_time, booking.status)
    )
    conn.commit()
    booking_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return {"id": booking_id, **booking.dict()}

# === MOUNT THE STATIC FRONTEND DIRECTORY (Crucial) ===
app.mount("/static", StaticFiles(directory="static"), name="static")