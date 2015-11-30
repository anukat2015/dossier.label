'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import

import pytest

from dossier.label.label import LabelStore, Label
from dossier.label.relation_label import RelationLabelStore, \
    RelationLabel, RelationStrength
from dossier.label.combined_store import CombinedLabelStore
from dossier.label.tests import kvl


@pytest.yield_fixture
def combined_label_store(kvl):
    store = CombinedLabelStore(kvl)
    yield store
    store.label_store.delete_all()
    store.rel_label_store.delete_all()


def test_relationship_graph(combined_label_store):
    entities = ['A', 'B', 'C', 'D', 'E', 'F']

    for ent in entities:
        coref_ents = [ent+str(i) for i in xrange(3)]
        for coref_ent in coref_ents:
            label = Label(ent, coref_ent, 'foo', 1)
            combined_label_store.label_store.put(label)

    rl1 = RelationLabel('A', 'B', 'foo', RelationStrength.STRONG)
    rl2 = RelationLabel('A', 'C', 'foo', RelationStrength.WEAK)
    rl3 = RelationLabel('A', 'D', 'foo', RelationStrength.NONE)
    rl4 = RelationLabel('A', 'E', 'foo', RelationStrength.AKA)
    rl5 = RelationLabel('A', 'F', 'foo', RelationStrength.NONE)
    combined_label_store.rel_label_store.put(
        rl1, rl2, rl3, rl4, rl5)

    cid_to_related = combined_label_store.get_related_coref_relationships('A')
    assert frozenset(cid_to_related['C']) == frozenset(['C0', 'C1', 'C2'])
    assert frozenset(cid_to_related['B']) == frozenset(['B0', 'B1', 'B2'])
    assert frozenset(cid_to_related['E']) == frozenset(['E0', 'E1', 'E2'])
