# apps/achats_fournisseurs/models.py
from django.db import models

from datetime import date, timedelta
from decimal import Decimal
import qrcode
from io import BytesIO
from django.core.files import File
from PIL import Image
import json
from users.models import CustomUser
from produits_stocks.models import Product, UnitMeasure, Warehouse, Lot


class Supplier(models.Model):
    """
    Fournisseur
    """
    TYPE_CHOICES = (
        ('local', 'Local'),
        ('international', 'International'),
        ('importateur', 'Importateur'),
        ('distributeur', 'Distributeur'),
        ('fabricant', 'Fabricant'),
    )

    PAYMENT_TERMS_CHOICES = (
        ('cash', 'Comptant'),
        ('15', '15 jours'),
        ('30', '30 jours'),
        ('45', '45 jours'),
        ('60', '60 jours'),
        ('90', '90 jours'),
    )

    # Identifiants
    code = models.CharField(max_length=50, unique=True,
                            verbose_name="Code fournisseur")
    name = models.CharField(
        max_length=200, verbose_name="Nom / Raison sociale")
    commercial_name = models.CharField(
        max_length=200, blank=True, verbose_name="Nom commercial")

    # Type
    type = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='local', verbose_name="Type")

    # Contacts
    contact_person = models.CharField(
        max_length=100, blank=True, verbose_name="Personne de contact")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    mobile = models.CharField(max_length=20, blank=True, verbose_name="Mobile")
    email = models.EmailField(verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Site web")

    # Adresse
    address = models.TextField(verbose_name="Adresse")
    city = models.CharField(max_length=100, verbose_name="Ville")
    country = models.CharField(
        max_length=100, default='Sénégal', verbose_name="Pays")
    postal_code = models.CharField(
        max_length=20, blank=True, verbose_name="Code postal")

    # Informations fiscales
    tax_id = models.CharField(
        max_length=50, blank=True, verbose_name="N° Identification fiscale")
    registration_number = models.CharField(
        max_length=50, blank=True, verbose_name="N° Registre de commerce")

    # Conditions commerciales
    payment_terms = models.CharField(
        max_length=20, choices=PAYMENT_TERMS_CHOICES, default='30', verbose_name="Délai de paiement")
    delivery_lead_time = models.IntegerField(
        default=7, help_text="Délai de livraison en jours", verbose_name="Délai de livraison (jours)")
    minimum_order = models.IntegerField(
        default=0, verbose_name="Commande minimum")

    # Évaluation
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0, verbose_name="Note (0-5)")
    total_purchases = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name="Total achats")
    total_orders = models.IntegerField(
        default=0, verbose_name="Nombre de commandes")
    on_time_delivery_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Taux livraison à temps (%)")

    # Statut
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    is_preferred = models.BooleanField(
        default=False, verbose_name="Fournisseur privilégié")
    notes = models.TextField(blank=True, verbose_name="Notes")

    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Date création")
    updated_at = models.DateTimeField(
        auto_now=True, verbose_name="Date modification")
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Créé par"
    )

    class Meta:
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"
        ordering = ['name']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def full_address(self):
        parts = [self.address, self.city, self.country]
        return ", ".join([p for p in parts if p])


class SupplierContact(models.Model):
    """
    Contact chez le fournisseur
    """
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=100, verbose_name="Nom complet")
    position = models.CharField(
        max_length=100, blank=True, verbose_name="Poste")
    phone = models.CharField(max_length=20, verbose_name="Téléphone")
    mobile = models.CharField(max_length=20, blank=True, verbose_name="Mobile")
    email = models.EmailField(verbose_name="Email")
    is_primary = models.BooleanField(
        default=False, verbose_name="Contact principal")
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact fournisseur"
        verbose_name_plural = "Contacts fournisseurs"

    def __str__(self):
        return f"{self.name} - {self.supplier.name}"


class SupplierProduct(models.Model):
    """
    Produits proposés par le fournisseur
    """
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='products')
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='suppliers')
    supplier_sku = models.CharField(
        max_length=100, blank=True, verbose_name="Référence fournisseur")
    purchase_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix d'achat")
    lead_time = models.IntegerField(
        default=7, verbose_name="Délai de livraison (jours)")
    minimum_order = models.IntegerField(
        default=1, verbose_name="Quantité minimum")
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    notes = models.TextField(blank=True, verbose_name="Notes")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit fournisseur"
        verbose_name_plural = "Produits fournisseurs"
        unique_together = ['supplier', 'product']

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"


