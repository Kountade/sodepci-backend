# apps/achats_fournisseurs/serializers.py
from rest_framework import serializers
from django.db import transaction
from django.db.models import Sum
from datetime import date
from .models import (
    Supplier, SupplierContact, SupplierProduct, PurchaseOrder,
    PurchaseOrderLine, Receipt, ReceiptLine, PurchaseReturn,
    PurchaseReturnLine, SupplierInvoice
)
from produits_stocks.models import Product, Lot, Stock, StockMovement
from produits_stocks.serializers import ProductListSerializer, LotListSerializer


# ==================== SUPPLIER ====================
class SupplierContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierContact
        fields = [
            'id', 'name', 'position', 'phone', 'mobile', 'email',
            'is_primary', 'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class SupplierProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    product_unit = serializers.CharField(
        source='product.unit.symbol', read_only=True)

    class Meta:
        model = SupplierProduct
        fields = [
            'id', 'product', 'product_name', 'product_code', 'product_unit',
            'supplier_sku', 'purchase_price', 'lead_time', 'minimum_order',
            'is_active', 'notes', 'last_updated'
        ]
        read_only_fields = ['id', 'last_updated']


class SupplierListSerializer(serializers.ModelSerializer):
    total_purchases_display = serializers.SerializerMethodField()

    class Meta:
        model = Supplier
        fields = [
            'id', 'code', 'name', 'commercial_name', 'type', 'phone',
            'email', 'city', 'is_active', 'is_preferred', 'rating',
            'total_purchases', 'total_purchases_display'
        ]
        read_only_fields = ['id', 'total_purchases', 'total_orders']

    def get_total_purchases_display(self, obj):
        return f"{obj.total_purchases:,.0f} FCFA" if obj.total_purchases else "0 FCFA"


class SupplierDetailSerializer(serializers.ModelSerializer):
    contacts = SupplierContactSerializer(many=True, read_only=True)
    products = SupplierProductSerializer(many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'code', 'name', 'commercial_name', 'type', 'contact_person',
            'phone', 'mobile', 'email', 'website', 'address', 'city',
            'country', 'postal_code', 'tax_id', 'registration_number',
            'payment_terms', 'delivery_lead_time', 'minimum_order',
            'rating', 'total_purchases', 'total_orders', 'on_time_delivery_rate',
            'is_active', 'is_preferred', 'notes', 'contacts', 'products',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at',
                            'updated_at', 'total_purchases', 'total_orders']


class SupplierWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'code', 'name', 'commercial_name', 'type', 'contact_person',
            'phone', 'mobile', 'email', 'website', 'address', 'city',
            'country', 'postal_code', 'tax_id', 'registration_number',
            'payment_terms', 'delivery_lead_time', 'minimum_order',
            'is_active', 'is_preferred', 'notes'
        ]

    def validate_code(self, value):
        if Supplier.objects.exclude(id=self.instance.id if self.instance else None).filter(code=value).exists():
            raise serializers.ValidationError(
                "Ce code fournisseur existe déjà")
        return value


# ==================== PURCHASE ORDER ====================
class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    quantity_remaining = serializers.ReadOnlyField()

    class Meta:
        model = PurchaseOrderLine
        fields = [
            'id', 'product', 'product_name', 'product_code', 'quantity',
            'quantity_received', 'quantity_remaining', 'unit_price',
            'discount', 'tax_rate', 'total', 'notes'
        ]
        read_only_fields = ['id', 'quantity_received', 'total']


class PurchaseOrderLineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrderLine
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


class PurchaseOrderListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(
        source='supplier.code', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    has_qr_code = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier', 'supplier_name', 'supplier_code',
            'order_date', 'expected_delivery_date', 'actual_delivery_date',
            'total', 'status', 'status_display', 'created_by',
            'has_qr_code'
        ]
        read_only_fields = ['id', 'order_date', 'po_number']

    def get_has_qr_code(self, obj):
        return bool(obj.qr_code)


class PurchaseOrderDetailSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    supplier_code = serializers.CharField(
        source='supplier.code', read_only=True)
    supplier_address = serializers.CharField(
        source='supplier.address', read_only=True)
    supplier_phone = serializers.CharField(
        source='supplier.phone', read_only=True)
    lines = PurchaseOrderLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(
        source='approved_by.full_name', read_only=True)

    # QR Code fields
    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier_reference', 'supplier', 'supplier_name',
            'supplier_code', 'supplier_address', 'supplier_phone', 'order_date',
            'expected_delivery_date', 'actual_delivery_date', 'subtotal',
            'discount_type', 'discount_value', 'discount_amount', 'tax_rate',
            'tax_amount', 'shipping_cost', 'total', 'status', 'status_display',
            'notes', 'internal_notes', 'shipping_address', 'tracking_number',
            'lines', 'created_at', 'updated_at', 'created_by', 'created_by_name',
            'approved_by', 'approved_by_name', 'approved_at',
            'qr_code', 'qr_code_data', 'qr_code_url'
        ]
        read_only_fields = ['id', 'order_date',
                            'po_number', 'qr_code', 'qr_code_data']

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None


class PurchaseOrderCreateSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineCreateSerializer(many=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'supplier_reference', 'expected_delivery_date',
            'discount_type', 'discount_value', 'tax_rate', 'shipping_cost',
            'notes', 'internal_notes', 'shipping_address', 'lines'
        ]

    def validate_expected_delivery_date(self, value):
        if value < date.today():
            raise serializers.ValidationError(
                "La date de livraison prévue ne peut pas être dans le passé")
        return value

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop('lines')

        last_po = PurchaseOrder.objects.order_by('-id').first()
        if last_po and last_po.po_number:
            try:
                num = int(last_po.po_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        po_number = f"PO-{date.today().year}-{num:04d}"

        purchase_order = PurchaseOrder.objects.create(
            po_number=po_number,
            **validated_data
        )

        for line_data in lines_data:
            PurchaseOrderLine.objects.create(
                purchase_order=purchase_order,
                **line_data
            )

        purchase_order.calculate_totals()

        # Générer le QR Code après la création
        purchase_order.generate_qr_code()
        purchase_order.save()

        return purchase_order


class PurchaseOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier_reference', 'expected_delivery_date', 'discount_type',
            'discount_value', 'tax_rate', 'shipping_cost', 'notes',
            'internal_notes', 'shipping_address', 'tracking_number'
        ]

    @transaction.atomic
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        instance.calculate_totals()

        # Régénérer le QR Code si nécessaire
        instance.generate_qr_code()
        instance.save()

        return instance


class PurchaseOrderApproveSerializer(serializers.Serializer):
    approved = serializers.BooleanField()
    notes = serializers.CharField(required=False, allow_blank=True)


# ==================== RECEIPT ====================
class ReceiptLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)
    po_line_quantity = serializers.IntegerField(
        source='po_line.quantity', read_only=True)

    class Meta:
        model = ReceiptLine
        fields = [
            'id', 'product', 'product_name', 'product_code', 'po_line',
            'po_line_quantity',
            'quantity_ordered', 'quantity_received', 'quantity_damaged',
            'lot', 'lot_number', 'expiry_date', 'manufacturing_date',
            'is_quality_checked', 'quality_status', 'quality_notes', 'notes'
        ]
        read_only_fields = ['id', 'po_line', 'quantity_ordered']


class ReceiptLineCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiptLine
        fields = [
            'po_line', 'quantity_received', 'quantity_damaged', 'lot_number',
            'expiry_date', 'manufacturing_date', 'quality_status', 'quality_notes', 'notes'
        ]

    def validate_quantity_received(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité reçue doit être supérieure à 0")
        return value


class ReceiptListSerializer(serializers.ModelSerializer):
    po_number = serializers.CharField(
        source='purchase_order.po_number', read_only=True)
    supplier_name = serializers.CharField(
        source='purchase_order.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    has_qr_code = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            'id', 'receipt_number', 'po_number', 'supplier_name', 'warehouse',
            'warehouse_name', 'receipt_date', 'expected_date', 'status',
            'status_display', 'created_by', 'has_qr_code'
        ]
        read_only_fields = ['id', 'receipt_number', 'receipt_date']

    def get_has_qr_code(self, obj):
        return bool(obj.qr_code)


class ReceiptDetailSerializer(serializers.ModelSerializer):
    po_number = serializers.CharField(
        source='purchase_order.po_number', read_only=True)
    supplier_name = serializers.CharField(
        source='purchase_order.supplier.name', read_only=True)
    warehouse_name = serializers.CharField(
        source='warehouse.name', read_only=True)
    lines = ReceiptLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)

    # QR Code fields
    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            'id', 'receipt_number', 'purchase_order', 'po_number', 'supplier_name',
            'receipt_date', 'expected_date', 'warehouse', 'warehouse_name',
            'status', 'status_display', 'notes', 'delivery_note', 'invoice_number',
            'lines', 'created_at', 'created_by', 'created_by_name',
            'qr_code', 'qr_code_data', 'qr_code_url'
        ]
        read_only_fields = ['id', 'receipt_number',
                            'receipt_date', 'qr_code', 'qr_code_data']

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None

