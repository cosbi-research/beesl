import os
import shutil
import argparse
import itertools


TOKEN_MIN_CHARS = 2
DOC_ID_KEY = "# doc_id = "
ENT_TYPES = ["B-Protein", "B-Entity"]
USE_TAGS = True


def is_empty_line(line):
    return (len(line) <= TOKEN_MIN_CHARS)


def get_doc_id(line):
    return line.rstrip("\n").split(DOC_ID_KEY)[1]


def struct_to_single_label(label):
    new_label = ""
    # O{}O
    if label == constants.TOK_OUTSIDE + constants.SEP_LABEL_TASK + constants.TOK_OUTSIDE:
        new_label += constants.TOK_OUTSIDE
    else:
        # B-T{}B-Positive_regulation, B-E|+1{}B-Protein|Theme
        structure, labels = label.split(constants.SEP_LABEL_TASK)
        if constants.SEP_LABEL_PART not in structure: # i.e., token without head
            if constants.SEP_LABEL_PART in labels:
                new_label += constants.TOK_OUTSIDE
                print("INCONSISTENCY:", label, "-->", new_label)
            else:
                new_label += labels + constants.SEP_LABEL_PART + constants.TOK_OUTSIDE

        else: # i.e., token with head
            if not constants.SEP_LABEL_PART in labels:
                if labels == constants.TOK_OUTSIDE: # not typed
                    new_label += constants.TOK_OUTSIDE
                    print("INCONSISTENCY:", label, "-->", new_label)
                else: # only type of the entity/trigger
                    new_label += labels + constants.SEP_LABEL_PART + constants.TOK_OUTSIDE
                    print("INCONSISTENCY:", label, "-->", new_label)
            else:
                m_tag, head_pos = structure.split(constants.SEP_LABEL_PART)
                m_type, head_type = labels.split(constants.SEP_LABEL_PART)
                if m_tag == "B-E":
                    # assert m_type is an entity
                    pass
                elif m_tag == "B-T":
                    # assert m_type is a trigger
                    pass
                else:
                    print(m_tag, "unrecognized.")
                new_label += m_type + constants.SEP_LABEL_PART
                new_label += head_type + constants.SEP_LABEL_PART
                new_label += "[UNK]" + constants.SEP_LABEL_PART + head_pos

    #print(label, "-->", new_label)
    return new_label


def get_token_info(line, encoding):
    splits = line.rstrip("\n").split(constants.SEP_COLUMN)
    word = splits[0]
    span = splits[1]
    ent_id = splits[2]
    if encoding == "struct":
        label = struct_to_single_label(splits[-1])
    else:
        label = splits[-1]

    #ent = splits[3][5:]
    #pos = splits[4][5:]
    #dep = splits[5][5:]
    return word, span, ent_id, label


def is_mention(mention_label):
    if mention_label is not constants.TOK_OUTSIDE:
        return True
    return False


def is_trigger(mention_label):
    if is_mention(mention_label) and (mention_label not in ENT_TYPES):
        return True
    return False


def is_entity(mention_label):
    if is_mention(mention_label) and (mention_label in ENT_TYPES):
        return True
    return False


def is_argument(argument_label):
    if argument_label is not constants.TOK_OUTSIDE:
        return True
    return False


