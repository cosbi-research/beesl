# Biomedical Event Extraction as Sequence Labeling (BeeSL)<img src="resources/bee.png" width="50" height="38"/>

BeeSL is a deep learning solution that is fast, accurate, end-to-end, and unlike current methods does not require any external knowledge base or preprocessing tools as it builds on [BERT](https://www.aclweb.org/anthology/N19-1423/). Empirical results show that BeeSL's speed and accuracy makes it a viable approach for large-scale real-world scenarios.

This repository contains the source code for [Biomedical Event Extraction as Sequence Labeling](https://www.researchgate.net/publication/344541520_Biomedical_Event_Extraction_as_Sequence_Labeling) (BeeSL). You may freely use [this work](#reference-and-contact) in your research and activities under the non-commercial [COSBI-SSLA license](https://www.cosbi.eu/research/prototypes/licence_terms).

For more information on ongoing work in biomedical information extraction you may want to visit the [COSBI knowledge extraction page](https://www.cosbi.eu/research/prototypes/biomedical_knowledge_extraction) or get in touch with the Cosbi Bioinformatics lab led by lombardo@cosbi.eu. We'll be happy to help!

## Table of contents

- [How does BeeSL work (in short)?](#how-does-beesl-work)
- [Installation](#installation)
- [Usage](#usage)
  + [Event extraction (prediction)](#event-extraction-prediction)
  + [Training a new model](#training-a-new-model)
- [Reference](#reference-and-contact)


# How does BeeSL work?

Biomedical events are structured representations which comprise multiple information units (Figure 1, above the line). We encode such event structure into a representation in which each token (roughly, word) is assigned the following labels summarizing its pertinent parts of the original event structure (Figure 1, below the line):
- **d**ependent or, *type of mention*, the token assumes in the event, either an *event trigger*, an *entity*, or *nothing*;
- **r**elation or, *thematic role*, the argument token is playing in the event;
- **h**ead of an event is a verbal form; here, the it's the event initiator to be denoted as head, along with the event *type* and position (subscript) of the event verb the initiator refers to.

![encoding](resources/encoding.png)
**Figure 1**: *Above the dashed line: an (italicized) text excerpt with four biomedical events. The mention types (**d**) shown upon the text are (boxed) triggers and entities. Thematic roles (**r**), characterizing the event, label the edges among the relevant mentions. Below the dashes: our proposed encoding for mention types (**d**), thematic roles (**r**) and heads (**h**). See the [paper](https://www.researchgate.net/publication/344541520_Biomedical_Event_Extraction_as_Sequence_Labeling) for more details.*

At this point we recast event extraction as a sequence labeling task as any token may have multiple associated labels. Adopting a Systems Thinking approach, we design a multi-label aware encoding strategy for jointly modeling the intermediate tasks via multi-task learning.

After encoding events as a sequence of labels, the labels for the token sequences are predicted using a neural architecture employing BERT as encoder. Dedicated classifiers for predicting the label parts (referred as tasks) are devised. Experimental results show that the best results are achieved by learning two tasks in a multi-task setup. A single label classifier for the mention types (**d**), and a multi-label classifier for thematic roles (**r**) and heads (**h**) `<`**r**,**h**`>` are able to capture the participation of the same token into multiple events. The sequences are finally decoded to the original event representation (Figure 1, above the line).


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
Download the BeeSL model described in the [paper](#reference-and-contact).
```
curl -O https://www.cosbi.eu/fx/2354/model.tar.gz
```
#### Installing the predictive model
Place the downloaded model https://www.cosbi.eu/fx/2354/model.tar.gz in `beesl/models/beesl-model/`. In that folder you may later place your [own trained models](#training-a-new-model). The models are declared in the file config/params.json, setting the parameter `pretrained_model`. The provided [`config/params.json`](config/params.json) already references the model at that path. If you place the model somewhere else, make sure to update the configuration.


You now have everything in place and are ready to start using the system.



# Usage

While this is a research product, the quality reached by the system makes it suitable to be used in real research settings for either [event detection](#event-extraction-prediction) or [training new models](#training-a-new-model) of your own. 

The system was designed to be trained on data where entity mentions have been hidden. This allows to learn the wider linguistic construction rather than the mentions themselves and avoid overfitting to training data, making it more apt to general use, beyond model data. The process is called *masking* of the mentions type (**d**) (e.g. by writing `$PROTEIN` in place of G6PD). A model trained on masked data will best perform event extraction on masked data. Easy masking/unmasking commands are provided in the following examples.

## Event extraction (prediction)

To detect biomedical events, run:
```
# conversion from BioNLP format and masking of "type" mentions
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking type
```
`$CORPUS_FOLDER` contains the biomedical text in the standard [BioNLP standoff format](http://2011.bionlp-st.org/home/file-formats), e.g., `$BEESL_DIR/data/GE11` you just downloaded. This command will create the subfolder `masked` with BeeSL input format suitable to the:

```
# actual event extraction
python predict.py $PATH_TO_MODEL $BEESL_INPUT_FILE $PREDICTIONS_FILE --device $DEVICE
```

Where:
* `$PATH_TO_MODEL`: a serialized model fine-tuned on biomedical events, for example the one provided above at https://www.cosbi.eu/fx/2354/model.tar.gz.
* `$BEESL_INPUT_FILE`: a BeeSL format with entities you have just masked with the previous command. For an example, see the provided [`$BEESL_DIR/data/GE11/masked/test.mt.1`](data/GE11/masked/test.mt.1). More info on the [BeeSL file format](FileFormats.md#beesl-data-format).
* `$PREDICTIONS_FILE`: the predictions of events in BeeSL format
* `$DEVICE`: a device where to run the inference (i.e., CPU: `-1`, GPU: `0`, `1`, ...)


The detected event parts and text portions are now masked in the `$PREDICTIONS_FILE`. To recover back the entities just unmask them with:
```
# unmasking of "type" mentions
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking no
```

The unmasked BeeSL prediction file can be converted into the BioNLP standoff format with the following two lines. An `output/` folder will be created in the BeeSL project with the converted files: 

```
# Merge predicted labels
python bio-mergeBack.py $PREDICTIONS_FILE $BEESL_INPUT_FILE 2 > $PREDICTIONS_NOT_MASKED
# Convert them back to the BioNLP standoff format
python bioscripts/postprocess.py --filepath $PREDICTIONS_NOT_MASKED
```

For example, if you want to evaluate the prediction performance on the GENIA test set (in the BioNLP standoff format), compress the results `cd $BEESL_DIR/output/ && tar -czf predictions.tar.gz *.a2` and submit `predictions.tar.gz` to the official [GENIA online evaluation service](http://bionlp-st.dbcls.jp/GE/2011/eval-test/).


## Training a new model

To train a new model, type:
```
# conversion from BioNLP format and masking of "type" mentions
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking type
```
`$CORPUS_FOLDER` contains the biomedical text in the standard [BioNLP standoff format](http://2011.bionlp-st.org/home/file-formats), e.g., `$BEESL_DIR/data/GE11` you just downloaded. This command will create the subfolder `masked` with BeeSL input format suitable to the:

```
# actual model training
python train.py --name $NAME --dataset_config $DATASET_CONFIG --parameters_config $PARAMETERS_CONFIG --device $DEVICE
```
* `$NAME`: a name for the execution that will be used as folder where outputs will be stored
* `$DATASET_CONFIG`: a filepath to a config file storing [task information](FileFormats.md#dataset-configuration-file)
  * e.g., [`$BEESL_DIR/config/mt.1.mh.0.50.json`](config/mt.1.mh.0.50.json) we provide (recommended), or your own one
* `$PARAMETERS_CONFIG`: a filepath to a config file storing [model parameters](FileFormats.md#model-parameters-configuration-file)
  * e.g., [`$BEESL_DIR/config/params.json`](config/params.json) we provide (recommended), or your own one
* `$DEVICE`: a device where to run the training (i.e., CPU: `-1`, GPU: `0`, `1`, ...)

The serialized masked model will be stored in `beesl/logs/$NAME/$DATETIME/model.tar.gz`, where `$DATETIME` is a folder to disambiguate multiple executions with the same `$NAME`. A performance report will be in `beesl/logs/$NAME/$DATETIME/results.txt`. To use your newly trained model to [predict](#event-extraction-prediction) new data see the [installation instructions](#installing-the-predictive-model) above.


# Reference and Contact

If you use this work in your research paper, we provide the full citation details for your reference.

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

For any information or request you may want to get in touch with the Cosbi Bioformatics lab led by lombardo@cosbi.eu. We'll be happy to help!
