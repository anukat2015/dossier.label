'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import

from pyquchk import qc
import pytest
import struct

from dossier.label import RelationLabel, RelationLabelStore, RelationType
from dossier.label.tests import kvl, relation_type, time_value, id_


@pytest.yield_fixture
def rel_label_store(kvl):
    lstore = RelationLabelStore(kvl)
    yield lstore
    lstore.delete_all()


def test_get_related(rel_label_store):
    l1 = RelationLabel('A', 'B', 'foo', RelationType.NONE)
    l2 = RelationLabel('A', 'C', 'foo', RelationType.UNKNOWN)
    l3 = RelationLabel('A', 'D', 'foo', RelationType.AKA)
    l4 = RelationLabel('A', 'E', 'foo', RelationType.WEAK)
    l5 = RelationLabel('A', 'F', 'foo', RelationType.STRONG)
    rel_label_store.put(l1, l2, l3, l4, l5)

    related = frozenset(rel_label_store.get_related('A'))
    assert related == frozenset([l3, l4, l5])

    strong_related = frozenset(rel_label_store.get_related(
        'A', min_strength=RelationType.STRONG))
    assert strong_related == frozenset([l3, l5])


def test_put_get(rel_label_store):
    l1 = RelationLabel('A', 'B', 'foo', RelationType.NONE)
    l2 = RelationLabel('A', 'B', 'foo', RelationType.AKA)
    rel_label_store.put(l1)
    rel_label_store.put(l2)
    l3 = rel_label_store.get('A', 'B', 'foo')

    # Only want latest label.
    assert l3 == l2
    assert l3 != l1


def test_get_relationships_for_idents(rel_label_store):
    l1 = RelationLabel('A', 'B1', 'foo', RelationType.NONE)
    l2 = RelationLabel('A', 'B2', 'foo', RelationType.UNKNOWN)
    l3 = RelationLabel('A', 'B3', 'foo', RelationType.AKA)
    l4 = RelationLabel('A', 'B4', 'foo', RelationType.WEAK)
    l5 = RelationLabel('A', 'B5', 'foo', RelationType.STRONG)

    rel_label_store.put(l1, l2, l3, l4, l5)

    idents = ['B1', 'B2', 'B3', 'B4', 'B5', 'C1', 'D1']

    relations = rel_label_store.get_relationships_for_idents('A', idents)

    assert relations['B1'] == RelationType.NONE
    assert relations['B2'] == RelationType.UNKNOWN
    assert relations['B3'] == RelationType.AKA
    assert relations['B4'] == RelationType.WEAK
    assert relations['B5'] == RelationType.STRONG

    assert 'C1' not in relations
    assert 'D1' not in relations
