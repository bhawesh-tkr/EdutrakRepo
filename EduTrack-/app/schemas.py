import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field

class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    created_at: datetime.datetime
    class Config:
        from_attributes = True

class EnrollmentCreate(BaseModel):
    user_id: int = Field(..., description="ID of the target registering user.")
    course_id: int = Field(..., description="ID of the course to enroll into.")

class EnrollmentResponse(BaseModel):
    id: int
    user_id: int
    course_id: int
    completed_lessons_count: int
    status: str
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime]
    class Config:
        from_attributes = True

class AchievementResponse(BaseModel):
    id: int
    title: str
    unlocked_at: datetime.datetime
    class Config:
        from_attributes = True

class DashboardCourseProgress(BaseModel):
    course_id: int
    title: str
    completed_lessons_count: int
    total_lessons: int
    progress_percentage: float = Field(..., description="Calculated progress value: (completed/total) * 100")

class DashboardResponse(BaseModel):
    user: UserResponse
    active_courses: List[DashboardCourseProgress]
    achievements: List[AchievementResponse]

class LeaderboardEntry(BaseModel):
    user_id: int
    name: str
    total_completed_lessons: int