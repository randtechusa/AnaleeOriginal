"""
Centralized scheduler for application tasks with enhanced error handling
"""
import logging
import traceback
from datetime import datetime
from pytz import timezone
from flask_apscheduler import APScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = APScheduler()

def init_scheduler(app):
    """Initialize scheduler with app configuration"""
    
    # Basic scheduler configuration
    app.config['SCHEDULER_API_ENABLED'] = True
    app.config['SCHEDULER_EXECUTORS'] = {
        'default': {'type': 'threadpool', 'max_workers': 5}
    }
    
    # Timezone configuration
    app.config['SCHEDULER_TIMEZONE'] = 'US/Eastern'
    
    # Initialize and start scheduler
    scheduler.init_app(app)
    
    # Set up error handling for scheduler jobs
    def job_listener(event):
        """Log scheduler job events"""
        if event.exception:
            logger.error(f"Job {event.job_id} failed with exception: {event.exception}")
            logger.error(f"Traceback: {event.traceback}")
            # Also log to database
            from models import ErrorLog
            from extensions import db
            
            try:
                error_log = ErrorLog(
                    error_type="SchedulerJobError",
                    error_message=str(event.exception),
                    stack_trace=event.traceback,
                    endpoint=f"scheduler.{event.job_id}"
                )
                with app.app_context():
                    db.session.add(error_log)
                    db.session.commit()
            except Exception as e:
                logger.error(f"Failed to log scheduler error to database: {e}")
        else:
            logger.info(f"Job {event.job_id} executed successfully")
    
    # Add listener for job execution and error events
    scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)
    
    # Start the scheduler
    scheduler.start()
    logger.info("Application scheduler initialized")
    return scheduler

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
        # Remove any existing job with this ID to avoid duplicates
        scheduler.remove_job(id, ignore_exceptions=True)
        
        # Add new job
        scheduler.add_job(
            id=id,
            func=func,
            trigger=trigger,
            **trigger_args
        )
        
        logger.info(f"Added scheduled job: {id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add scheduled job {id}: {e}")
        return False

def remove_scheduled_job(id):
    """Remove a job from the scheduler"""
    try:
        scheduler.remove_job(id)
        logger.info(f"Removed scheduled job: {id}")
        return True
    except Exception as e:
        logger.error(f"Failed to remove scheduled job {id}: {e}")
        return False

def get_job_list():
    """Get list of all scheduled jobs"""
    try:
        jobs = scheduler.get_jobs()
        return [{
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time,
            'trigger': str(job.trigger)
        } for job in jobs]
    except Exception as e:
        logger.error(f"Failed to get job list: {e}")
        return []

def get_eastern_time():
    """Get current time in US/Eastern timezone"""
    eastern = timezone('US/Eastern')
    return datetime.now(eastern)