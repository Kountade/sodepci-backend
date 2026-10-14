# apps/tresorerie/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# ============================================================
# SIGNAL : VENTE
# ============================================================
@receiver(post_save, sender='ventes_clients.Vente')
def creer_mouvement_vente(sender, instance, created, **kwargs):
    """
    Signal Vente.

    IMPORTANT : on ne cree PAS de mouvement d'encaissement ici.
    L'encaissement est gere par le signal Paiement.
    Confirmer une vente genere une facture, mais PAS un encaissement.
    """
    # Rien a faire : laisse le signal Paiement gerer les encaissements
    return


# ============================================================
# SIGNAL : PAIEMENT
# ============================================================
@receiver(post_save, sender='ventes_clients.Paiement')
def creer_mouvement_paiement(sender, instance, created, **kwargs):
    """
    Cree un mouvement de tresorerie (encaissement) lors d'un paiement client.
    """
    if not created:
        return

    try:
        from .models import MouvementTresorerie, Caisse, CompteBancaire

        # Anti-doublon
        existing = MouvementTresorerie.objects.filter(
            source_type='paiement_client',
            source_id=instance.id,
        ).first()

        if existing:
            logger.info(
                f"Mouvement deja existant pour paiement {instance.id}"
            )
            return

        facture = instance.facture
        if not facture:
            logger.warning(f"Paiement {instance.id} sans facture")
            return

        sale = facture.sale
        if not sale:
            logger.warning(f"Paiement {instance.id} sans vente")
            return

        if not sale.warehouse:
            logger.warning(f"Paiement {instance.id} sans entrepot")
            return

        # Recuperer la destination
        caisse = None
        compte = None

        if instance.caisse_destination_id:
            caisse = Caisse.objects.filter(
                id=instance.caisse_destination_id,
                warehouse=sale.warehouse,
            ).first()

        if instance.compte_destination_id:
            compte = CompteBancaire.objects.filter(
                id=instance.compte_destination_id,
                warehouse=sale.warehouse,
            ).first()

        # Fallback : caisse par defaut
        if not caisse and not compte:
            caisse = Caisse.objects.filter(
                warehouse=sale.warehouse,
                is_default=True,
                is_active=True,
            ).first()

        if not caisse and not compte:
            logger.warning(
                f"Aucune destination pour paiement {instance.id}"
            )
            return

        # Creer le mouvement
        with transaction.atomic():
            mouvement = MouvementTresorerie.objects.create(
                type_mouvement='encaissement',
                warehouse=sale.warehouse,
                source_type='paiement_client',
                source_id=instance.id,
                source_reference=instance.reference or f"PAY-{instance.id}",
                montant=instance.amount,
                mode_paiement=instance.method,
                caisse=caisse,
                compte_bancaire=compte,
                date_mouvement=instance.payment_date,
                date_valeur=instance.payment_date.date(),
                status='effectue',
                libelle=(
                    f"Paiement vente {sale.invoice_number} - "
                    f"{sale.client_name}"
                ),
                created_by=instance.received_by,
            )

            # Recalcul complet (idempotent, evite le double comptage)
            if caisse:
                caisse.mettre_a_jour_solde()
            if compte:
                compte.mettre_a_jour_solde()

        logger.info(
            f"Mouvement {mouvement.reference} cree pour "
            f"paiement {instance.id}"
        )

    except Exception as e:
        logger.error(
            f"Erreur creer_mouvement_paiement (paiement {instance.id}): {e}",
            exc_info=True,
        )