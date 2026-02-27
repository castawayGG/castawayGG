from celery import shared_task
from services.telegram.actions import send_bulk_messages, join_group, change_account_password, enable_2fa
from core.database import SessionLocal
from models.account import Account
from models.campaign import Campaign
from core.logger import log
from sqlalchemy.sql import func
import asyncio
import json

@shared_task(bind=True, max_retries=3)
def send_bulk_messages_task(self, account_id: str, contacts: list, base_text: str, variations: list):
    try:
        return asyncio.run(send_bulk_messages(account_id, contacts, base_text, variations))
    except Exception as e:
        log.error(f"send_bulk_messages_task failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def join_group_task(self, account_id: str, invite_link: str):
    try:
        success = asyncio.run(join_group(account_id, invite_link))
        return {'success': success}
    except Exception as e:
        log.error(f"join_group_task failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def change_password_task(self, account_id: str, new_password: str):
    try:
        success = asyncio.run(change_account_password(account_id, new_password))
        return {'success': success}
    except Exception as e:
        log.error(f"change_password_task failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task(bind=True, max_retries=3)
def enable_2fa_task(self, account_id: str, password: str, hint: str):
    try:
        success = asyncio.run(enable_2fa(account_id, password, hint))
        return {'success': success}
    except Exception as e:
        log.error(f"enable_2fa_task failed: {e}")
        self.retry(exc=e, countdown=60)

@shared_task
def run_campaign(campaign_id: int):
    db = SessionLocal()
    campaign = None
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign or campaign.status != 'running':
            return

        targets = json.loads(campaign.target_list)
        variations = json.loads(campaign.variations) if campaign.variations else []
        message = campaign.message_template

        accounts = db.query(Account).filter(Account.status == 'active').all()

        for account in accounts:
            result = asyncio.run(send_bulk_messages(account.id, targets, message, variations))
            campaign.processed += len(targets)
            campaign.successful += result['sent']
            campaign.failed += result['failed']
            db.commit()

        # Корректное завершение кампании
        campaign.status = 'completed'
        campaign.completed_at = func.now()
        db.commit()
        
    except Exception as e:
        log.error(f"run_campaign error for ID {campaign_id}: {e}")
        db.rollback()
        if campaign:
            campaign.status = 'paused'
            db.commit()
    finally:
        db.close()