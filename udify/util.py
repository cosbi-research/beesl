"""
A collection of handy utilities
"""

from typing import List, Tuple, Dict, Any

import os
import glob
import json
import logging
import tarfile
import traceback
import torch
import pprint
import copy
import numpy

from allennlp.common.checks import ConfigurationError
from allennlp.common import Params
from allennlp.common.params import with_fallback
from allennlp.commands.make_vocab import make_vocab_from_params
from allennlp.commands.predict import _PredictManager
from allennlp.common.checks import check_for_gpu
from allennlp.models.archival import load_archive
from allennlp.predictors.predictor import Predictor

from udify.dataset_readers.ge11_eval import evaluate_asrm

VOCAB_CONFIG_PATH = "config/create_vocab.json"

logger = logging.getLogger(__name__)


def merge_configs(parameters_config: str, dataset_config: str, overrides: Dict) -> Params:
    """
    Merges a dataset config file with a parameters config file
    """
    mergedSettings = Params.from_file(parameters_config)
    dataset_config = Params.from_file(dataset_config)
    defaultDecoder = mergedSettings['model'].pop('default_decoder').as_dict()
    orderedStuff = {}
    mergedSettings['dataset_reader']['datasets'] = {}
    mergedSettings['model']['decoders'] = {}
    for dataset in dataset_config:
        mergedSettings['dataset_reader']['datasets'][dataset] = {}
        mergedSettings['dataset_reader']['datasets'][dataset]['train'] = dataset_config[dataset]['train_data_path']
        mergedSettings['dataset_reader']['datasets'][dataset]['dev'] = dataset_config[dataset]['validation_data_path']
        mergedSettings['dataset_reader']['datasets'][dataset]['test'] = dataset_config[dataset]['test_data_path']

        # Set an optional evaluation for the whole task. Default to "conll18_ud_eval"
        if "evaluation" in dataset_config[dataset]:
            mergedSettings['dataset_reader']['datasets'][dataset]['evaluation'] = dataset_config[dataset]['evaluation']
        else:
            mergedSettings['dataset_reader']['datasets'][dataset]['evaluation'] = "conll18_ud_eval"

        mergedSettings['dataset_reader']['datasets'][dataset]['word_idx'] = dataset_config[dataset]['word_idx']
        mergedSettings['dataset_reader']['datasets'][dataset]['tasks'] = {}

        for task in dataset_config[dataset]['tasks']:
            mergedSettings['model']['decoders'][task] = copy.deepcopy(defaultDecoder)
            mergedSettings['model']['decoders'][task]['dataset'] = dataset
            mergedSettings['model']['decoders'][task]['task'] = task
            for item in dataset_config[dataset]['tasks'][task]:
                if type(dataset_config[dataset]['tasks'][task][item]) == Params:
                    for deepItem in dataset_config[dataset]['tasks'][task][item]:
                        mergedSettings['model']['decoders'][task][item][deepItem] = dataset_config[dataset]['tasks'][task][item][deepItem]
                else:
                    mergedSettings['model']['decoders'][task][item] = dataset_config[dataset]['tasks'][task][item]
            mergedSettings['dataset_reader']['datasets'][dataset]['tasks'][task] = copy.deepcopy(mergedSettings['model']['decoders'][task].as_dict())
            
            orderIdx = mergedSettings['dataset_reader']['datasets'][dataset]['tasks'][task]['order']
            curTrans = mergedSettings['dataset_reader']['datasets'][dataset]['tasks'][task]['transformer']
            curLayer = mergedSettings['dataset_reader']['datasets'][dataset]['tasks'][task]['layer']
            
            orderedStuff[task] = [orderIdx, curTrans, curLayer]
    # to support reading from multiple files we add them to the datasetreader constructor instead
    # the following ones are there just here to make allennlp happy
    mergedSettings['train_data_path'] = 'train'
    mergedSettings['validation_data_path'] = 'dev'
    mergedSettings['test_data_path'] = 'test'
    
    
    # generate ordered lists, which make it easier to use in the udify model
    orderedTasks = []
    orderedTransformers = []
    orderedLayers = []
    for label, idx in sorted(orderedStuff.items(), key=lambda item: item[1]):
        orderedTasks.append(label)
        orderedTransformers.append(orderedStuff[label][1])
        orderedLayers.append(orderedStuff[label][2])
    mergedSettings['model']['tasks'] = orderedTasks
    mergedSettings['model']['transformers'] = orderedTransformers
    mergedSettings['model']['layers_for_tasks'] = orderedLayers
    
    mergedSettings['model']['decoders'][orderedTasks[0]]['prev_task'] = None
    for taskIdx, task in enumerate(orderedTasks[1:]):
        mergedSettings['model']['decoders'][task]['prev_task'] = orderedTasks[taskIdx] 
        #taskIdx is not +1, because first item is skipped

    # remove items from tagdecoder, as they are not neccesary there
    for item in ['transformer', 'dataset', 'column_idx', 'layer', 'order']:
        for task in mergedSettings['model']['decoders']:
            if item in mergedSettings['model']['decoders'][task]:
                del mergedSettings['model']['decoders'][task][item]

    #TODO implement the other override options!
    if 'trainer' in overrides and 'cuda_device' in overrides['trainer']:
        mergedSettings['trainer']['cuda_device'] = overrides['trainer']['cuda_device']

    mergedSettings['model']['bert_path'] = mergedSettings['dataset_reader']['token_indexers']['bert']['pretrained_model']
    
    return mergedSettings


