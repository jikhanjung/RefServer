"""Peewee migrations -- 005_20250619_173532.py.

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
    class ContentHash(pw.Model):
        content_hash = pw.CharField(max_length=255, primary_key=True)
        pdf_title = pw.CharField(max_length=255, null=True)
        pdf_author = pw.CharField(max_length=255, null=True)
        pdf_creator = pw.CharField(max_length=255, null=True)
        first_three_pages_text = pw.TextField(null=True)
        page_count = pw.IntegerField()
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE')
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "contenthash"
            indexes = [(('page_count',), False)]

    @migrator.create_model
    class FileHash(pw.Model):
        file_md5 = pw.CharField(max_length=255, primary_key=True)
        file_size = pw.BigIntegerField()
        original_filename = pw.CharField(max_length=255)
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE')
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "filehash"
            indexes = [(('file_size',), False)]

    @migrator.create_model
    class SampleEmbeddingHash(pw.Model):
        embedding_hash = pw.CharField(max_length=255, primary_key=True)
        sample_strategy = pw.CharField(max_length=255)
        sample_text = pw.TextField(null=True)
        embedding_vector = pw.BlobField()
        vector_dim = pw.IntegerField()
        model_name = pw.CharField(default='bge-m3', max_length=255)
        paper = pw.ForeignKeyField(column_name='paper_id', field='doc_id', model=migrator.orm['paper'], on_delete='CASCADE')
        created_at = pw.DateTimeField()

        class Meta:
            table_name = "sampleembeddinghash"
            indexes = [(('sample_strategy',), False)]


def rollback(migrator: Migrator, database: pw.Database, *, fake=False):
    """Write your rollback migrations here."""
    
    migrator.remove_model('sampleembeddinghash')

    migrator.remove_model('filehash')

    migrator.remove_model('contenthash')
