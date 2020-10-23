"""
A Dataset Reader for Universal Dependencies, with support for multiword tokens and special handling for NULL "_" tokens
"""

from typing import Dict, Tuple, List, Any, Callable

from overrides import overrides
from udify.dataset_readers.parser import parse_line, DEFAULT_FIELDS

from allennlp.common.file_utils import cached_path
from allennlp.data.dataset_readers.dataset_reader import DatasetReader
from allennlp.data.fields import Field, TextField, SequenceLabelField, MetadataField
from allennlp.data.instance import Instance
from allennlp.data.token_indexers import SingleIdTokenIndexer, TokenIndexer
from allennlp.data.tokenizers.word_splitter import SpacyWordSplitter, WordSplitter
from allennlp.data.tokenizers import Token

from udify.dataset_readers.lemma_edit import gen_lemma_rule
from udify.dataset_readers.sequence_multilabel_field import SequenceMultiLabelField
import pprint
import logging

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name


def get_all_relative_encodings(head):
    encodings = []
    k = 10
    for i in range(k*2):
        enc = str(i-k)+','+head
        encodings.append(enc)
    return encodings


def dep_encoding(wordIdx, headIdx, label):
    position = wordIdx +1 - headIdx
    if headIdx == 0:
        position = 0
    k = 10
    if position < -k:
        position = -k
    if position > k:
        position = k
    return str(position) + ',' + label


def lazy_parse(text: str, fields: Tuple[str, ...]=DEFAULT_FIELDS):
    for sentence in text.split("\n\n"):
        if sentence:
            # TODO: upgrade conllu library
            yield [parse_line(line, fields)
                   for line in sentence.split("\n")
                   if line and not line.strip().startswith("#")]

def read_columns(conllu_file):
    sent = []
    for line in open(conllu_file):
        if len(line) < 2 and len(sent) > 0:
            #because in some datasets the wordIdx might be 0, and a line starting with # should be included
            #warning: breaks when the comment includes exactly the same amount of columns as the actual data
            numCols = len(sent[-1])
            begIdx = 0
            for i in range(len(sent)):
                backIdx = len(sent) -1 -i
                if len(sent[backIdx]) == numCols:
                    begIdx = len(sent)-1-i
            yield sent[begIdx:], sent
            sent = []
        #elif len(sent) == 0:
        #    continue
        else:
            sent.append(line.strip().split('\t'))