def get_annotations(tokens_attrs, trigger_id, event_id, doc_id):
    entities = []
    triggers = []
    events_idx = []

    # Variables used to detect and consider once the multi-token triggers
    m_id_prev = -1
    m_start_prev = -1
    m_end_prev = -1
    m_label_prev = None
    m_rel_position = None

    ent_already_present = []
    tri_already_present = []

    # t_attr_idx = 0
    for t_attr in tokens_attrs:
        m_text = t_attr[1]
        m_id = t_attr[3]
        #m_label = t_attr[4].split(constants.SEP_LABEL_PART)[0]
        raw_label = t_attr[4]
        labels = []

        if constants.SEP_MULTIPLE_INNER in raw_label:
            # e.g., B-Protein|Theme|Gene_expression|+1$B-Protein|Theme|Transcription|+1
            mheads = raw_label.split(constants.SEP_MULTIPLE_INNER)
            for i in range(0, len(mheads)):
                labels.append(mheads[i])
        else:
            labels = [raw_label]

        # t_attr[3] == entity ID
        # if (m_label.startswith("B-Protein|")) and (t_attr[3] == constants.TOK_OUTSIDE):
        #     print("{}: This is not a gold-standard entity: [{}]!".format(doc_id, m_text))
        #     pass

        label_index = 0
        for label in labels:
            # Avoid to insert twice the same trigger/event in multi-head inputs
            if label_index > 0: continue

            m_label = label.split(constants.SEP_LABEL_PART)[0]

            # The token is an entity. Build an entity object
            if is_entity(m_label):
                m_start, m_end = t_attr[2].split(constants.SEP_SPAN)
                m_label = m_label[2:] if USE_TAGS else m_label
                if m_id not in ent_already_present:
                    entity = EntityMention(m_id, m_label, m_start, m_end, m_text)
                    entities.append(entity)
                ent_already_present.append(m_id)
                #entity = EntityMention(m_id, m_label, m_start, m_end, m_text)
                #entities.append(entity)

            # The token is a trigger. Build trigger and (partial) event objects
            elif is_trigger(m_label):
                m_start, m_end = t_attr[2].split(constants.SEP_SPAN)
                m_label = m_label[2:] if USE_TAGS else m_label
                #m_rel_position = t_attr[4].split(constants.SEP_LABEL_PART)[-1]
                m_rel_position = label.split(constants.SEP_LABEL_PART)[-1]

                # CASE contiguous multi-token trigger (predicted)
                # Keeping attention to contiguous non-same triggers (using position)
                if (int(m_start) == m_end_prev+1) and (m_label == m_label_prev) and (m_rel_position == m_rel_position_prev):
                    is_contiguous = True
                # CASE all the other cases (reinitialize variables for later use)
                else:
                    is_contiguous = False
                    prev_triggers_idx = []
                    # prev_events_idx = []

                # If this token is part of a previous one, update the trigger
                # information. Note that event information remains the same.
                if is_contiguous:
                    # assert len(prev_triggers_idx) == len(prev_events_idx)

                    # Update each trigger type relative to the previous token
                    for idx in prev_triggers_idx:
                        triggers[idx].text = triggers[idx].text + " " + m_text
                        triggers[idx].end = m_end

                # If the token has multiple trigger labels, handle it
                if constants.SEP_MULTIPLE in m_label:
                    m_labels = m_label.split(constants.SEP_MULTIPLE)

                    # Print a message for unlikely cases that could happen with other corpora
                    if len(m_labels) > 2:
                        pass
                        # print("WARNING: More than 2 labels for the same trigger. Handle it.")
                else:
                    m_labels = [m_label]

                if not is_contiguous:
                    # For each label, create a trigger and a (partial) event object
                    for label in m_labels:
                        m_id = "T" + str(trigger_id)
                        e_id = "E" + str(event_id)

                        if m_id not in tri_already_present:
                            trigger = TriggerMention(m_id, label, m_start, m_end, m_text)
                            event = Event(e_id, label, m_id, None, None, None)
                            triggers.append(trigger)
                        tri_already_present.append(m_id)
                        # trigger = TriggerMention(m_id, label, m_start, m_end, m_text)
                        # event = Event(e_id, label, m_id, None, None, None)
                        # triggers.append(trigger)

                        # Update the ID on token_attrs to use it for event-event later
                        t_attr[3] = e_id

                        # Set a flag to track multiple events on the same token ID
                        is_idx_duplicate = False
                        for idx in events_idx:
                            if idx[0] == t_attr[0]:
                                is_idx_duplicate = True
                                break

                        # Change the token ID if two events are on the same token ID
                        if not is_idx_duplicate:
                            events_idx.append((t_attr[0], event))
                        else:
                            events_idx.append((t_attr[0] + 0.1, event))

                        prev_triggers_idx.append(len(triggers)-1)
                        # prev_events_idx.append(len(events_idx)-1)
                        trigger_id += 1
                        event_id += 1

                # Update the variables for multi-token triggers
                m_start_prev = int(m_start)
                m_end_prev = int(m_end)
                m_label_prev = m_label
                m_rel_position_prev = m_rel_position

            # The token is neither an entity nor a trigger
            else:
                pass

            label_index += 1

    return entities, triggers, events_idx, trigger_id, event_id


def update_left_right_lists(i, left_idx, right_idx):
    if right_idx:
        if (i >= right_idx[0]):
            left_idx.insert(0, right_idx[0])
            right_idx.pop(0)


def parse_token_label(label):
    raw_parts = label.split(constants.SEP_LABEL_PART)

    # Case "O"
    if len(raw_parts) == 1:
        return [constants.TOK_OUTSIDE, constants.TOK_OUTSIDE, constants.TOK_OUTSIDE, constants.TOK_OUTSIDE]
    # Case "[TYPE]|O"
    elif len(raw_parts) == 2:
        return [raw_parts[0], constants.TOK_OUTSIDE, constants.TOK_OUTSIDE, constants.TOK_OUTSIDE]
    else:
        return raw_parts


def attach_argument(idx_list, hops, events_idx, token_info, encoding, bind_only_tri):

    def filter_idx_list_by_type(idx_list, events_idx, tok_id, src_type, encoding, bind_only_tri):
        """Keep in the copied list the IDs referring to type of interest"""
        idx_list_by_type = idx_list.copy()

        if encoding != "struct":
            # For each ID on the list to consider, check the event trigger idx
            for idx in idx_list:
                for event_idx in events_idx:
                    # Normalize Binding[1|N|K|S] (@TODO: Generalize)
                    if (bind_only_tri == "yes") and (event_idx[1].type_.startswith("Binding")):
                        type_ = "Binding"
                    else:
                        type_ = event_idx[1].type_

                    # If the event trigger idx has different type, remove it
                    if (event_idx[0] == idx) and (type_ != src_type):
                        if idx in idx_list_by_type:
                            idx_list_by_type.remove(idx)

        # Remove event trigger idx that are the same of the current token or an alias (i.1)
        idx_list_by_type = [idx for idx in idx_list_by_type if ((idx != tok_id) and (idx != tok_id+0.1))]

        return idx_list_by_type


    # Filter the list of event trigger idx by type, and get the source index
    tok_id, text, span, id_, trg_type, arg, src_type, _ = token_info
    idx_list_by_type = filter_idx_list_by_type(idx_list, events_idx, tok_id, src_type, encoding, bind_only_tri)

    if len(idx_list_by_type) < hops:
        pass
        # print("Not enough hops in the sentence!", tok_id, text, span)
        # print(idx_list_by_type)
    else:
        src_tok_id = idx_list_by_type[hops-1]

        # print("Before filtering candidate source IDs", idx_list)
        # print("Analyzing target", token_info)
        # print("Among potential sources", idx_list_by_type, "we identified", src_tok_id, "at", hops, "hops")

        # Add the arguments to the (partial) event objects
        for event_idx in events_idx:
            if event_idx[0] == src_tok_id:
                # print("->", src_tok_id, "has been found")
                # If no edges are present yet, create a list with the element
                if event_idx[1].edge_types is None:
                    # Handling due to merging of multi-token triggers (@TODO: Other solutions?)
                    # the id_ is the column about the gold standard entity. If no one is present, do not add it
                    if id_ != constants.TOK_OUTSIDE:
                        # print("-> so assign", (span, id_, trg_type, arg, src_type), "to the event", event_idx[1].id_, event_idx[1].start_id, "\n")
                        event_idx[1].edge_types = [(span, id_, trg_type, arg, src_type)]
                # Otherwise, append it instead
                else:
                    # Handling due to merging of multi-token triggers (@TODO: Other solutions?)
                    if id_ != constants.TOK_OUTSIDE:
                        event_idx[1].edge_types.append((span, id_, trg_type, arg, src_type))

