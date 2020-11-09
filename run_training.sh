#!/bin/bash

if [ $# -ne 4 ]; then
    echo
    echo "Execute from beesl project home. Exactly 4 args are required:"
    echo "  arg1 = training data json path"
    echo "  arg2 = model json path"
    echo "  arg3 = testing file path"
    echo "  arg4 = validation folder path"
    echo 
    echo "Multiple training data and models can be given separated by ':'"
    echo
    echo "Eg1 ./run_training.sh config/base-genia.json                             \\"
    echo "                      config/cosbi-biobert-base-params.json              \\"
    echo "                      data/GE11/not-masked/dev.mt.1                      \\"
    echo "                      data/corpora/GE11/dev"
    echo "Eg2 ./run_training.sh conf/genia.json:conf/epi.json                      \\"
    echo "                      conf/bert.json:conf/MSbert.json:conf/scibert.json  \\"
    echo "                      data/GE11/not-masked/dev.mt.1                      \\"
    echo "                      data/corpora/GE11/dev"
    echo "Experiment names will be auto-named as 'model_training_testing'"
	echo
    echo "REMEMBER: Activate env with 'conda activate beesl-env' prior to execution"

    exit 1
fi

IFS=':' read -r -a traindata <<< "$1"
IFS=':' read -r -a models <<< "$2"
testfile="${3##*/}"
validationdir="$4"

for train in "${traindata[@]}"; do
	trainfile="${train##*/}"
	trainfile="${trainfile%%.*}"
	
	for model in "${models[@]}"; do
		modelfile="${model##*/}"
		modelfile="${modelfile%%.*}"
		
		#name="${1}_${trainfile}_${modelfile}"
		name="${modelfile}_${trainfile}_${testfile}"

		# Run training
		python train.py --name ${name} --dataset_config ${train} --parameters_config ${model} --device 0

		tstamp=`ls ~/beesl/logs/${1} | sort -k 2 | tail -1`
		
		# Deflatten and evaluate
		python predict.py logs/${1}/${tstamp}/model.tar.gz ${testfile} logs/${1}/${tstamp}/pred.txt --device 0
		python bio-mergeBack.py logs/${1}/${tstamp}/pred.txt ${testfile} 2 > logs/${1}/${tstamp}/pred-notmasked.txt
		python bioscripts/postprocess.py --filepath logs/${1}/${tstamp}/pred-notmasked.txt && mv output logs/${1}/${tstamp}/
		perl bioscripts/eval/a2-normalize.pl -v -g ${validationdir} -o logs/${1}/${tstamp}/output_norm logs/${1}/${tstamp}/output/*.a2
		perl bioscripts/eval/a2-evaluate.pl -g ${validationdir} -t1 -sp logs/${1}/${tstamp}/output_norm/*.a2 > logs/${1}/${tstamp}/results.txt
		
		mv ~/beesl/logs/${1}/${tstamp}/results.txt ~/beesl/logs/${1}/${tstamp}/results_${name}_${tstamp}.txt
		mv ~/beesl/logs/${1}/${tstamp}/metrics.txt ~/beesl/logs/${1}/${tstamp}/metrics_${name}_${tstamp}.txt

		# Copy data where needed, eg, an AWS bucket
		aws s3 cp ~/beesl/logs/${1}/${tstamp}/results_${name}_${tstamp}.txt s3://cosbi-beesl
		aws s3 cp ~/beesl/logs/${1}/${tstamp}/metrics_${name}_${tstamp}.txt s3://cosbi-beesl
	done
done
   
# Post training actions, eg, containers, shutdown, etc.
#sudo halt 
