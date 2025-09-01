from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction

from chatbot.models import UserSetting


class Command(BaseCommand):
    help = "Reset daily_message_count for all users (should be run daily at midnight)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        with transaction.atomic():
            qs = UserSetting.objects.all()
            updated = qs.update(daily_message_count=0, last_message_date=today)

        self.stdout.write(self.style.SUCCESS(
            f"Reset daily_message_count for {updated} user settings to 0 (date set to {today})."
        ))
