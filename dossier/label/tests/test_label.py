'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import, division, print_function

from pyquchk import qc

from dossier.label import CorefValue, Label
from dossier.label.tests import coref_value, id_, time_value


@qc
def test_label_reverse_equality(cid1=id_, cid2=id_, ann=id_, v=coref_value,
                                t=time_value):
    l1 = Label(cid1, cid2, ann, v, epoch_ticks=t)
    l2 = Label(cid2, cid1, ann, v, epoch_ticks=t)
    assert l1 == l2
    assert hash(l1) == hash(l2)


@qc
def test_content_id_order(cid1=id_, cid2=id_, ann=id_, v=coref_value):
    l = Label(cid1, cid2, ann, v)
    assert cid1 in l
    assert cid2 in l
    assert l.content_id1 <= l.content_id2
    assert l.content_id1 == min(cid1, cid2)
    assert l.content_id2 == max(cid1, cid2)


@qc
def test_subtopic_order(cid=id_, s1=id_, s2=id_, ann=id_, v=coref_value):
    l = Label(cid, cid, ann, v, subtopic_id1=s1, subtopic_id2=s2)
    assert cid in l
    assert (cid, s1) in l
    assert (cid, s2) in l
    assert l.content_id1 == cid
    assert l.content_id2 == cid
    assert l.subtopic_id1 <= l.subtopic_id2
    assert l.subtopic_id1 == min(s1, s2)
    assert l.subtopic_id2 == max(s1, s2)


@qc
def test_subtopic_id(cid1=id_, cid2=id_, s1=id_, s2=id_, ann=id_,
                     v=coref_value):
    l = Label(cid1, cid2, ann, v, subtopic_id1=s1, subtopic_id2=s2)
    assert cid1 in l
    assert (cid1, None) in l
    assert (cid1, s1) in l
    assert cid2 in l
    assert (cid2, None) in l
    assert (cid2, s2) in l
    assert l.other(cid1) == cid2
    assert l.other(cid2) == cid1
    if cid1 != cid2:
        assert l.subtopic_for(cid1) == s1
        assert l.subtopic_for(cid2) == s2
    else:
        assert l.subtopic_for(cid1) == min(s1, s2)


@qc
def test_same_subject(cid1=id_, cid2=id_, s1=id_, s2=id_, ann=id_,
                      v1=coref_value, v2=coref_value,
                      t1=time_value, t2=time_value):
    l1 = Label(cid1, cid2, ann, v1, epoch_ticks=t1,
               subtopic_id1=s1, subtopic_id2=s2)
    l2 = Label(cid1, cid2, ann, v2, epoch_ticks=t2,
               subtopic_id1=s1, subtopic_id2=s2)
    assert l1.same_subject_as(l2)
    assert l2.same_subject_as(l1)


@qc
def test_label_most_recent_first(cid1=id_, cid2=id_, ann=id_,
                                 v1=coref_value, v2=coref_value,
                                 t=time_value):
    lab1 = Label(cid1, cid2, ann, v1, epoch_ticks=t)
    lab2 = Label(cid1, cid2, ann, v2, epoch_ticks=t + 1)
    assert lab2 < lab1
    assert not (lab1 == lab2)
    assert sorted([lab1, lab2]) == [lab2, lab1]
    assert list(Label.most_recent([lab2, lab1])) == [lab2]


@qc
def test_label_most_recent_first_unordered(cid1=id_, cid2=id_, ann=id_,
                                           v1=coref_value, v2=coref_value,
                                           t=time_value):
    lab1 = Label(cid1, cid2, ann, v1, epoch_ticks=t)
    lab2 = Label(cid2, cid1, ann, v2, epoch_ticks=t + 1)
    assert lab2 < lab1
    assert not (lab1 == lab2)
    assert sorted([lab1, lab2]) == [lab2, lab1]
    assert list(Label.most_recent([lab2, lab1])) == [lab2]


@qc
def test_label_order_on_value(cid1=id_, cid2=id_, ann=id_, t=time_value,
                              v1=coref_value, v2=coref_value):
    lab1 = Label(cid1, cid2, ann, v1, epoch_ticks=t)
    lab2 = Label(cid1, cid2, ann, v2, epoch_ticks=t)
    assert ((v1 < v2 and lab1 < lab2) or
            (v1 == v2 and lab1 == lab2) or
            (v1 > v2 and lab1 > lab2))


def label(id1, id2, v=CorefValue.Positive, sid1=None, sid2=None):
    return Label(id1, id2, 'foo', v, subtopic_id1=sid1, subtopic_id2=sid2)


def diff_labels_sets(old, new):
    diff = Label.diff(old, new)
    return {
        'add': set(diff['add']),
        'delete': set(diff['delete']),
        'change': set(diff['change']),
    }

def test_label_diff_simple():
    old = [label('a', 'b'), label('a', 'c')]
    new = [label('a', 'b'), label('a', 'd')]
    assert diff_labels_sets(old, new) == {
        'add': {label('a', 'd')},
        'delete': {label('a', 'c')},
        'change': set(),
    }


def test_label_diff_change():
    old = [label('a', 'b')]
    new = [label('a', 'b', v=CorefValue.Negative)]
    assert diff_labels_sets(old, new) == {
        'add': set(),
        'delete': set(),
        'change': {label('a', 'b', v=CorefValue.Negative)},
    }


def test_label_diff_empty():
    old = [Label('a', 'b', 'foo', 1, epoch_ticks=0)]
    new = [Label('a', 'b', 'foo', 1, epoch_ticks=1)]
    assert old != new
    assert diff_labels_sets(old, new) == {
        'add': set(),
        'delete': set(),
        'change': set(),
    }


def test_label_diff_simple_change():
    old = [label('a', 'b'), label('a', 'c')]
    new = [label('a', 'b', v=CorefValue.Negative), label('a', 'd')]
    assert diff_labels_sets(old, new) == {
        'add': {label('a', 'd')},
        'delete': {label('a', 'c')},
        'change': {label('a', 'b', v=CorefValue.Negative)},
    }
