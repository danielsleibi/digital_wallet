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
