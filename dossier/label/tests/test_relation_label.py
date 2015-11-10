'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import

from pyquchk import qc

from dossier.label import RelationLabel
from dossier.label.tests import id_, time_value, relation_type


@qc
def test_label_reverse_equality(cid1=id_, cid2=id_, ann=id_, v=relation_type,
                                t=time_value):
    l1 = RelationLabel(cid1, cid2, ann, v, epoch_ticks=t)
    l2 = RelationLabel(cid2, cid1, ann, v, epoch_ticks=t)
    assert l1 == l2
    assert hash(l1) == hash(l2)

@qc
def test_content_id_order(cid1=id_, cid2=id_, ann=id_, v=relation_type):
    l = RelationLabel(cid1, cid2, ann, v)
    assert cid1 in l
    assert cid2 in l
    assert l.content_id1 <= l.content_id2
    assert l.content_id1 == min(cid1, cid2)
    assert l.content_id2 == max(cid1, cid2)

@qc
def test_label_order_on_value(cid1=id_, cid2=id_, ann=id_,
                              t=time_value, v1=relation_type,
                              v2=relation_type):
    lab1 = RelationLabel(cid1, cid2, ann, v1, epoch_ticks=t)
    lab2 = RelationLabel(cid1, cid2, ann, v2, epoch_ticks=t)
    assert ((v1 < v2 and lab1 < lab2) or
            (v1 == v2 and lab1 == lab2) or
            (v1 > v2 and lab1 > lab2))