def decode(args_filepath, args_encoding="single", args_bind_strategy="strategy", 
    args_use_dummy_args="no", args_preg_pp="yes", bind_only_tri="no"):
    documents = {}
    token_attrs = []
    token_id = 0
    trigger_id = 1001
    event_id = 1
    event_id_unmerged = 1001
    event_id_unmerged_two = 2001
    pp_e_id = 9001
    triggers_idx = 0
    overlapping_types = {}

    with open(args_filepath, "r") as f:
        for line in f:
            if not is_empty_line(line):
                # If the line is a doc_id, store it
                if line.startswith(DOC_ID_KEY):
                    doc_id = get_doc_id(line)
                    if doc_id not in documents:
                        documents[doc_id] = {}
                        documents[doc_id]["triggers"] = []
                        documents[doc_id]["events"] = []
                        trigger_id = 1001
                        event_id = 1
                        event_id_unmerged = 1001
                        event_id_unmerged_two = 2001
                        pp_e_id = 9001
                        triggers_idx = 0
                    continue

                # O.w., get the info and add the token to the list
                word, span, ent_id, label = get_token_info(line, args_encoding)
                token_attrs.append([token_id, word, span, ent_id, label])
                token_id += 1

            else:
                entities, triggers, events_idx, trigger_id, event_id = get_annotations(
                    token_attrs, trigger_id, event_id, doc_id)

                # for entity in entities:
                #     print(entity.id_, entity.type_, entity.start, entity.end, entity.text)

                for trigger_ in triggers:
                    trigger_ = trigger_.id_ + "\t" + trigger_.type_ + " " + trigger_.start + " " + trigger_.end + "\t" + trigger_.text
                    documents[doc_id]["triggers"].append(trigger_)
                    # print("{}\t{} {} {}\t{}".format(trigger.id_, trigger.type_, trigger.start, trigger.end, trigger.text))

                # print(events_idx)

                # Build the left/right lists of token IDs for event triggers
                left_idx = []
                right_idx = [e_idx[0] for e_idx in events_idx]
                #print("index 0", left_idx, right_idx)

                # Iterate over tokens to assign arguments to events
                for i in range(len(token_attrs)):
                    # Update the lists of event trigger idx to the sides
                    update_left_right_lists(i, left_idx, right_idx)
                    #print("index", i, left_idx, right_idx)

                    # Get the information about the current (target) token
                    #label = token_attrs[i][4]
                    left_part = token_attrs[i][:4] # e.g., [9, 'I kappa B alpha', '424-439', 'T3']
                    raw_label = token_attrs[i][4]
                    labels = []
                    if constants.SEP_MULTIPLE_INNER in raw_label:
                        # e.g., B-Protein|Theme|Gene_expression|+1$B-Protein|Theme|Transcription|+1
                        mheads = raw_label.split(constants.SEP_MULTIPLE_INNER)

                        # for single-task only
                        # keep all mention types even if they are different
                        # check if there are redundant cases and remove them
                        # todo: generalize to 2+ cases
                        to_remove = None
                        merge = False
                        for i in range(1, len(mheads)):
                            # if both are the same mention types
                            if (len(mheads[i-1].split("|")) == 2) and (len(mheads[i].split("|")) == 4):
                                if mheads[i-1].split("|")[0] == mheads[i].split("|")[0]:
                                    # keep the second
                                    to_remove = 0
                            elif (len(mheads[i-1].split("|")) == 4) and (len(mheads[i].split("|")) == 2):
                                if mheads[i-1].split("|")[0] == mheads[i].split("|")[0]:
                                    # keep the first
                                    to_remove = 1
                            # if they are different merge them
                            elif (len(mheads[i-1].split("|")) == 2) and (len(mheads[i].split("|")) == 2):
                                merge = True
                            else:
                                pass
                        if to_remove is not None:
                            del mheads[to_remove]
                        if merge:
                            mheads[0] = mheads[0].split("|")[0] + "////" + mheads[1]
                            del mheads[1]

                        # Remove multiheads with same head
                        to_keep = "Cause" # "Cause"
                        found_labels = {}
                        indices_to_ignore = []
                        for i in range(0, len(mheads)):
                            mheads_splitted = mheads[i].split("|")

                            # for single task
                            if len(mheads_splitted) == 2:
                                continue

                            key = mheads_splitted[0][2:] + "|" + mheads_splitted[2] + "|" + mheads_splitted[3]
                            if key not in found_labels:
                                found_labels[key] = mheads_splitted[1] + "_" + str(i)
                            else:
                                if to_keep == "Theme":
                                    if found_labels[key].split("_")[0] == "Theme":
                                        indices_to_ignore.append(i)
                                    elif found_labels[key].split("_")[0] == "Cause":
                                        indices_to_ignore.append(int(found_labels[key].split("_")[1]))
                                        found_labels[key] = mheads[i][1] + "_" + str(i)
                                    else:
                                        pass
                                elif to_keep == "Cause":
                                    if found_labels[key].split("_")[0] == "Cause":
                                        indices_to_ignore.append(i)
                                    elif found_labels[key].split("_")[0] == "Theme":
                                        indices_to_ignore.append(int(found_labels[key].split("_")[1]))
                                        found_labels[key] = mheads[i][1] + "_" + str(i)
                                    else:
                                        pass
                                else:
                                    print("WARNING: unrecognized edge type.")

                        for i in range(0, len(mheads)):
                            if i not in indices_to_ignore:
                                labels.append(mheads[i])
                    else:
                        labels = [raw_label]

                    for label in labels:
                        token_labels_list = parse_token_label(label)
                        trg_type, arg, src_type, pos = token_labels_list
                        token_info = left_part + token_labels_list

                    # token_labels_list = parse_token_label(label)
                    # trg_type, arg, src_type, pos = token_labels_list
                    # token_info = token_attrs[i][:4] + token_labels_list

                        # If the token is an argument of a source, analyze it
                        if is_argument(arg):
                            trg_position = pos[0]
                            hops = int(pos[1])

                            # Choose which list of event trigger idx to check
                            if trg_position == "-":
                                idx_list = left_idx
                            elif trg_position == "+":
                                idx_list = right_idx
                            else:
                                print("WARNING. trg_position is not '+' or '-'.")

                            #print("__before", idx_list)
                            attach_argument(idx_list, hops, events_idx, token_info, args_encoding, bind_only_tri)
                            #print("__after", idx_list)

                        # O.w., no argument is found. Go to the next token
                        else:
                            pass

                # print("__before", events_idx)
                empty_events = []
                for event in events_idx:
                    if event[1].edge_types == None:
                        empty_events.append(event)
                
                #for empty_event in empty_events:
                #    events_idx.remove(empty_event)
                # print("__after", events_idx)

                raw_events = []
                for event in events_idx:
                    event_string = ""
                    e_id = event[1].id_
                    e_type = event[1].type_
                    t_id = event[1].start_id
                    curr_event = e_id + "\t" + e_type + ":" + t_id
                    # print("{}\t{}:{}".format(e_id, e_type, t_id), end="")
                    event_string += "{}\t{}:{}".format(e_id, e_type, t_id)

                    if event[1].edge_types is not None:
                        for argument in event[1].edge_types:
                            curr_event += " " + argument[3] + ":" + argument[1]
                            # print(" {}:{}".format(argument[3], argument[1]), end="")
                            event_string += " {}:{}".format(argument[3], argument[1])
                        raw_events.append(event_string)
                        # print()

                    # Case trigger with no arguments (e.g., because on cross-sentence edges)
                    else:
                        # Add a dummy argument, if specified
                        if args_use_dummy_args == "yes":
                            event_string += " {}".format("Theme:T1")
                            raw_events.append(event_string)

                # Here goes the unmerging strategy
                raw_events_norm = {}
                events_unmerged = []
                for i in range(len(raw_events)):
                    # print("Analyzing", raw_events[i])

                    causes = []
                    themes = []
                    _e_id, content = raw_events[i].split("\t")

                    if " " in content: # i.e., if we have arguments
                        raw_trigger, raw_arguments = content.split(" ", 1)
                        _e_type, _t_id = raw_trigger.split(":")
                        arguments = raw_arguments.split(" ")

                        for argument in arguments:
                            if argument.split(":")[0] == "Cause":
                                causes.append(argument)
                            elif argument.split(":")[0] == "Theme":
                                themes.append(argument)

                    multiple_causes = True if (len(causes) > 1) else False
                    multiple_themes = True if (len(themes) > 1) else False
                    #is_binding = True if (_e_type == "Binding") else False
                    is_binding = True if (_e_type.startswith("Binding")) else False

                    # If we have no redundant arguments, add the event as is
                    if (not multiple_causes) and (not multiple_themes): # or nothing
                        # @TODO: Invert arguments if Cause < Theme
                        # documents[doc_id]["events"].append(raw_events[i])
                        events_unmerged.append(raw_events[i])

                    # O.w. checks for both causes and themes are needed
                    else:
                        assert _e_id not in raw_events_norm
                        raw_events_norm[_e_id] = []

                        if multiple_causes and (not multiple_themes):
                            for cause_arg in causes:
                                e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
                                if len(themes) > 0:
                                    e_curr += " {}".format(themes[0])
                                e_curr += " {}".format(cause_arg)

                                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                                # documents[doc_id]["events"].append(e_curr)
                                events_unmerged.append(e_curr)
                                event_id_unmerged += 1

                                # print(e_curr)

                        elif multiple_themes and (not multiple_causes):
                            if not is_binding:
                                for theme_arg in themes:
                                    e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
                                    e_curr += " {}".format(theme_arg)
                                    if len(causes) > 0:
                                        e_curr += " {}".format(causes[0])

                                    raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                                    # documents[doc_id]["events"].append(e_curr)
                                    events_unmerged.append(e_curr)
                                    event_id_unmerged += 1

                                    # print(e_curr)
                            else:
                                event_id_unmerged, events_unmerged, raw_events_norm = unmerge_binding_event(args_bind_strategy, themes, event_id_unmerged, raw_trigger, raw_events_norm, _e_id, events_unmerged, token_attrs)#, nlp)

                        else:
                            if not is_binding:
                                combinations = list(itertools.product(themes, causes))
                                for combination in combinations:
                                    e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
                                    e_curr += " {} {}".format(combination[0], combination[1])

                                    raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                                    # documents[doc_id]["events"].append(e_curr)
                                    events_unmerged.append(e_curr)
                                    event_id_unmerged += 1

                                    # print(e_curr)
                            else:
                                print("Note that Binding events have no Causes! Skipping.")

                # (Iterative) normalization of unreferenced events

                # print()
                # print("="*80)
                # print("="*80)
                # for raw_event in raw_events:
                #     print("*", raw_event)

                are_unref_args = True   # flag to know when to stop updating
                ids_to_remove = []
                #dict_of_ok_events = {}

                # If there are unreferenced arguments, update them
                events_unmerged = events_unmerged.copy()
                count = 0
                while are_unref_args:
                    # Keep track of the keys to check/substitute in this iteration
                    # to remove at the end, i.e., to prepare for the next iteration
                    # raw_events_norm: {'E1': ['E1001'], 'E4': ['E1002', 'E1003']}, i.e., the list of substituted IDs (also from prev stage)
                    prev_args_id = list(raw_events_norm.keys())

                    changed_events = {}
                    tmp_final = []

                    # print("="*80)
                    # print("Iteration. Check if {} are referenced.".format(prev_args_id))
                    # print("--> if so, substitute them as follows: {}.\n".format(raw_events_norm))

                    # print("EVENTS TO CHECK:")
                    # for event_unmerged in events_unmerged:
                    #     print("\t[[ {} ]]".format(event_unmerged))
                    # print()

                    # For each event, check if it needs to be updated
                    for event_unmerged in events_unmerged:
                        #print("Checking [[ {} ]].".format(event_unmerged))
                        
                        args_ok = []
                        args_to_reference = []

                        _e_id, content = event_unmerged.split("\t")

                        if " " in content: # i.e., if we have arguments
                            raw_trigger, raw_arguments = content.split(" ", 1)
                            _e_type, _t_id = raw_trigger.split(":")
                            arguments = raw_arguments.split(" ")

                            for argument in arguments:
                                arg_type, arg_id = argument.split(":")

                                if arg_id in raw_events_norm.keys():
                                    num_of_splits = len(raw_events_norm[arg_id])
                                    #print(arg_id, "to be splitted", num_of_splits, "times, into: ", arg_type, raw_events_norm[arg_id])

                                    curr_targets = []
                                    for new_e_ids in raw_events_norm[arg_id]:
                                        curr_targets.append("{}:{}".format(arg_type, new_e_ids))
                                    args_to_reference.append(curr_targets)

                                    ids_to_remove.append(_e_id)
                                else:
                                    args_ok.append(argument)


                        if len(args_to_reference) > 0:
                            raw_events_norm[_e_id] = []
                            changed_events[event_unmerged] = []

                            for combinations in itertools.product(*args_to_reference):
                                event_str = "E{}\t{}".format(event_id_unmerged_two, raw_trigger)
                                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged_two))

                                themes = []
                                causes = []
                                for arg_ok in args_ok:
                                    if arg_ok.split(":")[0] == "Theme":
                                        themes.append(arg_ok)
                                    elif arg_ok.split(":")[0] == "Cause":
                                        causes.append(arg_ok)
                                    else:
                                        pass

                                for combination in combinations:
                                    if combination.split(":")[0] == "Theme":
                                        themes.append(combination)
                                    elif combination.split(":")[0] == "Cause":
                                        causes.append(combination)
                                    else:
                                        pass

                                for theme in themes:
                                    event_str += " {}".format(theme)
                                for cause in causes:
                                    event_str += " {}".format(cause)

                                tmp_final.append(event_str)
                                #documents[doc_id]["events"].append(event_str)
                                changed_events[event_unmerged].append(event_str)
                                event_id_unmerged_two += 1

                        else:
                            tmp_final.append(event_unmerged)
                            #dict_of_ok_events[_e_id] = event_unmerged


                    # Remove for next iterations
                    for arg_id in prev_args_id:
                        del raw_events_norm[arg_id]

                    # Add to events_unmerged
                    for old, new_list in changed_events.items():
                        # print("delete", old)
                        events_unmerged.remove(old)
                        for new in new_list:
                            events_unmerged.append(new)

                    # print("\nFINAL OF ITERATION") # the events created
                    # for tmp in tmp_final:
                    #     print(tmp)
                    # print()
                    
                    if len(raw_events_norm) > 0:
                        are_unref_args = True
                    else:
                        are_unref_args = False

                    # Add final events
                    nothing_to_change = True
                    for tmp in tmp_final: # the candidates
                        to_be_changed = False
                        # get args
                        raw_args = tmp.split("\t")[1].split(" ")[1:]
                        for raw_arg in raw_args:
                            arg_type, arg_id = raw_arg.split(":")

                            for next_id in raw_events_norm: # the IDs to be changed in the next iteration
                                if arg_id == next_id:
                                    to_be_changed = True
                                    nothing_to_change = False

                        if not to_be_changed:
                            # To avoid infinite loop in evaluation where Themes are not present
                            # This doesn't affect the scores since these events are already wrong
                            # (i.e., they have only Cause), so they would impact precision in any case
                            if "Theme" not in tmp:
                                pass
                                #print(tmp)
                                #documents[doc_id]["events"].append(tmp + " Theme:T1")
                            else:
                                documents[doc_id]["events"].append(tmp)
                            events_unmerged.remove(tmp)

                    if nothing_to_change:
                        are_unref_args = False

                    count += 1
                    if count > 5:
                        print("Probable infinite loop. Skipping.")
                        are_unref_args = False
                # Add only the events (accumulated after the iterations) that are in their final form
                #for k, v in dict_of_ok_events.items():
                #    if k not in ids_to_remove:
                #        documents[doc_id]["events"].append(v)

                # print("\n\nAT THE END...\n=====\n")
                # for x in documents[doc_id]["events"]:
                #     print(x)

                # REMOVE ORPHAN EVENTS
                # solves both:
                # unknown reference: [PMID-9804806] E2006 => E5
                # Only a protein or a event can be a Theme or a Cause for a regulation event: [PMID-9804806] E2006 => Theme:E5
                removed_orphan_ids = []
                is_first_iter = True
                while (is_first_iter or (len(removed_orphan_ids) > 0)):
                    removed_orphan_ids = []
                    is_first_iter = False

                    e_ids_list = []
                    args_list = []
                    for event_string in documents[doc_id]["events"]:
                        e_id, e_content = event_string.split("\t")
                        raw_args = e_content.split(" ")[1:]
                        arg_ids = raw_args #[arg.split(":")[1] for arg in raw_args]
                        e_ids_list.append(e_id)
                        args_list.append(arg_ids)

                    offset = 0 # track the number of deleted events to recompute the index
                    # For each list of event arguments (index=event_no, event_args=[E3, E1])
                    for index, event_args in enumerate(args_list):
                        for event_arg in event_args:
                            event_arg_type, event_arg_id = event_arg.split(":")
                            # If the arg is an event, and it is not included in the final list of events, delete that event (e.g., E3)
                            if ((event_arg_id not in e_ids_list) and (not event_arg_id.startswith("T"))):
                                # Remove the ith event (with updated index w.r.t. previous removals)
                                # print("Removing orphan event {}...".format(documents[doc_id]["events"][index-offset]))
                                removed_orphan_ids.append(documents[doc_id]["events"][index-offset].split("\t")[0])
                                documents[doc_id]["events"].pop(index-offset)
                                offset += 1
                                break # avoid removing the following event if multiple arguments are not included in the final events we are checking


                #print("new sentence")


                # POSTPROCESSING
                #print("===NEW SENTENCE")
                #for i in range(len(documents[doc_id]["events"])):
                #    print("Event #{}: {}".format(i, documents[doc_id]["events"][i]))

                if args_preg_pp == "yes":
                    # Make a copy of triggers with a sentence-level index to avoid reiterating the same triggers
                    triggers = documents[doc_id]["triggers"][triggers_idx:]

                    prev_t_content = None
                    prev_t_type = None
                    prev_t_id = None
                    for trigger in triggers:
                        #print("Checking {}".format(trigger))
                        t_id, t_raw_content = trigger.split("\t", 1)
                        t_type, t_content = t_raw_content.split(" ", 1)

                        valid_pairs = [
                            ("Gene_expression", "Positive_regulation"),
                            ("Phosphorylation", "Positive_regulation"),
                            ("Phosphorylation", "Negative_regulation")
                        ]

                        is_overlapping = True if (t_content == prev_t_content) else False

                        for pair in valid_pairs:
                            is_trg_src = True if ((t_type == pair[0]) and (prev_t_type == pair[1])) else False
                            is_src_trg = True if ((t_type == pair[1]) and (prev_t_type == pair[0])) else False

                            if is_trg_src or is_src_trg:
                                src_type = pair[1]
                                trg_type = pair[0]
                                break

                        if is_overlapping and (is_trg_src or is_src_trg):

                            # Decide which trigger to consider as source or target
                            if is_src_trg:
                                source_id = t_id
                                target_id = prev_t_id
                            else:
                                source_id = prev_t_id
                                target_id = t_id

                            # Retrieve the target event ID
                            trg_event_ids = search_event_by_trigger(target_id, documents[doc_id]["events"]) # trg

                            # If the target trigger has not an associated event yet
                            if len(trg_event_ids) == 0:
                                # Create an event for it
                                # However, data suggests that target triggers without events are the cross-sentence ones, so it could increase FPs
                                pass

                            # If the target trigger has already associated an event
                            if len(trg_event_ids) > 0:

                                # Retrieve the source event ID
                                src_event_ids = search_event_by_trigger(source_id, documents[doc_id]["events"])
                                    
                                # In the case we already have an event for the source, use it
                                if len(src_event_ids) > 0:

                                    # For each ID, attach the new argument(s)
                                    for e_id in src_event_ids:
                                        # NOTE: the only one already existing is not connected so could increase FPs
                                        # But for instance, for +Reg->Phospho the two examples fall here

                                        #print(doc_id)
                                        # Create N events (based on len of trg_event_id?)

                                        #e_strings, indexes = search_event_string(e_id, documents[doc_id]["events"])
                                        #print("found", e_strings, indexes)
                                        # e_string = modify_event_string(e_string)
                                            
                                        # substitute_event_string(e_string, index)
                                        pass

                                # Otherwise, we need to create an event for the source
                                else:
                                    #print("  -> Need to create a new event for this +REG trigger towards {}.".format(trg_event_ids))
                                    for trg_event_id in trg_event_ids:
                                        e = "E{}\t{}:{} Theme:{}".format(pp_e_id, src_type, source_id, trg_event_id)
                                        #print("    -> Created: {}.".format(e))
                                        documents[doc_id]["events"].append(e)

                                        pp_e_id += 1

                        else:
                            pass


                        prev_t_content = t_content
                        prev_t_type = t_type
                        prev_t_id = t_id

                    # Update the sentence-level index to subset the triggers to check
                    triggers_idx = len(documents[doc_id]["triggers"])
                    #print()


                token_id = 0
                token_attrs = []


    output_dir = os.path.dirname(args_filepath)
    output_decoded = os.path.join(output_dir, "output")
    if os.path.exists(output_decoded):
        shutil.rmtree(output_decoded)
    os.makedirs(output_decoded)

    for id_, content in documents.items():
        with open(os.path.join(output_decoded, id_ + ".a2"), "w") as f:
        # with open("output/" + id_ + ".a2", "w") as f:
            for trigger_ in content["triggers"]:
                parts = trigger_.split("\t", 2)
                tri_type, other = parts[1].split(" ", 1)
                if tri_type in ["Binding1", "BindingK", "BindingN", "BindingS"]:
                    tri_type = "Binding"
                f.write(parts[0] + "\t" + tri_type + " " + other + "\t" + parts[2] + "\n")
                # f.write(trigger_ + "\n")
            for event_ in content["events"]:
                # print("RAW", event_)
                ev_id, ev_content = event_.split("\t")
                raw_ev_type, other = ev_content.split(" ", 1)
                event_type, trigger_id = raw_ev_type.split(":")
                if event_type in ["Binding1", "BindingK", "BindingN", "BindingS"]:
                    event_type = "Binding"
                f.write(ev_id + "\t" + event_type + ":" + trigger_id + " " + other + "\n")
                # print("NEW", ev_id + "\t" + event_type + ":" + trigger_id + " " + other + "\n")
                # f.write(event_ + "\n")


