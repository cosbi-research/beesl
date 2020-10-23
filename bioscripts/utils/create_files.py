import os
from utils import constants, language
from utils.document import Edge


incomings = []

def create_annotations(documents, data_split, corpus, use_sec_entities,
    keep_ent_tokens, keep_orphan_entities, encoding, multihead, masking):

    EVENT_TYPES = constants.GE11_EVENT_TYPES
    output_labels = {}
    extra_info = "" #if multihead == False else ".mh"

    print("Setting the NLP environment...")
    nlp = language.set_nlp_environment(keep_ent_tokens)

    for document in documents:
        par_start_char = 0
        par_end_char = 0
        sent_id = 0

        # Retrieve document-level edges from the event object
        edges = parse_edges(document)

        print("Processing", document.doc_id)

        # Iterate over the paragraphs within the document object
        for paragraph in document.paragraphs:
            # Track relative paragraph "end position" within the document
            par_end_char = par_start_char + len(paragraph) + 1

            # Variable to track inter-paragraph offset of token indices to
            # correctly get the span information subtracting it when printing
            prev_token_num = 0

            # Retrieve entities/triggers/edges falling within the paragraph
            par_entities = filter_mentions(
                par_start_char, par_end_char, document.entities)
            par_triggers = filter_mentions(
                par_start_char, par_end_char, document.triggers, overlap=True)
            par_edges = filter_edges(
                par_entities, par_triggers, edges, use_sec_entities)

            # Create an NLP object and store the basic attributes
            paragraph = nlp.make_doc(paragraph)
            paragraph._.id = document.doc_id
            paragraph._.start_char = par_start_char
            paragraph._.entities = par_entities
            paragraph._.triggers = par_triggers
            paragraph._.edges = par_edges

            # Apply a pipeline of NLP components to the paragraph
            for name, proc in nlp.pipeline:
                doc = proc(paragraph)

            # For each sentence in the paragraph, build example objects
            for sentence in doc.sents:
                # Retrieve entities/triggers/edges falling within the sentence
                sent_entities, sent_triggers = get_sent_mentions(
                    sentence, paragraph._.entities, paragraph._.triggers)
                sent_edges = filter_edges(
                    sent_entities, sent_triggers, paragraph._.edges, 
                    use_sec_entities)

                # print("ORIGINAL")
                # for e in sent_edges:
                #     print(e.ev_id, e.ev_type, e.src_id, e.trg_id, e.ev_trg_id, e.arg_type)
                # print()
                
                # Create an inverted dictionary for the edges (key: target)
                trg_dict = {}
                for edge in sent_edges:
                    if edge.trg_id not in trg_dict.keys():
                        trg_dict[edge.trg_id] = edge
                    else:
                        # print("The token [[{}]] has multiple incomings. Merging them.".format(edge.trg_id))
                        # print("\tRetaining:   {}".format(trg_dict[edge.trg_id]))
                        # print("\tSkipping:    {} {} {} {} {} {}".format(edge.ev_id, edge.ev_type, edge.src_id, edge.trg_id, edge.ev_trg_id, edge.arg_type))

                        # Merge the information of other incoming edges
                        if edge.src_id not in trg_dict[edge.trg_id].src_id.split(constants.SEP_MULTIPLE):
                            trg_dict[edge.trg_id].ev_id = trg_dict[edge.trg_id].ev_id + constants.SEP_MULTIPLE + edge.ev_id
                            trg_dict[edge.trg_id].ev_type = trg_dict[edge.trg_id].ev_type + constants.SEP_MULTIPLE + edge.ev_type
                            trg_dict[edge.trg_id].src_id = trg_dict[edge.trg_id].src_id + constants.SEP_MULTIPLE + edge.src_id
                            
                            # Avoid concatenation of None with strings
                            if trg_dict[edge.trg_id].ev_trg_id == edge.ev_trg_id == None:
                                trg_dict[edge.trg_id].ev_trg_id = None
                            else:
                                trg_dict[edge.trg_id].ev_trg_id = trg_dict[edge.trg_id].ev_trg_id + constants.SEP_MULTIPLE + edge.ev_trg_id
                            
                            trg_dict[edge.trg_id].arg_type = trg_dict[edge.trg_id].arg_type + constants.SEP_MULTIPLE + edge.arg_type

                # print("INVERTED")
                # for k,e in trg_dict.items():
                #     print(k, e.ev_id, e.ev_type, e.src_id, e.trg_id, e.ev_trg_id, e.arg_type)
                # print()

                # Create a linearised sequence view of entity and triggers
                seq_ids = []
                seq_types = []
                for t in sentence:
                    if t._.entity_id != None and t._.trigger_id != None:
                        print("Warning. An entity cannot be a trigger too!")

                    if t._.entity_id:
                        seq_ids.append(t._.entity_id)
                        seq_types.append(t._.entity_type)
                    if t._.trigger_id:
                        seq_ids.append(t._.trigger_id)
                        seq_types.append(t._.trigger_type)

                # Split multiple elements in the lists (it is supposed to 
                # maintains the capability of considering order of triggers)
                # e.g., [T1, T2////T3, T4] and [Ph, Ph////+Reg, Bi]
                #       in [T1, T2, T3, T4] and [Ph, Ph, +Reg, Bi]
                seq_ids = [id_ for e in seq_ids for id_ in e.split(constants.SEP_MULTIPLE)]
                seq_types = [typ_ for e in seq_types for typ_ in e.split(constants.SEP_MULTIPLE)]

                for t in sentence:
                    if t._.entity_id in trg_dict.keys():
                        t._.arg_of_id = trg_dict[t._.entity_id].src_id
                        t._.arg_type = trg_dict[t._.entity_id].arg_type
                        t._.arg_of_ev_type = trg_dict[t._.entity_id].ev_type

                        if t._.arg_of_id not in seq_ids:
                            # Manage the lookup of the arg_of_id when there
                            # are multiple incoming edges from different
                            # sources. Heuristics: keep the source with min ID
                            if constants.SEP_MULTIPLE in t._.arg_of_id:
                                min_id = 9999
                                arg_of_ids = t._.arg_of_id.split(constants.SEP_MULTIPLE)
                                x = []
                                for i in range(len(arg_of_ids)):
                                    x.append(paragraph._.triggers[arg_of_ids[i]].type_)
                                    #if (int(arg_of_ids[i][1:]) < min_id):
                                    #    id_idx = i
                                    #    min_id = int(arg_of_ids[i][1:])

                                if t._.entity_type:
                                    source = [t._.entity_type]
                                    id__ = [t._.entity_id]
                                else:
                                    source = [t._.trigger_type]
                                    id__ =[t._.entity_id]
                                simple_ = []
                                complex_ = []
                                for xx in x:
                                    if xx in ["Positive_regulation", "Negative_regulation", "Regulation"]:
                                        complex_.append(xx)
                                    else:
                                        simple_.append(xx)
                                incomings.append([document.doc_id, id__, t.text, source, simple_, complex_])
                                # print("Multiple incoming edges for {} in {}. We keep the one with the ID with a less high number.".format(t.text, document.doc_id))
                            else:
                                pass
                        else:
                            id_idx = 0

                    if t._.trigger_id is not None:
                        # Manage the lookup of the trigger ID in the presence
                        # of multiple IDs which cannot be retrieved after the
                        # filtering of duplicate edges
                        if constants.SEP_MULTIPLE in t._.trigger_id:
                            trigger_ids = t._.trigger_id.split(constants.SEP_MULTIPLE)
                        else:
                            trigger_ids = [t._.trigger_id]

                        for trigger_id in trigger_ids:
                            if trigger_id in trg_dict.keys():
                                t._.arg_type = trg_dict[trigger_id].arg_type
                                t._.arg_of_id = trg_dict[trigger_id].src_id
                                t._.arg_of_ev_type = trg_dict[trigger_id].ev_type

                                if t._.arg_of_id not in seq_ids:
                                    # Manage the lookup of the arg_of_id when there
                                    # are multiple incoming edges from different
                                    # sources. Heuristics: keep the source with min ID
                                    if constants.SEP_MULTIPLE in t._.arg_of_id:
                                        min_id = 9999
                                        arg_of_ids = t._.arg_of_id.split(constants.SEP_MULTIPLE)
                                        y = []
                                        for i in range(len(arg_of_ids)):
                                            y.append(paragraph._.triggers[arg_of_ids[i]].type_)
                                            #if (int(arg_of_ids[i][1:]) < min_id):
                                            #    id_idx = i
                                            #    min_id = int(arg_of_ids[i][1:])
                                        # print("Multiple incoming edges for {} in {}. We keep the one with the ID with a less high number.".format(t.text, document.doc_id))
                                    else:
                                        pass
                                else:
                                    id_idx = 0

                for t in sentence:
                    if t._.arg_of_id:
                        src_type = t._.arg_of_ev_type
                        if t._.arg_of_id not in seq_ids:
                            pass

                        # Remove duplicates from the lists
                        seq_ids, seq_types = filter_seq_duplicates(seq_ids, seq_types)

                        # Get first and last token indexes for the src mention
                        src_id_idx_firsts = []
                        src_id_idx_lasts = []
                        for arg in t._.arg_of_id.split(constants.SEP_MULTIPLE):
                            src_id_idx_firsts.append(seq_ids.index(arg))
                            src_id_idx_lasts.append((len(seq_ids)-1) - seq_ids[::-1].index(arg))
                        #src_id_idx_first = seq_ids.index(t._.arg_of_id)
                        #src_id_idx_last = (len(seq_ids)-1) - seq_ids[::-1].index(t._.arg_of_id)

                        if t._.entity_id:
                            # Get first and last token indexes for the curr mention
                            curr_id_idx_first = seq_ids.index(t._.entity_id)
                            curr_id_idx_last = (len(seq_ids)-1) - seq_ids[::-1].index(t._.entity_id)
                        elif t._.trigger_id:
                            # Manage the lookup of the trigger ID in the presence
                            # of multiple IDs which cannot be retrieved after the
                            # filtering of duplicate edges
                            if constants.SEP_MULTIPLE in t._.trigger_id:
                                trigger_ids = t._.trigger_id.split(constants.SEP_MULTIPLE)
                                for id_ in trigger_ids:
                                    if id_ in seq_ids:
                                        trigger_id = id_
                            else:
                                trigger_id = t._.trigger_id

                            # Get first and last token indexes for the curr mention
                            curr_id_idx_first = seq_ids.index(trigger_id)
                            curr_id_idx_last = (len(seq_ids)-1) - seq_ids[::-1].index(trigger_id)

                        t._.arg_of_position = ""
                        for i in range(len(src_id_idx_firsts)):
                            # Using "filter_seq_ids_duplicates()", first and last are the same
                            # CASE: Curr start is before the source trigger start
                            if curr_id_idx_first < src_id_idx_firsts[i]: # or last...last, it is the same
                                ids_in_btw = seq_ids[curr_id_idx_last+1:src_id_idx_firsts[i]]
                                types_in_btw = seq_types[curr_id_idx_last+1:src_id_idx_firsts[i]]
                                rel_position = "+" + str(types_in_btw.count(src_type.split(constants.SEP_MULTIPLE)[i])+1)
                                #print(seq_ids[curr_id_idx_first], ids_in_btw, types_in_btw, src_type, rel_position)
                            # CASE: Curr start is after the source trigger start
                            elif curr_id_idx_first > src_id_idx_firsts[i]:
                                ids_in_btw = seq_ids[src_id_idx_lasts[i]+1:curr_id_idx_first]
                                types_in_btw = seq_types[src_id_idx_lasts[i]+1:curr_id_idx_first]
                                rel_position = "-" + str(types_in_btw.count(src_type.split(constants.SEP_MULTIPLE)[i])+1)
                                #print(seq_ids[curr_id_idx_first], ids_in_btw, types_in_btw, src_type, rel_position)
                            else:
                                pass

                            if t._.arg_of_position != "":
                                t._.arg_of_position += constants.SEP_MULTIPLE + rel_position
                            else:
                                t._.arg_of_position += rel_position

                #for t in sentence:
                #    print(t.i, t.text, t._.entity_id, t._.entity_type, t._.trigger_id, t._.trigger_type, t._.arg_of_id, t._.arg_of_ev_type, t._.arg_of_position, t._.trigger_cardinal)
                #print()
                filename = os.path.join(data_split + "." + encoding + extra_info)

                if masking == "no":
                    not_masked_dir = os.path.join("data", corpus, "not-masked")
                    if not os.path.exists(not_masked_dir):
                        os.makedirs(not_masked_dir)
                    filepath = os.path.join(not_masked_dir, filename)
                else:
                    masked_dir = os.path.join("data", corpus, "masked")
                    if not os.path.exists(masked_dir):
                        os.makedirs(masked_dir)
                    filepath = os.path.join(masked_dir, filename)

                with open(filepath, "a") as f:
                    f.write("# doc_id = " + document.doc_id + "\n")
                    for token in sentence:
                        token_info = get_token_info(token, sentence, prev_token_num, par_start_char, keep_ent_tokens)
                        token_features = get_token_features(token)

                        # @WARN: Take care if we change the way we encode features
                        feats = token_features.split(constants.SEP_COLUMN)
                        for feat in feats:
                            if feat.startswith("[ENT]"):
                                ent_type = feat.split("]")[1]
                                break
                            ent_type = "-"

                        encoded_token, output_labels = encode_token(token, output_labels, document.doc_id, keep_orphan_entities, encoding, multihead)
                        if masking == "entity":
                            word = token.text if ent_type == "-" else "$ENTITY$"
                            f.write(word + constants.SEP_COLUMN + token_info + constants.SEP_COLUMN + token_features + constants.SEP_COLUMN + encoded_token + "\n")
                        elif masking == "type":
                            word = token.text if ent_type == "-" else "$" + ent_type.upper() + "$"
                            f.write(word + constants.SEP_COLUMN + token_info + constants.SEP_COLUMN + token_features + constants.SEP_COLUMN + encoded_token + "\n")
                        else:
                            f.write(token.text + constants.SEP_COLUMN + token_info + constants.SEP_COLUMN + token_features + constants.SEP_COLUMN + encoded_token + "\n")
                    f.write("\n")

                # Track the number of past tokens
                prev_token_num += len(sentence)

            # Track relative paragraph "start" position within the document
            par_start_char = par_end_char

    #print(output_labels)
    #stats_file = open(data_split + "-stats.csv", "w")
    #for k, v in output_labels.items():
    #    if len(v["docs"]) > 50000:
    #        stats_file.write(k + "," + str(v["count"]) + "," + str(v["docs"])[:4990] + "..." + "\n")
    #    else:
    #        stats_file.write(k + "," + str(v["count"]) + "," + str(v["docs"]) + "\n")
    #stats_file.close()


