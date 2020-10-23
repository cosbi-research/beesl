import numpy
from spacy.tokens import Token
from utils import constants

SEP = "////"
DEBUG = False

class CorpusER(object):
    """Module class that deals with the annotation of gold entities/triggers."""

    name = 'corpus_er'

    def __init__(self, nlp, keep_ent_tokens, attrs=('is_entity', 'entity_id', 'entity_type', 'is_trigger', 'trigger_id', 'trigger_type', 'arg_type', 'arg_of_id', 'arg_of_position', 'arg_of_ev_type', 'span')):
        """Initialization of the module."""

        # Set the attributes of the class
        self.keep_ent_tokens = keep_ent_tokens
        self._is_entity, self._entity_id, self._entity_type, self._is_trigger, self._trigger_id, self._trigger_type, self._arg_type, self._arg_of_id, self._arg_of_position, self._arg_of_ev_type, self._span = attrs

        # Set the extensions to keep track of the entities/triggers
        Token.set_extension(self._is_entity, default=False, force=True)
        Token.set_extension(self._entity_id, default=None, force=True)
        Token.set_extension(self._entity_type, default=None, force=True)

        Token.set_extension(self._is_trigger, default=False, force=True)
        Token.set_extension(self._trigger_id, default=None, force=True)
        Token.set_extension(self._trigger_type, default=None, force=True)

        Token.set_extension(self._arg_type, default=None, force=True)
        Token.set_extension(self._arg_of_id, default=None, force=True)
        Token.set_extension(self._arg_of_position, default=None, force=True)
        Token.set_extension(self._arg_of_ev_type, default=None, force=True)

        Token.set_extension(self._span, default=None, force=True)


    def __call__(self, doc):
        """Main logics of the corpus-based annotation module."""

        # If the doc has some marked gold entities/triggers, annotate them
        if doc._.entities:
            self.annotate_gold_entities(doc)

        # Workaround to manage missing tensors update
        # Waiting for the fix: @[https://github.com/explosion/spaCy/issues/1963]
        doc.tensor = numpy.zeros((0,), dtype='float32')

        return doc


    def annotate_gold_entities(self, doc):
        """A function that annotates all the gold entities/triggers of a doc 
        object based on a dictionary of entity/triggers attributes.

        ARGS:
            doc                 the doc object
        """

        ann_type_dicts = [{"entities": doc._.entities}, {"triggers": doc._.triggers}]
        spans_to_merge = []

        for ann_type_dict in ann_type_dicts:
            for ann_type, ann_dict in ann_type_dict.items():
                # Iterate over the gold entities/triggers associated to the doc
                for id_, mention in ann_dict.items():

                    # Skip 
                    #if entity.e_type in constants.ENTS_EXCLUSION_LIST:
                    #    print("Skipping entity of type:", entity.e_type)
                    #    continue

                    # Recalculate the indexes based on the start char of the doc
                    mention_start = mention.start - doc._.start_char
                    mention_end = mention.end - doc._.start_char

                    # Handle incorrect annotations including whitespaces
                    # E.g., "betaI " (T70) in "PMC-3245220-01-Introduction" (BioNLP13)
                    if doc.text[mention_end-1:mention_end] == " ":
                        mention_end = mention_end-1

                    # Match the entity/trigger in the doc
                    matched_mention = doc.char_span(
                        mention_start, mention_end, label=mention.type_)

                    # If there is not a match, retokenize the doc based on the char span
                    if matched_mention is None:
                        is_already_splitted = False # flag to update token indexes

                        # Get the token span from the misaligned character span
                        token_start, token_end = self.get_token_indexes_from_char_span(
                            doc, mention_start, mention_end)

                        if DEBUG:
                            print("Retokenization of \"{}\" (\"{}\": \"{}\").".format(
                                doc.text[mention_start:mention_end], id_, doc._.id))

                            _end = token_start+1 if token_end == None else token_end
                            o = "|".join([str(doc[i]) for i in range(token_start, _end)])
                            print("\tOriginal token(s): {}".format(o))
                        
                        # In case of a single-token splitting, make the end as the start
                        if token_end is None: token_end = token_start

                        # CASE 1: Misaligned start. Split the token_start
                        token_start_char = doc[token_start].idx
                        if (token_start_char != mention_start):
                            self.split_token_from_char_index(doc, token_start, mention_start)
                            is_already_splitted = True

                            if DEBUG:
                                print("\t(Start) splitting: {} | {}".format(
                                    doc[token_start], doc[token_start+1]))

                        # Recompute spans based on whether splitting has been already done
                        if (token_end != token_start) and not is_already_splitted:
                            token_index = token_end - 1
                        elif (token_end == token_start) and is_already_splitted:
                            token_index = token_end + 1
                        else:
                            token_index = token_end
                        token_end_len = len(doc[token_index])
                        token_end_char = doc[token_index].idx + token_end_len

                        # CASE 2: Misaligned end. Split the token_end
                        if (token_end_char != mention_end):
                            self.split_token_from_char_index(doc, token_index, mention_end)

                            if DEBUG:
                                print("\t(End) splitting:   {} | {}".format(
                                    doc[token_index], doc[token_index+1]))

                        # Match the entity/trigger in the retokenized doc
                        matched_mention = doc.char_span(
                            mention_start, mention_end, label=mention.type_)


                    # Annotated the matched entity/trigger (and make sure it exists)
                    if matched_mention is not None:
                        # For each token, set its entity flags
                        for token in matched_mention:
                            token._.set(self._span, str(mention_start + doc._.start_char) + "-" + str(mention_end + doc._.start_char))
                            if ann_type == "entities":
                                token._.set(self._is_entity, True)

                                # An entity may have duplicate types: handle them
                                if token._.entity_type is not None:
                                    if mention.type_ < token._.entity_type:
                                        token._.entity_type = mention.type_ + SEP + token._.entity_type
                                        token._.entity_id = id_ + SEP + token._.entity_id
                                    else:
                                        token._.entity_type = token._.entity_type + SEP + mention.type_
                                        token._.entity_id = token._.entity_id + SEP + id_
                                else:
                                    token._.set(self._entity_type, mention.type_)
                                    token._.set(self._entity_id, id_)

                                if self.keep_ent_tokens == False:
                                    spans_to_merge.append(matched_mention)

                            elif ann_type == "triggers":
                                token._.set(self._is_trigger, True)

                                # An event trigger may have duplicate types and ids: handle them
                                if token._.trigger_type is not None:
                                    if mention.type_ < token._.trigger_type:
                                        token._.trigger_type = mention.type_ + SEP + token._.trigger_type
                                        token._.trigger_id = id_ + SEP + token._.trigger_id
                                    else:
                                        token._.trigger_type = token._.trigger_type + SEP + mention.type_
                                        token._.trigger_id = token._.trigger_id + SEP + id_
                                else:
                                    token._.set(self._trigger_type, mention.type_)
                                    token._.set(self._trigger_id, id_)

                    # Otherwise, print a warning to later fix the error
                    else:
                        print("WARNING: Entity/trigger \"{}\" (id: \"{}\") was not " \
                            "recognized in doc_id: \"{}\".".format(
                                doc.text[mention_start:mention_end], id_, doc._.id))

        #print("Before:", [token.text for token in doc])
        if self.keep_ent_tokens == False:
            with doc.retokenize() as retokenizer:
                for span_to_merge in spans_to_merge:
                    retokenizer.merge(span_to_merge)
        #print("After:", [token.text for token in doc])


    def split_token_from_char_index(self, doc, token_index, char_index):
        """A method that takes care of the splitting of a token into its
        components based on a provided character offset.

        ARGS:
            doc                 the doc object
            token_index         the index of the token to split
            char_index          the char index where to split the token
        """

        token_start_char = doc[token_index].idx
        token_end_char = doc[token_index].idx + len(doc[token_index])

        # Surface text of the parts to split
        part1 = doc.text[token_start_char : char_index]
        part2 = doc.text[char_index : token_end_char]

        # Since we have not parsed the text yet, attach each subtoken to itself
        # See: https://spacy.io/usage/linguistic-features#retokenization
        heads = [(doc[token_index], 0), (doc[token_index], 1)]

        # Split the token into its identified components
        try:
            with doc.retokenize() as retokenizer:
                retokenizer.split(doc[token_index], [part1, part2], heads=heads)
        except:
            pass


    def get_token_indexes_from_char_span(self, doc, char_start, char_end):
        """A method that finds the token start and the token end indexes from a 
        given character span. This method is useful to perform retokenization in
        corner cases where the char span is not aligned to the token span.

        ARGS:
            doc                 the doc object
            char_start          the char index start of the entity
            char_end            the char index end of the entity

        RETURN:
            token_start         the token index start of the entity
            token_end           the token index end of the entity
        """

        token_start = None
        token_end = None

        for i, token in enumerate(doc):
            # If a start index has not been found yet, search for it
            if token_start is None:
                # Case S1: The span starts the same as the curr token start
                # e.g., {[X]-induced}
                if (token.idx == char_start):
                    token_start = i            # the curr is the start

                # Case S2: The span starts before the curr token start
                # e.g., {alpha-[X]} {CURR_TOKEN}
                elif (token.idx > char_start): # this means we skipped it
                    token_start = i-1          # the prev is the start

                    # CASE E1: Take care of the curr token: it may be the end!
                    curr_token_end = token.idx + len(token)
                    if (curr_token_end == char_end):
                        token_end = i+1        # the curr is the end
                        break                  # we are done

            # Otherwise, check succ tokens until we found the end
            else:
                # CASE E2: The span ends after the curr token start (so update)
                # e.g., {[TNF} {-} {alpha])-}
                if (token.idx < char_end):
                    token_end = i+1           # the succ is the end (exclusive)

        # Case CORNER1: The span starts after the last token start of the text,
        # thus it was skipped in the previous logics. Manually set it.
        # e.g., [BioNLP11: PMC-1134658-05-Results-04], first sentence
        if token_start == None:
            token_start = i

        return token_start, token_end