# apps/wallets/repository.py

from apps.wallets.models import Wallet


class WalletRepository:
    @staticmethod
    def get_wallets_for_update(wallet_ids, user):
        """
        Fetch and lock active wallets belonging to a user OR system wallets.

        Returns a queryset with SELECT ... FOR UPDATE applied.
        """
        from django.db.models import Q
        return (
            Wallet.objects
            .select_for_update()
            .filter(
                Q(user=user) | Q(user__username='SYSTEM'),
                id__in=wallet_ids,
                status=Wallet.Status.ACTIVE
            )
        )

    @staticmethod
    def wallet_exists(user, name: str, currency: str) -> bool:
        """
        Return True if any wallet (regardless of status) with the given
        name and currency already belongs to this user.

        We check across all statuses so that an archived wallet name
        cannot be silently reused with the same currency.
        """
        return Wallet.objects.filter(user=user, name=name, currency=currency).exists()

    @staticmethod
    def create_wallet(user, name: str, currency: str) -> Wallet:
        """
        Persist and return a new active wallet for the given user.
        """
        return Wallet.objects.create(
            user=user,
            name=name,
            currency=currency,
            status=Wallet.Status.ACTIVE,
        )

    @staticmethod
    def get_user_wallet(wallet_id, user):
        """
        Fetch an active wallet that belongs to the given user.

        Returns the wallet if found and active.
        Raises Wallet.DoesNotExist if the wallet doesn't exist, isn't active,
        or doesn't belong to the user.
        """
        return Wallet.objects.get(
            id=wallet_id,
            user=user,
            status=Wallet.Status.ACTIVE
        )

    @staticmethod
    def get_system_wallet(currency: str, name: str):
        """
        Return an active system wallet with the given name and currency, or None.
        """
        return Wallet.objects.filter(
            user__username='SYSTEM',
            name=name,
            currency=currency,
            status=Wallet.Status.ACTIVE
        ).first()
