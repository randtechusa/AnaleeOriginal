"""
Centralized scheduler for application tasks with enhanced error handling
Handles scheduled tasks such as daily automated audits
"""

import logging
import pytz
from datetime import datetime, timedelta

from flask_apscheduler import APScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED

from models import db, ScheduledJob

logger = logging.getLogger(__name__)
scheduler = APScheduler()

def init_scheduler(app):
    """Initialize scheduler with app configuration"""
    try:
        # Configure scheduler
        app.config['SCHEDULER_API_ENABLED'] = True
        app.config['SCHEDULER_TIMEZONE'] = 'UTC'
        
        # Initialize scheduler
        scheduler.init_app(app)
        app.scheduler = scheduler
        
        # Add event listeners
        scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED)
        
        # Start scheduler
        scheduler.start()
        
        # Set up scheduled jobs
        try:
            from admin.scheduled_audit import setup_scheduled_audits
            setup_scheduled_audits(app)
        except ImportError as e:
            logger.warning(f"Could not set up scheduled audits: {str(e)}")
        except Exception as e:
            logger.error(f"Error setting up scheduled audits: {str(e)}")
        
        logger.info("Scheduler initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing scheduler: {str(e)}")
        
def job_listener(event):
    """Log scheduler job events"""
    if event.exception:
        logger.error(f"Job '{event.job_id}' raised an exception: {str(event.exception)}")
        # Store in database for monitoring
        try:
            job = ScheduledJob.query.filter_by(job_id=event.job_id).first()
            if job:
                job.last_status = 'failed'
                job.last_error = str(event.exception)
                job.last_run = datetime.utcnow()
                job.error_count = (job.error_count or 0) + 1
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update job status in database: {str(e)}")
    else:
        logger.info(f"Job '{event.job_id}' executed successfully")
        # Store in database for monitoring
        try:
            job = ScheduledJob.query.filter_by(job_id=event.job_id).first()
            if job:
                job.last_status = 'success'
                job.last_error = None
                job.last_run = datetime.utcnow()
                job.success_count = (job.success_count or 0) + 1
                db.session.commit()
            elif event.job_id:
                # Create new job record if it doesn't exist
                new_job = ScheduledJob(
                    job_id=event.job_id,
                    last_status='success',
                    last_run=datetime.utcnow(),
                    success_count=1
                )
                db.session.add(new_job)
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update job status in database: {str(e)}")

def add_scheduled_job(id, func, trigger, **trigger_args):
    """
    Add a job to the scheduler with error handling
    
    Args:
        id: Unique job identifier
        func: Function to execute
        trigger: Trigger type (cron, interval, date)
        **trigger_args: Arguments for the trigger
    """
    try:
        if not scheduler:
            logger.error("Scheduler not initialized")
            return False
        
        # Check if job already exists
        job = scheduler.get_job(id)
        if job:
            logger.info(f"Job '{id}' already exists - removing old job")
            scheduler.remove_job(id)
        
        # Add job to scheduler
        scheduler.add_job(
            id=id,
            func=func,
            trigger=trigger,
            **trigger_args,
            replace_existing=True
        )
        
        # Create database entry
        try:
            job = ScheduledJob.query.filter_by(job_id=id).first()
            if not job:
                job = ScheduledJob(
                    job_id=id,
                    description=f"Scheduled job {id}",
                    enabled=True,
                    created_at=datetime.utcnow()
                )
                db.session.add(job)
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to create job database entry: {str(e)}")
        
        logger.info(f"Added scheduled job '{id}' with trigger {trigger}")
        return True
    except Exception as e:
        logger.error(f"Error adding scheduled job '{id}': {str(e)}")
        return False

def remove_scheduled_job(id):
    """Remove a job from the scheduler"""
    try:
        if not scheduler:
            logger.error("Scheduler not initialized")
            return False
        
        scheduler.remove_job(id)
        logger.info(f"Removed scheduled job '{id}'")
        
        # Update database entry
        try:
            job = ScheduledJob.query.filter_by(job_id=id).first()
            if job:
                job.enabled = False
                db.session.commit()
        except Exception as e:
            logger.error(f"Failed to update job database entry: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"Error removing scheduled job '{id}': {str(e)}")
        return False

def get_scheduled_jobs():
    """Get all scheduled jobs"""
    try:
        if not scheduler:
            logger.error("Scheduler not initialized")
            return []
        
        return scheduler.get_jobs()
    except Exception as e:
        logger.error(f"Error getting scheduled jobs: {str(e)}")
        return []

def get_eastern_time(utc_time=None):
    """Convert UTC time to Eastern Time"""
    eastern = pytz.timezone('US/Eastern')
    
    if utc_time is None:
        utc_time = datetime.utcnow()
        
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
        
    return utc_time.astimezone(eastern)