# ==================== PURCHASE ORDER WITH QR CODE ====================
class PurchaseOrder(models.Model):
    """
    Bon de commande avec QR Code
    """
    STATUS_CHOICES = (
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('confirmed', 'Confirmé'),
        ('partial', 'Partiellement reçu'),
        ('received', 'Reçu'),
        ('cancelled', 'Annulé'),
    )

    DISCOUNT_CHOICES = (
        ('percentage', 'Pourcentage'),
        ('amount', 'Montant fixe'),
    )

    # Identifiants
    po_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° Bon de commande")
    supplier_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence fournisseur")

    # Fournisseur
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, related_name='purchase_orders')

    # Dates
    order_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date commande")
    expected_delivery_date = models.DateField(
        verbose_name="Date livraison prévue")
    actual_delivery_date = models.DateField(
        null=True, blank=True, verbose_name="Date livraison réelle")

    # Montants
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Sous-total")
    discount_type = models.CharField(
        max_length=10, choices=DISCOUNT_CHOICES, default='amount', verbose_name="Type de remise")
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Valeur de la remise")
    discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant de la remise")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="Taux TVA (%)")
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Montant TVA")
    shipping_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Frais de livraison")
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Total")

    # Statut
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")
    internal_notes = models.TextField(
        blank=True, verbose_name="Notes internes")

    # Livraison
    shipping_address = models.TextField(
        blank=True, verbose_name="Adresse de livraison")
    tracking_number = models.CharField(
        max_length=100, blank=True, verbose_name="N° de suivi")

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/purchase_orders/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchase_orders',
        verbose_name="Créé par"
    )
    approved_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_orders',
        verbose_name="Approuvé par"
    )
    approved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Date approbation")

    class Meta:
        verbose_name = "Bon de commande"
        verbose_name_plural = "Bons de commande"
        ordering = ['-order_date']

    def __str__(self):
        return f"{self.po_number} - {self.supplier.name if self.supplier else 'N/A'}"

    def calculate_totals(self):
        """Calcule les totaux de la commande"""
        self.subtotal = sum(line.total for line in self.lines.all())

        if self.discount_type == 'percentage':
            self.discount_amount = self.subtotal * (self.discount_value / 100)
        else:
            self.discount_amount = self.discount_value

        after_discount = self.subtotal - self.discount_amount
        self.tax_amount = after_discount * (self.tax_rate / 100)
        self.total = after_discount + self.tax_amount + self.shipping_cost
        self.save()

    def generate_qr_code(self):
        """Génère un QR Code pour le bon de commande"""
        if not self.po_number:
            return

        # Données à encoder dans le QR Code
        qr_data = {
            'type': 'purchase_order',
            'id': self.id,
            'number': self.po_number,
            'supplier': self.supplier.name if self.supplier else '',
            'supplier_code': self.supplier.code if self.supplier else '',
            'total': str(self.total),
            'date': self.order_date.strftime('%Y-%m-%d %H:%M:%S'),
            'status': self.status,
            'expected_delivery': self.expected_delivery_date.strftime('%Y-%m-%d') if self.expected_delivery_date else '',
            'url': f'/commandes-fournisseurs/{self.id}/'
        }

        qr_data_str = json.dumps(qr_data, ensure_ascii=False)
        self.qr_code_data = qr_data_str

        # Générer l'image QR Code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data_str)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Sauvegarder dans un buffer
        buffer = BytesIO()
        img.save(buffer, format='PNG')

        # Créer le nom du fichier
        filename = f"qr_po_{self.po_number}.png"

        # Sauvegarder dans le champ ImageField
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        # Si c'est une nouvelle commande ou que le QR Code n'existe pas
        is_new = self.pk is None
        super().save(*args, **kwargs)

        # Générer le QR Code après la première sauvegarde
        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class PurchaseOrderLine(models.Model):
    """
    Ligne de bon de commande
    """
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name="Quantité commandée")
    quantity_received = models.IntegerField(
        default=0, verbose_name="Quantité reçue")
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix unitaire")
    discount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="Remise")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, verbose_name="TVA (%)")
    total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Total ligne")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    def __str__(self):
        return f"{self.purchase_order.po_number} - {self.product.name}"

    def save(self, *args, **kwargs):
        self.total = (self.quantity * self.unit_price) - self.discount
        super().save(*args, **kwargs)
        self.purchase_order.calculate_totals()

    @property
    def quantity_remaining(self):
        return self.quantity - self.quantity_received


