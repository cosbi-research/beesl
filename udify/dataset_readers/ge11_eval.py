import os
import logging

from bioscripts.postprocess import decode

logger = logging.getLogger(__name__)


def is_multitask_encoded(pred_file):
    """""" # To generalize better

    def check_label_columns(line):
        """"""
        columns = line.rstrip("\n").split("\t")
        if len(columns) != 7: return True
        return False

    def multitask_n(line):
        """"""
        columns = line.rstrip("\n").split("\t")
        return len(columns) - 6

    with open(pred_file, "r") as f:
        line_num = 0
        for line in f:
            if line_num == 0:
                line_num += 1
                continue
            elif line_num == 1:
                line_num += 1
                multitask_cols = multitask_n(line)
                #is_multitask = check_label_columns(line)
            else:
                break
    
    return multitask_cols
    # return is_multitask


# Remove hardcoded is_multihead
def merge_columns(gold_file, pred_file, multitask_cols, is_multihead=True):
    """"""

    def getSents(path):
        curSent = []
        sents = []
        for line in open(path):
            if len(line) < 2:
                sents.append(curSent)
                curSent = []
            else:
                # Handle multi-head for task 1
                #if len(line.split('\t')) > 1:
                #    if "$B-" in line.strip().split("\t")[-2]:
                #        before = line.strip().split("\t")[-2]
                #        normalized = line.strip().split("\t")[-2].replace("$B-", "////")
                #        line = line.replace(before, normalized)
                curSent.append(line)
        return sents

    sentsOut = getSents(pred_file)
    sentsGold = getSents(gold_file)
    convType = multitask_cols
    #convType = 1 if not is_multitask else 2

    merged_filename = pred_file + ".fixed"
    merged_file = open(merged_filename, "a")

    for sentGold, sentOut in zip(sentsGold, sentsOut):
        merged_file.write(sentGold[0].strip() + "\n")
        for i in range(1,len(sentGold)):
            newTok = sentGold[i].strip().split('\t')

            # a|b|c|d
            if convType == 1:
                if len(sentOut[i].split('\t')) > 1:
                    newTok[-1] = sentOut[i].split('\t')[-1]

            # a, b|c|d
            # a|b, c|d
            elif convType == 2:
                # a == O,   b|c|d == 0
                # a|b == O, c|d == 0
                if (sentOut[i].split('\t')[-2].startswith("O") and sentOut[i].split('\t')[-1].startswith("O")):
                    newTok[-2] = "O"
                elif ((not sentOut[i].split('\t')[-2].startswith("O")) and sentOut[i].split('\t')[-1].startswith("O")):
                    # if a|O ==> a|O
                    if "|" in sentOut[i].split('\t')[-2]:
                        newTok[-2] = sentOut[i].split('\t')[-2].split("|")[0] + "|" + "O"
                    # if a   ==> a|O
                    else:
                        newTok[-2] = sentOut[i].split('\t')[-2] + "|" + "O"
                # a == O, other == B|* ==> O
                elif (sentOut[i].split('\t')[-2].startswith("O") and (not sentOut[i].split('\t')[-1].startswith("O"))):
                    newTok[-2] = "O"
                # merge them
                else:
                    if "|" in sentOut[i].split('\t')[-2]:
                        # case d|a
                        if ("Theme" in sentOut[i].split('\t')[-2]) or ("Cause" in sentOut[i].split('\t')[-2]):
                            parts1 = sentOut[i].split('\t')[-2].split("$")
                            parts2 = sentOut[i].split('\t')[-1].split("$")
                            label = ""
                            ## Strictly ensure same dimensions ####################
                            if len(parts1) != len(parts2):
                                newTok[-2] = parts1[0].split("|")[0]
                            else:
                                for raw_part1, raw_part2 in zip(parts1, parts2):
                                    d, a = raw_part1.split("|")
                                    h, p = raw_part2.split("|")
                                    label += d + "|" + a + "|" + h[2:] + "|" + p + "$"
                                if label[-1] == "$":
                                    label = label[:-1]
                                newTok[-2] = label
                        #if sentOut[i].split('\t')[-2].split("|")[1] in ["Theme", "Cause"]:
                        #    newTok[-2] = sentOut[i].split('\t')[-2] + '|' + sentOut[i].split('\t')[-1][2:]
                        elif (not "Theme" in sentOut[i].split('\t')[-2]) and (not "Cause" in sentOut[i].split('\t')[-2]):
                            parts1 = sentOut[i].split('\t')[-2].split("$")
                            parts2 = sentOut[i].split('\t')[-1].split("$")
                            label = ""
                            ## Strictly ensure same dimensions ####################
                            if len(parts1) != len(parts2):
                                newTok[-2] = parts1[0].split("|")[0]
                            else:
                                for raw_part1, raw_part2 in zip(parts1, parts2):
                                    mention_and_src = raw_part1.split("|")
                                    if len(mention_and_src) < 3:
                                        label += d + "|O"
                                    else:
                                        d, h, p = mention_and_src
                                        a = raw_part2.rstrip()
                                        label += d + "|" + a[2:] + "|" + h + "|" + p + "$"
                                if label[-1] == "$":
                                    label = label[:-1]
                                newTok[-2] = label
                        elif sentOut[i].split('\t')[-2].split("|")[1].startswith("O"):
                            newTok[-2] = sentOut[i].split('\t')[-2]
                        # case d|h
                        else:
                            parts = sentOut[i].split('\t')[-2].split("|", 1)
                            newTok[-2] = parts[0] + '|' + sentOut[i].split('\t')[-1].rstrip()[2:] + "|" + parts[1]
                    # case d
                    else:
                        if is_multihead:
                            mention = sentOut[i].split('\t')[-2]
                            multihead_labels = sentOut[i].rstrip().split('\t')[-1].split("$")
                            merged_label = mention + "|" + multihead_labels[0][2:]
                            for k in range(1, len(multihead_labels)):
                                merged_label += "$" + mention + "|" + multihead_labels[k][2:]
                            newTok[-2] = merged_label
                        else:
                            newTok[-2] = sentOut[i].split('\t')[-2] + '|' + sentOut[i].split('\t')[-1][2:]
                newTok = newTok[:len(newTok)-1]

            # a, b, c|d
            elif convType == 3:
                # a == O, b == 0, c|d == 0
                if (sentOut[i].split('\t')[-3].startswith("O") and sentOut[i].split('\t')[-2].startswith("O") and sentOut[i].split('\t')[-1].startswith("O")):
                    newTok[-3] = "O"
                else:
                    if ((not sentOut[i].split('\t')[-3].startswith("O")) and (not sentOut[i].split('\t')[-2].startswith("O")) and (not sentOut[i].split('\t')[-1].startswith("O"))):
                        if is_multihead:
                            parts0 = sentOut[i].split('\t')[-3]
                            parts1 = sentOut[i].split('\t')[-2].split("$")
                            parts2 = sentOut[i].split('\t')[-1].split("$")
                            label = ""
                            ## Strictly ensure same dimensions ####################
                            if len(parts1) != len(parts2):
                                newTok[-2] = parts0
                            else:
                                for raw_part1, raw_part2 in zip(parts1, parts2):
                                    a = raw_part1
                                    h, p = raw_part2.split("|")
                                    label += parts0 + "|" + a[2:] + "|" + h[2:] + "|" + p + "$"
                                if label[-1] == "$":
                                    label = label[:-1]
                                newTok[-3] = label
                        else:
                            print("Not implemented yet.")
                            sys.exit()
                    else:
                        if (not sentOut[i].split('\t')[-3].startswith("O")):
                            newTok[-3] = sentOut[i].split('\t')[-3] + "|O"
                        else:
                            newTok[-3] = "O"

                    # b == B|*, c|d == B|* ==> a|b|c|d
                    # if (sentOut[i].split('\t')[-2].startswith("B-") and sentOut[i].split('\t')[-1].startswith("B-")):
                    #     newTok[-3] = sentOut[i].split('\t')[-3] + '|' + sentOut[i].split('\t')[-2][2:] + '|' + sentOut[i].split('\t')[-1][2:]
                    # # b != B|*, c|d != B|*
                    # else:
                    #     # a == B|*
                    #     if sentOut[i].split('\t')[-3].startswith("B-"):
                    #         newTok[-3] = sentOut[i].split('\t')[-3] + '|O'
                    #     # a != B|*
                    #     else:
                    #         newTok[-3] = 'O'
                newTok = newTok[:len(newTok)-2]
            merged_file.write('\t'.join(newTok).strip() + "\n")
        merged_file.write("\n")

    merged_file.close()

    return merged_filename


