from typing import List
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, status

from app.config import engine, Base, AsyncSessionLocal, get_db
from app import schemas, crud, models
from sqlalchemy import select, func

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Automatically build database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Seed data routines safely
    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count(models.Course.id)))).scalar()
        if count == 0:
            seed_courses = [
                models.Course(title="Python Basics", description="Learn Python fundamentals", total_lessons=5),
                models.Course(title="Intro to FastAPI", description="Build high-performance async APIs", total_lessons=3),
                models.Course(title="SQL 101", description="Master relational database architectures", total_lessons=10)
            ]
            # Create a demo user to make standard testing immediate
            seed_user = models.User(name="Alex Dev", email="alex@example.com")
            
            session.add_all(seed_courses)
            session.add(seed_user)
            await session.commit()
            print("Database initialized and successfully seeded.")
    yield

app = FastAPI(title="EduTrack — Micro-Learning Progress & Analytics API", lifespan=lifespan)

# --- APIS ENDPOINTS ---

@app.post("/enrollments", response_model=schemas.EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_user(payload: schemas.EnrollmentCreate, db=Depends(get_db)):
    return await crud.create_enrollment(db=db, payload=payload)

@app.post("/enrollments/{enrollment_id}/complete-lesson", response_model=schemas.EnrollmentResponse)
async def complete_lesson(enrollment_id: int, db=Depends(get_db)):
    return await crud.increment_lesson_progress(db=db, enrollment_id=enrollment_id)

@app.get("/users/{user_id}/dashboard", response_model=schemas.DashboardResponse)
async def get_user_dashboard(user_id: int, db=Depends(get_db)):
    return await crud.fetch_user_dashboard_payload(db=db, user_id=user_id)

@app.get("/analytics/leaderboard", response_model=List[schemas.LeaderboardEntry])
async def get_leaderboard(db=Depends(get_db)):
    return await crud.aggregate_leaderboard(db=db)