def filter_seq_duplicates(seq_ids, seq_types):
    seq_ids_tmp = []
    seq_types_tmp = []

    for i in range(len(seq_ids)):
        if seq_ids[i] not in seq_ids_tmp:
            seq_ids_tmp.append(seq_ids[i])
            seq_types_tmp.append(seq_types[i])

    return seq_ids_tmp, seq_types_tmp


def get_token_info(token, sentence, prev_token_num, par_start_char, keep_ent_tokens):
    # Set the normalized token id (sentence-level instead of paragraph-level)
    token_i_norm = token.i - prev_token_num

    # Set the span field (only gold tokens can be assigned the gold span)
    if ((token._.span is not None) and (token._.entity_id is not None)) and (not keep_ent_tokens):
        span = token._.span
    else:
        start = sentence[token_i_norm:token_i_norm+1].start_char+par_start_char
        end = sentence[token_i_norm:token_i_norm+1].end_char+par_start_char
        span = str(start) + constants.SEP_SPAN + str(end)
    # print(span, token_i_norm, token.text, 
    #   sentence[token_i_norm:token_i_norm+1].start_char+par_start_char, 
    #   sentence[token_i_norm:token_i_norm+1].end_char+par_start_char)

    # Set the mention id field
    if token._.entity_id is not None:
        ent_id = token._.entity_id
    else:
        ent_id = constants.TOK_OUTSIDE
        if token._.is_entity:
            print("Warning! {} is actually an entity but misses an ID.".format(
                token.text))

    return span + constants.SEP_COLUMN + ent_id


