# tresorerie/signals.py

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import models
from django.utils import timezone
from decimal import Decimal

from ventes_clients.models import Vente, Facture, Paiement
from .models import MouvementTresorerie, Caisse, Frais, TresorerieJournaliere

logger = logging.getLogger(__name__)

print("🔔 SIGNALS FILE LOADED - tresorerie/signals.py")


@receiver(post_save, sender=Vente)
def creer_mouvement_vente(sender, instance, created, **kwargs):
    print(
        f"🔔 Signal Vente post_save : {instance.invoice_number}, status={instance.status}, warehouse={instance.warehouse}")
    if instance.status == 'confirmed' and instance.warehouse:
        if not instance.mouvements_tresorerie.exists():
            caisse = Caisse.objects.filter(
                warehouse=instance.warehouse,
                is_default=True
            ).first()
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
                print(f"✅ Mouvement VENTE créé pour {instance.invoice_number}")
            else:
                print(f"⚠️ Pas de caisse par défaut pour {instance.warehouse}")
        else:
            print(f"ℹ️ Mouvement déjà existant pour {instance.invoice_number}")
    else:
        print(f"ℹ️ Condition non remplie pour vente {instance.invoice_number}")


@receiver(post_save, sender=Paiement)
def creer_mouvement_paiement(sender, instance, created, **kwargs):
    print(
        f"🔔 Signal Paiement post_save : paiement {instance.id}, created={created}, facture={instance.facture}")
    if created and instance.facture and instance.facture.sale:
        sale = instance.facture.sale
        warehouse = sale.warehouse if sale else None
        print(f"   Sale: {sale}, warehouse={warehouse}")
        if warehouse:
            # Utiliser les destinations choisies
            caisse = instance.caisse_destination
            compte = instance.compte_destination

            # Fallback : caisse par défaut
            if not caisse and not compte:
                caisse = Caisse.objects.filter(
                    warehouse=warehouse, is_default=True
                ).first()
                if not caisse:
                    print(
                        f"⚠️ Pas de destination et pas de caisse par défaut pour entrepôt {warehouse}")
                    return

            print(f"   Caisse choisie : {caisse}, Compte choisi : {compte}")

            # Vérifier doublon
            if instance.mouvements_tresorerie.exists():
                print(
                    f"ℹ️ Mouvement déjà existant pour paiement {instance.id}")
                return

            mouvement = MouvementTresorerie.objects.create(
                type_mouvement='encaissement',
                warehouse=warehouse,
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
                libelle=f"Paiement facture {instance.facture.invoice_number} - {instance.facture.client.name}",
                facture_vente=instance.facture,
                paiement=instance,
                created_by=instance.received_by
            )
            print(
                f"✅ Mouvement PAIEMENT créé pour paiement {instance.id} (réf. {mouvement.reference})")
        else:
            print(f"⚠️ Aucun entrepôt dans la vente associée")
    else:
        print(f"ℹ️ Condition non remplie pour paiement {instance.id}")


@receiver(pre_save, sender=Frais)
def creer_mouvement_frais(sender, instance, **kwargs):
    if instance.status != 'paye':
        return
    if instance.mouvement:
        logger.info(
            f"Le frais {instance.reference} a déjà un mouvement associé.")
        return
    if not instance.warehouse:
        logger.warning(
            f"Frais {instance.reference} sans entrepôt, impossible de créer un mouvement.")
        return

    caisse = Caisse.objects.filter(
        warehouse=instance.warehouse,
        is_default=True
    ).first()

    if not caisse:
        logger.error(
            f"Aucune caisse par défaut pour l'entrepôt {instance.warehouse}. Mouvement non créé.")
        return

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
    mouvement._mettre_a_jour_soldes()
    mouvement.save()
    instance.mouvement = mouvement
    logger.info(
        f"Mouvement {mouvement.reference} créé pour le frais {instance.reference}.")


@receiver(post_save, sender=MouvementTresorerie)
def mettre_a_jour_tresorerie_journaliere(sender, instance, **kwargs):
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

        if jour.solde_ouverture == 0:
            jour.solde_ouverture = Caisse.objects.filter(
                warehouse=instance.warehouse
            ).aggregate(total=models.Sum('solde_actuel'))['total'] or 0

        jour.solde_fermeture = jour.solde_ouverture + \
            jour.total_entrees - jour.total_sorties
        jour.save()
