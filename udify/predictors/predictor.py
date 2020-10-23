"""
The main UDify predictor to output conllu files
"""

from typing import List
from overrides import overrides

from allennlp.common.util import JsonDict, sanitize
from allennlp.data import DatasetReader, Instance
from allennlp.models import Model
from allennlp.predictors.predictor import Predictor
from udify.dataset_readers.lemma_edit import apply_lemma_rule

@Predictor.register("udify_predictor")
class UdifyPredictor(Predictor):
    """
    Predictor for a UDify model that takes in a sentence and returns
    a single set conllu annotations for it.
    """
    def __init__(self, model: Model, dataset_reader: DatasetReader) -> None:
        super().__init__(model, dataset_reader)
        self.model = model

    def predict(self, sentence: str) -> JsonDict:
        return self.predict_json({"sentence": sentence})

    @overrides
    def predict_batch_instance(self, instances: List[Instance]) -> List[JsonDict]:
        if "@@UNKNOWN@@" not in self._model.vocab._token_to_index["lemmas"]:
            # Handle cases where the labels are present in the test set but not training set
            for instance in instances:
                self._predict_unknown(instance)
        outputs = self._model.forward_on_instances(instances)
        return sanitize(outputs)

    @overrides
    def predict_instance(self, instance: Instance) -> JsonDict:
        if "@@UNKNOWN@@" not in self._model.vocab._token_to_index["lemmas"]:
            # Handle cases where the labels are present in the test set but not training set
            self._predict_unknown(instance)
        outputs = self._model.forward_on_instance(instance)
        return sanitize(outputs)

    def _predict_unknown(self, instance: Instance):
        """
        Maps each unknown label in each namespace to a default token
        :param instance: the instance containing a list of labels for each namespace
        """
        def replace_tokens(instance: Instance, namespace: str, token: str):
            if namespace not in instance.fields:
                return

            instance.fields[namespace].labels = [label
                                                 if label in self._model.vocab._token_to_index[namespace]
                                                 else token
                                                 for label in instance.fields[namespace].labels]

        replace_tokens(instance, "lemmas", "↓0;d¦")
        replace_tokens(instance, "feats", "_")
        replace_tokens(instance, "xpos", "_")
        replace_tokens(instance, "upos", "NOUN")
        replace_tokens(instance, "head_tags", "case")

    @overrides
    def _json_to_instance(self, json_dict: JsonDict) -> Instance:
        """
        Expects JSON that looks like ``{"sentence": "..."}``.
        Runs the underlying model, and adds the ``"words"`` to the output.
        """
        sentence = json_dict["sentence"]
        tokens = sentence.split()
        return self._dataset_reader.text_to_instance(tokens)

    @overrides
    def dump_line(self, outputs: JsonDict) -> str:
        lines = []
        #R: Warning, hacky!, allennlp requires each item to be in the length of metadata, but I just need it once
        #outputs['tasks'] = outputs['tasks'][0]
        #outputs['transformers'] = outputs['transformers'][0]
        for i in range(len(outputs['fullData'])):
            oppIdx = len(outputs['fullData']) -1 -i
            oppIdxProc = len(outputs['words']) -1 - i
            tok = outputs['fullData'][oppIdx]
            if oppIdxProc >= 0:
                #somehow a list of length 1 is transformed to a string by allennlp?, so I put it back in a list here..
                for taskIdx, task in enumerate(outputs['tasks'] if type(outputs['tasks']) is list else [outputs['tasks']]):
                    colIdx = outputs['colIdxs'][task]
                    tok[colIdx] = outputs[task][oppIdxProc]
                    if 'lemma' == (outputs['transformers'][taskIdx] if type(outputs['transformers']) is list else outputs['transformers']):
                        tok[colIdx] = apply_lemma_rule(outputs['words'][oppIdxProc], tok[colIdx])
            
                # ALSO FOR TRIGGERS
                # To generalize to multiple columns
                # if (len(tok[-1]) > 1):
                if isinstance(tok[-2], list):
                    #print(tok[-1])
                    prevlast_tok = "$".join(sorted(tok[-2]))
                    #print(last_tok)
                    tok = tok[:-2] + [prevlast_tok] + [tok[-1]]
                    #print(tok)

                # To generalize to multiple columns
                # if (len(tok[-1]) > 1):
                if isinstance(tok[-1], list):
                    #print(tok[-1])
                    last_tok = "$".join(sorted(tok[-1]))
                    #print(last_tok)
                    tok = tok[:-1] + [last_tok]
                    #print(tok)
            lines.append('\t'.join(tok))
        lines.reverse()
        return '\n'.join(lines) + '\n\n'

