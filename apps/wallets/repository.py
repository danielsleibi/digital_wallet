# apps/wallets/repository.py

from apps.wallets.models import Wallet


class WalletRepository:
    @staticmethod
    def get_wallets_for_update(wallet_ids, user_id):
        """
        Fetch and lock active wallets belonging to a user OR system wallets.

        Args:
            wallet_ids: Set of wallet UUIDs to fetch
            user_id: UUID or string ID of the user

        Returns:
            Queryset with SELECT ... FOR UPDATE applied.
        """
        from django.db.models import Q
        return (
            Wallet.objects
            .select_for_update()
            .filter(
                Q(user_id=user_id) | Q(user__username='SYSTEM'),
                id__in=wallet_ids,
                status=Wallet.Status.ACTIVE
            )
        )

    @staticmethod
    def wallet_exists(user_id, name: str, currency: str) -> bool:
        """
        Return True if any wallet (regardless of status) with the given
        name and currency already belongs to this user.

        We check across all statuses so that an archived wallet name
        cannot be silently reused with the same currency.
        """
        return Wallet.objects.filter(user_id=user_id, name=name, currency=currency).exists()

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
    def get_user_wallet(wallet_id, user_id):
        """
        Fetch an active wallet that belongs to the given user.

        Args:
            wallet_id: UUID of the wallet
            user_id: UUID or string ID of the user

        Returns:
            The wallet if found and active.

        Raises:
            Wallet.DoesNotExist: If wallet doesn't exist, isn't active,
                or doesn't belong to the user.
        """
        return Wallet.objects.get(
            id=wallet_id,
            user_id=user_id,
            status=Wallet.Status.ACTIVE
        )

    @staticmethod
    def get_user_wallets(user_id):
        """
        Return all active wallets belonging to the given user,
        ordered by creation date.
        """
        return Wallet.objects.filter(
            user_id=user_id,
            status=Wallet.Status.ACTIVE
        ).order_by("created_at")

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
