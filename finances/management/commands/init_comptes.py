# apps/finances/management/commands/init_comptes.py
from django.core.management.base import BaseCommand
from datetime import date

from finances.models import CompteComptable, ConfigurationFinanciere, BudgetCategorie


PLAN_COMPTABLE = [
    # CLASSE 1 - Capitaux
    ('101', 'Capital social', 'capitaux', '1'),
    ('106', 'Réserves', 'capitaux', '1'),
    ('120', 'Résultat de l\'exercice', 'capitaux', '1'),
    ('164', 'Emprunts', 'passif', '1'),

    # CLASSE 2 - Immobilisations
    ('211', 'Terrains', 'actif', '2'),
    ('213', 'Constructions', 'actif', '2'),
    ('218', 'Matériel et outillage', 'actif', '2'),
    ('241', 'Matériel informatique', 'actif', '2'),

    # CLASSE 3 - Stocks
    ('311', 'Marchandises', 'actif', '3'),
    ('321', 'Matières premières', 'actif', '3'),

    # CLASSE 4 - Tiers
    ('401', 'Fournisseurs', 'passif', '4'),
    ('411', 'Clients', 'actif', '4'),
    ('419', 'Clients - Avances reçues', 'passif', '4'),
    ('421', 'Personnel - Rémunérations dues', 'passif', '4'),
    ('431', 'Sécurité sociale', 'passif', '4'),
    ('445', 'TVA', 'passif', '4'),
    ('447', 'Impôts et taxes', 'passif', '4'),

    # CLASSE 5 - Trésorerie
    ('521', 'Banque', 'actif', '5'),
    ('531', 'Caisse', 'actif', '5'),
    ('571', 'Régies d\'avances', 'actif', '5'),

    # CLASSE 6 - Charges
    ('601', 'Achats de marchandises', 'charges', '6'),
    ('606', 'Achats non stockés de matières et fournitures', 'charges', '6'),
    ('613', 'Locations', 'charges', '6'),
    ('615', 'Entretien et réparations', 'charges', '6'),
    ('616', 'Primes d\'assurance', 'charges', '6'),
    ('623', 'Publicité, publications, relations publiques', 'charges', '6'),
    ('625', 'Déplacements, missions et réceptions', 'charges', '6'),
    ('627', 'Services bancaires et assimilés', 'charges', '6'),
    ('628', 'Frais divers de gestion courante', 'charges', '6'),
    ('631', 'Impôts, taxes et versements assimilés', 'charges', '6'),
    ('641', 'Rémunérations du personnel', 'charges', '6'),
    ('658', 'Charges diverses', 'charges', '6'),
    ('661', 'Charges d\'intérêts', 'charges', '6'),

    # CLASSE 7 - Produits
    ('701', 'Ventes de marchandises', 'produits', '7'),
    ('706', 'Services vendus', 'produits', '7'),
    ('707', 'Produits accessoires', 'produits', '7'),
    ('709', 'Rabais, remises, ristournes accordés', 'charges', '7'),
    ('771', 'Produits exceptionnels', 'produits', '7'),
]


BUDGET_CATEGORIES = [
    ('FOURN', 'Fournitures de bureau', 'fournitures'),
    ('UTIL', 'Services publics', 'utilities'),
    ('LOYER', 'Loyer', 'loyer'),
    ('SALAI', 'Salaires', 'salaires'),
    ('MARK', 'Marketing et publicité', 'marketing'),
    ('TRANS', 'Transport et déplacements', 'transport'),
    ('MAINT', 'Maintenance et réparation', 'maintenance'),
    ('FORMA', 'Formation', 'formation'),
    ('INFO', 'Informatique', 'informatique'),
    ('TELE', 'Télécommunication', 'telecommunication'),
    ('FBANQ', 'Frais bancaires', 'frais_bancaires'),
    ('IMPOT', 'Impôts et taxes', 'impots'),
    ('ASSUR', 'Assurance', 'assurance'),
    ('FPRO', 'Frais professionnels', 'frais_professionnels'),
    ('ASTOCK', 'Achat de stock', 'achat_stock'),
    ('AUTRE', 'Autre', 'autre'),
]


class Command(BaseCommand):
    help = 'Initialise le plan comptable, la config financière et les catégories de budget'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Réinitialiser la configuration existante'
        )

    def handle(self, *args, **options):
        # ==========================================================
        # 1. PLAN COMPTABLE
        # ==========================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            "\n🔧 Initialisation du plan comptable...\n"
        ))

        created = 0
        existing = 0

        for numero, nom, type_compte, classe in PLAN_COMPTABLE:
            obj, was_created = CompteComptable.objects.get_or_create(
                numero=numero,
                defaults={
                    'nom': nom,
                    'nom_complet': f"{numero} - {nom}",
                    'type': type_compte,
                    'classe': classe,
                    'is_active': True,
                }
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  ✅ {numero} - {nom}"))
            else:
                existing += 1

        self.stdout.write(
            f"\n  📊 {created} compte(s) créé(s), {existing} déjà présent(s)\n"
        )

        # ==========================================================
        # 2. CATÉGORIES DE BUDGET (liées aux dépenses)
        # ==========================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            "📁 Création des catégories de budget (liées aux dépenses)...\n"
        ))

        cat_created = 0
        cat_existing = 0

        for code, nom, categorie_depense in BUDGET_CATEGORIES:
            obj, was_created = BudgetCategorie.objects.get_or_create(
                code=code,
                defaults={
                    'nom': nom,
                    'categorie_depense': categorie_depense,
                    'is_active': True,
                }
            )
            if was_created:
                cat_created += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  ✅ {code} - {nom} → {categorie_depense}"
                ))
            else:
                # Mettre à jour le lien si absent
                if not obj.categorie_depense:
                    obj.categorie_depense = categorie_depense
                    obj.save(update_fields=['categorie_depense'])
                    self.stdout.write(
                        f"  🔄 {code} - {nom} → {categorie_depense} (lien ajouté)"
                    )
                else:
                    cat_existing += 1

        self.stdout.write(
            f"\n  📊 {cat_created} catégorie(s) créée(s), "
            f"{cat_existing} déjà présente(s)\n"
        )

        # ==========================================================
        # 3. CONFIGURATION FINANCIÈRE
        # ==========================================================
        self.stdout.write(self.style.MIGRATE_HEADING(
            "⚙️  Configuration financière...\n"
        ))

        config = ConfigurationFinanciere.objects.first()
        if not config or options['reset']:
            if config and options['reset']:
                config.delete()
            config = ConfigurationFinanciere.objects.create(
                devise='XOF',
                devise_symbole='FCFA',
                exercice_debut=date(date.today().year, 1, 1),
                exercice_fin=date(date.today().year, 12, 31),
                taxe_default=18,
                auto_validation=True,
                budget_alerte=80,
                arrondi=0
            )
            self.stdout.write(self.style.SUCCESS(
                "  ✅ Configuration financière créée"
            ))
        else:
            self.stdout.write(
                "  ℹ️  Configuration financière existante"
            )

        # ==========================================================
        # RÉSUMÉ
        # ==========================================================
        self.stdout.write(self.style.SUCCESS(
            "\n" + "=" * 60
        ))
        self.stdout.write(self.style.SUCCESS(
            "✅ INITIALISATION TERMINÉE"
        ))
        self.stdout.write(self.style.SUCCESS(
            "=" * 60 + "\n"
        ))
