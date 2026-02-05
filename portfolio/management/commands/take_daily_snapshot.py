from decimal import Decimal
import logging

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from portfolio.models import Asset, NetWorthSnapshot
from portfolio.views import get_user_total_net_worth

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Take daily net worth snapshot for all users with holdings"

    def handle(self, *args, **kwargs):
        today = timezone.localdate()
        User = get_user_model()
        users = User.objects.filter(is_active=True)

        self.stdout.write(
            f"Taking daily snapshots for {users.count()} user(s) on {today}"
        )
        logger.info(
            "Daily snapshot job started for %s user(s) on %s", users.count(), today
        )

        for user in users:
            net_worth = None
            used_fallback = False
            try:
                net_worth = get_user_total_net_worth(user, "USD")
            except Exception:
                logger.exception(
                    "Error fetching prices for user_id=%s username=%s; using fallback value",
                    user.id,
                    user.username,
                )
                last_snapshot = (
                    NetWorthSnapshot.objects.filter(user=user)
                    .order_by("-date")
                    .first()
                )
                if last_snapshot is not None:
                    net_worth = last_snapshot.net_worth
                else:
                    net_worth = Decimal("0")
                used_fallback = True

            NetWorthSnapshot.objects.update_or_create(
                user=user,
                date=today,
                defaults={"net_worth": net_worth},
            )

            if used_fallback:
                self.stdout.write(
                    self.style.WARNING(
                        f"Saved snapshot for {user.username} with fallback value: ${net_worth:,.2f}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Saved snapshot for {user.username}: ${net_worth:,.2f}"
                    )
                )

        logger.info("Daily snapshot job completed for %s", today)