def cache_vocab(params: Params, vocab_config_path: str = None):
    """
    Caches the vocabulary given in the Params to the filesystem. Useful for large datasets that are run repeatedly.
    :param params: the AllenNLP Params
    :param vocab_config_path: an optional config path for constructing the vocab
    """
    if "vocabulary" not in params or "directory_path" not in params["vocabulary"]:
        return

    vocab_path = params["vocabulary"]["directory_path"]

    if os.path.exists(vocab_path):
        if os.listdir(vocab_path):
            return

        # Remove empty vocabulary directory to make AllenNLP happy
        try:
            os.rmdir(vocab_path)
        except OSError:
            pass

    vocab_config_path = vocab_config_path if vocab_config_path else VOCAB_CONFIG_PATH

    params = merge_configs([params, Params.from_file(vocab_config_path)])
    params["vocabulary"].pop("directory_path", None)
    make_vocab_from_params(params, os.path.split(vocab_path)[0])


def get_ud_treebank_files(dataset_dir: str, treebanks: List[str] = None) -> Dict[str, Tuple[str, str, str]]:
    """
    Retrieves all treebank data paths in the given directory.
    :param dataset_dir: the directory where all treebank directories are stored
    :param treebanks: if not None or empty, retrieve just the subset of treebanks listed here
    :return: a dictionary mapping a treebank name to a list of train, dev, and test conllu files
    """
    datasets = {}
    treebanks = os.listdir(dataset_dir) if not treebanks else treebanks
    for treebank in treebanks:
        treebank_path = os.path.join(dataset_dir, treebank)
        conllu_files = [file for file in sorted(os.listdir(treebank_path)) if file.endswith(".conllu")]

        train_file = [file for file in conllu_files if file.endswith("train.conllu")]
        dev_file = [file for file in conllu_files if file.endswith("dev.conllu")]
        test_file = [file for file in conllu_files if file.endswith("test.conllu")]

        train_file = os.path.join(treebank_path, train_file[0]) if train_file else None
        dev_file = os.path.join(treebank_path, dev_file[0]) if dev_file else None
        test_file = os.path.join(treebank_path, test_file[0]) if test_file else None

        datasets[treebank] = (train_file, dev_file, test_file)
    return datasets


def get_ud_treebank_names(dataset_dir: str) -> List[Tuple[str, str]]:
    """
    Retrieves all treebank names from the given directory.
    :param dataset_dir: the directory where all treebank directories are stored
    :return: a list of long and short treebank names
    """
    treebanks = os.listdir(dataset_dir)
    short_names = []

    for treebank in treebanks:
        treebank_path = os.path.join(dataset_dir, treebank)
        conllu_files = [file for file in sorted(os.listdir(treebank_path)) if file.endswith(".conllu")]

        test_file = [file for file in conllu_files if file.endswith("test.conllu")]
        test_file = test_file[0].split("-")[0] if test_file else None

        short_names.append(test_file)

    treebanks = ["_".join(treebank.split("_")[1:]) for treebank in treebanks]

    return list(zip(treebanks, short_names))


