from django.db import connection, models
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import (
    Avatar, Parent, RequiredFieldsChild, RequiredFieldsInheritedChild,
    RequiredFieldsLeaf,
)


class RequiredFieldsDeletionTests(TestCase):
    def create_cascade(self):
        avatar = Avatar.objects.create(desc='parent')
        child = RequiredFieldsChild.objects.create(
            avatar=avatar, code='child-code', payload='unneeded payload',
        )
        RequiredFieldsLeaf.objects.create(child=child)
        return avatar

    def child_select(self, queries):
        table = connection.ops.quote_name(RequiredFieldsChild._meta.db_table)
        selects = [
            query['sql'] for query in queries
            if query['sql'].lstrip().upper().startswith('SELECT')
            and 'FROM %s' % table in query['sql']
        ]
        self.assertEqual(len(selects), 1, selects)
        return selects[0].split(' FROM ', 1)[0]

    def test_cascade_omits_unrequired_column(self):
        avatar = self.create_cascade()
        self.assertFalse(models.signals.pre_delete.has_listeners(RequiredFieldsChild))
        self.assertFalse(models.signals.post_delete.has_listeners(RequiredFieldsChild))
        with CaptureQueriesContext(connection) as queries:
            avatar.delete()
        self.assertNotIn(connection.ops.quote_name('payload'), self.child_select(queries))

    def test_delete_listeners_keep_all_columns(self):
        for signal in (models.signals.pre_delete, models.signals.post_delete):
            with self.subTest(signal=signal):
                avatar = self.create_cascade()
                seen = []

                def receiver(sender, instance, **kwargs):
                    seen.append((instance.get_deferred_fields(), instance.payload))

                signal.connect(receiver, sender=RequiredFieldsChild)
                try:
                    with CaptureQueriesContext(connection) as queries:
                        avatar.delete()
                finally:
                    signal.disconnect(receiver, sender=RequiredFieldsChild)
                select = self.child_select(queries)
                for field in RequiredFieldsChild._meta.concrete_fields:
                    self.assertIn(connection.ops.quote_name(field.column), select)
                self.assertEqual(seen, [(set(), 'unneeded payload')])

    def test_non_primary_key_multilevel_cascade(self):
        avatar = self.create_cascade()
        avatar.delete()
        self.assertFalse(Avatar.objects.exists())
        self.assertFalse(RequiredFieldsChild.objects.exists())
        self.assertFalse(RequiredFieldsLeaf.objects.exists())

    def test_multitable_cascade_queries(self):
        parent = Parent.objects.create()
        RequiredFieldsInheritedChild.objects.create(parent=parent, desc='inherited')
        with CaptureQueriesContext(connection) as queries:
            parent.delete()
        selects = [
            query['sql'] for query in queries
            if query['sql'].lstrip().upper().startswith('SELECT')
        ]
        avatar_table = connection.ops.quote_name(Avatar._meta.db_table)
        parent_fetches = [sql for sql in selects if 'FROM %s' % avatar_table in sql]
        print('MTI cascade: %d queries; %d SELECTs; %d standalone parent fetches. SQL: %s' % (
            len(queries), len(selects), len(parent_fetches),
            [query['sql'] for query in queries],
        ))


        self.assertEqual(parent_fetches, [], selects)
        self.assertFalse(Parent.objects.exists())
        self.assertFalse(RequiredFieldsInheritedChild.objects.exists())
        self.assertFalse(Avatar.objects.exists())
