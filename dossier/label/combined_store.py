'''dossier.label.combined_store

.. This software is released under an MIT/X11 open source license.
   Copyright 2012-2015 Diffeo, Inc.
'''

from __future__ import absolute_import

from dossier.label.label import LabelStore
from dossier.label.relation_label import RelationLabelStore


class CombinedLabelStore(object):
    '''Class providing utilities that need both label stores at the same
    time.
    '''

    def __init__(self, kvl):
        self.kvl = kvl
        self.label_store = LabelStore(kvl)
        self.rel_label_store = RelationLabelStore(kvl)

    def get_related_coref_relationships(self, content_id, min_strength=None):
        '''Follow coreference relationships to get full related graph.

        :rtype: dict mapping related identifier to list of documents
        coref to that identifier.
        '''
        related_labels = self.rel_label_store.get_related(
            content_id, min_strength=min_strength)
        related_cids = [rel_label.other(content_id)
                        for rel_label in related_labels]
        related_cid_to_idents = {}
        for cid in related_cids:
            conn_labels = self.label_store.directly_connected(cid)
            idents = [label.other(cid) for label in conn_labels]
            related_cid_to_idents[cid] = idents
        return related_cid_to_idents

    def get_related_flat(self, content_id, min_strength=None):
        '''Follow coreference relationships to get full related graph.

        This differs from ``get_related_coref_relationships`` in that
        it returns a flat list of all identifiers found through the
        coreference layer of indirection.

        :rtype: list of identifiers
        '''
        rel_id_to_idents = self.get_related_coref_relationships(
            content_id, min_strength=min_strength)
        flat_list = []
        for val in rel_id_to_idents.values():
            flat_list.extend(val)
        return flat_list
