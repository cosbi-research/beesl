import sys

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

sentsOut = getSents(sys.argv[1])
sentsGold = getSents(sys.argv[2])
convType = int(sys.argv[3])

is_multihead = True

for sentGold, sentOut in zip(sentsGold, sentsOut):
    print(sentGold[0].strip())
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

        # if convType == 1:
        #     if len(sentOut[i].split('\t')) > 1:
        #         newTok[-1] = sentOut[i].split('\t')[-1]
        # elif convType == 2:
        #     if (sentOut[i].split('\t')[-2]) == "O" and (sentOut[i].split('\t')[-1]) == "O":
        #         newTok[-2] = "O"
        #     else:
        #         if sentOut[i].split('\t')[-1].startswith("B-"):
        #             newTok[-2] = sentOut[i].split('\t')[-2] + '|' + sentOut[i].split('\t')[-1][2:]
        #         else:
        #             newTok[-2] = sentOut[i].split('\t')[-2] + '|' + sentOut[i].split('\t')[-1]
        #     newTok = newTok[:len(newTok)-1]
        # elif convType == 3:
        #     newTok[-1] = sentOut[i-1].split('\t')[-2] + '{}' + sentOut[i-1].split('\t')[-1]
        print('\t'.join(newTok).strip())
    print()