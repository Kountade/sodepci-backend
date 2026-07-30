# apps/tresorerie/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.db import models          # <--- AJOUT OBLIGATOIRE
from django.utils import timezone     # <--- AJOUT OBLIGATOIRE
from decimal import Decimal

from ventes_clients.models import Vente, Facture, Paiement
from achats_fournisseurs.models import PurchaseOrder, SupplierInvoice
from produits_stocks.models import Warehouse

from .models import MouvementTresorerie, Caisse, CompteBancaire, Frais, TresorerieJournaliere


@receiver(post_save, sender=Vente)
def creer_mouvement_vente(sender, instance, created, **kwargs):
    """
    Crée un mouvement de trésorerie lors de la confirmation d'une vente
    """
    if instance.status == 'confirmed' and instance.warehouse:
        if not instance.mouvements_tresorerie.exists():
            caisse = Caisse.objects.filter(
                warehouse=instance.warehouse, is_default=True).first()
            if caisse:
                MouvementTresorerie.objects.create(
                    type_mouvement='encaissement',
                    warehouse=instance.warehouse,
                    source_type='vente',
                    source_id=instance.id,
                    source_reference=instance.invoice_number,
                    montant=instance.total,
                    mode_paiement='especes',
                    caisse=caisse,
                    date_mouvement=instance.sale_date,
                    date_valeur=instance.sale_date.date(),
                    status='effectue',
                    libelle=f"Vente {instance.invoice_number} - {instance.client_name}",
                    vente=instance,
                    created_by=instance.created_by
                )


@receiver(post_save, sender=Paiement)
def creer_mouvement_paiement(sender, instance, created, **kwargs):
    """
    Crée un mouvement de trésorerie lors d'un paiement
    """
    if created and instance.facture and instance.facture.sale:
        sale = instance.facture.sale
        warehouse = sale.warehouse if sale else None
        if warehouse:
            caisse = Caisse.objects.filter(
                warehouse=warehouse, is_default=True).first()
            if caisse:
                MouvementTresorerie.objects.create(
                    type_mouvement='encaissement',
                    warehouse=warehouse,
                    source_type='paiement_client',
                    source_id=instance.id,
                    source_reference=instance.reference or f"PAY-{instance.id}",
                    montant=instance.amount,
                    mode_paiement=instance.method,
                    caisse=caisse,
                    date_mouvement=instance.payment_date,
                    date_valeur=instance.payment_date.date(),
                    status='effectue',
                    libelle=f"Paiement facture {instance.facture.invoice_number} - {instance.facture.client.name}",
                    facture_vente=instance.facture,
                    paiement=instance,
                    created_by=instance.received_by
                )


@receiver(pre_save, sender=Frais)
def creer_mouvement_frais(sender, instance, **kwargs):
    """
    Crée un mouvement de trésorerie pour les frais payés
    """
    if instance.status == 'paye' and not instance.mouvement and instance.warehouse:
        caisse = Caisse.objects.filter(
            warehouse=instance.warehouse, is_default=True).first()
        if caisse:
            mouvement = MouvementTresorerie.objects.create(
                type_mouvement='decaissement',
                warehouse=instance.warehouse,
                source_type='frais',
                source_id=instance.id,
                source_reference=instance.reference,
                montant=instance.montant,
                mode_paiement=instance.mode_paiement,
                caisse=caisse,
                date_mouvement=timezone.now(),
                date_valeur=instance.date_paiement or timezone.now().date(),
                status='effectue',
                libelle=f"Frais: {instance.titre}",
                created_by=instance.created_by
            )
            instance.mouvement = mouvement


@receiver(post_save, sender=MouvementTresorerie)
def mettre_a_jour_tresorerie_journaliere(sender, instance, **kwargs):
    """
    Met à jour la trésorerie journalière après un mouvement
    """
    if instance.status == 'effectue':
        try:
            jour = TresorerieJournaliere.objects.get(
                date=instance.date_mouvement.date(),
                warehouse=instance.warehouse
            )
        except TresorerieJournaliere.DoesNotExist:
            jour = TresorerieJournaliere.objects.create(
                date=instance.date_mouvement.date(),
                warehouse=instance.warehouse
            )

        # Mettre à jour les totaux (maintenant models est importé)
        jour.total_entrees = MouvementTresorerie.objects.filter(
            warehouse=instance.warehouse,
            date_mouvement__date=instance.date_mouvement.date(),
            status='effectue',
            type_mouvement='encaissement'
        ).aggregate(total=models.Sum('montant'))['total'] or 0

        jour.total_sorties = MouvementTresorerie.objects.filter(
            warehouse=instance.warehouse,
            date_mouvement__date=instance.date_mouvement.date(),
            status='effectue',
            type_mouvement='decaissement'
        ).aggregate(total=models.Sum('montant'))['total'] or 0

        # Mettre à jour les soldes
        if jour.solde_ouverture == 0:
            jour.solde_ouverture = Caisse.objects.filter(
                warehouse=instance.warehouse
            ).aggregate(total=models.Sum('solde_actuel'))['total'] or 0

        jour.solde_fermeture = jour.solde_ouverture + \
            jour.total_entrees - jour.total_sorties
        jour.save()