def get_token_features(token):

    def get_entity_feature(token):
        if token._.entity_type:
            return "[ENT]" + token._.entity_type
        else:
            return "[ENT]-"

    def get_pos_feature(token):
        if token.pos_:
            return "[POS]" + token.pos_
        else:
            return "[POS]-"

    def get_dep_feature(token):
        if token.dep_:
            return "[DEP]" + token.dep_
        else:
            return "[DEP]-"

    entity = get_entity_feature(token)
    pos = get_pos_feature(token)
    dep = get_dep_feature(token)

    return entity + constants.SEP_COLUMN + pos + constants.SEP_COLUMN + dep


def encode_token(token, output_labels, doc_id, keep_orphan_entities, encoding,
    multihead):

    def mention_encoding(token, doc_id):
        mention_string = None

        if token._.entity_type:
            mention_string = constants.TOK_SINGLE + token._.entity_type
        elif token._.trigger_type:
            mention_string = constants.TOK_SINGLE + token._.trigger_type
            if constants.SEP_MULTIPLE in token._.trigger_type:
                splits = token._.trigger_type.split(constants.SEP_MULTIPLE)
                if splits[0] == splits[1]:
                    print(token._.trigger_type, "duplicate in", doc_id)
        else:
            mention_string = constants.TOK_OUTSIDE

        return mention_string

    def argument_encoding(token, separator, doc_id, multihead):
        arg_string = None

        if token._.arg_of_id:
            if token._.arg_of_position:
                arg_position = token._.arg_of_position
            else:
                print("Error in position! {} {} {} {} {} {} {} {} {}".format(
                    doc_id, token.text, separator, token._.entity_id, 
                    token._.trigger_id, separator, token._.arg_of_id, 
                    token._.arg_of_ev_type, token._.arg_of_position))
                arg_position = "?"

            # Normalize arg_type Type[0,1,2,...,9] -> Type
            if token._.arg_type[-1] in ["1","2","3","4","5","6","7","8","9"]:
                arg_type = token._.arg_type[:-1]
            else:
                arg_type = token._.arg_type
            arg_string = arg_type + separator + token._.arg_of_ev_type + separator + arg_position
        else:
            arg_string = constants.TOK_OUTSIDE

        # Check if the labels must be decomposed
        if arg_string != constants.TOK_OUTSIDE:
            args_parts = arg_string.split(separator)
            a = args_parts[0].split("////")
            b = args_parts[1].split("////")
            c = args_parts[2].split("////")

            assert len(a) == len(b) == len(c)

            # Split, order, and merge labels
            heads = []
            for i in range(len(a)):
                if a[i][-1] in ["1","2","3","4","5","6","7","8","9"]:
                    arg_type = a[i][:-1]
                else:
                    arg_type = a[i]
                heads.append(arg_type + separator + b[i] + separator + c[i])

            if multihead:
                heads.sort()
                inner_sep = constants.SEP_MULTIPLE_INNER
                arg_string = inner_sep.join(heads)
            else:
                arg_string = heads[0]
            # print(arg_string)

        return arg_string

    encoded_string = ""

    # Get the encoding of the mention (either [S|B|I]-[TYPE] or "O")
    mention_string = mention_encoding(token, doc_id)

    # If we have entity/trigger type, check the args. O.w., mark "O"
    if mention_string != constants.TOK_OUTSIDE:
        arg_string = argument_encoding(token, constants.SEP_LABEL_PART, doc_id, multihead)

        # If specified, mark "O" entities alone. O.w., build the string
        if (arg_string == constants.TOK_OUTSIDE) and (not keep_orphan_entities):
            # @TODO: Generalize to entities besides "Protein" and "Entity"
            if mention_string == (constants.TOK_SINGLE + "Protein") or (mention_string == (constants.TOK_SINGLE + "Entity")):
                encoded_string = constants.TOK_OUTSIDE
                #encoded_string = constants.TOK_OUTSIDE + constants.SEP_LABEL_TASK + constants.TOK_OUTSIDE
            else:
                if "$" in arg_string:
                    arg_string_parts = arg_string.split("$")
                    encoded_string += mention_string + constants.SEP_LABEL_PART + arg_string_parts[0]
                    for arg_i in range(1, len(arg_string_parts)):
                        encoded_string += "$" + mention_string + constants.SEP_LABEL_PART + arg_string_parts[arg_i]
                else:
                    encoded_string += mention_string + constants.SEP_LABEL_PART + arg_string
                #encoded_string += mention_string + constants.SEP_LABEL_TASK + arg_string
                # encoded_string += mention_string + constants.SEP_LABEL_TASK + mention_string + constants.SEP_LABEL_PART + arg_string
        else:
            if "$" in arg_string:
                arg_string_parts = arg_string.split("$")
                encoded_string += mention_string + constants.SEP_LABEL_PART + arg_string_parts[0]
                for arg_i in range(1, len(arg_string_parts)):
                    encoded_string += "$" + mention_string + constants.SEP_LABEL_PART + arg_string_parts[arg_i]
            else:
                encoded_string += mention_string + constants.SEP_LABEL_PART + arg_string
            #encoded_string += mention_string + constants.SEP_LABEL_TASK + arg_string
            # encoded_string += mention_string + constants.SEP_LABEL_TASK + mention_string + constants.SEP_LABEL_PART + arg_string
    else:
        encoded_string += mention_string
        #encoded_string += mention_string + constants.SEP_LABEL_TASK + constants.TOK_OUTSIDE

    if encoding == "mt.1":
        new_label_a = ""
        new_label_b = ""
        if encoded_string == "O":
            new_label_a = "O"
            new_label_b = "O"
        else:
            parts = encoded_string.split(constants.SEP_LABEL_PART, 1)
            new_label_a = parts[0]
            if parts[1] != "O":
                if "$" in parts[1]:
                    raw_parts = parts[1].split("$")
                    new_label_b += "B-" + raw_parts[0]
                    for i in range(1, len(raw_parts)):
                        clean_label = raw_parts[i].split("|", 1)[1]
                        new_label_b += "$" + "B-" + clean_label
                else:
                    new_label_b = "B-" + parts[1]
            else:
                new_label_b = parts[1]
        encoded_string = new_label_a + constants.SEP_COLUMN + new_label_b

    if encoding == "mt.2":
        new_label_a = ""
        new_label_b = ""
        if encoded_string == "O":
            new_label_a = "O"
            new_label_b = "O"
        else:
            if encoded_string.count("|") == 1:
                parts = encoded_string.split(constants.SEP_LABEL_PART, 1)
                new_label_a = parts[0] + "|O"
                new_label_b = "O"
            elif encoded_string.count("|") >= 2:
                if not multihead:
                    parts = encoded_string.split(constants.SEP_LABEL_PART, 2)
                    new_label_a = parts[0] + "|" + parts[1]
                    if parts[1] != "O":
                        new_label_b = "B-" + parts[2]
                    else:
                        new_label_b = "O"
                else:
                    # B-Protein|Theme|Gene_expression|-1$B-Protein|Cause|Positive_regulation|-2
                    labels = encoded_string.split(constants.SEP_MULTIPLE_INNER)
                    part_1 = labels[0].split("|")[0]
                    part_1_raw = part_1 + "|"
                    for raw_label in labels:
                        raw_label_parts = raw_label.split("|")
                        new_label_a += part_1_raw + raw_label_parts[1] + "$"
                        new_label_b += "B-" + raw_label_parts[2] + "|" + raw_label_parts[3] + "$"
                    if new_label_a[-1] == "$": # remove last $
                        new_label_a = new_label_a[:-1]
                    if new_label_b[-1] == "$": # remove last $
                        new_label_b = new_label_b[:-1]
            else:
                pass
        encoded_string = new_label_a + constants.SEP_COLUMN + new_label_b

    if encoding == "mt.3":
        new_label_a = ""
        new_label_b = ""
        if encoded_string == "O":
            new_label_a = "O"
            new_label_b = "O"
        else:
            if encoded_string.count("|") == 1:
                parts = encoded_string.split(constants.SEP_LABEL_PART, 1)
                new_label_a = parts[0] + "|O"
                new_label_b = "O"
            elif encoded_string.count("|") >= 2:
                if not multihead:
                    parts = encoded_string.split(constants.SEP_LABEL_PART, 3)
                    new_label_a = parts[0] + "|" + parts[2] + "|" + parts[3]
                    new_label_b = "B-" + parts[1]
                else:
                    # B-Protein|Theme|Gene_expression|-1$B-Protein|Cause|Positive_regulation|-2
                    labels = encoded_string.split(constants.SEP_MULTIPLE_INNER)
                    part_1 = labels[0].split("|")[0]
                    part_1_raw = part_1 + "|"
                    for raw_label in labels:
                        raw_label_parts = raw_label.split("|")
                        new_label_a += part_1_raw + raw_label_parts[2] + "|" + raw_label_parts[3] + "$"
                        new_label_b += "B-" + raw_label_parts[1] + "$"
                    if new_label_a[-1] == "$": # remove last $
                        new_label_a = new_label_a[:-1]
                    if new_label_b[-1] == "$": # remove last $
                        new_label_b = new_label_b[:-1]
            else:
                pass
        encoded_string = new_label_a + constants.SEP_COLUMN + new_label_b

    if encoding == "mt.4":
        new_label_a = ""
        new_label_b = ""
        new_label_c = ""
        if encoded_string == "O":
            new_label_a = "O"
            new_label_b = "O"
            new_label_c = "O"
        else:
            if encoded_string.count("|") == 1:
                parts = encoded_string.split(constants.SEP_LABEL_PART, 1)
                new_label_a = parts[0]
                new_label_b = "O"
                new_label_c = "O"
            elif encoded_string.count("|") >= 2:
                if not multihead:
                    parts = encoded_string.split(constants.SEP_LABEL_PART, 2)
                    new_label_a = parts[0]
                    if parts[1] != "O":
                        new_label_b = "B-" + parts[1]
                        new_label_c = "B-" + parts[2]
                    else:
                        new_label_b = "O"
                        new_label_c = "O"
                else:
                    # B-Protein|Theme|Gene_expression|-1$B-Protein|Cause|Positive_regulation|-2
                    labels = encoded_string.split(constants.SEP_MULTIPLE_INNER)
                    part_1 = labels[0].split("|")[0]
                    new_label_a = part_1
                    for raw_label in labels:
                        raw_label_parts = raw_label.split("|")
                        new_label_b += "B-" + raw_label_parts[1] + "$"
                        new_label_c += "B-" + raw_label_parts[2] + "|" + raw_label_parts[3] + "$"
                    if new_label_a[-1] == "$": # remove last $
                        new_label_a = new_label_a[:-1]
                    if new_label_b[-1] == "$": # remove last $
                        new_label_b = new_label_b[:-1]
                    if new_label_c[-1] == "$": # remove last $
                        new_label_c = new_label_c[:-1]
        encoded_string = new_label_a + constants.SEP_COLUMN + new_label_b + constants.SEP_COLUMN + new_label_c

    if encoded_string not in output_labels:
        output_labels[encoded_string] = {}
        output_labels[encoded_string]["count"] = 1
        output_labels[encoded_string]["docs"] = doc_id
    else:
        output_labels[encoded_string]["count"] += 1
        output_labels[encoded_string]["docs"] += constants.SEP_MULTIPLE + doc_id

    return encoded_string, output_labels


