"""Peewee migrations -- 001_20250617_162708.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['table_name']            # Return model in current state by name
    > Model = migrator.ModelClass                   # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.run(func, *args, **kwargs)           # Run python function with the given args
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.add_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)
    > migrator.add_constraint(model, name, sql)
    > migrator.drop_index(model, *col_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.drop_constraints(model, *constraints)

"""

from contextlib import suppress

import peewee as pw
from peewee_migrate import Migrator


with suppress(ImportError):
    import playhouse.postgres_ext as pw_pext


def migrate(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your migrations here."""
    
    @migrator.create_model
    class Paper(pw.Model):
        doc_id = pw.CharField(max_length=255, primary_key=True)
        content_id = pw.CharField(max_length=255, null=True, unique=True)
        filename = pw.CharField(max_length=255)
        file_path = pw.CharField(max_length=255)
        ocr_text = pw.TextField(null=True)
        ocr_quality = pw.CharField(max_length=255, null=True)
        created_at = pw.DateTimeField()
        updated_at = pw.DateTimeField()

        class Meta:
            table_name = "paper"
            indexes = [(('content_id',), False)]

    @migrator.create_model
    class Embedding(pw.Model):
        id = pw.AutoField()
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE')
        vector_blob = pw.BlobField()
        vector_dim = pw.IntegerField()
        model_name = pw.CharField(default='bge-m3', max_length=255)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "embedding"

    @migrator.create_model
    class LayoutAnalysis(pw.Model):
        id = pw.AutoField()
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE', unique=True)
        layout_json = pw.TextField()
        page_count = pw.IntegerField()
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "layoutanalysis"

    @migrator.create_model
    class Metadata(pw.Model):
        id = pw.AutoField()
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE', unique=True)
        title = pw.CharField(max_length=255, null=True)
        authors = pw.TextField(null=True)
        journal = pw.CharField(max_length=255, null=True)
        year = pw.IntegerField(null=True)
        doi = pw.CharField(max_length=255, null=True)
        abstract = pw.TextField(null=True)
        keywords = pw.TextField(null=True)
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "metadata"


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.remove_model('metadata')

    migrator.remove_model('layoutanalysis')

    migrator.remove_model('embedding')

    migrator.remove_model('paper')
