# File formats and configuration

This section gives complete yet concise details on how to create and use configuration files and data files in BeeSL.

For any information or request you may want to get in touch with the Cosbi Bioformatics lab led by lombardo@cosbi.eu. We'll be happy to help!

## BeeSL data format

Biomedical events are commonly defined using the standard [BioNLP standoff format](http://2011.bionlp-st.org/home/file-formats). A script `bioscripts/preprocess.py` is provided to convert the BioNLP standoff biomedical events format into BeeSL format. It also has an additional argument to mask and unmask the mentions of entities as described in the [usage](README.md#usage):

```
# For masking mentions
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking type
# For unmasking the mentions
python bioscripts/preprocess.py --corpus $CORPUS_FOLDER --masking no
```

Masking is used during training and prediction to avoid overfitting to mention types (**d**) during training (argument `type` e.g. `$PROTEIN` in the example below).
Unmasking is used to write the entities back and be able to use and verify the mention types in your work or for performance evaluation (the argument `no`).

**Details on the BeeSL file format**
The BeeSL file format makes explicit the sequence of labels proved to boost perfomances. Each sentence starts with a header `doc_id = $DOC_ID` denoting the sentence identifier. All sentence tokens are then placed one per line. An empty line follows the last token. Note that senteces can be at most 512 tokens long as per BERT model input.

Here is the specification, followed by an excerpt of a [full example](data/GE11/masked/test.mt.1):
```
# doc_id = $DOC_ID
$TOKEN_TEXT  $START-$END  $ENTITY_ID  $ENT_TYPE $EXTRA  $EXTRA      $LABEL(1) ... $LABEL(n)
```
Excerpt:
```
# doc_id = PMC-1064873-00-TIAB
Resistance   0-10         O           [ENT]-    [POS]NOUN [DEP]ROOT   O       O
to           11-13        O           [ENT]-    [POS]PART [DEP]case   O       O
$PROTEIN$    14-19        T1          [ENT]Protein [POS]NOUN [DEP]compound   O       O
inhibition   20-30        O           [ENT]-    [POS]NOUN [DEP]nmod   O       O
of           31-33        O           [ENT]-    [POS]ADP  [DEP]case   O       O
$PROTEIN$    34-50        T2          [ENT]Protein [POS]NOUN [DEP]compound   O       O
production   51-61        O           [ENT]-    [POS]NOUN [DEP]nmod   O       O
and          62-65        O           [ENT]-    [POS]CCONJ [DEP]cc    O       O
expression   66-76        O           [ENT]-    [POS]NOUN [DEP]conj   O       O
of           77-79        O           [ENT]-    [POS]ADP  [DEP]case   O       O
$PROTEIN$    80-114       T3          [ENT]Protein [POS]NOUN [DEP]nmod O       O
in           115-117      O           [ENT]-    [POS]ADP  [DEP]case   O       O
$PROTEIN$    118-121      T4          [ENT]Protein [POS]NOUN [DEP]compound O       O
+            121-122      O           [ENT]-    [POS]CCONJ [DEP]cc    O       O
T            123-124      O           [ENT]-    [POS]NOUN [DEP]conj   O       O
cells        125-130      O           [ENT]-    [POS]NOUN [DEP]nmod   O       O

# doc_id = PMC-1064873-00-TIAB
$PROTEIN$    172-177   T5             [ENT]Protein [POS]NOUN [DEP]nsubjpass O       O
has          178-181   O              [ENT]-    [POS]AUX  [DEP]aux    O       O
...
```

Where:

- `$TOKEN_TEXT`: the text of the token (or a masked version, as described above)
- `$START-$END`: the `start` and `end` offsets of the token with respect to the document
- `$ENTITY_ID`: the entity id, if any. If not an entity, `O` is printed
- `$ENT_TYPE`: the entity type, if any. If not an entity, `-` is printed
- `$EXTRA`: any extra information (not needed for the computation)
- `$LABEL(i)`: a label part. You can have many columns as the number of tasks, 3 in the example.

## Configuration files

The training process requires configuration files to know how to conduct the training itself. For more information on possible keys refer to the original [AllenNLP configuration template](https://github.com/allenai/allennlp-template-config-files/blob/master/training_config/my_model_trained_on_my_dataset.jsonnet), on which our configuration files are based.

### Dataset configuration file

A dataset configuration file is used to define the data path and details on the tasks. **We recommend to use our configuration file for the multi-task multi-label setup [`$BEESL_DIR/config/mt.1.mh.0.50.json`](config/mt.1.mh.0.50.json)**. In the case you need to train BeeSL on new data, you need to define the path to [your data](#beesl-data-format):

```
"train_data_path": "",      # path to the masked token-level training file
"validation_data_path": "", # path to the masked token-level validation file
"test_data_path": "",       # path to the masked token-level validation file
```

### Model parameters configuration file

A parameters configuration file is used to define the details of the model (i.e., hyper-parameters, BERT details, etc.). **We recommend to use our parameters configuration file [`$BEESL_DIR/config/params.json`](config/params.json)**. Expert users that want to run an hyper-parameter tuning themselves can refer to the [AllenNLP configuration template](https://github.com/allenai/allennlp-template-config-files/blob/master/training_config/my_model_trained_on_my_dataset.jsonnet) for the meaning of all keys in the `json` file.
