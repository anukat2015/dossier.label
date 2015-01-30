'''dossier.label.label

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2014 Diffeo, Inc.
'''
from __future__ import absolute_import, division, print_function

from collections import namedtuple
from datetime import datetime
import functools
from itertools import groupby, imap, combinations, ifilter
import logging
import struct
import sys
import time

import enum


logger = logging.getLogger(__name__)


MAX_SECOND_TICKS = ((60 * 60 * 24) * 365 * 100)
'''The maximum number of seconds supported.

Our kvlayer backend cannot (currently) guarantee a correct ordering
of signed integers, but can guarantee a correct ordering of unsigned
integers.

Labels, however, should be sorted with the most recent label first.
This is trivially possible by negating its epoch ticks.

Because kvlayer cannot guarantee a correct ordering of signed integers,
we avoid the sign switch by subtracting the ticks from an arbitrary
date in the future (UNIX epoch + 100 years).
'''


def time_complement(t):
    return MAX_SECOND_TICKS - t



class CorefValue(enum.Enum):
    '''
    An enumeration that describes the value of a coreference judgment by a
    human. The judgment is always made with respect to a pair of content
    items.

    :cvar Negative: The two items are not coreferent.
    :cvar Unknown: It is unknown whether the two items are coreferent.
    :cvar Positive: The two items are coreferent.
    '''
    Negative = -1
    Unknown = 0
    Positive = 1