def unmerge_binding_event(bind_strategy, themes, event_id_unmerged, raw_trigger, raw_events_norm, _e_id, events_unmerged, token_attrs):#, nlp):

    def build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation):
        if operation == "1:N":
            number = ""
            binding_type, binding_id = raw_trigger.split(":")
            norm_raw_trigger = binding_type + ":" + binding_id
            e_curr = "E{}\t{}".format(event_id_unmerged, norm_raw_trigger)
            i = 1
            for theme in themes:
                if i > 1:
                    number = str(i)
                theme_name, theme_id = theme.split(":")
                e_curr += " {}".format(theme_name + number + ":" + theme_id)
                i += 1
                if i > 5: # avoid blocking on Theme6 for eval script
                    break

            raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
            events_unmerged.append(e_curr)
            event_id_unmerged += 1

        elif operation == "L:N":
            theme_left = themes[0]
            for theme in themes[1:]:
                e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
                e_curr += " {} {}".format(theme_left, "Theme2:" + theme.split(":")[1])
                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                events_unmerged.append(e_curr)
                event_id_unmerged += 1

        elif operation == "R:N":
            theme_left = themes[-1]
            for theme in themes[:-1]:
                e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
                e_curr += " {} {}".format(theme_left, "Theme2:" + theme.split(":")[1])
                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                events_unmerged.append(e_curr)
                event_id_unmerged += 1

        elif operation == "1:1":
            for theme in themes:
                binding_type, binding_id = raw_trigger.split(":")
                norm_raw_trigger = binding_type + ":" + binding_id
                e_curr = "E{}\t{}".format(event_id_unmerged, norm_raw_trigger)
                e_curr += " {}".format(theme)
                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                events_unmerged.append(e_curr)
                event_id_unmerged += 1

        else:
            pass

        return event_id_unmerged


    if bind_strategy == "two":
        combinations = list(itertools.combinations(themes, 2))
        for combination in combinations:
            e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
            e_curr += " {} {}".format(combination[0], "Theme2:" + combination[1].split(":")[1])

            raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
            events_unmerged.append(e_curr)
            event_id_unmerged += 1

    elif bind_strategy == "positional":
        theme_left = themes[0]
        for theme in themes[1:]:
            e_curr = "E{}\t{}".format(event_id_unmerged, raw_trigger)
            e_curr += " {} {}".format(theme_left, "Theme2:" + theme.split(":")[1])
            
            raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
            events_unmerged.append(e_curr)
            event_id_unmerged += 1

    elif bind_strategy == "strategy":
        theme_indices = []
        theme_ids = [theme.split(":")[1] for theme in themes]
        trigger_index = None
        left_themes = []
        right_themes = []
        case_dict = {}
        case_dict["of"] = []
        case_dict["to"] = []
        case_dict["with"] = []
        case_dict_list = []
        masked_list = [None] * len(token_attrs)
        last_theme_index = None

        is_trigger_found = False ###
        case_list = ["of", "to", "with"]
        case_list_found = set() ###

        # Store the trigger index and the themes indices
        for token_attr in token_attrs:
            token_id = token_attr[0]
            token_text = token_attr[1]
            mention_id = token_attr[3]

            if mention_id in theme_ids:
                theme_indices.append(token_id)
                masked_list[token_id] = "Theme"
            elif mention_id == _e_id:
                trigger_index = token_id
                masked_list[token_id] = "TRIGGER"
                is_trigger_found = True ###
            else:
                pass

            if token_text in case_list:
                case_dict[token_text].append(token_id)
                if token_text not in case_list_found: ###
                    case_dict_list.append(token_id)
                    masked_list[token_id] = token_text

                if is_trigger_found: case_list_found.add(token_text) ###

        # Create the lists on the left and on the right of the trigger
        for theme_index in theme_indices:
            if theme_index < trigger_index:
                left_themes.append(theme_index)
            elif theme_index > trigger_index:
                right_themes.append(theme_index)
                last_theme_index = theme_index
            else:
                print("WARNING: A token cannot be a trigger and a Theme!")


        both_sides = True if ((len(left_themes) != 0) and (len(right_themes) != 0)) else False
        only_left_side = True if (len(right_themes) == 0) else False
        only_right_side = True if (len(left_themes) == 0) else False
        window = 3

        if both_sides:
            if len(left_themes) == 1:
                event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="L:N")
            elif len(right_themes) == 1:
                event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="R:N")
            else:
                event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="1:N")
        else:
            is_followed_by_case_marker = False
            if "with" in masked_list[trigger_index+1 : trigger_index+1 + window]:
                is_followed_by_case_marker = True
            elif "to" in masked_list[trigger_index+1 : trigger_index+1 + window]:
                is_followed_by_case_marker = True
            else:
                pass

            case_dict_list_right = []
            if only_right_side:
                case_dict_list_right = [x for x in case_dict_list if (trigger_index < x < last_theme_index+1)] # Keep only the cases on the right and before the last theme

            are_two_case_markers_in_btw = True if (len(case_dict_list_right) >= 2) else False

            if only_left_side and is_followed_by_case_marker:
                event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="1:1")
            
            elif only_right_side and are_two_case_markers_in_btw:
                num_themes_in_segment_1 = masked_list[case_dict_list_right[0] + 1 : case_dict_list_right[1] + 1].count("Theme")
                if last_theme_index > case_dict_list_right[1]:
                    num_themes_in_segment_2 = masked_list[case_dict_list_right[1] + 1 : last_theme_index + 1].count("Theme")
                else:
                    num_themes_in_segment_2 = 0

                if (num_themes_in_segment_1==0) or (num_themes_in_segment_2==0):
                    event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="1:1")
                elif num_themes_in_segment_1==1:
                    event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="L:N")
                elif num_themes_in_segment_2==1:
                    event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="R:N")
                else:
                    event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="1:N")
          
            else:
                event_id_unmerged = build_event(raw_trigger, event_id_unmerged, themes, raw_events_norm, _e_id, events_unmerged, operation="1:N")

        

    elif bind_strategy == "encoded":
        binding_type, binding_id = raw_trigger.split(":")
        norm_raw_trigger = binding_type[:-1] + ":" + binding_id

        if (binding_type == "BindingN"): #or (binding_type == "BindingS"):
            for theme in themes:
                e_curr = "E{}\t{}".format(event_id_unmerged, norm_raw_trigger)
                e_curr += " {}".format(theme)
                
                raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
                events_unmerged.append(e_curr)
                event_id_unmerged += 1

        elif binding_type == "Binding1":
            number = ""
            e_curr = "E{}\t{}".format(event_id_unmerged, norm_raw_trigger)
            i = 1
            for theme in themes:
                if i > 1:
                    number = str(i)
                theme_name, theme_id = theme.split(":")
                e_curr += " {}".format(theme_name + number + ":" + theme_id)
                i += 1
                
            raw_events_norm[_e_id].append("E{}".format(event_id_unmerged))
            events_unmerged.append(e_curr)
            event_id_unmerged += 1

        else:
            pass

    else:
        print("Strategy not found for Binding events")

    return event_id_unmerged, events_unmerged, raw_events_norm