# ==================== RECEIPT WITH QR CODE ====================
class Receipt(models.Model):
    """
    Réception de marchandises avec QR Code
    """
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
    )

    # Références
    receipt_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° de réception")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='receipts')

    # Dates
    receipt_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de réception")
    expected_date = models.DateField(verbose_name="Date prévue")

    # Entrepôt
    warehouse = models.ForeignKey(
        Warehouse, on_delete=models.SET_NULL, null=True, verbose_name="Entrepôt de destination")

    # Statut
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    notes = models.TextField(blank=True, verbose_name="Notes")

    # Documents
    delivery_note = models.CharField(
        max_length=100, blank=True, verbose_name="N° Bon de livraison")
    invoice_number = models.CharField(
        max_length=100, blank=True, verbose_name="N° Facture")

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/receipts/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Réceptionné par"
    )

    class Meta:
        verbose_name = "Réception"
        verbose_name_plural = "Réceptions"
        ordering = ['-receipt_date']

    def __str__(self):
        return f"{self.receipt_number} - {self.purchase_order.po_number}"

    def generate_qr_code(self):
        """Génère un QR Code pour la réception"""
        if not self.receipt_number:
            return

        qr_data = {
            'type': 'receipt',
            'id': self.id,
            'number': self.receipt_number,
            'purchase_order': self.purchase_order.po_number if self.purchase_order else '',
            'supplier': self.purchase_order.supplier.name if self.purchase_order and self.purchase_order.supplier else '',
            'warehouse': self.warehouse.name if self.warehouse else '',
            'date': self.receipt_date.strftime('%Y-%m-%d %H:%M:%S') if self.receipt_date else '',
            'status': self.status,
            'url': f'/receptions/{self.id}/'
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

        filename = f"qr_rec_{self.receipt_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class ReceiptLine(models.Model):
    """
    Ligne de réception
    """
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, related_name='lines')
    po_line = models.ForeignKey(
        PurchaseOrderLine, on_delete=models.CASCADE, related_name='receipt_lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    # Quantité
    quantity_ordered = models.IntegerField(verbose_name="Quantité commandée")
    quantity_received = models.IntegerField(verbose_name="Quantité reçue")
    quantity_damaged = models.IntegerField(
        default=0, verbose_name="Quantité endommagée")

    # Lot
    lot = models.ForeignKey(Lot, on_delete=models.SET_NULL,
                            null=True, blank=True, verbose_name="Lot associé")
    lot_number = models.CharField(
        max_length=100, blank=True, verbose_name="Numéro de lot")
    expiry_date = models.DateField(
        null=True, blank=True, verbose_name="Date d'expiration")
    manufacturing_date = models.DateField(
        null=True, blank=True, verbose_name="Date de fabrication")

    # Contrôle qualité
    is_quality_checked = models.BooleanField(
        default=False, verbose_name="Contrôle qualité effectué")
    quality_status = models.CharField(max_length=20, blank=True, choices=[
        ('passed', 'Approuvé'),
        ('failed', 'Refusé'),
        ('pending', 'En attente')
    ], default='pending')
    quality_notes = models.TextField(blank=True, verbose_name="Notes qualité")

    # Métadonnées
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Ligne de réception"
        verbose_name_plural = "Lignes de réception"

    def __str__(self):
        return f"{self.receipt.receipt_number} - {self.product.name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Mettre à jour la quantité reçue sur la ligne de commande
        from django.db.models import Sum
        total_received = ReceiptLine.objects.filter(po_line=self.po_line).aggregate(
            total=Sum('quantity_received')
        )['total'] or 0
        self.po_line.quantity_received = total_received
        self.po_line.save()

        # Mettre à jour le statut de la commande
        po = self.receipt.purchase_order
        total_ordered = po.lines.aggregate(total=Sum('quantity'))['total'] or 0
        total_received_po = po.lines.aggregate(
            total=Sum('quantity_received'))['total'] or 0

        if total_received_po >= total_ordered:
            po.status = 'received'
        elif total_received_po > 0:
            po.status = 'partial'
        else:
            po.status = 'confirmed' if po.status != 'draft' else po.status
        po.save()


# ==================== PURCHASE RETURN WITH QR CODE ====================
class PurchaseReturn(models.Model):
    """
    Retour fournisseur avec QR Code
    """
    REASON_CHOICES = (
        ('defective', 'Produit défectueux'),
        ('wrong_product', 'Produit incorrect'),
        ('expired', 'Produit expiré'),
        ('damaged', 'Produit endommagé'),
        ('other', 'Autre'),
    )

    STATUS_CHOICES = (
        ('requested', 'Demandé'),
        ('approved', 'Approuvé'),
        ('shipped', 'Expédié'),
        ('refunded', 'Remboursé'),
        ('replaced', 'Remplacé'),
        ('rejected', 'Refusé'),
    )

    return_number = models.CharField(
        max_length=50, unique=True, verbose_name="N° de retour")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='returns')
    receipt = models.ForeignKey(
        Receipt, on_delete=models.CASCADE, null=True, blank=True, related_name='returns')

    return_date = models.DateTimeField(
        auto_now_add=True, verbose_name="Date de retour")
    reason = models.CharField(
        max_length=20, choices=REASON_CHOICES, verbose_name="Raison")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='requested', verbose_name="Statut")

    notes = models.TextField(blank=True, verbose_name="Notes")
    created_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, verbose_name="Créé par")

    # QR Code
    qr_code = models.ImageField(
        upload_to='qrcodes/purchase_returns/', null=True, blank=True, verbose_name="QR Code")
    qr_code_data = models.TextField(blank=True, verbose_name="Données QR Code")

    class Meta:
        verbose_name = "Retour fournisseur"
        verbose_name_plural = "Retours fournisseurs"
        ordering = ['-return_date']

    def __str__(self):
        return f"{self.return_number} - {self.purchase_order.po_number}"

    def generate_qr_code(self):
        """Génère un QR Code pour le retour"""
        if not self.return_number:
            return

        qr_data = {
            'type': 'purchase_return',
            'id': self.id,
            'number': self.return_number,
            'purchase_order': self.purchase_order.po_number if self.purchase_order else '',
            'supplier': self.purchase_order.supplier.name if self.purchase_order and self.purchase_order.supplier else '',
            'reason': self.reason,
            'status': self.status,
            'date': self.return_date.strftime('%Y-%m-%d %H:%M:%S') if self.return_date else '',
            'url': f'/purchase-returns/{self.id}/'
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

        filename = f"qr_ret_{self.return_number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)

        if is_new or not self.qr_code or not self.qr_code_data:
            self.generate_qr_code()
            super().save(update_fields=['qr_code', 'qr_code_data'])


class PurchaseReturnLine(models.Model):
    """
    Ligne de retour fournisseur
    """
    purchase_return = models.ForeignKey(
        PurchaseReturn, on_delete=models.CASCADE, related_name='lines')
    receipt_line = models.ForeignKey(
        ReceiptLine, on_delete=models.CASCADE, related_name='return_lines')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(verbose_name="Quantité retournée")
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Prix unitaire")
    total = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Total")

    def save(self, *args, **kwargs):
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class SupplierInvoice(models.Model):
    """
    Facture fournisseur
    """
    STATUS_CHOICES = (
        ('received', 'Reçue'),
        ('verified', 'Vérifiée'),
        ('paid', 'Payée'),
        ('partial', 'Partiellement payée'),
        ('disputed', 'Contestée'),
    )

    invoice_number = models.CharField(
        max_length=100, unique=True, verbose_name="N° Facture")
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name='invoices')
    supplier = models.ForeignKey(
        Supplier, on_delete=models.CASCADE, related_name='invoices')

    invoice_date = models.DateField(verbose_name="Date facture")
    due_date = models.DateField(verbose_name="Date d'échéance")

    amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Montant")
    tax_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="TVA")
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Total")

    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Montant payé")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='received', verbose_name="Statut")

    payment_date = models.DateField(
        null=True, blank=True, verbose_name="Date de paiement")
    payment_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence paiement")

    pdf_file = models.FileField(
        upload_to='invoices/', null=True, blank=True, verbose_name="PDF facture")
    notes = models.TextField(blank=True, verbose_name="Notes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Facture fournisseur"
        verbose_name_plural = "Factures fournisseurs"
        ordering = ['-invoice_date']

    def __str__(self):
        return f"{self.invoice_number} - {self.supplier.name}"

    @property
    def remaining_amount(self):
        return self.total_amount - self.amount_paid
