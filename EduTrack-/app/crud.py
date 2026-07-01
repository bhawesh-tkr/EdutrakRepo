import datetime
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app import models, schemas

async def create_enrollment(db: AsyncSession, payload: schemas.EnrollmentCreate) -> models.Enrollment:
    # 1. Verify existence of relational entities
    user = await db.get(models.User, payload.user_id)
    course = await db.get(models.Course, payload.course_id)
    if not user or not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User or Course record not found.")

    # 2. Enforce constraint: Block duplicated active enrollments
    stmt = select(models.Enrollment).where(
        and_(
            models.Enrollment.user_id == payload.user_id,
            models.Enrollment.course_id == payload.course_id,
            models.Enrollment.status == "active"
        )
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User is already actively enrolled in this course."
        )

    new_enrollment = models.Enrollment(user_id=payload.user_id, course_id=payload.course_id)
    db.add(new_enrollment)
    await db.commit()
    await db.refresh(new_enrollment)
    return new_enrollment


async def increment_lesson_progress(db: AsyncSession, enrollment_id: int) -> models.Enrollment:
    # 1. Fetch targeted tracking element
    enrollment = await db.get(models.Enrollment, enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment record not found.")

    # 2. Safeguard status rules
    if enrollment.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Cannot progress: Course has already been completed."
        )

    course = await db.get(models.Course, enrollment.course_id)
    
    # 3. Apply incrementation
    enrollment.completed_lessons_count += 1

    # 4. Handle course completion and milestone logic
    if enrollment.completed_lessons_count >= course.total_lessons:
        enrollment.completed_lessons_count = course.total_lessons  # Floor capping
        enrollment.status = "completed"
        enrollment.completed_at = datetime.datetime.utcnow()

        # Execute business logic rules for achievements
        # Audit overall user success volume
        count_stmt = select(func.count(models.Enrollment.id)).where(
            and_(models.Enrollment.user_id == enrollment.user_id, models.Enrollment.status == "completed")
        )
        completed_courses_count = (await db.execute(count_stmt)).scalar() or 0
        
        # Check current existing achievement collection to prevent duplicates
        ach_stmt = select(models.Achievement.title).where(models.Achievement.user_id == enrollment.user_id)
        current_achievements = (await db.execute(ach_stmt)).scalars().all()

        # Rule 1: "Fast Starter" -> Earned on the very first course completion
        if completed_courses_count == 1 and "Fast Starter" not in current_achievements:
            db.add(models.Achievement(user_id=enrollment.user_id, title="Fast Starter"))

        # Rule 2: "Deep Diver" -> Earned when completing a course with 10 or more lessons
        if course.total_lessons >= 10 and "Deep Diver" not in current_achievements:
            db.add(models.Achievement(user_id=enrollment.user_id, title="Deep Diver"))

    await db.commit()
    await db.refresh(enrollment)
    return enrollment


async def fetch_user_dashboard_payload(db: AsyncSession, user_id: int) -> schemas.DashboardResponse:
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User target profile not found.")

    # Get active enrollments with course details
    stmt = select(models.Enrollment, models.Course).join(models.Course).where(
        and_(models.Enrollment.user_id == user_id, models.Enrollment.status == "active")
    )
    results = (await db.execute(stmt)).all()
    
    active_progress = []
    for enroll, crs in results:
        progress_pct = 0.0
        if crs.total_lessons > 0:
            progress_pct = round((enroll.completed_lessons_count / crs.total_lessons) * 100.0, 2)
            
        active_progress.append(
            schemas.DashboardCourseProgress(
                course_id=crs.id,
                title=crs.title,
                completed_lessons_count=enroll.completed_lessons_count,
                total_lessons=crs.total_lessons,
                progress_percentage=progress_pct
            )
        )

    # Get achievements
    ach_stmt = select(models.Achievement).where(models.Achievement.user_id == user_id).order_by(models.Achievement.unlocked_at.desc())
    achievements = (await db.execute(ach_stmt)).scalars().all()

    return schemas.DashboardResponse(
        user=schemas.UserResponse.from_orm(user),
        active_courses=active_progress,
        achievements=[schemas.AchievementResponse.from_orm(a) for a in achievements]
    )


async def aggregate_leaderboard(db: AsyncSession) -> List[schemas.LeaderboardEntry]:
    # Optimized SQL aggregation query
    stmt = (
        select(
            models.User.id.label("user_id"),
            models.User.name.label("name"),
            func.sum(models.Enrollment.completed_lessons_count).label("total_completed_lessons")
        )
        .join(models.Enrollment, models.User.id == models.Enrollment.user_id)
        .group_by(models.User.id, models.User.name)
        .order_by(func.sum(models.Enrollment.completed_lessons_count).desc())
        .limit(5)
    )
    
    result = await db.execute(stmt)
    return [
        schemas.LeaderboardEntry(
            user_id=row.user_id,
            name=row.name,
            total_completed_lessons=row.total_completed_lessons or 0
        ) for row in result.all()
    ]