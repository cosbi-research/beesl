# FILES constants
DATA_SPLITS = ["train", "dev", "test"]
EXCL_FILENAMES = ["README", "LICENSE", ".DS_Store"]
EXT_FILES = {"txt": ".txt", "a1": ".a1", "a2": ".a2"}

# ANNOTATION constants
ANN_SKIP = ["M", "*", "R", "A"] # mod, rel, cor@GE13, mod@MLEE

SEC_ENTITIES = ["Entity"]
SEC_EDGES = ["Site", "Site2", "Site3", "CSite", "AtLoc", "FromLoc", "ToLoc"]
GE11_EVENT_TYPES = ["Gene_expression", "Transcription", "Protein_catabolism", 
					"Phosphorylation", "Localization", "Binding", "Regulation", 
					"Positive_regulation", "Negative_regulation"]

# ENCODING constants
SEP_MULTIPLE = "////"
SEP_MULTIPLE_INNER = "$"
SEP_SPAN = "-"
SEP_LABEL_PART = "|"
SEP_LABEL_TASK = "{}" # to deprecate
SEP_COLUMN = "\t"
TOK_SINGLE = "B-"
TOK_OUTSIDE = "O"