def parse_edges(document):
    edges = []

    # For each event, build an edge object for each event target argument
    for ev_id, event in document.events.items():
        for i in range(len(event.end_ids)):
            ev_type = event.type_               # type of the event
            src_id = event.start_id             # source mention ID
            trg_id = event.end_ids[i]           # target mention ID
            arg_type = event.edge_types[i]      # argument type
            ev_trg_id = None                    # target trigger ID, if any

            # If an event argument is another event, retrieve its trigger ID
            if trg_id[0] == "E":
                ev_trg_id = trg_id
                trg_id = document.events[trg_id].start_id

            edge = Edge(ev_id, ev_type, src_id, trg_id, ev_trg_id, arg_type)
            edges.append(edge)

    return edges


def filter_mentions(start_char, end_char, mentions, overlap=False):
    if overlap:
        prev_start = -1
        prev_end = -1
        prev_type = None
        prev_mention = None
        spurious_mentions = []

        for mention in mentions.items():
            curr_start = mention[1].start
            curr_end = mention[1].end
            curr_type = mention[1].type_

            # If multiple triggers on the same token, go to the next
            if (curr_start == prev_start) and (curr_end == prev_end):
                continue

            # Overlapping when there is the same start char index
            elif (curr_start == prev_start):
                # CASE: [x/y, ..., y]
                if (curr_end > prev_end):
                    # If we have the same type, keep the largest
                    if curr_type == prev_type:
                        spurious_mentions.append(prev_mention)
                        # print("Overlapping found and one deleted")
                    # O.w., split into two parts, recalculating y start
                    else:
                        curr_start = prev_end + 1
                        mention[1].start = curr_start
                        # print("Overlapping found and managed")

                # CASE: [x/y, ..., x]
                elif (curr_end < prev_end):
                    # If we have the same type, keep the largest
                    if curr_type == prev_type:
                        spurious_mentions.append(mention)
                        # print("Overlapping found and one deleted")
                    # O.w., split into two parts, recalculating x start
                    else:
                        prev_start = curr_end + 1
                        prev_mention[1].start = prev_start
                        # print("Overlapping found and managed")

            # Overlapping when there is the same end char index
            elif (curr_end == prev_end):
                # CASE: [x, ..., x/y]
                if (curr_start > prev_start):
                    # If we have the same type, keep the largest
                    if curr_type == prev_type:
                        spurious_mentions.append(mention)
                        # print("Overlapping found and one deleted")
                    # O.w., split into two parts, recalculating x end
                    else:
                        prev_end = curr_start - 1
                        prev_mention[1].end = prev_end
                        # print("Overlapping found and managed")

                # CASE: [y, ..., x/y]
                elif (curr_start < prev_start):
                    # If we have the same type, keep the largest
                    if curr_type == prev_type:
                        spurious_mentions.append(prev_mention)
                        # print("Overlapping found and one deleted")
                    # O.w., split into two parts, recalculating y end
                    else:
                        curr_end = prev_start - 1
                        mention[1].end = curr_end
                        # print("Overlapping found and managed")

            # Current token in the middle of the previous one
            elif (curr_start > prev_start) and (curr_end < prev_end):
                curr_start = prev_start
                curr_end = prev_end
                spurious_mentions.append(mention)
                # print("Overlapping found and one deleted")

            # Current token enclosing the previous one
            elif (curr_start < prev_start) and (curr_end > prev_end):
                spurious_mentions.append(prev_mention)
                # print("Overlapping found and one deleted")

            # O.w., we have different spans
            else:
                pass

            prev_start = curr_start
            prev_end = curr_end
            prev_type = curr_type
            prev_mention = mention

        # Remove spurious mentions
        for sp_mention in spurious_mentions:
            del mentions[sp_mention[0]]

    filtered_mentions = {id_: mention for id_, mention in mentions.items() 
                if (start_char <= mention.start < end_char)}
    return filtered_mentions