@functools.total_ordering
class Label(namedtuple('_Label', 'content_id1 content_id2 subtopic_id1 ' +
                                 'subtopic_id2 annotator_id epoch_ticks '+
                                 'value rating')):
    '''A label is an immutable unit of ground truth data.

    .. automethod:: __new__
    .. automethod:: reversed
    .. automethod:: other
    .. automethod:: __lt__
    .. automethod:: __eq__
    .. automethod:: __hash__
    .. automethod:: __contains__
    '''

    def __new__(cls, content_id1, content_id2, annotator_id, value,
                subtopic_id1=None, subtopic_id2=None, epoch_ticks=None,
                rating=None):
        # `__new__` is overridden instead of `__init__` because `namedtuple`
        # defines a `__new__` method. We modify construction by making
        # several values optional.
        if isinstance(value, int):
            value = CorefValue(value)
        if epoch_ticks is None:
            epoch_ticks = long(time.time())
        if subtopic_id1 is None:
            subtopic_id1 = ''
        if subtopic_id2 is None:
            subtopic_id2 = ''

        if value == CorefValue.Positive:
            if rating is None:
                rating = 1
        else:
            rating = 0

        return super(Label, cls).__new__(
            cls, content_id1=content_id1, content_id2=content_id2,
            subtopic_id1=subtopic_id1, subtopic_id2=subtopic_id2,
            annotator_id=annotator_id, epoch_ticks=epoch_ticks, value=value,
            rating=rating)

    def reversed(self):
        '''Returns a new label with ids swapped.

        This method satisfies the following law: for every label
        ``lab``, ``lab == lab.reversed()``.
        '''
        return self._replace(
            content_id1=self.content_id2, content_id2=self.content_id1,
            subtopic_id1=self.subtopic_id2, subtopic_id2=self.subtopic_id1)

    def __contains__(self, v):
        '''Tests membership of identifiers.

        If `v` is a tuple of ``(content_id, subtopic_id)``, then the
        pair is checked for membership. Otherwise, `v` must be a `str`
        and is checked for equality to one of the content ids in this
        label.

        As a special case, if ``v`` is ``(content_id, None)``, then
        ``v`` is treated as if it were ``content_id``.
        '''
        if isinstance(v, tuple) and len(v) == 2 and v[1] is None:
            v = v[0]

        if isinstance(v, tuple) and len(v) == 2:
            cid, subid = v
            cid1, subid1 = self.content_id1, self.subtopic_id1
            cid2, subid2 = self.content_id2, self.subtopic_id2
            return (cid == cid1 and subid == subid1) \
                or (cid == cid2 and subid == subid2)
        else:
            return v == self.content_id1 or v == self.content_id2

    def other(self, content_id):
        '''Returns the other content id.

        If ``content_id == self.content_id1``, then return
        ``self.content_id2`` (and vice versa).
        '''
        if content_id == self.content_id1:
            return self.content_id2
        else:
            return self.content_id1

    def subtopic_for(self, content_id):
        '''Get the subtopic id that corresponds with a content id.

        Beware ``content_id`` must be one of either ``self.content_id1``
        or ``self.content_id2``.
        '''

        assert content_id == self.content_id1 or \
            content_id == self.content_id2

        if content_id == self.content_id1:
            return self.subtopic_id1
        else:
            return self.subtopic_id2

    def _to_kvlayer(self):
        '''Converts this label to a kvlayer tuple.

        The tuple returned can be used directly in a :mod:`kvlayer`
        ``put`` call.

        :rtype: ``(key, value)``
        '''
        epoch_ticks_rev = long(time_complement(self.epoch_ticks))
        negated = self._replace(epoch_ticks=epoch_ticks_rev)[0:len(self)-2]
        packed_val = self._pack_value()
        return (negated, packed_val)

    @staticmethod
    def _from_kvlayer(row):
        '''Create a new :class:`Label` from a kvlayer result.

        The ``row`` should be a tuple of ``(key, value)``
        where ``key`` corresponds to the namespace defined at
        :attr:`LabelStore._kvlayer_namespace`.

        :param row: kvlayer result
        :type row: ``(key, value)``
        :rtype: :class:`Label`
        '''
        key, value = row
        cid1, cid2, subid1, subid2, ann, ticks = key
        coref_val, rating = Label._unpack_value(value)
        return Label(content_id1=cid1, content_id2=cid2,
                     subtopic_id1=subid1, subtopic_id2=subid2,
                     annotator_id=ann,
                     epoch_ticks=time_complement(int(ticks)),
                     value=coref_val, rating=rating)

    @staticmethod
    def _unpack_value(val):
        '''Unpack byte into CorefValue and rating score.

        Subtracting 1 from the lower 4 bits gives us the coref score.
        The upper 4 bits gives us the rating score.
        '''
        (unpacked,) = struct.unpack('B', val)
        coref_val = (unpacked & 15) - 1
        rating = (unpacked >> 4)
        return coref_val, rating

    def _pack_value(self):
        '''Pack CorefValue and rating score into a byte.

        We add one to the coref value to make it unsigned.
        This unsiged value makes the lower 4 bits of the byte.
        The rating score makes up the upper 4 bits.
        '''
        to_pack = (self.value.value+1) | (self.rating << 4)
        packed = struct.pack('B', to_pack)
        return packed

    def __lt__(l1, l2):
        '''Defines a total ordering for labels.

        The ordering is meant to be the same as the ordering used
        in the underlying database storage. Namely, the key used
        to determine ordering is: ``(cid1, cid2, subid1, subid2,
        annotator_id, MAX_TIME - epoch_ticks)`` where ``cid1 <= cid2``
        and ``subid1 <= subid2``.

        Notably, the ordering does not include the coreferent ``value``
        and it complements ``epoch_ticks`` so that more recent
        labels appear first in ascending order.
        '''
        return l1._cmp_value < l2._cmp_value

    @property
    def _cmp_value(self):
        cid1, cid2 = normalize_pair(self.content_id1, self.content_id2)
        subid1, subid2 = normalize_pair(self.subtopic_id1, self.subtopic_id2)
        ticks = time_complement(self.epoch_ticks)
        return (cid1, cid2, subid1, subid2, self.annotator_id, ticks)

    def __eq__(l1, l2):
        '''Tests equality between two labels.

        Equality is keyed on ``annotator_id`` and the unordered
        comparison between content ids and subtopic ids.

        This definition of equality does not include the values for
        ``epoch_ticks`` or ``value``.
        '''
        return (
            l1.annotator_id == l2.annotator_id
            and unordered_pair_eq((l1.content_id1, l1.content_id2),
                                  (l2.content_id1, l2.content_id2))
            and unordered_pair_eq((l1.subtopic_id1, l1.subtopic_id2),
                                  (l2.subtopic_id1, l2.subtopic_id2))
        )

    def __hash__(self):
        '''Returns a hash of this label.

        The hash is made up of the content ids, subtopic ids and the
        annotator id. This hash function obeys the following law:
        for all labels ``x`` and ``y``, ``x == y`` if and only if
        ``hash(x) == hash(y)``.
        '''
        # This code is clearer if we use `frozenset`, but let's avoid
        # creating intermediate objects.
        cid1, cid2 = normalize_pair(self.content_id1, self.content_id2)
        subid1, subid2 = normalize_pair(self.subtopic_id1, self.subtopic_id2)
        return hash((self.annotator_id, cid1, cid2, subid1, subid2))

    def __repr__(self):
        tpl = 'Label({cid1}, {cid2}, ' + \
                    '{subid1}{subid2}annotator={ann}, {tstr}, value={v})'
        subid1, subid2 = '', ''
        if self.subtopic_id1:
            subid1 = 'subtopic1=%s, ' % self.subtopic_id1
        if self.subtopic_id2:
            subid2 = 'subtopic2=%s, ' % self.subtopic_id2
        dt = datetime.utcfromtimestamp(self.epoch_ticks)
        return tpl.format(cid1=self.content_id1, cid2=self.content_id2,
                         subid1=subid1, subid2=subid2, tstr=str(dt),
                         ann=self.annotator_id, v=self.value)


