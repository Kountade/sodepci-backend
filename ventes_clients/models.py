# apps/ventes_clients/models.py

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import json

import qrcode

from django.core.exceptions import ValidationError
from django.core.files import File
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from users.models import CustomUser
from produits_stocks.models import (
    Product,
    Lot,
    Warehouse,
    Stock,
    StockMovement,
)


# ============================================================
# UTILITAIRES
# ============================================================

def generate_number(model, field_name, prefix):
    """
    Génère un numéro séquentiel :
    DEV-2026-0001
    INV-2026-0001
    FAC-2026-0001
    AV-2026-0001
    """

    year = date.today().year

    last_object = (
        model.objects
        .filter(**{
            f"{field_name}__startswith": f"{prefix}-{year}-"
        })
        .order_by("-id")
        .first()
    )

    if last_object:
        last_number = getattr(last_object, field_name)

        try:
            number = int(last_number.split("-")[-1]) + 1
        except (ValueError, IndexError):
            number = 1
    else:
        number = 1

    return f"{prefix}-{year}-{number:04d}"


def generate_qr_image(data):
    """
    Génère une image QR Code.
    """

    qr_data = json.dumps(
        data,
        ensure_ascii=False,
        default=str
    )

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(qr_data)
    qr.make(fit=True)

    image = qr.make_image(
        fill_color="black",
        back_color="white"
    )

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return qr_data, buffer


# ============================================================
# CLIENT
# ============================================================

