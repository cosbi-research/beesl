import spacy
import scispacy
from spacy.tokens import Doc
from utils import corpus_er

def set_nlp_environment(keep_ent_tokens):
    """A function that sets the NLP workflow (with custom components) along with
    the language model."""
    
    def merger(doc):
        indices = []

        for token in doc:
            if (token.i > 0):
                if (token.text == "/-") and (doc[token.i-1].text == "+"):
                    indices.append(token.i)

        offset = 0
        for index in indices:            
            with doc.retokenize() as retokenizer:
                retokenizer.merge(doc[index-1-offset : index+1-offset])
                offset += 1

        return doc

    def custom_sentencizer(doc):
        for i, token in enumerate(doc[:-2]):
            if (token.text == "B.") and (doc[i-1].text.endswith("kappa")) and (doc[i+1].text[0].istitle()): # more robust than: (doc[i+1].is_title) for cases such as "Transient-transfection"
                doc[i+1].is_sent_start = True
            elif ((token.text == "A.") or (token.text == "B.") or (token.text == "C.")) and (doc[i-1].text.endswith("ase") or doc[i-1].text.endswith("lin")) and (doc[i+1].text[0].istitle()):
                doc[i+1].is_sent_start = True
            elif (token.text in ["h.", "d."]) and (doc[i+1].text[0].istitle()): # ßand (doc[i-1].like_num):
                doc[i+1].is_sent_start = True
            elif token.text.endswith("kappaB.") and (doc[i+1].text[0].istitle()):
                doc[i+1].is_sent_start = True
            elif ((token.text == "CyA.") or (token.text == "CsA.") or (token.text == "IgM.") or (token.text == "IgE.")) and (doc[i+1].text[0].istitle()):
                doc[i+1].is_sent_start = True

        return doc

    def load_language_model(keep_ent_tokens):
        nlp = spacy.load("en_core_sci_md")

        # Build a pipeline of NLP components
        nlp.remove_pipe('ner')
        nlp.add_pipe(merger, name="merger", before="tagger")
        nlp.add_pipe(custom_sentencizer, name="sentencizer", before="parser")
        corpus_based_er = corpus_er.CorpusER(nlp, keep_ent_tokens)
        nlp.add_pipe(corpus_based_er, before='parser')

        # Set attribute extensions to the document object
        Doc.set_extension("id", default=None, force=True)
        Doc.set_extension("start_char", default=None, force=True)
        Doc.set_extension("entities", default=None, force=True)
        Doc.set_extension("triggers", default=None, force=True)
        Doc.set_extension("edges", default=None, force=True)

        return nlp

    return load_language_model(keep_ent_tokens)