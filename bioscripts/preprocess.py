import os
import argparse
from utils import create_files, constants
from utils.document import Document, EntityMention, TriggerMention, Event


def main(args):
    corpus_path = os.path.join("data", "corpora", args.corpus)

    for data_split in constants.DATA_SPLITS:
        documents = []

        # Get the document IDs from the split folder of the corpus
        corpus_split_path = os.path.join(corpus_path, data_split)
        doc_ids = get_doc_ids_from_dir(corpus_split_path)
        
        # Create a list of document objects containing the annotations
        for doc_id in doc_ids:
            document = parse_document_files(
                corpus_split_path, doc_id, args.use_sec_entities, data_split,
                args.bind_renaming)
            documents.append(document)

        # Create the file of encoded events for the documents in the split
        create_files.create_annotations(
            documents, data_split, args.corpus, args.use_sec_entities, 
            args.keep_entity_tokens, args.keep_orphan_entities, args.encoding,
            args.multihead, args.masking)
        

def parse_document_files(folder, doc_id, use_sec_entities, data_split,
    bind_renaming):
    txt_path = os.path.join(folder, doc_id + constants.EXT_FILES["txt"])
    a1_path = os.path.join(folder, doc_id + constants.EXT_FILES["a1"])
    a2_path = os.path.join(folder, doc_id + constants.EXT_FILES["a2"])
    paragraphs = []
    entities = {}
    triggers = {}
    events = {}

    # [.TXT]: Store the list of paragraphs in the document
    with open(txt_path, mode="r", encoding="utf-8") as f:
        for line in f:
            paragraphs.append(line.rstrip("\n"))

    # [.A1]: Store the list of entities which BioNLP-ST format is:
    #   [EID]\t[TYPE] [START_CHAR] [END_CHAR]\t[TEXT]
    with open(a1_path, mode="r", encoding="utf-8") as f:
        for line in f:
            spl_line = line.rstrip("\n").split("\t")
            assert len(spl_line) == 3

            e_id, e_type, e_start, e_end, e_text = parse_mention(spl_line)
            entity = EntityMention(e_id, e_type, e_start, e_end, e_text)
            entities[e_id] = entity

    if data_split != "test":
        # [.A2] Store the list of triggers&events, which BioNLP-ST format is:
        #   Trigger: [TID]\t[TYPE] [START_CHAR] [END_CHAR]\t[TEXT]
        #   Event:   [ID]\t[TYPE]:[TID] [ETYPE]:[ID/EID]...[ARG_TYPE]:[ID/EID]
        with open(a2_path, mode="r", encoding="utf-8") as f:
            tmp_triggers = []
            tmp_events = []

            for line in f:
                spl_line = line.rstrip("\n").split("\t")
                ann_id = spl_line[0]

                # CASE: entity/trigger
                if ann_id[0] == "T":
                    assert len(spl_line) == 3
                    attributes = parse_mention(spl_line)
                    id_, type_, start, end, text = attributes

                    if type_ in constants.SEC_ENTITIES:
                        # Add secondary entity mentions only if specified
                        if use_sec_entities == True:
                            sec_ent = EntityMention(
                                id_, type_, start, end, text)
                            entities[id_] = sec_ent
                    else:
                        trigger = TriggerMention(
                            id_, type_, start, end, text)
                        triggers[id_] = trigger

                # CASE: event
                elif ann_id[0] == "E":
                    assert len(spl_line) == 2
                    attributes = parse_event(spl_line)
                    id_, type_, start_id, arg_types, end_ids = attributes
                    tmp_triggers.append(start_id)
                    num = tmp_triggers.count(start_id)
                    tmp_events.append(id_)

                    # If there are previous Binding events centered on the
                    # same trigger, update their "num" to optionally renaming
                    # them afterwards (@TODO: Generalize to Theme+ events)
                    if (num > 1) and (type_ == "Binding"):
                        # Get the indexes of all occurrences of the trigger
                        trigger_pos_idx = get_index_positions(
                            tmp_triggers, start_id)

                        # For each index, update the "num" of the event
                        # The last one is the current (already correct)
                        for i in range(len(trigger_pos_idx)-1):
                            events[tmp_events[trigger_pos_idx[i]]].num = num

                    event = Event(
                        id_, type_, start_id, num, arg_types, end_ids)
                    events[id_] = event

                # CASE: other
                elif ann_id[0] in constants.ANN_SKIP:
                    pass

                # CASE: unknown
                else:
                    print("Warning. {} ann type is unknown.".format(ann_id))
    
    # Rename the Binding events
    if bind_renaming != "no":
        rename_binding_events(events, triggers, bind_renaming)

    # Store all the information into a Document object
    document = Document(doc_id, paragraphs, entities, triggers, events)

    return document


