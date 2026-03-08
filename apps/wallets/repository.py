# apps/wallets/repository.py

from apps.wallets.models import Wallet


class WalletRepository:
    @staticmethod
    def get_wallets_for_update(wallet_ids, user):
        """
        Fetch and lock active wallets belonging to a user.

        Returns a queryset with SELECT ... FOR UPDATE applied.
        """
        return (
            Wallet.objects
            .select_for_update()
            .filter(id__in=wallet_ids, user=user, status=Wallet.Status.ACTIVE)
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
