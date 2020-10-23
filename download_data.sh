#!/bin/bash

mkdir data/corpora
cd data/corpora

echo "=> Downloading GENIA corpus (GE11)..."
ge11_folder="GE11"
eval_folder="bioscripts/eval"
mkdir $ge11_folder

echo "    => Training set..."
curl -O http://bionlp-st.dbcls.jp/GE/2011/downloads/BioNLP-ST_2011_genia_train_data_rev1.tar.gz
tar xzf BioNLP-ST_2011_genia_train_data_rev1.tar.gz
rm BioNLP-ST_2011_genia_train_data_rev1.tar.gz
mv BioNLP-ST_2011_genia_train_data_rev1 train
mv train/ $ge11_folder

echo "    => Development set..."
curl -O http://bionlp-st.dbcls.jp/GE/2011/downloads/BioNLP-ST_2011_genia_devel_data_rev1.tar.gz
tar xzf BioNLP-ST_2011_genia_devel_data_rev1.tar.gz
rm BioNLP-ST_2011_genia_devel_data_rev1.tar.gz
mv BioNLP-ST_2011_genia_devel_data_rev1 dev
cp -r dev/ ../../$eval_folder/dev_gold
mv ../../$eval_folder/dev ../../$eval_folder/dev_gold
mv dev/ $ge11_folder

echo "    => Test set..."
curl -O http://bionlp-st.dbcls.jp/GE/2011/downloads/BioNLP-ST_2011_genia_test_data.tar.gz
tar xzf BioNLP-ST_2011_genia_test_data.tar.gz
rm BioNLP-ST_2011_genia_test_data.tar.gz
mv BioNLP-ST_2011_genia_test_data test
mv test/ $ge11_folder

echo "=> Done."