def parse_mention(line):
    m_id = line[0]
    raw_info = line[1].split(" ")   # the middle part, space-separated
    m_type = raw_info[0]
    m_start = int(raw_info[1])
    m_end = int(raw_info[2])
    m_text = line[2]

    return m_id, m_type, m_start, m_end, m_text


def parse_event(line):
    e_id = line[0]
    participants = line[1].split()  # list of [ARG_TYPE]:[ID/E_ID]
    is_event_trigger = True
    e_edge_types = []
    e_end_ids = []

    for participant in participants:
        arg_label, participant_id = participant.split(":")

        # The first participant is the event trigger, i.e., [TYPE]:[TID]
        if is_event_trigger:
            e_type = arg_label          # the event type, e.g., Binding
            e_start_id = participant_id # the ID of the source trigger
            is_event_trigger = False    # switch the flag off for arguments

        # From the second onwards, there are arguments, i.e., [ETYPE]:[ID/EID]
        else:
            e_edge_type = arg_label     # the argument type, e.g., Theme
            e_end_id = participant_id   # the ID of the target event/entity
            e_edge_types.append(e_edge_type)
            e_end_ids.append(e_end_id)

    return e_id, e_type, e_start_id, e_edge_types, e_end_ids


def get_doc_ids_from_dir(path):
    ids = set()

    # Get only the files (no directories)
    files = [f for f in os.listdir(path) if os.path.isfile(
        os.path.join(path, f))]

    # Add only the filenames (no extensions) without duplicates
    for file in files:
        filename, extension = os.path.splitext(file)
        if filename not in constants.EXCL_FILENAMES:
            ids.add(filename)
    
    return sorted(list(ids))


def get_index_positions(list, element):
    indexes = []
    index_position = 0

    while True:
        try:
            index_position = list.index(element, index_position)
            indexes.append(index_position)
            index_position += 1
        except ValueError as error:
            break
 
    return indexes


def rename_binding_events(events, triggers, bind_renaming):
    #last_start_id = None
    for event in events.items():
        if event[1].type_ == "Binding":
            is_multi_trigger = False
            is_multi_argument = False
            #is_multi_argument_partial = False
            #same_event_of_before = (last_start_id == event[1].start_id)

            # Check if there are multiple events centered on the trigger
            if event[1].num > 1:
                is_multi_trigger = True

            # Check if there are multiple arguments for the event
            list_of_args = event[1].edge_types
            count = 0
            #print(event[1].start_id, same_event_of_before, list_of_args)
            for arg in list_of_args:
                if arg.startswith("Theme"):
                    count += 1
            if count > 1:
                is_multi_argument = True

            # Rename the trigger types (and optionally the triggers)
            if is_multi_trigger:
                # CASE: K
                if is_multi_argument:
                    triggers[event[1].start_id].type_ = "Binding1"
                    if not bind_renaming.endswith("only_tri"):
                        event[1].type_ = "Binding1"
                # CASE: N
                else:
                    triggers[event[1].start_id].type_ = "BindingN"
                    if not bind_renaming.endswith("only_tri"):
                        event[1].type_ = "BindingN"
            else:
                triggers[event[1].start_id].type_ = "Binding1"
                if not bind_renaming.endswith("only_tri"):
                    event[1].type_ = "Binding1"

            #last_start_id = event[1].start_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", default="GE11", 
        help="The name of the corpus to use. For now GE11 only is supported.")
    parser.add_argument("--multihead", default=True,
        action="store_true", help="Whether or not to encode multiple heads at\
                a token level.")
    parser.add_argument("--masking", default="no", 
        choices=["no", "entity", "type"], help="Whether or not to mask entities.")
    parser.add_argument("--bind_renaming", default="no",
        choices=["no", "all", "s-to-1", "s-to-n", "all_only_tri", "s-to-1_only_tri", 
        "s-to-n_only_tri"], help="Which strategy to use to rename Binding events.")
    parser.add_argument("--encoding", default="mt.1",
        choices=["st", "mt.1", "mt.2", "mt.3", "mt.4"], help="The encoding to use.")
    parser.add_argument("--use_sec_entities", default=False, 
        action="store_true", help="Whether or not to use annotated secondary\
                entities. Note that since we are interested in the core task,\
                no edge will be created for them.")
    parser.add_argument("--keep_entity_tokens", default=False, 
        action="store_true", help="Whether or not to merge multi-token\
                entities. By default, entity spans are merged.")
    parser.add_argument("--keep_orphan_entities", default=False, 
        action="store_true", help="Whether or not to model entities without\
                incoming edges as a label.")
    args = parser.parse_args()

    main(args)