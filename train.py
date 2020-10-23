"""
Training script useful for debugging UDify and AllenNLP code
"""

import os
import copy
import datetime
import logging
import argparse

from allennlp.common import Params
from allennlp.common.util import import_submodules
from allennlp.commands.train import train_model

from udify import util

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

parser = argparse.ArgumentParser()
parser.add_argument("--name", default="", type=str, help="Log dir name")
parser.add_argument("--dataset_config", default="", type=str, help="Configuration file for datasets")
parser.add_argument("--parameters_config", default="", type=str, help="Configuration file for parameters of the model")
parser.add_argument("--device", default=None, type=int, help="CUDA device; set to -1 for CPU")
parser.add_argument("--resume", type=str, help="Resume training with the given model")
parser.add_argument("--lazy", default=None, action="store_true", help="Lazy load the dataset")
parser.add_argument("--cleanup_archive", action="store_true", help="Delete the model archive")
parser.add_argument("--replace_vocab", action="store_true", help="Create a new vocab and replace the cached one")
parser.add_argument("--archive_bert", action="store_true", help="Archives the finetuned BERT model after training")
parser.add_argument("--predictor", default="udify_predictor", type=str, help="The type of predictor to use")

args = parser.parse_args()

log_dir_name = args.name
if not log_dir_name:
    file_name = args.dataset_config if args.dataset_config else args.parameters_config
    log_dir_name = os.path.basename(file_name).split(".")[0]

if not args.resume:
    serialization_dir = os.path.join("logs", log_dir_name, datetime.datetime.now().strftime("%Y.%m.%d_%H.%M.%S"))

    overrides = {}
    if args.device is not None:
        overrides["trainer"] = {"cuda_device": args.device}
    if args.lazy is not None:
        overrides["dataset_reader"] = {"lazy": args.lazy}
    train_params = util.merge_configs(args.parameters_config, args.dataset_config, overrides)
#else:
#    serialization_dir = args.resume
#    train_params = Params.from_file(os.path.join(serialization_dir, "config.json"))
    #TODO override stuff!

if "vocabulary" in train_params:
    # Remove this key to make AllenNLP happy
    train_params["vocabulary"].pop("non_padded_namespaces", None)

predict_params = train_params.duplicate()

import_submodules("udify")

try:
    util.cache_vocab(train_params)
    train_model(train_params, serialization_dir, recover=bool(args.resume))
except KeyboardInterrupt:
    logger.warning("KeyboardInterrupt, skipping training")

#dev_file = train_params["validation_data_path"]
#test_file = train_params["test_data_path"]

#dev_pred, dev_eval, test_pred, test_eval = [
#    os.path.join(serialization_dir, name)
#    for name in ["dev.conllu", "dev_results.json", "test.conllu", "test_results.json"]
#]

#if dev_file != test_file:
#    util.predict_and_evaluate_model(args.predictor, predict_params, serialization_dir, dev_file, dev_pred, dev_eval)

#util.predict_and_evaluate_model(args.predictor, predict_params, serialization_dir, test_file, test_pred, test_eval)

for dataset in predict_params['dataset_reader']['datasets']:
    dev_file = predict_params['dataset_reader']['datasets'][dataset]['dev']
    dev_pred = os.path.join(serialization_dir, 'dev.conllu')
    dev_eval = os.path.join(serialization_dir, 'dev_results.json' )
    eval_type = predict_params['dataset_reader']['datasets'][dataset]['evaluation']
    util.predict_and_evaluate_model(args.predictor, predict_params, serialization_dir, dev_file, dev_pred, dev_eval, eval_type)

#if args.archive_bert:
#    bert_config = "config/archive/bert-base-multilingual-cased/bert_config.json"
#    util.archive_bert_model(serialization_dir, bert_config)

# If we want to use trainer>num_serialized_models_to_keep we need to comment this automatic cleanup
util.cleanup_training(serialization_dir, keep_archive=not args.cleanup_archive)
