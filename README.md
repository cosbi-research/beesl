# Biomedical Event Extraction as Sequence Labeling <img src="resources/bee.png" width="50" height="38"/>

This repository contains the source code for the paper: [Biomedical Event Extraction as Sequence Labeling](https://www.researchgate.net/publication/344541520_Biomedical_Event_Extraction_as_Sequence_Labeling) (**BeeSL**). You may freely use [this work](#reference-and-contact) in your research and activities under the non-commercial [COSBI-SSLA license](https://www.cosbi.eu/research/prototypes/licence_terms).

BeeSL is a deep learning solution that is fast, accurate, end-to-end, and unlike current methods does not require any external knowledge base or preprocessing tools as it builds on [BERT](https://www.aclweb.org/anthology/N19-1423/). Empirical results show that BeeSL's speed and accuracy makes it a viable approach for large-scale real-world scenarios.

For more information on ongoing work on biomedical information extraction you may want to visit the [COSBI knowledge extraction page](https://www.cosbi.eu/research/prototypes/biomedical_knowledge_extraction) or get in touch with the Cosbi Bioinformatics lab led by lombardo@cosbi.eu.

- [How does BeeSL work (in short)?](#how-does-beesl-work)
- [Installation](#installation)
- [Usage](#system-usage)
  + [Event detection (prediction)](#event-detection-prediction)
  + [Training a new model](#training-a-new-model)
- [Configuration and formats](#configuration-and-formats)
- [Reference](#reference-and-contact)


# How does BeeSL work?

Biomedical events are structured representations which comprise multiple information units (Figure 1, top part). We convert the event structures into a representation in which each token (roughly, word) is assigned labels summarizing its pertinent parts of the original event structure (Figure 1, bottom part), where:
- `d` (*dependent*): the mention type of the token (either an event trigger, entity, or nothing)
- `r` (*relation*): the argument role of the token (with respect to the event it is participating in)
- `h` (*head*): the type and the relative position of the event the token refers to (of which it is an argument)

![encoding](resources/encoding.png)
**Figure 1**: *Top: a text excerpt with four biomedical events. Above the text (italicized), mentions (triggers inside rounded boxes, and entities without rounded boxes) and argument roles are indicated. Bottom: our proposed encoding, where d, r and h represent the label parts for dependents, relations, and heads, respectively. See the [paper]() for more details.*

At this point any token may then have multiple associated labels. We recast event extraction as a sequence labeling task and, adopting a system thinking approach, we design a multi-label aware encoding strategy for jointly modeling the intermediate tasks via multi-task learning.

After encoding events as a sequence of labels the labels for the token sequences are predicted using a neural architecture employing BERT as encoder. Dedicated classifiers for predicting the label parts (referred as tasks) are devised. Experimental results show that the best results are achieved by learning two tasks in a multi-task setup: `<d>` (with a single label classifier) and `<r,h>` (with a multi-label classifier, to capture the participation of the token into multiple events). The sequences are thus decoded to the original event representation (Figure 1, top part).


# Installation

It is recommended to install an environment management system (e.g., [miniconda3](https://docs.conda.io/en/latest/miniconda.html)) to avoid conflicts with other programs. After installing miniconda3, create the environment and install the requirements:
```
cd $BEESL_DIR                             # the folder where you put this codebase
conda create --name beesl-env python=3.7  # create an python 3.7 env called beesl-env
conda activate beesl-env                  # activate the environment
python -m pip install -r requirements.txt # install the packages from requirements.txt
```
**NOTE**: we have tried hard, but there is no easy way to ship the installation of conda across operating systems and users, therefore this step is a necessary manual operation to do.

Download the pre-trained [BioBERT-Base v1.1 (+ PubMed 1M) model](https://github.com/dmis-lab/biobert "here") and run:
```
# Extract the model, convert it to pytorch, and clean the directory
tar xC models -f $DOWNLOAD_DIR/biobert_v1.1_pubmed.tar.gz 
pytorch_transformers bert models/biobert_v1.1_pubmed/model.ckpt-1000000 models/biobert_v1.1_pubmed/bert_config.json models/biobert_v1.1_pubmed/pytorch_model.bin
rm models/biobert_v1.1_pubmed/model.ckpt*
```
Download the GENIA event data with our automatized script:
```
sh download_data.sh
```
Download the BeeSL model described in the [paper](#reference-and-contact). Place the model in beesl/models/beesl-model/. In that folder you may later place your [own BERT-based models](#training). The models are declared in the file config/params.json, setting the parameter `pretrained_model`. The provided config.json already references the model at that path. If you place the model somewhere else, make sure to update the configuration.
```
curl -O https://www.cosbi.eu/fx/2354/model.tar.gz
```

Done! You now have everything to move to next sestion of using the system.



# Usage

While this is a research product, the quality reached by the systems makes it suitable to be used in real settings for [event detection](#prediction) and [training of new models of your own](#training). 


## Event detection (prediction)

In order to predict biomedical events, run:
```
python predict.py $PATH_TO_MODEL $INPUT_FILE $OUTPUT_FILE --device $DEVICE
```

The arguments are
* `$PATH_TO_MODEL`: a serialized model fine-tuned on biomedical events, for example the one provided above at https://www.cosbi.eu/fx/2354/model.tar.gz.
* `$INPUT_FILE`: a filepath with data into a token-level format with entities masked ([details on the format](#configuration-and-formats))
  * e.g., `$BEESL_DIR/data/GE11/masked/test.mt.1` we provide, or your own data (see [how to do it](#token-level-data-format))
* `$OUTPUT_FILE`: a filepath where to write the predictions of events
* `$DEVICE`: a device where to run the inference (i.e., CPU: `-1`, GPU: `0`, `1`, ...)

To convert the token-level predictions to a standard event format use:
```
# Merge predicted label parts, and convert them back to the BioNLP standoff format
python bio-mergeBack.py $PRED_FILE $INPUT_FILE 2 > $MERGED_PRED_FILE
python bioscripts/postprocess.py --filepath $MERGED_PRED_FILE
```
- `$PRED_FILE`: a filepath containing predictions (i.e., the `$OUTPUT_FILE` above)
- `$INPUT_FILE`: a filepath with data into a token-level format with entities not masked
- `$MERGED_PRED_FILE`: a filepath containing the resulting merged predictions

Predicted event files in the standard [BioNLP standoff format](http://2011.bionlp-st.org/home/file-formats) will be created in `$BEESL_DIR/output`.

To evaluate the prediction performance on the GENIA test set, compress the results `cd $BEESL_DIR/output/ && tar -czf predictions.tar.gz *.a2` and submit `predictions.tar.gz` to the official [GENIA online evaluation service](http://bionlp-st.dbcls.jp/GE/2011/eval-test/).


## Training a new model

To train a new model type:
```
python train.py --name $NAME --dataset_config $DATASET_CONFIG --parameters_config $PARAMETERS_CONFIG --device $DEVICE
```
* `$NAME`: a name for the execution that will be used as folder where outputs will be stored
* `$DATASET_CONFIG`: a filepath to a config file storing information on the task(s) (see [details](#dataset-configuration-file))
  * e.g., `$BEESL_DIR/config/mt.1.mh.0.50.json` we provide (recommended), or your own one
* `$PARAMETERS_CONFIG`: a filepath to a config file storing network parameters details (see [details](#parameters-configuration-file))
  * e.g., `$BEESL_DIR/config/params.json` we provide (recommended), or your own one
* `$DEVICE`: a device where to run the training (i.e., CPU: `-1`, GPU: `0`, `1`, ...)

The serialized model will be stored in `beesl/logs/$NAME/$DATETIME/model.tar.gz`, where `$DATETIME` is a folder to disambiguate multiple executions with the same `$NAME`. A performance report will be in `beesl/logs/$NAME/$DATETIME/results.txt`. You can then use the model to [predict](#prediction) new data.



# Configuration and formats


## Token-level data format

Biomedical events are defined using the standard [BioNLP standoff format](http://2011.bionlp-st.org/home/file-formats). To encode biomedical events from the BioNLP standoff format into sequences of labels for BeeSL, run the following:
```
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking $MASKING
```
- `$CORPUS_FOLDER`: the folder name in `$BEESL_DIR/data/corpora/` containing biomedical events in the standard BioNLP standoff format
  - e.g., `GE11` you just downloaded, or your standard BioNLP standoff formatted corpus
- `$MASKING`: the masking of entity. You need to run for both `no` and `type` values
  - `type` means masking the token with the entity type text placeholder (to avoid overfitting to words during training), whereas `no` is used during evaluation only (to ensure the correct evaluation of entity arguments)

### Details on the format

The token-level file format has the following shape, where each sentence has an header `doc_id = $DOC_ID` indicating the document id, and all its tokens are on new lines (with token information on columns, described below). Finally, an empty newline follows the last token (see this [token-level file example](data/GE11/masked/test.mt.1) for more information):
```
# doc_id = $DOC_ID
$TOKEN_TEXT	$START-$END	$ID	$ENTITY_TYPE	$EXTRA	$EXTRA	$LABEL(1)	...	$LABEL(n)
...
```

- `$DOC_ID`: the identifier of the document
- `$TOKEN_TEXT`: the text of the token (or a masked version, as described above)
- `$START`: the start offset of the token with respect to the document
- `$END`: the end offset of the token with respect to the document
- `$ID`: the entity id, if any. If not, `O` is printed
- `$ENT_TYPE`: the entity type, if any. If not, `-` is printed
- `$EXTRA`: any extra information (not needed for the computation)
- `$LABEL(i)`: a label part. You can have many columns as the number of tasks


## Configuration files

The training process requires configuration files to know how to conduct the training itself. For more information on possible keys refer to the original [AllenNLP configuration template](https://github.com/allenai/allennlp-template-config-files/blob/master/training_config/my_model_trained_on_my_dataset.jsonnet), on which our configuration files are based.

**Dataset configuration file**

A dataset configuration file is used to define the data path and details on the tasks. **We recommend to use our configuration file for the multi-task multi-label setup** (`$BEESL_DIR/config/mt.1.mh.0.50.json` [here](config/mt.1.mh.0.50.json)). In the case you need to train BeeSL on new data, you need to define the path to your data (we explained how to create these data files in the [Token-level data format](#token-level-data-format) section):
```
"train_data_path": "",      # path to the masked token-level training file
"validation_data_path": "", # path to the masked token-level validation file
"test_data_path": "",       # path to the masked token-level validation file
```

**Parameters configuration file**

A parameters configuration file is used to define the details of the model (i.e., hyper-parameters, BERT details, etc.). **We recommend to use our parameters configuration file** (`$BEESL_DIR/config/params.json` [here](config/params.json)). Expert users that want to run an hyper-parameter tuning themselves can refer to the [AllenNLP configuration template](https://github.com/allenai/allennlp-template-config-files/blob/master/training_config/my_model_trained_on_my_dataset.jsonnet) for the meaning of all keys in the `json` file.



# Reference and Contact

If you use this work in your research paper, please cite us!

```
@inproceedings{ramponi-etal-2020-biomedical,
    title     = "{B}iomedical {E}vent {E}xtraction as {S}equence {L}abeling",
    author    = "Ramponi, Alan and van der Goot, Rob and Lombardo, Rosario and Plank, Barbara",
    year      = "2020",
    booktitle = "Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP)",
    publisher = "Association for Computational Linguistics",
    pages     = "", % we will update this field when available
    location  = "Online",
    url       = ""  % we will update this field when available
}
```
For any information of request please get in touch with the Cosbi Bioformatics lab led by lombardo@cosbi.eu where we'll happy to help.