class LabelStore(object):
    '''A label database.

    .. automethod:: __init__
    .. automethod:: put
    .. automethod:: get
    .. automethod:: directly_connected
    .. automethod:: connected_component
    .. automethod:: expand
    .. automethod:: everything
    .. automethod:: delete_all
    '''
    config_name = 'dossier.label'
    TABLE = 'label'

    _kvlayer_namespace = {
        # (cid1, cid2, subid1, subid2, annotator_id, time) -> value
        # N.B. The `long` type here is for the benefit of the underlying
        # database storage. It will hopefully result in a storage type
        # that is big enough to contain milliseconds epoch ticks. (A 64 bit
        # integer is more than sufficient, which makes `long` unnecessary from
        # a Python 2 perspective.)
        TABLE: (str, str, str, str, str, long),
    }

    def __init__(self, kvlclient):
        '''Create a new label store.

        :param kvlclient: kvlayer client
        :type kvlclient: :class:`kvlayer._abstract_storage.AbstractStorage`
        :rtype: :class:`LabelStore`
        '''
        self.kvl = kvlclient
        self.kvl.setup_namespace(self._kvlayer_namespace)

    def put(self, label):
        '''Add a new label to the store.

        :param label: label
        :type label: :class:`Label`
        '''
        logger.info('adding label "%r"', label)
        self.kvl.put(self.TABLE,
                     label._to_kvlayer(), label.reversed()._to_kvlayer())

    def get(self, cid1, cid2, annotator_id, subid1='', subid2=''):
        '''Retrieve a label from the store.

        When ``subid1`` and ``subid2`` are empty, then a label without
        subtopic identifiers will be returned.

        Note that the combination of content ids, subtopic ids and
        an annotator id *uniquely* identifies a label.

        :param str cid1: content id
        :param str cid2: content id
        :param str annotator_id: annotator id
        :param str subid1: subtopic id
        :param str subid2: subtopic id
        :rtype: :class:`Label`
        :raises: :exc:`KeyError` if no label could be found.
        '''
        s = (cid1, cid2, subid1, subid2, annotator_id, long(-sys.maxint - 1))
        e = (cid1, cid2, subid1, subid2, annotator_id, long(sys.maxint))

        # We return the first result because the `kvlayer` abstraction
        # guarantees that the first result will be the most recent entry
        # for this particular key (since the timestamp is inserted as a
        # complement value).
        for row in self.kvl.scan(self.TABLE, (s, e)):
            return Label._from_kvlayer(row)
        raise KeyError((s, e))

    def directly_connected(self, ident):
        '''Return a generator of labels connected to ``ident``.

        ``ident`` may be a ``content_id`` or a ``(content_id,
        subtopic_id)``.

        If no labels are defined for ``ident``, then the generator
        will yield no labels.

        Note that this only returns *directly* connected labels. It
        will not follow transitive relationships.

        :param ident: content id or (content id and subtopic id)
        :type ident: ``str`` or ``(str, str)``
        :rtype: generator of :class:`Label`
        '''
        content_id, subtopic_id = normalize_ident(ident)
        s = (content_id,)
        e = (content_id + '\xff',)
        results = imap(Label._from_kvlayer, self.kvl.scan(self.TABLE, (s, e)))
        results = latest_labels(results)
        if subtopic_id is not None:
            pair = (content_id, subtopic_id)
            results = ifilter(lambda lab: pair in lab, results)
        else:
            results = ifilter(lambda lab: content_id in lab, results)
        return results

    def connected_component(self, ident):
        '''Return a connected component generator for ``ident``.

        ``ident`` may be a ``content_id`` or a ``(content_id,
        subtopic_id)``.

        Given an ``ident``, return the corresponding connected
        component by following all positive transitivity relationships.

        For example, if ``(a, b, 1)`` is a label and ``(b, c, 1)`` is
        a label, then ``connected_component('a')`` will return both
        labels even though ``a`` and ``c`` are not directly connected.

        (Note that even though this returns a generator, it will still
        consume memory proportional to the number of labels in the
        connected component.)

        :param ident: content id or (content id and subtopic id)
        :type ident: ``str`` or ``(str, str)``
        :rtype: generator of :class:`Label`
        '''
        ident = normalize_ident(ident)
        done = set()  # set of cids that we've queried with
        todo = set([ident])  # set of cids to do a query for
        label_hashes = set()
        while todo:
            ident = todo.pop()
            done.add(ident)
            for label in self.directly_connected(ident):
                if label.value != CorefValue.Positive:
                    continue
                ident1, ident2 = idents_from_label(
                    label, subtopic=ident_has_subtopic(ident))
                if ident1 not in done:
                    todo.add(ident1)
                if ident2 not in done:
                    todo.add(ident2)

                h = hash(label)
                if h not in label_hashes:
                    label_hashes.add(h)
                    yield label

    def expand(self, ident):
        '''Return expanded set of labels from a connected component.

        The connected component is derived from ``ident``. ``ident``
        may be a ``content_id`` or a ``(content_id, subtopic_id)``.
        If ``ident`` identifies a subtopic, then expansion is done
        on a subtopic connected component (and expanded labels retain
        subtopic information).

        The labels returned by :meth:`LabelStore.connected_component`
        contains only the :class:`Label` stored in the
        :class:`LabelStore`, and does not include the labels you can
        infer from the connected component. This method returns both
        the data-backed labels and the inferred labels.

        Subtopic assignments of the expanded labels will be empty. The
        ``annotator_id`` will be an arbitrary ``annotator_id`` within
        the connected component.

        :param str content_id: content id
        :param value: coreferent value
        :type value: :class:`CorefValue`
        :rtype: ``list`` of :class:`Label`
        '''
        subtopic = ident_has_subtopic(normalize_ident(ident))
        labels = list(self.connected_component(ident))
        labels.extend(expand_labels(labels, subtopic=subtopic))
        return labels

    def negative_inference(self, content_id):
        '''Return a generator of inferred negative label relationships
        centered on ``content_id``.

        Negative labels are inferred by getting all other content ids
        connected to ``content_id`` through a negative label, then
        running :meth:`LabelStore.negative_label_inference` on those
        labels. See :meth:`LabelStore.negative_label_inference` for
        more information.
        '''
        neg_labels = ifilter(lambda l: l.value == CorefValue.Negative,
                             self.directly_connected(content_id))
        for label in neg_labels:
            label_inf = self.negative_label_inference(label)
            for label in label_inf:
                yield label

    def negative_label_inference(self, label):
        '''Return a generator of inferred negative label relationships.

        Construct ad-hoc negative labels between ``label.content_id1``
        and the positive connected component of ``label.content_id2``,
        and ``label.content_id2`` to the connected component of
        ``label.content_id1``.

        Note this will allocate memory proportional to the size of the
        connected components of ``label.content_id1`` and
        ``label.content_id2``.
        '''
        assert label.value == CorefValue.Negative

        yield label

        cid2_comp = self.connected_component(label.content_id2)
        for comp_label in cid2_comp:
            cid = comp_label.other(label.content_id2)
            yield Label(label.content_id1, cid, 'auto', CorefValue.Negative)

        cid1_comp = self.connected_component(label.content_id1)
        for comp_label in cid1_comp:
            cid = comp_label.other(label.content_id1)
            yield Label(label.content_id2, cid, 'auto', CorefValue.Negative)

    def everything(self, include_deleted=False):
        '''Returns a generator of all labels in the store.

        If ``include_deleted`` is ``True``, labels that have been
        deleted are also included.

        :rtype: generator of :class:`Label`
        '''
        results = imap(Label._from_kvlayer, self.kvl.scan(self.TABLE))
        return results if include_deleted else latest_labels(results)

    def delete_all(self):
        '''Deletes all labels in the store.'''
        self.kvl.clear_table(self.TABLE)