def predict_model_with_archive(predictor: str, params: Params, archive: str,
                               input_file: str, output_file: str, batch_size: int = 1):
    cuda_device = params["trainer"]["cuda_device"]

    check_for_gpu(cuda_device)
    archive = load_archive(archive,
                           cuda_device=cuda_device)

    predictor = Predictor.from_archive(archive, predictor)

    manager = _PredictManager(predictor,
                              input_file,
                              output_file,
                              batch_size,
                              print_to_console=False,
                              has_dataset_reader=True)
    manager.run()


def predict_and_evaluate_model_with_archive(predictor: str, params: Params, archive: str, gold_file: str,
                               pred_file: str, output_file: str, eval_type: str, segment_file: str = None, batch_size: int = 1):
    if not gold_file or not os.path.isfile(gold_file):
        logger.warning(f"No file exists for {gold_file}")
        return

    segment_file = segment_file if segment_file else gold_file
    predict_model_with_archive(predictor, params, archive, segment_file, pred_file, batch_size)

    if eval_type == "conll18_ud_eval":
        try:
            evaluation = evaluate(load_conllu_file(gold_file), load_conllu_file(pred_file))
            save_metrics(evaluation, output_file)
        except UDError:
            logger.warning(f"Failed to evaluate {pred_file}")
            traceback.print_exc()
    elif eval_type == "GE11_ASRM":
        evaluation = evaluate_asrm(gold_file, pred_file)
    else:
        logger.warning(f"The metric \"{eval_type}\" is not implemented yet.")


def predict_model(predictor: str, params: Params, archive_dir: str,
                  input_file: str, output_file: str, batch_size: int = 1):
    """
    Predict output annotations from the given model and input file and produce an output file.
    :param predictor: the type of predictor to use, e.g., "udify_predictor"
    :param params: the Params of the model
    :param archive_dir: the saved model archive
    :param input_file: the input file to predict
    :param output_file: the output file to save
    :param batch_size: the batch size, set this higher to speed up GPU inference
    """
    archive = os.path.join(archive_dir, "model.tar.gz")
    predict_model_with_archive(predictor, params, archive, input_file, output_file, batch_size)


def predict_and_evaluate_model(predictor: str, params: Params, archive_dir: str, gold_file: str,
                               pred_file: str, output_file: str, eval_type: str, segment_file: str = None, batch_size: int = 1):
    """
    Predict output annotations from the given model and input file and evaluate the model.
    :param predictor: the type of predictor to use, e.g., "udify_predictor"
    :param params: the Params of the model
    :param archive_dir: the saved model archive
    :param gold_file: the file with gold annotations
    :param pred_file: the input file to predict
    :param output_file: the output file to save
    :param eval_type: the kind of evaluation to perform at the end
    :param segment_file: an optional file separate gold file that can be evaluated,
    useful if it has alternate segmentation
    :param batch_size: the batch size, set this higher to speed up GPU inference
    """
    archive = os.path.join(archive_dir, "model.tar.gz")
    predict_and_evaluate_model_with_archive(predictor, params, archive, gold_file,
                                            pred_file, output_file, eval_type, segment_file, batch_size)


def save_metrics(evaluation: Dict[str, Any], output_file: str):
    """
    Saves CoNLL 2018 evaluation as a JSON file.
    :param evaluation: the evaluation dict calculated by the CoNLL 2018 evaluation script
    :param output_file: the output file to save
    """
    evaluation_dict = {k: v.__dict__ for k, v in evaluation.items()}

    with open(output_file, "w") as f:
        json.dump(evaluation_dict, f, indent=4)

    logger.info("Metric     | Correct   |      Gold | Predicted | Aligned")
    logger.info("-----------+-----------+-----------+-----------+-----------")
    for metric in ["Tokens", "Sentences", "Words", "UPOS", "XPOS", "UFeats",
                   "AllTags", "Lemmas", "UAS", "LAS", "CLAS", "MLAS", "BLEX"]:
        logger.info("{:11}|{:10.2f} |{:10.2f} |{:10.2f} |{}".format(
                    metric,
                    100 * evaluation[metric].precision,
                    100 * evaluation[metric].recall,
                    100 * evaluation[metric].f1,
                    "{:10.2f}".format(100 * evaluation[metric].aligned_accuracy)
                    if evaluation[metric].aligned_accuracy is not None else ""))