def get_sdp_path(doc, subj, obj, lca_matrix):
    # https://towardsdatascience.com/find-lowest-common-ancestor-subtree-and-shortest-dependency-path-with-spacy-only-32da4d107d7a
    lca = lca_matrix[subj, obj]
  
    current_node = doc[subj]
    subj_path = [current_node]
    if lca != -1: 
        if lca != subj: 
            while current_node.head.i != lca:
                current_node = current_node.head
                subj_path.append(current_node)
            subj_path.append(current_node.head)

    current_node = doc[obj]
    obj_path = [current_node]
    if lca != -1: 
        if lca != obj: 
            while current_node.head.i != lca:
                current_node = current_node.head
                obj_path.append(current_node)
            obj_path.append(current_node.head)
              
    return subj_path + obj_path[::-1][1:]


def search_event_string(e_id, events):
    e_strings = []
    indexes = []

    print("Searching event string for {}...".format(e_id))

    for i in range(len(events)):
        e_id_curr = events[i].split("\t")[0]
        if e_id == e_id_curr:
            e_strings.append(events[i])
            indexes.append(i)

    return e_strings, indexes


def search_event_by_trigger(t_id, events):
    event_ids = []

    for event in events:
        e_id, e_content = event.split("\t")
        e_info, e_args = e_content.split(" ", 1)
        e_type, e_t_id = e_info.split(":")

        if t_id == e_t_id:
            event_ids.append(e_id)

    return event_ids


if __name__ == "__main__":
    from utils import constants
    from utils.document import EntityMention, TriggerMention, Event

    parser = argparse.ArgumentParser()
    parser.add_argument("--filepath", default="data/dev-bee-test.st",
        help="The filepath of the document containing predictions to decode.")
    parser.add_argument("--encoding", default="single",
        help="The encoding to use to know how to decode.")
    parser.add_argument("--bind_strategy", default="strategy",
        help="The strategy to use to unfold Binding events.")
    parser.add_argument("--bind_only_tri", default="yes",
        help="The strategy to use to unfold Binding events.")
    parser.add_argument("--use_dummy_args", default="no", 
        help="Whether to include events without arguments and use a dummy \
              argument for them due to the cross-sentence edges they have \
              (would result in -Pr for its event type and +R for other \
              events connected to it.")
    parser.add_argument("--preg_pp", default="yes", 
        help="Whether to use postprocessing of self-argument events.")
    args = parser.parse_args()

    decode(args.filepath, args.encoding, args.bind_strategy, args.use_dummy_args, args.preg_pp, args.bind_only_tri)

else:
    from bioscripts.utils import constants
    from bioscripts.utils.document import EntityMention, TriggerMention, Event