def unordered_pair_eq(pair1, pair2):
    '''Performs pairwise unordered equality.

    ``pair1`` == ``pair2`` if and only if
    ``frozenset(pair1)`` == ``frozenset(pair2)``.
    '''
    (x1, y1), (x2, y2) = pair1, pair2
    return (x1 == x2 and y1 == y2) or (x1 == y2 and y1 == x2)


def normalize_pair(x, y):
    '''Normalize a pair of values.

    Returns ``(y, x)`` if and only if ``y < x`` and ``(x, y)``
    otherwise.
    '''
    if y < x:
        return y, x
    else:
        return x, y


def latest_labels(label_iterable):
    '''Returns the most recent labels from a sorted iterable.'''
    for _, group in groupby(label_iterable):
        for lab in group:
            yield lab
            break


def expand_labels(labels, subtopic=False):
    '''Expand a set of labels that define a connected component.

    ``labels`` must define a *positive* connected component: it is all
    of the edges that make up the *single* connected component in the
    :class:`LabelStore`. expand will ignore subtopic assignments, and
    annotator_id will be an arbitrary one selected from ``labels``.

    Note that this function only returns the expanded labels, which
    is guaranteed to be disjoint with the given ``labels``. This
    requirement implies that ``labels`` is held in memory to ensure
    that no duplicates are returned.

    If ``subtopic`` is ``True``, then it is assumed that ``labels``
    defines a ``subtopic`` connected component. In this case, subtopics
    are included in the expanded labels.

    :param labels: iterable of :class:`Label` for the connected component.
    :rtype: generator of expanded :class:`Label`s only
    '''
    labels = list(labels)
    assert all(lab.value == CorefValue.Positive for lab in labels)

    # Anything to expand?
    if len(labels) == 0:
        return

    annotator = labels[0].annotator_id

    data_backed = set()
    connected_component = set()
    for label in labels:
        ident1, ident2 = idents_from_label(label, subtopic=subtopic)
        data_backed.add(normalize_pair(ident1, ident2))
        connected_component.add(ident1)
        connected_component.add(ident2)

    # We do not want to rebuild the Labels we already have,
    # because they have true annotator_id and subtopic
    # fields that we may want to preserve.
    for ident1, ident2 in combinations(connected_component, 2):
        if normalize_pair(ident1, ident2) not in data_backed:
            (cid1, subid1), (cid2, subid2) = ident1, ident2
            yield Label(cid1, cid2, annotator, CorefValue.Positive,
                        subtopic_id1=subid1, subtopic_id2=subid2)