@DatasetReader.register("udify_universal_dependencies")
class UniversalDependenciesDatasetReader(DatasetReader):
    def __init__(self,
                 token_indexers: Dict[str, TokenIndexer] = None,
                 lazy: bool = False, 
                 tasks: Dict = None, datasets: Dict = None
                )-> None:
        super().__init__(lazy)
        self._token_indexers = token_indexers or {'tokens': SingleIdTokenIndexer()}
        self.datasets = datasets
        self.tasks = tasks

    @overrides
    def _read(self, file_path: str):
        # WARNING file_path only contains split information, not the path
        #not true anymore!, from predict.py it will contain the path. Now it is really confusing
        split = file_path

        # sentTasks is a dict with for each task a list of labels
        # entry 'dataset' contains name of dataset
        # entry 'words' contains the words
        # entry 'dep_encoded' contains an empty list, is necessary for dependency decoder
        for dataset in self.datasets:
            pprint.pprint(self.datasets[dataset])
            word_idx = self.datasets[dataset]['word_idx']
            #for sent read_columns(self.datasets[dataset][split]):
            #TODO: this is a hacky fix, to make predict.py usable
            for sent, fullData in read_columns(split if split not in self.datasets[dataset] else self.datasets[dataset][split]):
                sentTasks = {}

                sentTasks['words'] = []
                sentTasks['dep_encoded'] = []
                sentTasks['dataset'] = []
                for wordData in sent:
                    sentTasks['dataset'].append(dataset)
                    sentTasks['words'].append(wordData[word_idx])
                    sentTasks['dep_encoded'].append('')
                colIdxs = {}
                for task in self.datasets[dataset]['tasks']:
                    sentTasks[task] = []
                    transformer = self.datasets[dataset]['tasks'][task]['transformer']
                    taskIdx = self.datasets[dataset]['tasks'][task]['column_idx']
                    colIdxs[task] = taskIdx
                    if transformer == '':
                        for wordData in sent:
                            sentTasks[task].append(wordData[taskIdx])
                    elif transformer == 'lemma':
                        for wordData in sent:
                            taskLabel = gen_lemma_rule(wordData[word_idx], wordData[taskIdx])
                            sentTasks[task].append(taskLabel)
                    elif transformer == 'dependency':
                        heads = []
                        rels = []
                        for wordData in sent:
                            heads.append(wordData[taskIdx])
                            rels.append(wordData[taskIdx + 1])
                        sentTasks[task] = list(zip(rels, heads))
                    else:
                        print('Error: transfomer ' + transformer + ' for task ' + task + ' in dataset ' + dataset + ' is unknown')
                        exit(1)
                yield self.text_to_instance(sentTasks, fullData, colIdxs)


    @overrides
    def text_to_instance(self,  # type: ignore
                         sentTasks: Dict[str, List[str]],
                         fullData: List[str],
                         colIdxs: Dict[str, int],
                         ) -> Instance:
        fields: Dict[str, Field] = {}

        tokens = TextField([Token(w) for w in sentTasks['words']], self._token_indexers)
        fields["tokens"] = tokens
        for task in sentTasks:
            if task == 'rependency':#TODO fix, this is the only hardcoded position, should check transformer somehow
                fields['head_tags'] = SequenceLabelField([x[0] for x in sentTasks[task]],
                                                    tokens, label_namespace='head_tags')
                fields['head_indices'] = SequenceLabelField([int(x[1]) for x in sentTasks[task]], 
                                                    tokens, label_namespace='head_index_tags')

            # HARD-CODED FOR NOW
            elif (task == "multi-labels") or (task == "multii-labels"):
                label_sequence = []

                # For each token label, check if it is a multilabel and handle it
                for raw_label in sentTasks[task]:
                    if "$" in raw_label:
                        label_list = raw_label.split("$")
                        label_sequence.append(label_list)
                    else:
                        label_sequence.append([raw_label])
                
                fields[task] = SequenceMultiLabelField(label_sequence, tokens, label_namespace=task)

            else:
                fields[task] = SequenceLabelField(sentTasks[task], tokens, label_namespace=task)

        sentTasks["fullData"] = fullData
        sentTasks["colIdxs"] = colIdxs
        fields["metadata"] = MetadataField(sentTasks)
        #fullDataDict = {}
        #for i in range(len(fullData)):
        #    fullDataDict[i] = fullData[i]
        return Instance(fields)


@DatasetReader.register("udify_universal_dependencies_raw")
class UniversalDependenciesRawDatasetReader(DatasetReader):
    """Like UniversalDependenciesDatasetReader, but reads raw sentences and tokenizes them first."""

    def __init__(self,
                 dataset_reader: DatasetReader,
                 tokenizer: WordSplitter = None) -> None:
        super().__init__(lazy=dataset_reader.lazy)
        self.dataset_reader = dataset_reader
        if tokenizer:
            self.tokenizer = tokenizer
        else:
            self.tokenizer = SpacyWordSplitter(language="xx_ent_wiki_sm")

    @overrides
    def _read(self, file_path: str):
        # if `file_path` is a URL, redirect to the cache
        file_path = cached_path(file_path)

        with open(file_path, 'r') as conllu_file:
            for sentence in conllu_file:
                if sentence:
                    words = [word.text for word in self.tokenizer.split_words(sentence)]
                    yield self.text_to_instance(words)

    @overrides
    def text_to_instance(self,  words: List[str]) -> Instance:
        return self.dataset_reader.text_to_instance(words)
