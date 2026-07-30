# apps/ventes_clients/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from datetime import date, timedelta
from decimal import Decimal
from .models import (
    Client, Vente, LigneVente, Paiement, Facture,
    Avoir, Taxe, Remise, Devis, LigneDevis
)
from produits_stocks.models import Product, Lot, Stock, StockMovement
from produits_stocks.serializers import ProductListSerializer, LotListSerializer


# ==================== CLIENT ====================
class ClientSerializer(serializers.ModelSerializer):
    full_address = serializers.ReadOnlyField()
    total_purchases_display = serializers.SerializerMethodField()
    credit_limit_display = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'id', 'code', 'name', 'commercial_name', 'type',
            'contact_person', 'phone', 'mobile', 'email', 'website',
            'address', 'city', 'country', 'postal_code',
            'tax_id', 'registration_number',
            'payment_terms', 'credit_limit', 'credit_limit_display',
            'current_balance', 'rating', 'total_purchases',
            'total_purchases_display', 'total_orders',
            'statut', 'is_favorite', 'notes',
            'created_at', 'updated_at', 'created_by', 'full_address'
        ]
        read_only_fields = ['id', 'created_at',
                            'updated_at', 'total_purchases', 'total_orders']

    def get_total_purchases_display(self, obj):
        return f"{obj.total_purchases:,.0f} FCFA" if obj.total_purchases else "0 FCFA"

    def get_credit_limit_display(self, obj):
        return f"{obj.credit_limit:,.0f} FCFA" if obj.credit_limit else "0 FCFA"

    def validate_code(self, value):
        if Client.objects.exclude(id=self.instance.id if self.instance else None).filter(code=value).exists():
            raise serializers.ValidationError("Ce code client existe déjà")
        return value


class ClientListSerializer(serializers.ModelSerializer):
    """Serializer léger pour la liste des clients"""
    total_purchases_display = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            'id', 'code', 'name', 'commercial_name', 'type',
            'phone', 'email', 'city', 'statut', 'is_favorite',
            'total_purchases', 'total_purchases_display', 'rating'
        ]

    def get_total_purchases_display(self, obj):
        return f"{obj.total_purchases:,.0f} FCFA" if obj.total_purchases else "0 FCFA"


# ==================== DEVIS ====================
class LigneDevisSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = LigneDevis
        fields = [
            'id', 'product', 'product_name', 'product_code',
            'quantity', 'unit_price', 'discount', 'tax_rate', 'total', 'notes'
        ]
        read_only_fields = ['id', 'total']


class LigneDevisCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneDevis
        fields = ['product', 'quantity', 'unit_price',
                  'discount', 'tax_rate', 'notes']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à 0")
        return value

    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le prix unitaire doit être supérieur à 0")
        return value


class DevisListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    total_display = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    has_been_converted = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)

    class Meta:
        model = Devis
        fields = [
            'id', 'devis_number', 'client', 'client_name',
            'devis_date', 'valid_until', 'total', 'total_display',
            'status', 'status_display', 'is_expired', 'has_been_converted',
            'warehouse', 'warehouse_name', 'created_by'
        ]
        read_only_fields = ['id', 'devis_date', 'devis_number']

    def get_total_display(self, obj):
        return f"{obj.total:,.0f} FCFA" if obj.total else "0 FCFA"

    def get_is_expired(self, obj):
        return obj.valid_until < date.today() and obj.status not in ['accepted', 'converted']

    def get_has_been_converted(self, obj):
        return obj.status == 'converted' and obj.sale is not None


class DevisDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_phone = serializers.CharField(source='client.phone', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    client_address = serializers.CharField(
        source='client.address', read_only=True)
    lignes = LigneDevisSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    total_display = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    sale_info = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(
        source='warehouse.code', read_only=True)

    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Devis
        fields = [
            'id', 'devis_number', 'client', 'client_name',
            'client_phone', 'client_email', 'client_address',
            'devis_date', 'valid_until',
            'subtotal', 'discount_type', 'discount_value', 'discount_amount',
            'tax_rate', 'tax_amount', 'shipping_fee', 'total', 'total_display',
            'status', 'status_display', 'is_expired',
            'notes', 'internal_notes', 'lignes', 'sale', 'sale_info',
            'warehouse', 'warehouse_name', 'warehouse_code',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'qr_code', 'qr_code_data', 'qr_code_url'
        ]
        read_only_fields = ['id', 'devis_date',
                            'devis_number', 'qr_code', 'qr_code_data']

    def get_total_display(self, obj):
        return f"{obj.total:,.0f} FCFA" if obj.total else "0 FCFA"

    def get_is_expired(self, obj):
        return obj.valid_until < date.today() and obj.status not in ['accepted', 'converted']

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_sale_info(self, obj):
        if obj.sale:
            from .serializers import VenteListSerializer
            return VenteListSerializer(obj.sale).data
        return None


class DevisCreateSerializer(serializers.ModelSerializer):
    lignes = LigneDevisCreateSerializer(many=True)

    class Meta:
        model = Devis
        fields = [
            'client', 'warehouse', 'valid_until',
            'discount_type', 'discount_value', 'tax_rate', 'shipping_fee',
            'notes', 'internal_notes', 'lignes'
        ]

    def validate_valid_until(self, value):
        if value < date.today():
            raise serializers.ValidationError(
                "La date de validité ne peut pas être dans le passé")
        return value

    def validate_lignes(self, value):
        if not value:
            raise serializers.ValidationError("Au moins un produit est requis")

        # Vérification des doublons
        product_ids = [line.get('product')
                       for line in value if line.get('product')]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Un produit ne peut apparaître qu'une seule fois dans le devis."
            )
        return value

    def validate_warehouse(self, value):
        if not value:
            raise serializers.ValidationError("Un entrepôt est requis")
        return value

    @transaction.atomic
    def create(self, validated_data):
        lignes_data = validated_data.pop('lignes')
        client = validated_data.get('client')

        last_devis = Devis.objects.order_by('-id').first()
        if last_devis and last_devis.devis_number:
            try:
                num = int(last_devis.devis_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        devis_number = f"DEV-{date.today().year}-{num:04d}"

        devis = Devis.objects.create(
            devis_number=devis_number,
            client_name=client.name if client else '',
            client_phone=client.phone if client else '',
            client_email=client.email if client else '',
            client_address=client.address if client else '',
            **validated_data
        )

        for line_data in lignes_data:
            LigneDevis.objects.create(devis=devis, **line_data)

        devis.calculate_totals()
        devis.generate_qr_code()
        devis.save()

        return devis


class DevisUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Devis
        fields = [
            'valid_until', 'discount_type', 'discount_value',
            'tax_rate', 'shipping_fee', 'notes', 'internal_notes'
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.calculate_totals()
        instance.generate_qr_code()
        instance.save()
        return instance


class DevisStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        allowed = ['draft', 'sent', 'accepted', 'refused', 'expired']
        if value not in allowed:
            raise serializers.ValidationError(
                f"Statut invalide. Choisir parmi: {', '.join(allowed)}")
        return value


# ==================== LIGNE VENTE ====================
class LigneVenteSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    lot_number = serializers.CharField(source='lot.lot_number', read_only=True)

    class Meta:
        model = LigneVente
        fields = [
            'id', 'product', 'product_name', 'product_code',
            'lot', 'lot_number', 'quantity', 'unit_price',
            'discount', 'tax_rate', 'total', 'notes'
        ]
        read_only_fields = ['id', 'total']


class LigneVenteCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LigneVente
        fields = ['product', 'lot', 'quantity',
                  'unit_price', 'discount', 'tax_rate', 'notes']

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à 0")
        return value

    def validate_unit_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le prix unitaire doit être supérieur à 0")
        return value


# ==================== VENTE ====================
class VenteListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(
        source='get_payment_status_display', read_only=True)
    total_display = serializers.SerializerMethodField()
    has_facture = serializers.SerializerMethodField()
    from_devis = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)

    class Meta:
        model = Vente
        fields = [
            'id', 'invoice_number', 'order_number', 'client', 'client_name',
            'sale_date', 'total', 'total_display', 'status', 'status_display',
            'payment_status', 'payment_status_display', 'amount_paid', 'amount_due',
            'warehouse', 'warehouse_name', 'created_by', 'has_facture', 'from_devis'
        ]
        read_only_fields = ['id', 'sale_date', 'invoice_number']

    def get_total_display(self, obj):
        return f"{obj.total:,.0f} FCFA" if obj.total else "0 FCFA"

    def get_has_facture(self, obj):
        return obj.invoices.exists()

    def get_from_devis(self, obj):
        return obj.devis_source.filter(status='converted').exists()


class VenteDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    client_phone = serializers.CharField(source='client.phone', read_only=True)
    client_email = serializers.CharField(source='client.email', read_only=True)
    client_address = serializers.CharField(
        source='client.address', read_only=True)
    lines = LigneVenteSerializer(many=True, read_only=True)
    payments = serializers.SerializerMethodField()
    factures = serializers.SerializerMethodField()
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    payment_status_display = serializers.CharField(
        source='get_payment_status_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    total_display = serializers.SerializerMethodField()
    from_devis = serializers.SerializerMethodField()
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(
        source='warehouse.code', read_only=True)

    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Vente
        fields = [
            'id', 'invoice_number', 'order_number', 'client', 'client_name',
            'client_phone', 'client_email', 'client_address',
            'sale_date', 'delivery_date', 'payment_due_date',
            'subtotal', 'discount_type', 'discount_value', 'discount_amount',
            'tax_rate', 'tax_amount', 'shipping_fee', 'total', 'total_display',
            'payment_method', 'payment_status', 'payment_status_display',
            'amount_paid', 'amount_due', 'delivery_method', 'delivery_address',
            'delivery_status', 'tracking_number', 'status', 'status_display',
            'notes', 'internal_notes', 'lines', 'payments', 'factures',
            'warehouse', 'warehouse_name', 'warehouse_code',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'qr_code', 'qr_code_data', 'qr_code_url', 'from_devis'
        ]
        read_only_fields = ['id', 'sale_date',
                            'invoice_number', 'qr_code', 'qr_code_data']

    def get_total_display(self, obj):
        return f"{obj.total:,.0f} FCFA" if obj.total else "0 FCFA"

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_payments(self, obj):
        payments = []
        for facture in obj.invoices.all():
            for paiement in facture.paiements.all():
                payments.append(paiement)
        return PaiementSerializer(payments, many=True).data

    def get_factures(self, obj):
        factures = obj.invoices.all()
        return FactureSerializer(factures, many=True, context=self.context).data

    def get_from_devis(self, obj):
        return obj.devis_source.filter(status='converted').exists()


class VenteCreateSerializer(serializers.ModelSerializer):
    lines = LigneVenteCreateSerializer(many=True)

    class Meta:
        model = Vente
        fields = [
            'client', 'warehouse', 'delivery_date', 'payment_due_date',
            'discount_type', 'discount_value', 'tax_rate', 'shipping_fee',
            'payment_method', 'delivery_method', 'delivery_address',
            'notes', 'internal_notes', 'lines'
        ]

    def validate_payment_due_date(self, value):
        if value < date.today():
            raise serializers.ValidationError(
                "La date d'échéance ne peut pas être dans le passé")
        return value

    def validate_lines(self, value):
        if not value:
            raise serializers.ValidationError("Au moins un produit est requis")

        product_ids = []
        for line in value:
            product_id = line.get('product')
            if product_id:
                if hasattr(product_id, 'id'):
                    product_id = product_id.id
                product_ids.append(product_id)

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Un produit ne peut apparaître qu'une seule fois dans la vente."
            )
        return value

    def validate_warehouse(self, value):
        if not value:
            raise serializers.ValidationError("Un entrepôt est requis")
        return value

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        client = validated_data.get('client')

        # ✅ CORRECTION ICI : year est un attribut, pas une méthode
        last_vente = Vente.objects.order_by('-id').first()
        if last_vente and last_vente.invoice_number:
            try:
                num = int(last_vente.invoice_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        invoice_number = f"INV-{date.today().year}-{num:04d}"

        vente = Vente.objects.create(
            invoice_number=invoice_number,
            client_name=client.name if client else '',
            client_phone=client.phone if client else '',
            client_email=client.email if client else '',
            client_address=client.address if client else '',
            **validated_data
        )

        for line_data in lines_data:
            LigneVente.objects.create(sale=vente, **line_data)

        vente.calculate_totals()
        vente.generate_qr_code()
        vente.save()

        return vente


class VenteUpdateSerializer(serializers.ModelSerializer):
    lines = LigneVenteCreateSerializer(many=True, required=False)

    class Meta:
        model = Vente
        fields = [
            'delivery_date', 'payment_due_date', 'discount_type',
            'discount_value', 'tax_rate', 'shipping_fee',
            'payment_method', 'delivery_method', 'delivery_address',
            'notes', 'internal_notes', 'tracking_number', 'lines'
        ]

    def validate_lines(self, value):
        if value is None:
            return value

        if not value:
            raise serializers.ValidationError("Au moins un produit est requis")

        product_ids = []
        for line in value:
            product_id = line.get('product')
            if product_id:
                if hasattr(product_id, 'id'):
                    product_id = product_id.id
                product_ids.append(product_id)

        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Un produit ne peut apparaître qu'une seule fois dans la vente."
            )
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        lines_data = validated_data.pop('lines', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if lines_data is not None:
            instance.lines.all().delete()
            for line_data in lines_data:
                LigneVente.objects.create(sale=instance, **line_data)

        instance.calculate_totals()
        instance.generate_qr_code()
        instance.save()
        return instance


class VenteStatusUpdateSerializer(serializers.Serializer):
    status = serializers.CharField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_status(self, value):
        allowed = ['draft', 'confirmed', 'paid',
                   'delivered', 'cancelled', 'returned']
        if value not in allowed:
            raise serializers.ValidationError(
                f"Statut invalide. Choisir parmi: {', '.join(allowed)}")
        return value


# ==================== FACTURE ====================
class FactureSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    sale_number = serializers.CharField(
        source='sale.invoice_number', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    remaining_amount = serializers.ReadOnlyField()
    paiements = serializers.SerializerMethodField()
    total_display = serializers.SerializerMethodField()
    remaining_display = serializers.SerializerMethodField()

    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = [
            'id', 'invoice_number', 'sale', 'sale_number', 'client', 'client_name',
            'invoice_date', 'due_date', 'subtotal', 'tax_amount', 'total',
            'total_display', 'amount_paid', 'remaining_amount', 'remaining_display',
            'status', 'status_display',
            'pdf_file', 'notes', 'paiements',
            'qr_code', 'qr_code_data', 'qr_code_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'invoice_date', 'qr_code', 'qr_code_data']

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

    def get_paiements(self, obj):
        paiements = obj.paiements.all()
        return PaiementSerializer(paiements, many=True).data

    def get_total_display(self, obj):
        return f"{obj.total:,.0f} FCFA" if obj.total else "0 FCFA"

    def get_remaining_display(self, obj):
        return f"{obj.remaining_amount:,.0f} FCFA" if obj.remaining_amount else "0 FCFA"


class FactureCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Facture
        fields = ['sale', 'due_date', 'notes']

    def validate(self, data):
        sale = data.get('sale')
        if sale and sale.status in ['cancelled']:
            raise serializers.ValidationError(
                "Cette vente ne peut pas être facturée")

        if sale and Facture.objects.filter(sale=sale).exists():
            raise serializers.ValidationError(
                "Une facture existe déjà pour cette vente")

        return data

    @transaction.atomic
    def create(self, validated_data):
        sale = validated_data.get('sale')
        client = sale.client

        last_facture = Facture.objects.order_by('-id').first()
        if last_facture and last_facture.invoice_number:
            try:
                num = int(last_facture.invoice_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        invoice_number = f"FAC-{date.today().year}-{num:04d}"

        facture = Facture.objects.create(
            invoice_number=invoice_number,
            client=client,
            subtotal=sale.subtotal,
            tax_amount=sale.tax_amount,
            total=sale.total,
            **validated_data
        )

        facture.generate_qr_code()
        facture.save()

        return facture


# ==================== PAIEMENT ====================
class PaiementSerializer(serializers.ModelSerializer):
    method_display = serializers.CharField(
        source='get_method_display', read_only=True)
    received_by_name = serializers.CharField(
        source='received_by.full_name', read_only=True)

    facture_number = serializers.CharField(
        source='facture.invoice_number', read_only=True)
    client_name = serializers.CharField(
        source='facture.client.name', read_only=True)
    remaining_amount = serializers.SerializerMethodField()
    facture_total = serializers.SerializerMethodField()
    amount_display = serializers.SerializerMethodField()

    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Paiement
        fields = [
            'id',
            'facture', 'facture_number',
            'client_name',
            'amount', 'amount_display',
            'method', 'method_display',
            'reference',
            'payment_date',
            'received_by', 'received_by_name',
            'remaining_amount',
            'facture_total',
            'notes',
            'qr_code', 'qr_code_data', 'qr_code_url'
        ]
        read_only_fields = ['id', 'payment_date', 'qr_code', 'qr_code_data']

    def get_remaining_amount(self, obj):
        return obj.facture.remaining_amount

    def get_facture_total(self, obj):
        return obj.facture.total

    def get_amount_display(self, obj):
        return f"{obj.amount:,.0f} FCFA" if obj.amount else "0 FCFA"

    def get_qr_code_url(self, obj):
        if obj.qr_code and hasattr(obj.qr_code, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None


class PaiementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paiement
        fields = ['facture', 'amount', 'method', 'reference', 'notes']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être supérieur à 0")
        return value

    def validate(self, data):
        facture = data.get('facture')
        amount = data.get('amount', 0)

        if facture and amount > facture.remaining_amount:
            raise serializers.ValidationError(
                {"amount": f"Le montant dépasse le solde restant ({facture.remaining_amount:,.0f} FCFA)"}
            )
        return data


# ==================== AVOIR ====================
class AvoirSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source='client.name', read_only=True)
    sale_number = serializers.CharField(
        source='sale.invoice_number', read_only=True)
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    amount_display = serializers.SerializerMethodField()

    class Meta:
        model = Avoir
        fields = [
            'id', 'avoir_number', 'sale', 'sale_number', 'client', 'client_name',
            'type', 'type_display', 'amount', 'amount_display', 'reason', 'date',
            'notes', 'created_by', 'created_by_name', 'created_at'
        ]
        read_only_fields = ['id', 'date', 'avoir_number']

    def get_amount_display(self, obj):
        return f"{obj.amount:,.0f} FCFA" if obj.amount else "0 FCFA"


class AvoirCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Avoir
        fields = ['sale', 'client', 'type', 'amount', 'reason', 'notes']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être supérieur à 0")
        return value

    def validate(self, data):
        sale = data.get('sale')
        amount = data.get('amount', 0)

        if sale and amount > sale.total:
            raise serializers.ValidationError(
                {"amount": f"Le montant de l'avoir ne peut pas dépasser le total de la vente ({sale.total:,.0f} FCFA)"}
            )
        return data

    @transaction.atomic
    def create(self, validated_data):
        last_avoir = Avoir.objects.order_by('-id').first()
        if last_avoir and last_avoir.avoir_number:
            try:
                num = int(last_avoir.avoir_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        avoir_number = f"AV-{date.today().year}-{num:04d}"

        avoir = Avoir.objects.create(
            avoir_number=avoir_number,
            **validated_data
        )

        return avoir


# ==================== TAXE ====================
class TaxeSerializer(serializers.ModelSerializer):
    rate_display = serializers.SerializerMethodField()

    class Meta:
        model = Taxe
        fields = ['id', 'name', 'rate',
                  'rate_display', 'is_default', 'is_active']
        read_only_fields = ['id']

    def get_rate_display(self, obj):
        return f"{obj.rate}%"


# ==================== REMISE ====================
class RemiseSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(
        source='get_type_display', read_only=True)
    clients_count = serializers.SerializerMethodField()
    value_display = serializers.SerializerMethodField()

    class Meta:
        model = Remise
        fields = [
            'id', 'name', 'type', 'type_display', 'value', 'value_display',
            'min_purchase', 'start_date', 'end_date',
            'is_active', 'clients', 'clients_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_clients_count(self, obj):
        return obj.clients.count()

    def get_value_display(self, obj):
        if obj.type == 'percentage':
            return f"{obj.value}%"
        return f"{obj.value:,.0f} FCFA"


# ==================== DASHBOARD STATS SERIALIZERS ====================
class SalesSummarySerializer(serializers.Serializer):
    sales = serializers.DictField()
    amounts = serializers.DictField()
    payments = serializers.DictField()
    clients = serializers.DictField()
    invoices = serializers.DictField()
    devis = serializers.DictField()


class SalesTrendSerializer(serializers.Serializer):
    date = serializers.DateField()
    total_sales = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class TopProductsSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    quantity_sold = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)


class TopClientsSerializer(serializers.Serializer):
    client_id = serializers.IntegerField()
    client_name = serializers.CharField()
    total_orders = serializers.IntegerField()
    total_purchases = serializers.DecimalField(max_digits=15, decimal_places=2)


class DevisStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    en_attente = serializers.IntegerField()
    acceptes = serializers.IntegerField()
    expires = serializers.IntegerField()
    convertis = serializers.IntegerField()