def evaluate_asrm(gold_file, pred_file):
    """"""
    # print(gold_file) # data/GE11/masked/dev.st.singleX
    # print(pred_file) # logs/X/2020.01.22_16.28.45/dev.conllu

    # It will be better to include the masking into the model instead
    gold_file_unmasked = gold_file.replace("masked", "not-masked")
    
    raw_split_number = gold_file_unmasked.split(".")[-1]
    if (len(raw_split_number)==2 and raw_split_number[0]=="s"):
        split_number = raw_split_number[1]
    else:
        split_number = ""

    multitask_cols = is_multitask_encoded(pred_file)
    merged_file = merge_columns(gold_file_unmasked, pred_file, multitask_cols)
    #is_multitask = is_multitask_encoded(pred_file)
    #merged_file = merge_columns(gold_file_unmasked, pred_file, is_multitask)
    logger.info("Merged predictions in {}".format(merged_file))

    # Decode
    decode(merged_file)
    logger.info("Decoded predictions in {}".format(os.path.join(os.path.dirname(merged_file), "output")))

    x = "data/corpora/GE11/dev" + split_number
    out_norm = os.path.dirname(merged_file) + "/" + "output_norm"
    out_a2 = os.path.dirname(merged_file) + "/" + "output" + "/*.a2"
    out_results = os.path.dirname(merged_file) + "/results.txt"

    # Run eval scripts (hard-coded for now)
    os.system("perl bioscripts/eval/a2-normalize.pl -v -g " + x + " -o " + out_norm + " " + out_a2)
    os.system("perl bioscripts/eval/a2-evaluate.pl -g " + x + " -t1 -sp " + out_norm + "/*.a2 > " + out_results)
