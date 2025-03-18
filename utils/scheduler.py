"""
Enhanced Scheduler Module

Provides centralized scheduling capabilities for the application
with comprehensive error handling and monitoring.
"""

import logging
import datetime
import pytz
from flask_apscheduler import APScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.job import Job
from models import db, ScheduledJob
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = APScheduler()

def init_scheduler(app):
    """
    Initialize the scheduler with the Flask app
    
    Args:
        app: Flask application instance
    """
    # Configure scheduler
    scheduler.api_enabled = True
    scheduler.init_app(app)
    
    # Add event listeners
    scheduler.add_listener(job_executed_listener, EVENT_JOB_EXECUTED)
    scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)
    
    # Start scheduler
    scheduler.start()
    
    # Register existing jobs
    register_database_jobs()
    
    logger.info("Scheduler initialized successfully")
    return scheduler

def job_executed_listener(event):
    """
    Listener for successful job execution events
    
    Args:
        event: Job execution event
    """
    try:
        job_id = event.job_id
        update_job_status(job_id, 'success')
    except Exception as e:
        logger.error(f"Error in job executed listener: {e}")

def job_error_listener(event):
    """
    Listener for job error events
    
    Args:
        event: Job error event
    """
    try:
        job_id = event.job_id
        exception = event.exception
        traceback = event.traceback
        
        update_job_status(job_id, 'failed', str(exception))
        
        # Log the error
        logger.error(f"Job {job_id} failed: {exception}\n{traceback}")
    except Exception as e:
        logger.error(f"Error in job error listener: {e}")

def update_job_status(job_id, status, error=None):
    """
    Update job status in the database
    
    Args:
        job_id: ID of the job
        status: New job status (success, failed)
        error: Error message if job failed
    """
    try:
        job = ScheduledJob.query.filter_by(job_id=job_id).first()
        
        if not job:
            job = ScheduledJob(
                job_id=job_id,
                description=f"Job {job_id}",
                enabled=True
            )
            db.session.add(job)
        
        job.last_run = datetime.datetime.utcnow()
        job.last_status = status
        
        if status == 'success':
            job.success_count += 1
            job.last_error = None
        else:
            job.error_count += 1
            job.last_error = error
            
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Failed to update job status: {e}")
        return False

def register_database_jobs():
    """Register jobs from database with scheduler"""
    try:
        jobs = ScheduledJob.query.filter_by(enabled=True).all()
        
        for job in jobs:
            # Check if job already exists in scheduler
            if scheduler.get_job(job.job_id):
                logger.debug(f"Job {job.job_id} already registered")
                continue
            
            # Register job with scheduler (job-specific logic would go here)
            logger.info(f"Registered job {job.job_id} from database")
    except Exception as e:
        logger.error(f"Failed to register database jobs: {e}")

def add_job(func, trigger, job_id, **kwargs):
    """
    Add a job to the scheduler with database tracking
    
    Args:
        func: Function to execute
        trigger: APScheduler trigger (e.g., 'interval', 'cron')
        job_id: Unique job ID
        **kwargs: Additional arguments for scheduler
    """
    try:
        # Add job to scheduler
        job = scheduler.add_job(
            func=func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            **kwargs
        )
        
        # Add/update job in database
        db_job = ScheduledJob.query.filter_by(job_id=job_id).first()
        
        if not db_job:
            description = kwargs.get('name', f"Job {job_id}")
            db_job = ScheduledJob(
                job_id=job_id,
                description=description,
                enabled=True
            )
            db.session.add(db_job)
            
        db.session.commit()
        
        logger.info(f"Added scheduled job '{job_id}' with trigger {trigger}")
        return job
    except SQLAlchemyError as e:
        logger.error(f"Failed to create job database entry: {e}")
        # Still return the job from scheduler even if database update fails
        return scheduler.get_job(job_id)
    except Exception as e:
        logger.error(f"Failed to add job: {e}")
        return None

def remove_job(job_id):
    """
    Remove a job from the scheduler and database
    
    Args:
        job_id: ID of the job to remove
    """
    try:
        # Remove from scheduler
        scheduler.remove_job(job_id)
        
        # Update database
        job = ScheduledJob.query.filter_by(job_id=job_id).first()
        if job:
            job.enabled = False
            db.session.commit()
            
        logger.info(f"Removed scheduled job '{job_id}'")
        return True
    except Exception as e:
        logger.error(f"Failed to remove job: {e}")
        return False

def pause_job(job_id):
    """
    Pause a job in the scheduler
    
    Args:
        job_id: ID of the job to pause
    """
    try:
        scheduler.pause_job(job_id)
        
        # Update database
        job = ScheduledJob.query.filter_by(job_id=job_id).first()
        if job:
            job.enabled = False
            db.session.commit()
            
        logger.info(f"Paused scheduled job '{job_id}'")
        return True
    except Exception as e:
        logger.error(f"Failed to pause job: {e}")
        return False

def resume_job(job_id):
    """
    Resume a paused job in the scheduler
    
    Args:
        job_id: ID of the job to resume
    """
    try:
        scheduler.resume_job(job_id)
        
        # Update database
        job = ScheduledJob.query.filter_by(job_id=job_id).first()
        if job:
            job.enabled = True
            db.session.commit()
            
        logger.info(f"Resumed scheduled job '{job_id}'")
        return True
    except Exception as e:
        logger.error(f"Failed to resume job: {e}")
        return False

def get_eastern_time(dt=None):
    """
    Convert UTC datetime to US Eastern Time
    
    Args:
        dt: Datetime to convert (default: current UTC time)
        
    Returns:
        Datetime in US Eastern Time
    """
    if dt is None:
        dt = datetime.datetime.utcnow()
        
    eastern = pytz.timezone('US/Eastern')
    
    # If the datetime is not timezone-aware, assume it's UTC
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
        
    return dt.astimezone(eastern)

def get_scheduled_jobs():
    """
    Get all scheduled jobs
    
    Returns:
        List of scheduled jobs
    """
    return scheduler.get_jobs()