# apps/achats_fournisseurs/serializers.py


class ReceiptCreateSerializer(serializers.ModelSerializer):
    lines = ReceiptLineCreateSerializer(many=True)

    class Meta:
        model = Receipt
        fields = ['purchase_order', 'expected_date', 'warehouse',
                  'delivery_note', 'invoice_number', 'notes', 'lines']

    def validate(self, data):
        purchase_order = data.get('purchase_order')
        if purchase_order and purchase_order.status in ['cancelled', 'received']:
            raise serializers.ValidationError(
                "Cette commande ne peut plus être réceptionnée")

        lines_data = data.get('lines', [])
        for line_data in lines_data:
            po_line = line_data.get('po_line')
            quantity_received = line_data.get('quantity_received', 0)

            total_received = ReceiptLine.objects.filter(po_line=po_line).aggregate(
                total=Sum('quantity_received')
            )['total'] or 0
            quantity_remaining = po_line.quantity - total_received

            if quantity_received > quantity_remaining:
                raise serializers.ValidationError(
                    f"Quantité reçue ({quantity_received}) dépasse la quantité restante ({quantity_remaining})"
                )

        return data

    @transaction.atomic
    def create(self, validated_data):
        from produits_stocks.models import Stock, StockMovement
        from django.db import transaction

        lines_data = validated_data.pop('lines')
        purchase_order = validated_data.get('purchase_order')
        warehouse = validated_data.get('warehouse')
        user = self.context['request'].user

        # Générer le numéro de réception
        last_receipt = Receipt.objects.order_by('-id').first()
        num = 1
        if last_receipt and last_receipt.receipt_number:
            try:
                num = int(last_receipt.receipt_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        receipt_number = f"REC-{date.today().year}-{num:04d}"

        # Créer la réception
        receipt = Receipt.objects.create(
            receipt_number=receipt_number,
            status='in_progress',
            **validated_data
        )

        # Traiter chaque ligne de réception
        for line_data in lines_data:
            po_line = line_data['po_line']
            quantity_received = line_data['quantity_received']
            quantity_damaged = line_data.get('quantity_damaged', 0)
            lot_number = line_data.get('lot_number', '').strip()
            expiry_date = line_data.get('expiry_date')
            manufacturing_date = line_data.get('manufacturing_date')
            quality_status = line_data.get('quality_status', 'pending')
            notes = line_data.get('notes', '')

            product = po_line.product
            lot = None

            # Gestion du lot
            if lot_number:
                # Vérifier si le lot existe déjà
                existing_lot = Lot.objects.filter(
                    lot_number=lot_number).first()

                if existing_lot:
                    # Lot existant - on ajoute la quantité
                    lot = existing_lot
                    # Si le lot n'a pas d'entrepôt ou est différent, on met à jour
                    if not lot.warehouse:
                        lot.warehouse = warehouse
                    # Ajouter la quantité reçue
                    lot.current_quantity += quantity_received
                    # Mettre à jour les dates si elles ne sont pas définies
                    if expiry_date and not lot.expiry_date:
                        lot.expiry_date = expiry_date
                    if manufacturing_date and not lot.manufacturing_date:
                        lot.manufacturing_date = manufacturing_date
                    lot.save()
                else:
                    # Créer un nouveau lot
                    lot = Lot.objects.create(
                        lot_number=lot_number,
                        product=product,
                        warehouse=warehouse,
                        initial_quantity=quantity_received,
                        current_quantity=quantity_received,
                        purchase_price=po_line.unit_price,
                        selling_price=product.selling_price,
                        created_by=user,
                        expiry_date=expiry_date,
                        manufacturing_date=manufacturing_date,
                        status='good'
                    )
            else:
                # Si pas de numéro de lot, on crée un lot automatiquement
                auto_lot_number = f"LOT-{product.code}-{date.today().strftime('%Y%m%d')}-{ReceiptLine.objects.filter(product=product).count() + 1}"
                lot = Lot.objects.create(
                    lot_number=auto_lot_number,
                    product=product,
                    warehouse=warehouse,
                    initial_quantity=quantity_received,
                    current_quantity=quantity_received,
                    purchase_price=po_line.unit_price,
                    selling_price=product.selling_price,
                    created_by=user,
                    expiry_date=expiry_date,
                    manufacturing_date=manufacturing_date,
                    status='good'
                )

            # Créer la ligne de réception
            ReceiptLine.objects.create(
                receipt=receipt,
                po_line=po_line,
                product=product,
                quantity_ordered=po_line.quantity,
                quantity_received=quantity_received,
                quantity_damaged=quantity_damaged,
                lot=lot,
                lot_number=lot_number if lot_number else auto_lot_number,
                expiry_date=expiry_date,
                manufacturing_date=manufacturing_date,
                quality_status=quality_status,
                notes=notes
            )

            # --- CORRECTION : MISE À JOUR DU STOCK ---
            # 1. Récupérer ou créer le stock pour ce produit dans cet entrepôt
            stock, created = Stock.objects.get_or_create(
                product=product,
                warehouse=warehouse,
                defaults={
                    'quantity': 0,
                    'reserved_quantity': 0
                }
            )

            # 2. IMPORTANT : Recalculer la quantité totale à partir des lots
            # Cela évite le double comptage car on ne fait PAS d'addition manuelle
            stock.update_quantity()

            # 3. Créer le mouvement de stock
            StockMovement.objects.create(
                product=product,
                lot=lot,
                to_warehouse=warehouse,
                movement_type='purchase_in',
                quantity=quantity_received,
                reference_type='purchase_order',
                reference_id=purchase_order.id,
                reference_number=purchase_order.po_number,
                reason=f"Réception commande {purchase_order.po_number}",
                created_by=user,
                notes=f"Réception n°{receipt_number}"
            )

        # Mettre à jour le statut de la commande
        total_ordered = purchase_order.lines.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        total_received = purchase_order.lines.aggregate(
            total=Sum('quantity_received')
        )['total'] or 0

        if total_received >= total_ordered:
            purchase_order.status = 'received'
        elif total_received > 0:
            purchase_order.status = 'partial'
        purchase_order.save()

        # Terminer la réception
        receipt.status = 'completed'
        receipt.save()

        # Générer le QR Code après la création
        receipt.generate_qr_code()
        receipt.save()

        return receipt

# ==================== PURCHASE RETURN ====================


class PurchaseReturnLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True)

    class Meta:
        model = PurchaseReturnLine
        fields = ['id', 'receipt_line', 'product', 'product_name',
                  'product_code', 'quantity', 'unit_price', 'total']
        read_only_fields = ['total']


