'''Unit tests for the ``dossier.label`` tool.

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.

'''
from __future__ import absolute_import
from cStringIO import StringIO

import cbor
import pytest

from kvlayer._local_memory import LocalStorage

from dossier.label import CorefValue, Label, LabelStore
from dossier.label.run import App


@pytest.fixture
def kvlclient():
    c = LocalStorage(app_name='a', namespace='n')
    c._data = {}
    return c


@pytest.fixture
def label_store(kvlclient):
    return LabelStore(kvlclient)


@pytest.fixture
def app(label_store):
    a = App()
    a._label_store = label_store
    a.stdout = StringIO()
    return a


@pytest.fixture
def four_labels(label_store):
    labels = [
        Label('c1', 'c2', 'a1', CorefValue.Positive, epoch_ticks=1234567890),
        Label('c1', 'c2', 'a1', CorefValue.Positive, epoch_ticks=1234567891),
        Label('c1', 'c2', 'a1', CorefValue.Positive, epoch_ticks=1234567892),
        Label('c1', 'c2', 'a2', CorefValue.Negative, epoch_ticks=1234567890),
    ]
    for label in labels:
        label_store.put(label)
    return labels


@pytest.fixture
def four_item_dump():
    return [
        {u'content_id1': 'c1',
         u'content_id2': 'c2',
         u'annotator_id': 'a1',
         u'value': 1,
         u'subtopic_id1': '',
         u'subtopic_id2': '',
         u'epoch_ticks': 1234567892,
         u'rating': 1},
        {u'content_id1': 'c1',
         u'content_id2': 'c2',
         u'annotator_id': 'a1',
         u'value': 1,
         u'subtopic_id1': '',
         u'subtopic_id2': '',
         u'epoch_ticks': 1234567891,
         u'rating': 1},
        {u'content_id1': 'c1',
         u'content_id2': 'c2',
         u'annotator_id': 'a1',
         u'value': 1,
         u'subtopic_id1': '',
         u'subtopic_id2': '',
         u'epoch_ticks': 1234567890,
         u'rating': 1},
        {u'content_id1': 'c1',
         u'content_id2': 'c2',
         u'annotator_id': 'a2',
         u'value': -1,
         u'subtopic_id1': '',
         u'subtopic_id2': '',
         u'epoch_ticks': 1234567890,
         u'rating': 0},
    ]


@pytest.fixture
def two_item_dump(four_item_dump):
    return [four_item_dump[0], four_item_dump[3]]


def test_list_short(app, label_store):
    label_store.put(Label('c1', 'c2', 'annotator', CorefValue.Positive,
                          epoch_ticks=1234567890))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by annotator at 2009-02-13 23:31:30\n')


def test_list_two(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c1', 'c2', 'a2', CorefValue.Negative,
                          epoch_ticks=1234567890))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_collapses(app, four_labels):
    app.runcmd('list', [])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:32\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_deleted(app, four_labels):
    app.runcmd('list', ['--include-deleted'])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:32\n'
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:31\n'
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_list_subtopics(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890,
                          subtopic_id1='s1', subtopic_id2='s2'))

    app.runcmd('list', [])

    assert (app.stdout.getvalue() ==
            'c1(s1) ==(1) c2(s2) by a1 at 2009-02-13 23:31:30\n')


def test_dump_all(app, four_labels, four_item_dump):
    app.runcmd('dump_all', [])
    dump = cbor.loads(app.stdout.getvalue())
    assert dump == four_item_dump


def test_dump_all_exclude_deleted(app, four_labels, two_item_dump):
    app.runcmd('dump_all', ['--exclude-deleted'])
    dump = cbor.loads(app.stdout.getvalue())
    assert dump == two_item_dump


def test_load_short(app, label_store, two_item_dump, tmpdir):
    fn = tmpdir.join('dump.cbor')
    fn.write(cbor.dumps(two_item_dump), mode='wb')

    app.runcmd('load', [str(fn)])
    assert (len(list(label_store.everything(include_deleted=True))) ==
            len(two_item_dump))
    assert (len(list(label_store.everything(include_deleted=False))) ==
            len(two_item_dump))
    assert app.stdout.getvalue() == ''
    app.runcmd('dump_all', [])
    assert cbor.loads(app.stdout.getvalue()) == two_item_dump


def test_load_full(app, label_store, four_item_dump, tmpdir):
    fn = tmpdir.join('dump.cbor')
    fn.write(cbor.dumps(four_item_dump), mode='wb')

    app.runcmd('load', [str(fn)])
    assert (len(list(label_store.everything(include_deleted=True))) ==
            len(four_item_dump))
    assert (len(list(label_store.everything(include_deleted=False))) == 2)
    assert app.stdout.getvalue() == ''
    app.runcmd('dump_all', [])
    assert cbor.loads(app.stdout.getvalue()) == four_item_dump


def test_get(app, four_labels):
    app.runcmd('get', ['c1'])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:32\n'
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_get_missing(app, four_labels):
    app.runcmd('get', ['c0'])
    assert app.stdout.getvalue() == ''


def test_get_negative(app, four_labels):
    app.runcmd('get', ['--value', '-1', 'c1'])
    assert (app.stdout.getvalue() ==
            'c1 !=(0) c2 by a2 at 2009-02-13 23:31:30\n')


def test_connected(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c3', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))

    app.runcmd('connected', ['c1'])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c2 ==(1) c3 by a1 at 2009-02-13 23:31:30\n')


def test_connected_two(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c3', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))

    app.runcmd('connected', ['c2'])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n'
            'c2 ==(1) c3 by a1 at 2009-02-13 23:31:30\n')


def test_connected_negative(app, label_store):
    label_store.put(Label('c1', 'c2', 'a1', CorefValue.Positive,
                          epoch_ticks=1234567890))
    label_store.put(Label('c3', 'c2', 'a1', CorefValue.Negative,
                          epoch_ticks=1234567890))

    app.runcmd('connected', ['c2'])
    assert (app.stdout.getvalue() ==
            'c1 ==(1) c2 by a1 at 2009-02-13 23:31:30\n')