class Client(models.Model):

    TYPE_CHOICES = (
        ("particulier", "Particulier"),
        ("entreprise", "Entreprise"),
        ("revendeur", "Revendeur"),
        ("grossiste", "Grossiste"),
    )

    STATUT_CHOICES = (
        ("actif", "Actif"),
        ("inactif", "Inactif"),
        ("bloque", "Bloqué"),
    )

    code = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Code client"
    )

    name = models.CharField(
        max_length=200,
        verbose_name="Nom / Raison sociale"
    )

    commercial_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom commercial"
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="particulier",
        verbose_name="Type"
    )

    contact_person = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Personne de contact"
    )

    phone = models.CharField(
        max_length=20,
        verbose_name="Téléphone"
    )

    mobile = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Mobile"
    )

    email = models.EmailField(
        blank=True,
        verbose_name="Email"
    )

    website = models.URLField(
        blank=True,
        verbose_name="Site web"
    )

    address = models.TextField(
        blank=True,
        verbose_name="Adresse"
    )

    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ville"
    )

    country = models.CharField(
        max_length=100,
        default="Sénégal",
        verbose_name="Pays"
    )

    postal_code = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Code postal"
    )

    tax_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° Identification fiscale"
    )

    registration_number = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="N° Registre de commerce"
    )

    payment_terms = models.CharField(
        max_length=20,
        choices=[
            ("cash", "Comptant"),
            ("15", "15 jours"),
            ("30", "30 jours"),
            ("45", "45 jours"),
            ("60", "60 jours"),
        ],
        default="cash",
        verbose_name="Délai de paiement"
    )

    credit_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Limite de crédit"
    )

    current_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Solde actuel"
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Note"
    )

    total_purchases = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Total achats"
    )

    total_orders = models.PositiveIntegerField(
        default=0,
        verbose_name="Nombre de commandes"
    )

    statut = models.CharField(
        max_length=20,
        choices=STATUT_CHOICES,
        default="actif",
        verbose_name="Statut"
    )

    is_favorite = models.BooleanField(
        default=False,
        verbose_name="Client favori"
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notes"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_created",
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["name"]

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def full_address(self):
        parts = [
            self.address,
            self.city,
            self.country
        ]

        return ", ".join(
            part for part in parts if part
        )


# ============================================================
# DEVIS
# ============================================================
# apps/ventes_clients/models.py - DEVIS SEULEMENT

from django.db import models
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import qrcode
from io import BytesIO
from django.core.files import File

from users.models import CustomUser
from produits_stocks.models import Product, Lot, Warehouse, Stock, StockMovement


# ==================== DEVIS ====================
class Devis(models.Model):
    """
    Devis / Proforma
    """
    STATUS_CHOICES = (
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('accepted', 'Accepté'),
        ('refused', 'Refusé'),
        ('expired', 'Expiré'),
        ('converted', 'Converti en vente'),
    )

    devis_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° Devis"
    )
    client = models.ForeignKey(
        'Client', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='devis'
    )
    client_name = models.CharField(
        max_length=200, verbose_name="Nom client"
    )
    client_phone = models.CharField(
        max_length=20, blank=True, verbose_name="Téléphone client"
    )
    client_email = models.EmailField(
        blank=True, verbose_name="Email client"
    )
    client_address = models.TextField(
        blank=True, verbose_name="Adresse client"
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='devis',
        verbose_name="Entrepôt"
    )

    devis_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date devis"
    )
    valid_until = models.DateField(
        verbose_name="Valable jusqu'au"
    )

    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Sous-total"
    )
    discount_type = models.CharField(
        max_length=20, 
        choices=[
            ('percentage', 'Pourcentage'),
            ('amount', 'Montant')
        ], 
        default='percentage', 
        verbose_name="Type remise"
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Valeur remise"
    )
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant remise"
    )
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Taux TVA (%)"
    )
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant TVA"
    )
    shipping_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Frais de livraison"
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Total TTC"
    )

    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='draft', 
        verbose_name="Statut"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    internal_notes = models.TextField(blank=True, verbose_name="Notes internes")

    sale = models.ForeignKey(
        'Vente', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='devis_source'
    )

    qr_code = models.ImageField(
        upload_to='qrcodes/devis/', 
        null=True, 
        blank=True, 
        verbose_name="QR Code"
    )
    qr_code_data = models.TextField(
        blank=True, verbose_name="Données QR Code"
    )

    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date création"
    )
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Date modification"
    )
    created_by = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        related_name='devis', 
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        ordering = ['-devis_date']

    def __str__(self):
        return f"{self.devis_number} - {self.client_name}"

    def calculate_totals(self):
        """
        Calcule les totaux du devis
        """
        self.subtotal = sum(line.total for line in self.lignes.all())

        if self.discount_type == 'percentage':
            self.discount_amount = self.subtotal * (self.discount_value / 100)
        else:
            self.discount_amount = self.discount_value

        after_discount = self.subtotal - self.discount_amount
        self.tax_amount = after_discount * (self.tax_rate / 100)
        self.total = after_discount + self.tax_amount + self.shipping_fee
        
        # Sauvegarder sans déclencher de boucle
        super().save(update_fields=[
            'subtotal', 'discount_amount', 'tax_amount', 'total'
        ])

    def generate_qr_code(self):
        """
        Génère un QR Code pour le devis
        """
        if not self.devis_number:
            return

        import json
        qr_data = {
            'type': 'devis',
            'id': self.id,
            'number': self.devis_number,
            'client': self.client_name,
            'total': str(self.total),
            'date': self.devis_date.strftime('%Y-%m-%d %H:%M:%S'),
            'valid_until': self.valid_until.strftime('%Y-%m-%d'),
            'status': self.status,
            'url': f'/devis/{self.id}/'
        }

        qr_data_str = json.dumps(qr_data, ensure_ascii=False)
        self.qr_code_data = qr_data_str

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data_str)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format='PNG')

        filename = f"qr_devis_{self.devis_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        """
        Sauvegarde avec génération automatique du QR Code
        """
        # Sauvegarder d'abord si c'est une nouvelle instance
        if not self.pk:
            super().save(*args, **kwargs)
        
        # Générer le QR Code si nécessaire
        if not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])
        else:
            super().save(*args, **kwargs)

    # ✅ METHODE CONVERT_TO_SALE CORRIGÉE
    def convert_to_sale(self, user=None):
        """
        Convertit le devis en vente
        """
        from .models import Vente, LigneVente

        # Vérifications préalables
        if not self.warehouse:
            raise ValueError(
                "L'entrepôt doit être défini pour convertir le devis en vente"
            )

        if self.status != 'accepted':
            raise ValueError(
                "Seul un devis accepté peut être converti en vente"
            )

        if self.sale:
            raise ValueError(
                "Ce devis a déjà été converti en vente"
            )

        # Générer le numéro de facture
        last_vente = Vente.objects.order_by('-id').first()
        if last_vente and last_vente.invoice_number:
            try:
                num = int(last_vente.invoice_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        invoice_number = f"INV-{date.today().year}-{num:04d}"

        # ✅ ÉTAPE 1: Créer la vente en brouillon
        vente = Vente(
            invoice_number=invoice_number,
            client=self.client,
            client_name=self.client_name or "Client anonyme",
            client_phone=self.client_phone,
            client_email=self.client_email,
            client_address=self.client_address,
            warehouse=self.warehouse,
            payment_due_date=date.today() + timedelta(days=30),
            subtotal=self.subtotal,
            discount_type=self.discount_type,
            discount_value=self.discount_value,
            discount_amount=self.discount_amount,
            tax_rate=self.tax_rate,
            tax_amount=self.tax_amount,
            shipping_fee=self.shipping_fee,
            total=self.total,
            notes=self.notes,
            internal_notes=self.internal_notes,
            status='draft',  # ✅ Statut brouillon - PAS de déduction de stock
            created_by=user
        )
        vente.save()

        # ✅ ÉTAPE 2: Créer les lignes de vente à partir du devis
        for ligne_devis in self.lignes.all():
            LigneVente.objects.create(
                sale=vente,
                product=ligne_devis.product,
                quantity=ligne_devis.quantity,
                unit_price=ligne_devis.unit_price,
                discount=ligne_devis.discount,
                tax_rate=ligne_devis.tax_rate,
                total=ligne_devis.total,
                notes=ligne_devis.notes
            )

        # ✅ ÉTAPE 3: Mettre à jour le statut du devis
        self.status = 'converted'
        self.sale = vente
        self.save(update_fields=['status', 'sale'])

        # ✅ ÉTAPE 4: Recalculer les totaux de la vente
        vente.calculate_totals()
        
        # ✅ ÉTAPE 5: Générer le QR Code de la vente
        vente.generate_qr_code()
        vente.save(update_fields=['qr_code', 'qr_code_data'])

        return vente


# ==================== LIGNE DEVIS ====================

# ============================================================

class LigneDevis(models.Model):

    devis = models.ForeignKey(
        Devis,
        on_delete=models.CASCADE,
        related_name="lignes"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notes = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Ligne de devis"
        verbose_name_plural = "Lignes de devis"

    def __str__(self):
        return f"{self.devis.devis_number} - {self.product.name}"

    def save(self, *args, **kwargs):

        if self.quantity <= 0:
            raise ValidationError(
                "La quantité doit être supérieure à zéro."
            )

        gross_total = (
            Decimal(self.quantity)
            * self.unit_price
        )

        self.total = max(
            Decimal("0.00"),
            gross_total - self.discount
        )

        super().save(*args, **kwargs)

        self.devis.calculate_totals()


# ============================================================
# VENTE
# ============================================================

class Vente(models.Model):

    STATUS_CHOICES = (
        ("draft", "Brouillon"),
        ("confirmed", "Confirmée"),
        ("paid", "Payée"),
        ("delivered", "Livrée"),
        ("cancelled", "Annulée"),
        ("returned", "Retournée"),
    )

    PAYMENT_STATUS_CHOICES = (
        ("pending", "En attente"),
        ("partial", "Paiement partiel"),
        ("paid", "Payé"),
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True
    )

    order_number = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales"
    )

    client_name = models.CharField(
        max_length=200,
        blank=True
    )

    client_phone = models.CharField(
        max_length=20,
        blank=True
    )

    client_email = models.EmailField(
        blank=True
    )

    client_address = models.TextField(
        blank=True
    )

    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes"
    )

    sale_date = models.DateTimeField(
        auto_now_add=True
    )

    delivery_date = models.DateTimeField(
        null=True,
        blank=True
    )

    payment_due_date = models.DateField(
        null=True,
        blank=True
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount_type = models.CharField(
        max_length=20,
        choices=[
            ("percentage", "Pourcentage"),
            ("amount", "Montant"),
        ],
        default="percentage"
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    payment_method = models.CharField(
        max_length=50,
        blank=True
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending"
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    amount_due = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    delivery_method = models.CharField(
        max_length=50,
        blank=True
    )

    delivery_address = models.TextField(
        blank=True,
        null=True
    )

    delivery_status = models.CharField(
        max_length=50,
        default="pending"
    )

    tracking_number = models.CharField(
        max_length=100,
        blank=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    notes = models.TextField(
        blank=True
    )

    internal_notes = models.TextField(
        blank=True
    )

    qr_code = models.ImageField(
        upload_to="qrcodes/sales/",
        null=True,
        blank=True
    )

    qr_code_data = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_created"
    )

    class Meta:
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"
        ordering = ["-sale_date"]

    def __str__(self):
        return f"{self.invoice_number} - {self.client_name}"

    def calculate_totals(self, save=True):

        self.subtotal = sum(
            (
                line.total
                for line in self.lines.all()
            ),
            Decimal("0.00")
        )

        if self.discount_type == "percentage":

            self.discount_amount = (
                self.subtotal
                * self.discount_value
                / Decimal("100")
            )

        else:

            self.discount_amount = self.discount_value

        self.discount_amount = min(
            self.discount_amount,
            self.subtotal
        )

        after_discount = (
            self.subtotal
            - self.discount_amount
        )

        self.tax_amount = (
            after_discount
            * self.tax_rate
            / Decimal("100")
        )

        self.total = (
            after_discount
            + self.tax_amount
            + self.shipping_fee
        )

        self.amount_due = max(
            Decimal("0.00"),
            self.total - self.amount_paid
        )

        if self.amount_due <= 0:
            self.payment_status = "paid"

        elif self.amount_paid > 0:
            self.payment_status = "partial"

        else:
            self.payment_status = "pending"

        if save and self.pk:

            super().save(
                update_fields=[
                    "subtotal",
                    "discount_amount",
                    "tax_amount",
                    "total",
                    "amount_due",
                    "payment_status",
                    "updated_at"
                ]
            )

    def generate_qr_code(self):

        if not self.pk or not self.invoice_number:
            return

        data = {
            "type": "sale",
            "id": self.id,
            "number": self.invoice_number,
            "client": self.client_name,
            "total": str(self.total),
            "status": self.status,
            "url": f"/ventes/{self.id}/",
        }

        qr_data, buffer = generate_qr_image(data)

        self.qr_code_data = qr_data

        self.qr_code.save(
            f"qr_sale_{self.invoice_number}.png",
            File(buffer),
            save=False
        )

    @transaction.atomic
    def deduct_stock(self):

        if not self.warehouse:

            raise ValidationError(
                "L'entrepôt de vente est obligatoire."
            )

        lines = list(
            self.lines
            .select_related("product")
            .all()
        )

        if not lines:

            raise ValidationError(
                "La vente doit contenir au moins un produit."
            )

        # Vérification globale AVANT de modifier le stock
        for line in lines:

            stock = (
                Stock.objects
                .select_for_update()
                .filter(
                    product=line.product,
                    warehouse=self.warehouse
                )
                .first()
            )

            if not stock:

                raise ValidationError(
                    f"Aucun stock trouvé pour "
                    f"{line.product.name}."
                )

            if stock.available_quantity < line.quantity:

                raise ValidationError(
                    f"Stock insuffisant pour "
                    f"{line.product.name}. "
                    f"Disponible : "
                    f"{stock.available_quantity}, "
                    f"Demandé : {line.quantity}."
                )

        # Déduction FIFO
        for line in lines:

            stock = (
                Stock.objects
                .select_for_update()
                .get(
                    product=line.product,
                    warehouse=self.warehouse
                )
            )

            lots = (
                Lot.objects
                .select_for_update()
                .filter(
                    product=line.product,
                    warehouse=self.warehouse,
                    current_quantity__gt=0,
                    is_blocked=False
                )
                .exclude(
                    status="expired"
                )
                .order_by(
                    "expiry_date",
                    "id"
                )
            )

            remaining = line.quantity

            for lot in lots:

                if remaining <= 0:
                    break

                quantity = min(
                    lot.available_quantity,
                    remaining
                )

                if quantity <= 0:
                    continue

                # IMPORTANT :
                # Ne pas modifier directement lot.current_quantity.
                # StockMovement.save() le fait une seule fois.
                StockMovement.objects.create(
                    product=line.product,
                    lot=lot,
                    from_warehouse=self.warehouse,
                    movement_type="sale_out",
                    quantity=quantity,
                    reference_type="sale",
                    reference_id=self.id,
                    reference_number=self.invoice_number,
                    reason=f"Vente {self.invoice_number}",
                    created_by=self.created_by
                )

                remaining -= quantity

            if remaining > 0:

                raise ValidationError(
                    f"Stock insuffisant pour "
                    f"{line.product.name}."
                )

            stock.update_quantity()

    @transaction.atomic
    def restore_stock(self):

        if not self.warehouse:
            return

        movements = (
            StockMovement.objects
            .filter(
                reference_type="sale",
                reference_id=self.id,
                movement_type="sale_out"
            )
            .select_related("product", "lot")
        )

        for movement in movements:

            if not movement.lot:
                continue

            # IMPORTANT :
            # Ne pas modifier directement le lot.
            # Le mouvement return_in augmente le lot une seule fois.
            StockMovement.objects.create(
                product=movement.product,
                lot=movement.lot,
                to_warehouse=self.warehouse,
                movement_type="return_in",
                quantity=movement.quantity,
                reference_type="sale_cancel",
                reference_id=self.id,
                reference_number=self.invoice_number,
                reason=f"Annulation vente {self.invoice_number}",
                created_by=self.created_by
            )

        product_ids = (
            movements
            .values_list(
                "product_id",
                flat=True
            )
            .distinct()
        )

        for product_id in product_ids:

            stock = Stock.objects.filter(
                product_id=product_id,
                warehouse=self.warehouse
            ).first()

            if stock:
                stock.update_quantity()

    def get_or_create_anonymous_client(self):

        client = Client.objects.filter(
            name="Client anonyme",
            statut="actif"
        ).first()

        if client:
            return client

        return Client.objects.create(
            code=f"ANON-{date.today().year}-{Client.objects.count() + 1:04d}",
            name="Client anonyme",
            phone="00000000",
            email="anonyme@example.com",
            address="Non renseigné",
            city="Non renseigné",
            country="Sénégal",
            statut="actif",
            created_by=self.created_by
        )

    @transaction.atomic
    def generate_invoice(self):

        if self.invoices.exists():
            return self.invoices.first()

        client = self.client

        if not client:

            client = self.get_or_create_anonymous_client()

            self.client = client

            super().save(
                update_fields=[
                    "client",
                    "updated_at"
                ]
            )

        facture = Facture.objects.create(
            invoice_number=generate_number(
                Facture,
                "invoice_number",
                "FAC"
            ),
            sale=self,
            client=client,
            due_date=(
                self.payment_due_date
                or date.today() + timedelta(days=30)
            ),
            subtotal=self.subtotal,
            tax_amount=self.tax_amount,
            total=self.total,
            status="sent",
            notes=(
                f"Facture générée automatiquement "
                f"depuis la vente {self.invoice_number}"
            )
        )

        facture.generate_qr_code()
        facture.save(
            update_fields=[
                "qr_code",
                "qr_code_data",
                "updated_at"
            ]
        )

        return facture

    def save(self, *args, **kwargs):

        is_new = self.pk is None
        old_status = None

        if self.pk:

            old_status = (
                Vente.objects
                .filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        if not self.client_name:

            self.client_name = (
                self.client.name
                if self.client
                else "Client anonyme"
            )

        if not self.invoice_number:

            self.invoice_number = generate_number(
                Vente,
                "invoice_number",
                "INV"
            )

        is_confirming = (
            not is_new
            and old_status == "draft"
            and self.status == "confirmed"
        )

        is_cancelling = (
            not is_new
            and old_status in [
                "confirmed",
                "paid",
                "delivered"
            ]
            and self.status == "cancelled"
        )

        # Sauvegarde normale
        super().save(*args, **kwargs)

        # QR après création
        if not self.qr_code or not self.qr_code_data:

            self.generate_qr_code()

            super().save(
                update_fields=[
                    "qr_code",
                    "qr_code_data",
                    "updated_at"
                ]
            )

        # Confirmation
        if is_confirming:

            try:

                self.deduct_stock()
                self.generate_invoice()

            except Exception as error:

                self.status = "draft"

                super().save(
                    update_fields=[
                        "status",
                        "updated_at"
                    ]
                )

                raise ValidationError(
                    f"Erreur lors de la confirmation : {error}"
                )

        # Annulation
        if is_cancelling:

            self.restore_stock()


# ============================================================
# LIGNE VENTE
# ============================================================

class LigneVente(models.Model):

    sale = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name="lines"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT
    )

    lot = models.ForeignKey(
        Lot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField(
        verbose_name="Quantité"
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    notes = models.TextField(
        blank=True
    )

    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    def __str__(self):

        return (
            f"{self.sale.invoice_number} - "
            f"{self.product.name}"
        )

    def save(self, *args, **kwargs):

        if self.quantity <= 0:

            raise ValidationError(
                "La quantité doit être supérieure à zéro."
            )

        gross_total = (
            Decimal(self.quantity)
            * self.unit_price
        )

        self.total = max(
            Decimal("0.00"),
            gross_total - self.discount
        )

        super().save(*args, **kwargs)

        self.sale.calculate_totals()


# ============================================================
# FACTURE
# ============================================================

class Facture(models.Model):

    STATUS_CHOICES = (
        ("draft", "Brouillon"),
        ("sent", "Envoyée"),
        ("paid", "Payée"),
        ("overdue", "En retard"),
        ("cancelled", "Annulée"),
        ("partial", "Partiellement payée"),
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True
    )

    sale = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name="invoices"
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="invoices"
    )

    invoice_date = models.DateField(
        auto_now_add=True
    )

    due_date = models.DateField()

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    amount_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    pdf_file = models.FileField(
        upload_to="invoices/",
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    qr_code = models.ImageField(
        upload_to="qrcodes/invoices/",
        null=True,
        blank=True
    )

    qr_code_data = models.TextField(
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ["-invoice_date"]

    def __str__(self):

        return (
            f"{self.invoice_number} - "
            f"{self.client.name}"
        )

    @property
    def remaining_amount(self):

        return max(
            Decimal("0.00"),
            self.total - self.amount_paid
        )

    def update_payment_status(self):

        total_paid = (
            self.paiements.aggregate(
                total=Sum("amount")
            )["total"]
            or Decimal("0.00")
        )

        self.amount_paid = total_paid

        if self.amount_paid >= self.total:

            self.status = "paid"

        elif self.amount_paid > 0:

            self.status = "partial"

        else:

            self.status = "sent"

        super().save(
            update_fields=[
                "amount_paid",
                "status",
                "updated_at"
            ]
        )

    def generate_qr_code(self):

        if not self.pk:
            return

        data = {
            "type": "invoice",
            "id": self.id,
            "number": self.invoice_number,
            "client": self.client.name,
            "total": str(self.total),
            "status": self.status,
            "url": f"/factures/{self.id}/",
        }

        qr_data, buffer = generate_qr_image(data)

        self.qr_code_data = qr_data

        self.qr_code.save(
            f"qr_invoice_{self.invoice_number}.png",
            File(buffer),
            save=False
        )

    def save(self, *args, **kwargs):

        if not self.invoice_number:

            self.invoice_number = generate_number(
                Facture,
                "invoice_number",
                "FAC"
            )

        super().save(*args, **kwargs)


# ============================================================
# PAIEMENT
# ============================================================
# ============================================================
# PAIEMENT
# ============================================================

class Paiement(models.Model):

    METHOD_CHOICES = (
        ("cash", "Espèces"),
        ("card", "Carte bancaire"),
        ("check", "Chèque"),
        ("transfer", "Virement"),
        ("mobile_money", "Mobile Money"),
        ("credit", "Crédit"),
    )

    facture = models.ForeignKey(
        Facture,
        on_delete=models.CASCADE,
        related_name="paiements"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES
    )

    reference = models.CharField(
        max_length=100,
        blank=True
    )

    payment_date = models.DateTimeField(
        auto_now_add=True
    )

    received_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    notes = models.TextField(
        blank=True
    )

    qr_code = models.ImageField(
        upload_to="qrcodes/payments/",
        null=True,
        blank=True
    )

    qr_code_data = models.TextField(
        blank=True
    )

    # ✅ CHAMP AJOUTÉ pour corriger l'erreur "updated_at" inexistant
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-payment_date"]

    def __str__(self):
        return (
            f"{self.facture.invoice_number} - "
            f"{self.amount} FCFA"
        )

    def clean(self):
        if self.amount <= 0:
            raise ValidationError(
                "Le montant du paiement doit être supérieur à zéro."
            )

        if self.facture_id:
            previous_paid = (
                self.facture.paiements
                .exclude(pk=self.pk)
                .aggregate(
                    total=Sum("amount")
                )["total"]
                or Decimal("0.00")
            )

            if (
                previous_paid + self.amount
                > self.facture.total
            ):
                raise ValidationError(
                    "Le paiement dépasse le montant restant."
                )

    def generate_qr_code(self):
        if not self.pk:
            return

        data = {
            "type": "payment",
            "id": self.id,
            "amount": str(self.amount),
            "method": self.method,
            "invoice": self.facture.invoice_number,
            "reference": self.reference,
            "url": f"/paiements/{self.id}/",
        }

        qr_data, buffer = generate_qr_image(data)

        self.qr_code_data = qr_data

        self.qr_code.save(
            f"qr_payment_{self.id}.png",
            File(buffer),
            save=False
        )

    def save(self, *args, **kwargs):
        self.full_clean()

        is_new = self.pk is None

        # Sauvegarde initiale
        super().save(*args, **kwargs)

        # Si c'est un nouveau paiement, on génère le QR code
        if is_new:
            self.generate_qr_code()

            # ✅ Maintenant que `updated_at` existe, on peut le mettre à jour
            super().save(
                update_fields=[
                    "qr_code",
                    "qr_code_data",
                    "updated_at"
                ]
            )

        # Mise à jour du statut de paiement de la facture
        self.facture.update_payment_status()

        # Mise à jour des montants sur la vente associée
        sale = self.facture.sale

        if sale:
            total_paid = (
                sale.invoices.aggregate(
                    total=Sum("amount_paid")
                )["total"]
                or Decimal("0.00")
            )

            sale.amount_paid = total_paid

            sale.amount_due = max(
                Decimal("0.00"),
                sale.total - sale.amount_paid
            )

            if sale.amount_due <= 0:
                sale.payment_status = "paid"
            elif sale.amount_paid > 0:
                sale.payment_status = "partial"
            else:
                sale.payment_status = "pending"

            super(
                Vente,
                sale
            ).save(
                update_fields=[
                    "amount_paid",
                    "amount_due",
                    "payment_status",
                    "updated_at"      # Vente possède bien ce champ
                ]
            )
# ============================================================
# AVOIR
# ============================================================


class Avoir(models.Model):

    TYPE_CHOICES = (
        ("credit", "Avoir"),
        ("debit", "Note de débit"),
    )

    avoir_number = models.CharField(
        max_length=50,
        unique=True
    )

    sale = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name="credits"
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="credits"
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default="credit"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    reason = models.TextField()

    date = models.DateField(
        auto_now_add=True
    )

    notes = models.TextField(
        blank=True
    )

    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Avoir"
        verbose_name_plural = "Avoirs"
        ordering = ["-date"]

    def __str__(self):

        return (
            f"{self.avoir_number} - "
            f"{self.client.name} - "
            f"{self.amount} FCFA"
        )

    def save(self, *args, **kwargs):

        if not self.avoir_number:

            self.avoir_number = generate_number(
                Avoir,
                "avoir_number",
                "AV"
            )

        super().save(*args, **kwargs)


# ============================================================
# TAXE
# ============================================================

class Taxe(models.Model):

    name = models.CharField(
        max_length=100
    )

    rate = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )

    is_default = models.BooleanField(
        default=False
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Taxe"
        verbose_name_plural = "Taxes"

    def __str__(self):

        return (
            f"{self.name} "
            f"({self.rate}%)"
        )


# ============================================================
# REMISE
# ============================================================

class Remise(models.Model):

    TYPE_CHOICES = (
        ("percentage", "Pourcentage"),
        ("amount", "Montant fixe"),
    )

    name = models.CharField(
        max_length=100
    )

    type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    min_purchase = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    start_date = models.DateField(
        null=True,
        blank=True
    )

    end_date = models.DateField(
        null=True,
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    clients = models.ManyToManyField(
        Client,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Remise"
        verbose_name_plural = "Remises"

    def __str__(self):

        suffix = (
            "%"
            if self.type == "percentage"
            else " FCFA"
        )

        return (
            f"{self.name} - "
            f"{self.value}{suffix}"
        )

    def is_valid(self):

        today = date.today()

        if not self.is_active:
            return False

        if (
            self.start_date
            and today < self.start_date
        ):
            return False

        if (
            self.end_date
            and today > self.end_date
        ):
            return False

        return True