class PurchaseReturnSerializer(serializers.ModelSerializer):
    po_number = serializers.CharField(
        source='purchase_order.po_number', read_only=True)
    supplier_name = serializers.CharField(
        source='purchase_order.supplier.name', read_only=True)
    supplier_code = serializers.CharField(
        source='purchase_order.supplier.code', read_only=True)
    receipt_number = serializers.CharField(
        source='receipt.receipt_number', read_only=True)
    lines = PurchaseReturnLineSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    reason_display = serializers.CharField(
        source='get_reason_display', read_only=True)
    created_by_name = serializers.CharField(
        source='created_by.full_name', read_only=True)

    # QR Code fields
    qr_code = serializers.ImageField(read_only=True)
    qr_code_data = serializers.CharField(read_only=True)
    qr_code_url = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseReturn
        fields = [
            'id', 'return_number', 'purchase_order', 'po_number', 'supplier_name',
            'supplier_code', 'receipt', 'receipt_number', 'return_date', 'reason',
            'reason_display', 'status', 'status_display', 'notes', 'lines',
            'created_by', 'created_by_name',
            'qr_code', 'qr_code_data', 'qr_code_url'
        ]
        read_only_fields = ['id', 'return_number',
                            'return_date', 'qr_code', 'qr_code_data']

    def get_qr_code_url(self, obj):
        if obj.qr_code:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.qr_code.url)
            return obj.qr_code.url
        return None