def expand_labels_with_subtopics(labels):
    '''Expand a connected component of labels with subtopics.

    This is just like ``expand_labels``, except it assumes that the
    connected component given is a *subtopic* connected component.
    '''
    labels = list(labels)
    assert all(lab.value == CorefValue.Positive for lab in labels)

    # Anything to expand?
    if len(labels) == 0:
        return

    annotator = labels[0].annotator_id

    data_backed = set()
    connected_component = set()
    for label in labels:
        ident1, ident2 = idents_from_label(label, tuple)
        data_backed.add(normalize_pair(ident1, ident2))
        connected_component.add(ident1)
        connected_component.add(ident2)

    # We do not want to rebuild the Labels we already have,
    # because they have true annotator_id and subtopic
    # fields that we may want to preserve.
    for ident1, ident2 in combinations(connected_component, 2):
        if normalize_pair(ident1, ident2) not in data_backed:
            (cid1, subid1), (cid2, subid2) = ident1, ident2
            yield Label(cid1, cid2, annotator, CorefValue.Positive,
                        subtopic_id1=subid1, subtopic_id2=subid2)


def normalize_ident(ident):
    '''Splits a generic identifier.

    If ``ident`` is a tuple, then ``(ident[0], ident[1])`` is returned.
    Otherwise, ``(ident[0], None)`` is returned.
    '''
    if isinstance(ident, tuple) and len(ident) == 2:
        return ident[0], ident[1]  # content_id, subtopic_id
    else:
        return ident, None


def ident_has_subtopic(ident):
    return ident[1] is not None


def idents_from_label(lab, subtopic=False):
    '''Returns the "ident" of a label.

    If ``subtopic`` is ``True``, then a pair of pairs is returned,
    where each pair corresponds to the content id and subtopic id in
    the given label.

    Otherwise, a pair of pairs is returned, but the second element of each
    pair is always ``None``.

    This is a helper function that is useful for dealing with generic
    label identifiers.
    '''
    if not subtopic:
        return (lab.content_id1, None), (lab.content_id2, None)
    else:
        return (
            (lab.content_id1, lab.subtopic_id1),
            (lab.content_id2, lab.subtopic_id2),
        )
