'''dossier.label.tests

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''
from __future__ import absolute_import, division, print_function

from pyquchk import qc
import pytest

from dossier.label import Label, LabelStore
from dossier.label.tests import kvl, coref_value, time_value, id_  # noqa


@pytest.yield_fixture  # noqa
def label_store(kvl):
    lstore = LabelStore(kvl)
    yield lstore
    lstore.delete_all()


def test_no_prefix(label_store):
    foo_bar = Label('Foo', 'Bar', '', 1)
    foobaz_bar = Label('Foo Baz', 'Bar', '', 1)

    label_store.put(foo_bar)
    label_store.put(foobaz_bar)

    direct = list(label_store.directly_connected('Foo'))
    assert direct == [foo_bar]


def test_no_prefix_subtopic(label_store):
    foo_bar = Label('Foo', 'Bar', '', 1, 'Foo', 'Bar')
    foobaz_bar = Label('Foo Baz', 'Bar', '', 1, 'Foo Baz', 'Bar')

    label_store.put(foo_bar)
    label_store.put(foobaz_bar)

    direct = list(label_store.directly_connected(('Foo', 'Foo')))
    assert direct == [foo_bar]


def test_put_get(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v=coref_value):
        label_store.delete_all()

        lab = Label(cid1, cid2, ann, v)
        label_store.put(lab)
        got = label_store.get(cid1, cid2, ann)
        assert lab == got and lab.value == got.value
    _()


def test_put_get_unordered(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v=coref_value):
        label_store.delete_all()

        lab = Label(cid1, cid2, ann, v)
        label_store.put(lab)
        got = label_store.get(cid2, cid1, ann)
        assert lab == got and lab.value == got.value
    _()


def test_put_get_recent(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v1=coref_value, v2=coref_value):
        label_store.delete_all()

        lab1 = Label(cid1, cid2, ann, v1)
        lab2 = Label(cid1, cid2, ann, v2, epoch_ticks=lab1.epoch_ticks + 1)
        label_store.put(lab1)
        label_store.put(lab2)
        got = label_store.get(cid1, cid2, ann)
        assert got == lab2
        assert got != lab1
        assert got.value == lab2.value
    _()


def test_put_get_recent_unordered(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v1=coref_value, v2=coref_value):
        label_store.delete_all()

        lab1 = Label(cid1, cid2, ann, v1)
        lab2 = Label(cid2, cid1, ann, v2, epoch_ticks=lab1.epoch_ticks + 1)
        label_store.put(lab1)
        label_store.put(lab2)
        got = label_store.get(cid1, cid2, ann)
        assert got == lab2
        assert got != lab1
        assert got.value == lab2.value
    _()


def test_everything_simple(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v=coref_value):
        label_store.delete_all()
        l = Label(cid1, cid2, ann, v)
        label_store.put(l)
        assert list(label_store.everything()) == [l]
    _()


def test_everything_two(label_store):
    @qc
    def _(cid1a=id_, cid1b=id_, ann1=id_, v1=coref_value, t1=time_value,
          cid2a=id_, cid2b=id_, ann2=id_, v2=coref_value, t2=time_value):
        label_store.delete_all()
        l1 = Label(cid1a, cid1b, ann1, v1, epoch_ticks=t1)
        l2 = Label(cid2a, cid2b, ann2, v2, epoch_ticks=t2)
        label_store.put(l1)
        label_store.put(l2)
        if l1.same_subject_as(l2) and l1.epoch_ticks == l2.epoch_ticks:
            expected = [l2]
        else:
            expected = list(sorted([l1, l2]))
        assert (list(label_store.everything(include_deleted=True)) ==
                expected)
    _()


def test_everything_overwrite(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v=coref_value, t=time_value):
        label_store.delete_all()
        l1 = Label(cid1, cid2, ann, v, epoch_ticks=t)
        l2 = Label(cid1, cid2, ann, v, epoch_ticks=t+1)
        label_store.put(l1)
        label_store.put(l2)
        assert list(label_store.everything()) == [l2]
        assert list(label_store.everything(include_deleted=True)) == [l2, l1]
    _()


def test_everything_content_id(label_store):
    @qc
    def _(cid1a=id_, cid1b=id_, ann1=id_, v1=coref_value, t1=time_value,
          cid2a=id_, cid2b=id_, ann2=id_, v2=coref_value, t2=time_value):
        label_store.delete_all()
        l1 = Label(cid1a, cid1b, ann1, v1, epoch_ticks=t1)
        l2 = Label(cid2a, cid2b, ann2, v2, epoch_ticks=t2)
        label_store.put(l1)
        label_store.put(l2)
        if l1.same_subject_as(l2):
            if l1.epoch_ticks == l2.epoch_ticks:
                expected = [l2]
            else:
                expected = list(sorted([l1, l2]))[0:1]
        elif cid1a == cid2a or cid1a == cid2b:
            expected = list(sorted([l1, l2]))
        else:
            expected = [l1]
        assert (list(label_store.everything(content_id=cid1a)) == expected)
    _()


def test_everything_subtopic_id(label_store):
    @qc
    def _(cid1a=id_, cid1b=id_, sid1a=id_, sid1b=id_, ann1=id_,
          v1=coref_value, t1=time_value,
          cid2a=id_, cid2b=id_, sid2a=id_, sid2b=id_, ann2=id_,
          v2=coref_value, t2=time_value):
        label_store.delete_all()
        l1 = Label(cid1a, cid1b, ann1, v1, epoch_ticks=t1,
                   subtopic_id1=sid1a, subtopic_id2=sid1b)
        l2 = Label(cid2a, cid2b, ann2, v2, epoch_ticks=t2,
                   subtopic_id1=sid2a, subtopic_id2=sid2b)
        label_store.put(l1)
        label_store.put(l2)
        if l1.same_subject_as(l2):
            if l1.epoch_ticks == l2.epoch_ticks:
                expected = [l2]
            else:
                expected = list(sorted([l1, l2]))[0:1]
        elif ((cid1a == cid2a and sid1a == sid2a) or
              (cid1a == cid2b and sid1a == sid2b)):
            expected = list(sorted([l1, l2]))
        else:
            expected = [l1]
        assert (list(label_store.everything(content_id=cid1a,
                                            subtopic_id=sid1a)) == expected)
    _()


def test_direct_connect_recent(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v1=coref_value, v2=coref_value):
        label_store.delete_all()

        lab1 = Label(cid1, cid2, ann, v1)
        lab2 = Label(cid1, cid2, ann, v2, epoch_ticks=lab1.epoch_ticks + 1)
        label_store.put(lab1)
        label_store.put(lab2)

        assert list(label_store.directly_connected(cid1)) == [lab2]
        assert list(label_store.directly_connected(cid2)) == [lab2]
    _()


def test_direct_connect_recent_unordered(label_store):
    @qc
    def _(cid1=id_, cid2=id_, ann=id_, v1=coref_value, v2=coref_value):
        label_store.delete_all()

        lab1 = Label(cid1, cid2, ann, v1)
        lab2 = Label(cid2, cid1, ann, v2, epoch_ticks=lab1.epoch_ticks + 1)
        label_store.put(lab1)
        label_store.put(lab2)

        assert list(label_store.directly_connected(cid1)) == [lab2]
        assert list(label_store.directly_connected(cid2)) == [lab2]
    _()


def test_direct_connect(label_store):
    ab = Label('a', 'b', '', 1)
    ac = Label('a', 'c', '', 1)
    bc = Label('b', 'c', '', 1)
    label_store.put(ab)
    label_store.put(ac)
    label_store.put(bc)

    direct = list(label_store.directly_connected('a'))
    assert direct == [ab, ac]


def test_direct_connect_unordered(label_store):
    ab = Label('a', 'b', '', 1)
    ac = Label('c', 'a', '', 1)
    bc = Label('b', 'c', '', 1)
    label_store.put(ab)
    label_store.put(ac)
    label_store.put(bc)

    direct = list(label_store.directly_connected('a'))
    assert direct == [ab, ac]


def test_connected_component_basic(label_store):
    ab = Label('a', 'b', '', 1)
    ac = Label('a', 'c', '', 1)
    bc = Label('b', 'c', '', 1)
    label_store.put(ab)
    label_store.put(ac)
    label_store.put(bc)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, ac, bc])


def test_connected_component_unordered(label_store):
    ab = Label('a', 'b', '', 1)
    ac = Label('c', 'a', '', 1)
    bc = Label('b', 'c', '', 1)
    label_store.put(ab)
    label_store.put(ac)
    label_store.put(bc)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, ac, bc])


def test_connected_component_diff_value(label_store):
    ab = Label('a', 'b', '', 1)
    ac = Label('a', 'c', '', -1)
    bc = Label('b', 'c', '', 1)
    label_store.put(ab)
    label_store.put(ac)
    label_store.put(bc)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, bc])


def test_connected_component_many(label_store):
    ab = Label('a', 'b', '', 1)
    bc = Label('b', 'c', '', 1)
    cd = Label('c', 'd', '', 1)
    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, bc, cd])


def test_connected_component_many_diff_value(label_store):
    ab = Label('a', 'b', '', 1)
    bc = Label('b', 'c', '', -1)
    cd = Label('c', 'd', '', 1)
    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab])


def test_connected_component_many_most_recent(label_store):
    ab = Label('a', 'b', '', 1)
    bc = Label('b', 'c', '', -1)
    cd = Label('c', 'd', '', 1)
    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab])

    # This label should overwrite the existing `bc` label and expand
    # the connected component to `cd` through transitivity.
    bc = Label('b', 'c', '', 1, epoch_ticks=bc.epoch_ticks + 1)
    label_store.put(bc)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, bc, cd])


def test_connected_component_many_most_recent_diff_value(label_store):
    ab = Label('a', 'b', '', 1)
    bc = Label('b', 'c', '', 1)
    cd = Label('c', 'd', '', 1)
    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab, bc, cd])

    # This label should overwrite the existing `bc` label and contract
    # the connected component to just `ab`.
    bc = Label('b', 'c', '', -1, epoch_ticks=bc.epoch_ticks + 1)
    label_store.put(bc)

    connected = list(label_store.connected_component('a'))
    assert frozenset(connected) == frozenset([ab])


def test_connected_component_collision(label_store):
    # You can't store the hashes of objects and expect there to never
    # be collisions.  As a corollary, hash(str) isn't that great
    # vs. small changes, and the recommended technique of xoring
    # together field hashes can get collisions quickly.
    # In particular, hash('test0') ^ hash('test1') is 1,
    # as is hash('test2') ^ hash('test3').
    ab = Label('test0', 'test1', '', 1)
    bc = Label('test1', 'test2', '', 1)
    cd = Label('test2', 'test3', '', 1)
    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)

    assert list(label_store.connected_component('test0')) == [ab, bc, cd]


def test_expand(label_store):
    ab = Label('a', 'b', '', 1)
    bc = Label('b', 'c', '', 1)
    cd = Label('c', 'd', '', 1)
    ae = Label('a', 'e', '', -1)
    fg = Label('f', 'g', '', 1)

    label_store.put(ab)
    label_store.put(bc)
    label_store.put(cd)
    label_store.put(ae)
    label_store.put(fg)

    correct_pairs = [Label('a', 'b', '', 1),
                     Label('a', 'c', '', 1),
                     Label('a', 'd', '', 1),
                     Label('b', 'c', '', 1),
                     Label('b', 'd', '', 1),
                     Label('c', 'd', '', 1)]

    assert frozenset(label_store.expand('a')) == frozenset(correct_pairs)
    assert len(label_store.expand('e')) == 0
    assert label_store.expand('f') == [Label('f', 'g', '', 1)]


def test_negative_label_inference(label_store):
    ac = Label('a', 'c', '', 1)
    bc = Label('b', 'c', '', 1)

    de = Label('d', 'e', '', 1)
    df = Label('d', 'f', '', 1)
    dg = Label('d', 'g', '', -1)

    cd = Label('c', 'd', '', -1)

    label_store.put(ac)
    label_store.put(bc)
    label_store.put(de)
    label_store.put(df)
    label_store.put(cd)
    label_store.put(dg)

    def get_pair(label):
        return (label.content_id1, label.content_id2)

    correct_pairs = [('a', 'd'),
                     ('b', 'd'),
                     ('c', 'd'),
                     ('c', 'e'),
                     ('c', 'f')]
    # [but not (a,b) <-/-> (e,f)]

    inference = label_store.negative_label_inference(cd)

    assert frozenset(map(get_pair, inference)) == \
        frozenset(correct_pairs)


def test_negative_inference(label_store):
    ac = Label('a', 'c', '', 1)
    bc = Label('b', 'c', '', 1)

    de = Label('d', 'e', '', 1)
    df = Label('d', 'f', '', 1)

    cg = Label('c', 'g', '', -1)
    dg = Label('d', 'g', '', -1)

    hg = Label('h', 'g', '', 1)

    label_store.put(ac)
    label_store.put(bc)
    label_store.put(de)
    label_store.put(df)
    label_store.put(cg)
    label_store.put(dg)
    label_store.put(hg)

    def get_pair(label):
        return (label.content_id1, label.content_id2)

    correct_pairs = [('a', 'g'),
                     ('b', 'g'),
                     ('c', 'g'),
                     ('c', 'h'),
                     ('d', 'g'),
                     ('d', 'h'),
                     ('e', 'g'),
                     ('f', 'g')]

    inference = label_store.negative_inference('g')

    assert frozenset(map(get_pair, inference)) == \
        frozenset(correct_pairs)


# Subtopic testing is below.


def test_sub_direct_connect(label_store):
    a1b2 = Label('a', 'b', '', 1, '1', '2')
    a1c3 = Label('a', 'c', '', 1, '1', '3')
    b2c3 = Label('b', 'c', '', 1, '2', '3')
    a4b2 = Label('a', 'b', '', 1, '4', '2')
    label_store.put(a1b2)
    label_store.put(a1c3)
    label_store.put(b2c3)
    label_store.put(a4b2)

    # a4b2 should not be included because we're demanding a specific
    # subtopic_id of 'a'.
    direct = list(label_store.directly_connected(('a', '1')))
    assert direct == [a1b2, a1c3]


def test_sub_connected(label_store):
    a1b2 = Label('a', 'b', '', 1, '1', '2')
    b2c3 = Label('b', 'c', '', 1, '2', '3')
    b4c5 = Label('b', 'c', '', 1, '4', '5')
    label_store.put(a1b2)
    label_store.put(b2c3)
    label_store.put(b4c5)

    connected = list(label_store.connected_component(('a', '1')))
    assert frozenset(connected) == frozenset([a1b2, b2c3])


def test_sub_expand(label_store):
    a1b2 = Label('a', 'b', '', 1, '1', '2')
    b2c3 = Label('b', 'c', '', 1, '2', '3')
    b4c5 = Label('b', 'c', '', 1, '4', '5')  # not in subtopic expansion!
    label_store.put(a1b2)
    label_store.put(b2c3)
    label_store.put(b4c5)

    # Not phyiscally present in the label table, but part of expansion!
    a1c3 = Label('a', 'c', '', 1, '1', '3')

    connected = list(label_store.expand(('a', '1')))
    assert frozenset(connected) == frozenset([a1b2, b2c3, a1c3])