def filter_edges(entities, triggers, edges, use_sec_entities):
    filtered = []

    # If both source and target mention IDs are in the par/sent scope of the
    # pre-filtered entity and trigger lists, retain them
    for edge in edges:
        # Skip secondary edges even in the case of the use of secondary
        # entities (for evaluation on the BioNLP core task)
        if (edge.arg_type in constants.SEC_EDGES) and use_sec_entities:
            continue

        is_src_trigger = edge.src_id in triggers.keys()
        is_trg_trigger = edge.trg_id in triggers.keys()
        is_trg_entity = edge.trg_id in entities.keys()

        if is_src_trigger and (is_trg_trigger or is_trg_entity):
            same_span = False

            # In case of trigger->trigger edges, check if they are different
            # trigger types but the same token (i.e., the same span)
            if is_src_trigger and is_trg_trigger:
                src_start = triggers[edge.src_id].start
                trg_start = triggers[edge.trg_id].start
                src_end = triggers[edge.src_id].end
                trg_end = triggers[edge.trg_id].end
                same_span = (src_start == trg_start) and (src_end == trg_end)
            
            # Filter edges on the same trigger having either:
            # (i)  the same type, e.g., +Reg -> +Reg
            # (ii) a different type but the same span, e.g., +Reg -> GeneExp
            if (edge.src_id != edge.trg_id) and (not same_span):
                filtered.append(edge)
            else:
                pass
                # print("The edge has the same source and target. Skipping.")

    # Remove duplicates on the equality of start/end trigger and end event ID
    edges_tmp = []
    dupl_edges_idx = []
    for i in range(len(filtered)):
        identity_edge = (filtered[i].src_id, filtered[i].trg_id, filtered[i].ev_trg_id)
        if identity_edge not in edges_tmp:
            edges_tmp.append(identity_edge)
        else:
            dupl_edges_idx.append(i)

    for index in sorted(dupl_edges_idx, reverse=True):
        del filtered[index]

    return filtered


def get_sent_mentions(sentence, par_entities, par_triggers):
    entities = {}
    triggers = {}

    for token in sentence:
        if token._.entity_id != None:
            ids_list = token._.entity_id.split(constants.SEP_MULTIPLE)
            types_list = token._.entity_type.split(constants.SEP_MULTIPLE)
            for i in range(len(ids_list)):
                if ids_list[i] not in entities:
                    entities[ids_list[i]] = par_entities[ids_list[i]]

        if token._.trigger_id != None:
            ids_list = token._.trigger_id.split(constants.SEP_MULTIPLE)
            types_list = token._.trigger_type.split(constants.SEP_MULTIPLE)
            for i in range(len(ids_list)):
                if ids_list[i] not in triggers:
                    triggers[ids_list[i]] = par_triggers[ids_list[i]]

    return entities, triggers