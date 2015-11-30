'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import

from pyquchk import qc
import pytest
import struct

from dossier.label import RelationLabel, RelationLabelStore, RelationStrength
from dossier.label.tests import kvl, relation_type, time_value, id_


@pytest.yield_fixture
def rel_label_store(kvl):
    lstore = RelationLabelStore(kvl)
    yield lstore
    lstore.delete_all()


def test_get_related(rel_label_store):
    l1 = RelationLabel('A', 'B', 'foo', RelationStrength.NONE)
    l2 = RelationLabel('A', 'C', 'foo', RelationStrength.UNKNOWN)
    l3 = RelationLabel('A', 'D', 'foo', RelationStrength.AKA)
    l4 = RelationLabel('A', 'E', 'foo', RelationStrength.WEAK)
    l5 = RelationLabel('A', 'F', 'foo', RelationStrength.STRONG)
    rel_label_store.put(l1, l2, l3, l4, l5)

    related = frozenset(rel_label_store.get_related('A'))
    assert related == frozenset([l3, l4, l5])

    strong_related = frozenset(rel_label_store.get_related(
        'A', min_strength=RelationStrength.STRONG))
    assert strong_related == frozenset([l3, l5])


def test_put_get(rel_label_store):
    l1 = RelationLabel('A', 'B', 'foo', RelationStrength.NONE)
    l2 = RelationLabel('A', 'B', 'foo', RelationStrength.AKA)
    rel_label_store.put(l1)
    rel_label_store.put(l2)
    l3 = rel_label_store.get('A', 'B', 'foo')

    # Only want latest label.
    assert l3 == l2
    assert l3 != l1


def test_get_relationships_for_idents(rel_label_store):
    l1 = RelationLabel('A', 'B1', 'foo', RelationStrength.NONE)
    l2 = RelationLabel('A', 'B2', 'foo', RelationStrength.UNKNOWN)
    l3 = RelationLabel('A', 'B3', 'foo', RelationStrength.AKA)
    l4 = RelationLabel('A', 'B4', 'foo', RelationStrength.WEAK)
    l5 = RelationLabel('A', 'B5', 'foo', RelationStrength.STRONG)

    rel_label_store.put(l1, l2, l3, l4, l5)

    idents = ['B1', 'B2', 'B3', 'B4', 'B5', 'C1', 'D1']

    relations = rel_label_store.get_relationships_for_idents('A', idents)

    assert relations['B1'] == RelationStrength.NONE
    assert relations['B2'] == RelationStrength.UNKNOWN
    assert relations['B3'] == RelationStrength.AKA
    assert relations['B4'] == RelationStrength.WEAK
    assert relations['B5'] == RelationStrength.STRONG

    assert 'C1' not in relations
    assert 'D1' not in relations