def cleanup_training(serialization_dir: str, keep_archive: bool = False, keep_weights: bool = False):
    """
    Removes files generated from training.
    :param serialization_dir: the directory to clean
    :param keep_archive: whether to keep a copy of the model archive
    :param keep_weights: whether to keep copies of the intermediate model checkpoints
    """
    if not keep_weights:
        for file in glob.glob(os.path.join(serialization_dir, "*.th")):
            os.remove(file)
    if not keep_archive:
        os.remove(os.path.join(serialization_dir, "model.tar.gz"))


def archive_bert_model(serialization_dir: str, config_file: str, output_file: str = None):
    """
    Extracts BERT parameters from the given model and saves them to an archive.
    :param serialization_dir: the directory containing the saved model archive
    :param config_file: the configuration file of the model archive
    :param output_file: the output BERT archive name to save
    """
    archive = load_archive(os.path.join(serialization_dir, "model.tar.gz"))

    model = archive.model
    model.eval()

    try:
        bert_model = model.text_field_embedder.token_embedder_bert.model
    except AttributeError:
        logger.warning(f"Could not find the BERT model inside the archive {serialization_dir}")
        traceback.print_exc()
        return

    weights_file = os.path.join(serialization_dir, "pytorch_model.bin")
    torch.save(bert_model.state_dict(), weights_file)

    if not output_file:
        output_file = os.path.join(serialization_dir, "bert-finetune.tar.gz")

    with tarfile.open(output_file, 'w:gz') as archive:
        archive.add(config_file, arcname="bert_config.json")
        archive.add(weights_file, arcname="pytorch_model.bin")

    os.remove(weights_file)


def evaluate_sigmorphon_model(gold_file: str, pred_file: str, output_file: str):
    """
    Evaluates the predicted file according to SIGMORPHON 2019 Task 2
    :param gold_file: the gold annotations
    :param pred_file: the predicted annotations
    :param output_file: a JSON file to save with the evaluation metrics
    """
    results_keys = ["lemma_acc", "lemma_dist", "msd_acc", "msd_f1"]

    reference = read_conllu(gold_file)
    output = read_conllu(pred_file)
    results = manipulate_data(input_pairs(reference, output))

    output_dict = {k: v for k, v in zip(results_keys, results)}

    with open(output_file, "w") as f:
        json.dump(output_dict, f, indent=4)


def to_multilabel_sequence(predictions, vocab, task):
    # Hard-coded parameters for now
    THRESH = 0.99#0.5
    k = 2
    outside_index = vocab.get_token_index("O", namespace=task)

    # Get the thresholded matrix and prepare the prediction sequence
    pred_over_thresh = (predictions >= THRESH) * predictions
    sequence_token_labels = []

    # For each label set, check if to apply argmax or sigmoid thresh
    for pred in pred_over_thresh:
        num_pred_over_thresh = numpy.count_nonzero(pred)

        if num_pred_over_thresh < k:
            pred_idx_list = [numpy.argmax(predictions, axis=-1)]
            # print("argmax  ->", pred_idx_list)
        else:
            pred_idx_list = [numpy.argmax(predictions, axis=-1)]
            # pred_idx_list = list(numpy.argpartition(pred, -k)[-k:])
            # # print("sigmoid ->", pred_idx_list)

            # # If the first (i.e., second best) is "O", ignore/remove it
            # if pred_idx_list[0] == outside_index:
            #     pred_idx_list = pred_idx_list[1:]
            # # If the second (i.e., the best) is "O", ignore/remove the first
            # elif pred_idx_list[1] == outside_index:
            #     pred_idx_list = pred_idx_list[1:]
            # else:
            #     pass

        sequence_token_labels.append(pred_idx_list)

    return sequence_token_labels