class PurchaseReturnCreateSerializer(serializers.ModelSerializer):
    lines = serializers.ListField(
        child=serializers.DictField(), write_only=True)

    class Meta:
        model = PurchaseReturn
        fields = ['purchase_order', 'receipt', 'reason', 'notes', 'lines']

    def validate(self, data):
        purchase_order = data.get('purchase_order')
        receipt = data.get('receipt')

        if receipt and receipt.purchase_order != purchase_order:
            raise serializers.ValidationError(
                "La réception ne correspond pas à la commande")

        lines_data = data.get('lines', [])
        if not lines_data or all(line.get('quantity', 0) <= 0 for line in lines_data):
            raise serializers.ValidationError(
                {"lines": "Au moins un produit doit être retourné"})

        for line_data in lines_data:
            receipt_line_id = line_data.get('receipt_line')
            quantity = line_data.get('quantity', 0)

            if quantity <= 0:
                continue

            try:
                receipt_line = ReceiptLine.objects.get(id=receipt_line_id)
                if quantity > receipt_line.quantity_received:
                    raise serializers.ValidationError(
                        f"Quantité retournée ({quantity}) dépasse la quantité reçue ({receipt_line.quantity_received})"
                    )
            except ReceiptLine.DoesNotExist:
                raise serializers.ValidationError(
                    f"Ligne de réception {receipt_line_id} non trouvée")

        return data

    @transaction.atomic
    def create(self, validated_data):
        lines_data = validated_data.pop('lines')
        purchase_order = validated_data.get('purchase_order')
        receipt = validated_data.get('receipt')

        last_return = PurchaseReturn.objects.order_by('-id').first()
        num = 1
        if last_return and last_return.return_number:
            try:
                num = int(last_return.return_number.split('-')[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        return_number = f"RET-{date.today().year}-{num:04d}"

        purchase_return = PurchaseReturn.objects.create(
            return_number=return_number,
            purchase_order=purchase_order,
            receipt=receipt,
            reason=validated_data.get('reason'),
            notes=validated_data.get('notes', ''),
            created_by=self.context['request'].user
        )

        for line_data in lines_data:
            quantity = line_data.get('quantity', 0)
            if quantity <= 0:
                continue

            receipt_line_id = line_data.get('receipt_line')
            receipt_line = ReceiptLine.objects.get(id=receipt_line_id)
            product = receipt_line.product

            PurchaseReturnLine.objects.create(
                purchase_return=purchase_return,
                receipt_line=receipt_line,
                product=product,
                quantity=quantity,
                unit_price=receipt_line.po_line.unit_price
            )

            if receipt_line.lot:
                receipt_line.lot.current_quantity -= quantity
                receipt_line.lot.save()

                StockMovement.objects.create(
                    product=product,
                    lot=receipt_line.lot,
                    from_warehouse=receipt_line.lot.warehouse,
                    movement_type='return_out',
                    quantity=quantity,
                    reference_type='purchase_return',
                    reference_id=purchase_return.id,
                    reference_number=return_number,
                    reason=f"Retour fournisseur - {purchase_return.get_reason_display()}",
                    created_by=self.context['request'].user
                )

            receipt_line.quantity_received -= quantity
            receipt_line.save()

        # Générer le QR Code après la création
        purchase_return.generate_qr_code()
        purchase_return.save()

        return purchase_return


# ==================== SUPPLIER INVOICE ====================
class SupplierInvoiceSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source='supplier.name', read_only=True)
    po_number = serializers.CharField(
        source='purchase_order.po_number', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)
    remaining_amount = serializers.ReadOnlyField()

    class Meta:
        model = SupplierInvoice
        fields = [
            'id', 'invoice_number', 'purchase_order', 'po_number', 'supplier',
            'supplier_name', 'invoice_date', 'due_date', 'amount', 'tax_amount',
            'total_amount', 'amount_paid', 'remaining_amount', 'status',
            'status_display', 'payment_date', 'payment_reference', 'notes'
        ]
        read_only_fields = ['id', 'amount_paid']


class SupplierInvoiceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierInvoice
        fields = [
            'invoice_number', 'purchase_order', 'invoice_date', 'due_date',
            'amount', 'tax_amount', 'total_amount', 'notes'
        ]

    def validate_invoice_number(self, value):
        if SupplierInvoice.objects.filter(invoice_number=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de facture existe déjà")
        return value


class SupplierInvoicePaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_date = serializers.DateField()
    payment_reference = serializers.CharField(required=False, allow_blank=True)

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Le montant doit être supérieur à 0")
        return value


# ==================== QR CODE SERIALIZER ====================
class QRCodeSerializer(serializers.Serializer):
    """Serializer pour générer des QR Codes"""
    type = serializers.CharField()
    id = serializers.IntegerField()
    number = serializers.CharField()
    data = serializers.JSONField()

    class Meta:
        fields = ['type', 'id', 'number', 'data']
