class Document:
    """"""
    def __init__(self, doc_id, paragraphs, entities, triggers, events):
        self.doc_id = doc_id
        self.paragraphs = paragraphs
        self.entities = entities
        self.triggers = triggers
        self.events = events

    def __str__(self):
        return "{}:({},{},{},{})".format(
            self.doc_id,
            [p for p in self.paragraphs],
            [e for e in self.entities],
            [t for t in self.triggers],
            [e for e in self.events])


class Mention:
    """"""
    def __init__(self, id_, type_, start, end, text):
        self.id_ = id_
        self.type_ = type_
        self.start = start
        self.end = end
        self.text = text

    def __str__(self):
        return "{}: ({},{},{},{})".format(
            self.id_,
            self.type_,
            self.start,
            self.end,
            self.text)


class EntityMention(Mention):
    def __init__(self, id_, type_, start, end, text):
        super().__init__(id_, type_, start, end, text)

    def __str__(self):
        super().__str__()


class TriggerMention(Mention):
    def __init__(self, id_, type_, start, end, text):
        super().__init__(id_, type_, start, end, text)

    def __str__(self):
        super().__str__()


class Edge:
    """"""
    def __init__(self, ev_id, ev_type, src_id, trg_id, ev_trg_id, arg_type):
        self.ev_id = ev_id
        self.ev_type = ev_type
        self.src_id = src_id
        self.trg_id = trg_id
        self.ev_trg_id = ev_trg_id
        self.arg_type = arg_type

    def __str__(self):
        return "{}/{}: ({},{},{},{})".format(
            self.ev_id,
            self.ev_type,
            self.src_id,
            self.trg_id,
            self.ev_trg_id,
            self.arg_type)


class Event:
    """"""
    def __init__(self, id_, type_, start_id, num, edge_types, end_ids):
        self.id_ = id_
        self.type_ = type_
        self.start_id = start_id
        self.num = num
        self.edge_types = edge_types
        self.end_ids = end_ids

    def __str__(self):
        return "{}: ({},{},{},{},{})".format(
            self.id_,
            self.type_,
            self.start_id,
            self.num,
            [e for e in self.edge_types],
            [e for e in self.end_ids])